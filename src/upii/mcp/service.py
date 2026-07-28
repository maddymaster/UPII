"""Consent-aware facade over UPII's retrieval stack for the MCP tools.

This module contains **no** MCP SDK code — it is the pure, unit-testable core that
``server.py`` wraps. Responsibilities:

- enforce per-tool scopes (a disabled tool raises :class:`ToolDisabledError`);
- compute the set of *visible* source_types = MCP ``expose_sources`` allowlist ∩
  ambient consent (a source disabled in the ambient registry is invisible);
- filter every retrieved chunk against that set — a chunk whose document's
  source_type isn't visible never leaves this process;
- log every call to the local egress audit log (``mcp_call_log``).

Retrieval itself is unchanged and deterministic (the fusion rehydrator sorts by
fused score then ``chunk_hash``), so the same corpus + query yields identical
chunk ids call to call.
"""
from typing import Dict, List, Optional, Set

from upii.core.config import config as core_config
from upii.mcp.config import MCPConfig
from upii.storage.db import DB


class ToolDisabledError(Exception):
    """Raised when a client calls a tool that is off in the MCP config/scope."""


class MCPService:
    def __init__(
        self,
        mcp_config: Optional[MCPConfig] = None,
        search_engine=None,
        llm=None,
        db: Optional[DB] = None,
    ):
        # Lazily construct the heavy collaborators so tests can inject fakes and so
        # importing this module never spins up a model or LanceDB.
        self.cfg = mcp_config if mcp_config is not None else MCPConfig.load()
        self._search_engine = search_engine
        self._llm = llm
        self.db = db if db is not None else DB()
        try:
            self.db.init_db()
        except Exception:
            pass

    # -- lazy collaborators ----------------------------------------------------
    @property
    def search_engine(self):
        if self._search_engine is None:
            from upii.analysis.search import SearchEngine

            self._search_engine = SearchEngine()
        return self._search_engine

    @property
    def llm(self):
        if self._llm is None:
            from upii.analysis.llm import LocalLLM

            self._llm = LocalLLM()
        return self._llm

    # -- consent ---------------------------------------------------------------
    def _ambient_disabled_sources(self) -> Set[str]:
        """Source names the ambient registry knows about but has disabled.

        Best-effort: a source_type that shares a name with a disabled ambient
        source (e.g. ``email``) is hidden from agents even if the allowlist would
        otherwise permit it. Never raises.
        """
        disabled: Set[str] = set()
        try:
            from upii.ambient.sources import registry

            for s in registry.get_all():
                if not s.get("enabled", False):
                    disabled.add(s.get("name"))
        except Exception:
            pass
        return disabled

    def source_visible(self, source_type: Optional[str]) -> bool:
        """A source_type is visible iff the allowlist permits it AND it is not a
        disabled ambient source."""
        if source_type is None:
            return False
        if not self.cfg.source_allowed_by_allowlist(source_type):
            return False
        if source_type in self._ambient_disabled_sources():
            return False
        return True

    def visible_source_types(self) -> Set[str]:
        """Every source_type present in the corpus that is currently exposable."""
        try:
            summary = self.db.get_source_summary()
        except Exception:
            summary = []
        return {row["source"] for row in summary if self.source_visible(row["source"])}

    # -- chunk enrichment / filtering -----------------------------------------
    def _enrich_and_filter(self, ranked, source: Optional[str] = None) -> List[Dict]:
        """Map RankedChunks to public dicts, dropping any not-visible source.

        ``ranked`` order is preserved (deterministic). Each result carries the
        chunk id, its document path, source_type, fused score and the per-signal
        breakdown. An optional ``source`` narrows to a single source_type.
        """
        out: List[Dict] = []
        for r in ranked:
            doc = None
            try:
                doc = self.db.get_document_by_id(r.doc_hash)
            except Exception:
                doc = None
            source_type = (doc or {}).get("source_type")
            doc_path = (doc or {}).get("source_path", r.doc_hash)
            # Synthetic chunks (calendar events, entity-recall) have no backing
            # document; treat them as source_type "synthetic" and only expose if
            # the allowlist is "all" (they never carry corpus bytes from a file).
            if source_type is None:
                source_type = "synthetic"
                doc_path = r.doc_hash
            if not self.source_visible(source_type):
                continue
            if source is not None and source_type != source:
                continue
            out.append(
                {
                    "chunk_id": r.chunk_hash,
                    "doc_path": doc_path,
                    "source": source_type,
                    "score": round(float(r.score), 6),
                    "text": r.text,
                    "signals": {
                        "semantic": round(float(r.signals.get("semantic", 0.0)), 6),
                        "temporal": round(float(r.signals.get("temporal", 0.0)), 6),
                        "relational": round(float(r.signals.get("relational", 0.0)), 6),
                    },
                }
            )
        return out

    # -- tools -----------------------------------------------------------------
    def _require(self, tool: str) -> None:
        if not self.cfg.tool_enabled(tool):
            raise ToolDisabledError(
                f"Tool '{tool}' is disabled. Enable the MCP server "
                f"('upii mcp enable') and allow the tool in mcp.yaml."
            )

    def search(
        self,
        query: str,
        k: int = 8,
        since: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict]:
        self._require("upii_search")
        # Cap the pool the client can pull at the configured ceiling, then apply
        # the allowlist filter, then truncate to the (capped) k so the *visible*
        # result count still honours the requested k.
        cap = max(1, int(self.cfg.max_chunks_per_call))
        k = max(1, min(int(k), cap))
        # Over-fetch a little so consent filtering can't starve the result set.
        raw = self.search_engine.search(query, time_filter=since, limit=k + cap)
        results = self._enrich_and_filter(raw, source=source)[:k]
        self._log("upii_search", query, [r["chunk_id"] for r in results])
        return results

    def ask(self, question: str) -> Dict:
        self._require("upii_ask")
        cap = max(1, int(self.cfg.max_chunks_per_call))
        limit = min(core_config.rag_max_chunks, cap)
        raw = self.search_engine.search(question, limit=limit + cap)
        results = self._enrich_and_filter(raw)[:limit]
        # Rebuild lightweight Chunk-likes for the LLM from the consented chunks
        # only — the model never sees a non-exposed source.
        from upii.core.types import Chunk

        chunks = [
            Chunk(
                doc_hash=r["doc_path"],
                chunk_hash=r["chunk_id"],
                text=r["text"],
                start_char=0,
                end_char=len(r["text"] or ""),
            )
            for r in results
        ]
        answer = self.llm.answer_with_citations(question, chunks)
        self._log("upii_ask", question, [r["chunk_id"] for r in results])
        return {
            "answer": answer,
            "citations": [
                {"chunk_id": r["chunk_id"], "doc_path": r["doc_path"], "source": r["source"]}
                for r in results
            ],
        }

    def list_sources(self) -> List[Dict]:
        self._require("upii_list_sources")
        try:
            summary = self.db.get_source_summary()
        except Exception:
            summary = []
        visible = [
            {
                "source": row["source"],
                "doc_count": row.get("doc_count", 0),
                "chunk_count": row.get("chunk_count", 0),
                "last_updated": row.get("last_updated"),
            }
            for row in summary
            if self.source_visible(row["source"])
        ]
        self._log("upii_list_sources", None, [])
        return visible

    # -- audit -----------------------------------------------------------------
    def _log(self, tool: str, query: Optional[str], chunk_ids: List[str]) -> None:
        try:
            self.db.log_mcp_call(tool, query, chunk_ids)
        except Exception:
            pass
