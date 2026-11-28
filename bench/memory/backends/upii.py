"""upii backend: each benchmark user gets its own temporary upii store.

Turns are buffered per session (one ``add`` timestamp = one session). Before the
first search for a user, each session becomes one upii Document
("(date) Speaker: text" lines), and goes through upii's production ingest path
(``ingest_document``: RecursiveChunker, MiniLM embeddings, SQLite + LanceDB).
Search is upii's ``SearchEngine.search`` with the configured fusion weights.

``min_similarity`` defaults to None (no threshold) so the harness's top-k cutoffs
compare like for like with the other backends; pass a value to measure upii's
abstention threshold as shipped.

upii's config is a process-wide singleton, so users are handled one at a time:
run this backend with ``--max-workers 1`` (the runner enforces it).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any

from . import BaseBackend


class UpiiBackend(BaseBackend):
    name = "upii"

    def __init__(self, root: str | None = None, min_similarity: float | None = None, **_: Any) -> None:
        super().__init__()
        self.root = root or tempfile.mkdtemp(prefix="upii-bench-")
        self._own_root = root is None
        self.min_similarity = min_similarity
        self.flushed: set[str] = set()
        self.chunk_dates: dict[str, dict[str, str]] = {}  # user -> doc_id -> created_at

    # -- store selection -------------------------------------------------------
    def _use_store(self, user_id: str) -> None:
        from upii.core.config import config
        d = os.path.join(self.root, hashlib.sha256(user_id.encode()).hexdigest()[:16])
        os.makedirs(d, exist_ok=True)
        config.db_path = os.path.join(d, "upii.db")
        config.vector_store_path = os.path.join(d, "upii_vectors")

    def _flush(self, user_id: str) -> None:
        if user_id in self.flushed:
            return
        from upii.analysis.embeddings import Embedder
        from upii.core.types import Document
        from upii.ingestion.chunker import RecursiveChunker
        from upii.ingestion.pipeline import ingest_document
        from upii.storage.db import DB
        from upii.storage.vector import LocalVectorStore

        self._use_store(user_id)
        db = DB()
        db.init_db()
        vector_store = LocalVectorStore()
        chunker = RecursiveChunker()
        embedder = Embedder()

        sessions: dict[Any, list[dict]] = {}
        for t in self.turns.get(user_id, []):
            sessions.setdefault(t["timestamp"], []).append(t)
        dates = self.chunk_dates.setdefault(user_id, {})
        for n, (ts, turns) in enumerate(sessions.items()):
            created = (datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)
                       if ts is not None else datetime(1970, 1, 1))
            day = created.strftime("%d %B %Y")
            content = "\n".join(f"({day}) {t['text']}" for t in turns) + "\n"
            doc = Document(
                path=f"bench://{user_id}/session_{n:03d}.md",
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                content=content,
                created_at=created,
                source_type="md",
            )
            res = ingest_document(doc, db, vector_store, embedder, chunker, force=True)
            dates[res.doc_id] = turns[0]["created_at"]
        self.flushed.add(user_id)

    # -- backend API -----------------------------------------------------------
    def _add(self, user_id: str, new_turns: list[dict]) -> None:
        # A late add after a search would need a re-flush; the harness never does that.
        self.flushed.discard(user_id)

    def _search(self, query: str, user_id: str, top_k: int) -> list[dict]:
        if not self.turns.get(user_id):
            return []
        self._flush(user_id)
        self._use_store(user_id)
        from upii.analysis.search import SearchEngine
        results = SearchEngine().search(query, limit=top_k, min_similarity=self.min_similarity)
        dates = self.chunk_dates.get(user_id, {})
        return [
            {"id": r.chunk_hash, "memory": r.text.strip(), "score": float(getattr(r, "score", 0.0)),
             "created_at": dates.get(r.doc_hash, "")}
            for r in results
        ]

    async def delete_user(self, user_id: str) -> bool:
        d = os.path.join(self.root, hashlib.sha256(user_id.encode()).hexdigest()[:16])
        shutil.rmtree(d, ignore_errors=True)
        self.flushed.discard(user_id)
        self.chunk_dates.pop(user_id, None)
        return await super().delete_user(user_id)

    async def close(self) -> None:
        if self._own_root:
            shutil.rmtree(self.root, ignore_errors=True)
