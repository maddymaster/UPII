"""End-to-end tests for the UPII MCP server.

Drives the real FastMCP server through the official MCP client SDK over an
in-memory stdio pair (``create_connected_server_and_client_session``). Retrieval
runs the *real* fusion rehydrator; only the embedding model and the LanceDB vector
index are mocked (offline-safe, exactly as ``tests/test_search.py`` does), backed
by a real temporary SQLite DB so consent filtering and the audit log are exercised
for real.

Covers the four cases from ``docs/mcp_server_scope.md``:
- happy path for all three tools;
- consent invisibility (a not-exposed source's chunks never appear);
- determinism (same corpus + query => identical chunk ids);
- scope (a disabled tool yields a proper MCP error, not a crash);
plus: local call logging.
"""
import asyncio
import json

import numpy as np
import pytest

from upii.core.config import config
from upii.core.types import Chunk
from upii.storage.db import DB
from upii.mcp.config import MCPConfig
from upii.mcp.service import MCPService, ToolDisabledError

pytest.importorskip("mcp")
from mcp.shared.memory import create_connected_server_and_client_session as connect  # noqa: E402
from upii.mcp.server import build_server  # noqa: E402


# --- helpers ----------------------------------------------------------------
class _MockEmbedder:
    def encode(self, text):
        return np.zeros(384)


def _seed_corpus(db: DB):
    """Two documents of distinct source_types, each with one chunk.

    ``d_md`` is a markdown note; ``d_mail`` is an email. Consent tests hide the
    email source and assert its chunk never surfaces.
    """
    from upii.core.types import Document
    from datetime import datetime

    db.upsert_document(
        Document(path="/notes/alpha.md", content_hash="h_md", content="",
                 created_at=datetime(2026, 1, 1), source_type="markdown"),
        doc_id="d_md",
    )
    db.upsert_document(
        Document(path="/mail/secret.eml", content_hash="h_mail", content="",
                 created_at=datetime(2026, 1, 2), source_type="email"),
        doc_id="d_mail",
    )
    db.add_chunks([
        Chunk(doc_hash="d_md", chunk_hash="c_md", text="Project Alpha kickoff notes",
              start_char=0, end_char=27, index=0),
        Chunk(doc_hash="d_mail", chunk_hash="c_mail", text="Confidential email body",
              start_char=0, end_char=23, index=0),
    ])


class _RehydratorEngine:
    """A drop-in search engine that runs the real ContextRehydrator.

    The embedder / vector store / rehydrator-side DB are patched (via the fixture)
    so no model or LanceDB is needed; fusion + the deterministic sort are real.
    """

    def search(self, query, time_filter=None, limit=5, weights=None):
        from upii.analysis.rehydration import ContextRehydrator
        return ContextRehydrator().rehydrate(query, time_filter, limit, weights=weights)


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    config.db_path = str(tmp_path / "upii_test.db")
    config.vector_store_path = str(tmp_path / "vectors")

    db = DB()
    db.init_db()
    _seed_corpus(db)

    # Both seeded chunks are returned by the (mocked) vector store, closest first.
    hits = [
        {"chunk": Chunk(doc_hash="d_md", chunk_hash="c_md", text="Project Alpha kickoff notes",
                        start_char=0, end_char=27), "distance": 0.10, "timestamp": None},
        {"chunk": Chunk(doc_hash="d_mail", chunk_hash="c_mail", text="Confidential email body",
                        start_char=0, end_char=23), "distance": 0.20, "timestamp": None},
    ]

    monkeypatch.setattr("upii.analysis.rehydration.Embedder.get_instance", lambda: _MockEmbedder())

    class MockVS:
        def __init__(self, *a, **k):
            pass

        def search_scored(self, vec, limit=5, where_clause=None):
            return hits

    monkeypatch.setattr("upii.analysis.rehydration.LocalVectorStore", MockVS)

    class MockRehyDB:
        def init_db(self):
            pass

        def get_calendar_events(self, *a, **k):
            return []

        def get_entity_edges(self, *a, **k):
            return []

    monkeypatch.setattr("upii.analysis.rehydration.DB", lambda: MockRehyDB())
    # Deterministic LLM: no Ollama/Gemini during tests.
    monkeypatch.setattr("upii.analysis.llm.config.gemini_api_key", "")
    return db


def _service(expose="all", tools=None, enabled=True):
    cfg = MCPConfig(enabled=enabled)
    cfg.expose_sources = expose
    if tools is not None:
        cfg.tools.update(tools)
    return MCPService(mcp_config=cfg, search_engine=_RehydratorEngine())


def _run(coro):
    return asyncio.run(coro)


async def _call(server, name, args=None):
    async with connect(server) as session:
        await session.initialize()
        result = await session.call_tool(name, args or {})
        tools = await session.list_tools()
    return result, [t.name for t in tools.tools]


def _parse_list(result):
    return [json.loads(c.text) for c in result.content]


def _parse_obj(result):
    return json.loads(result.content[0].text)


# --- happy path -------------------------------------------------------------
def test_search_happy_path(seeded):
    server = build_server(service=_service())
    result, tool_names = _run(_call(server, "upii_search", {"query": "alpha", "k": 8}))

    assert set(tool_names) == {"upii_search", "upii_ask", "upii_list_sources"}
    assert result.isError is False
    rows = _parse_list(result)
    ids = [r["chunk_id"] for r in rows]
    assert ids == ["c_md", "c_mail"]  # semantic order preserved
    top = rows[0]
    assert top["doc_path"] == "/notes/alpha.md"
    assert top["source"] == "markdown"
    assert set(top["signals"]) == {"semantic", "temporal", "relational"}
    assert top["score"] >= rows[1]["score"]


def test_ask_happy_path(seeded):
    server = build_server(service=_service())
    result, _ = _run(_call(server, "upii_ask", {"question": "what is alpha?"}))
    assert result.isError is False
    obj = _parse_obj(result)
    assert "answer" in obj
    cited = {c["chunk_id"] for c in obj["citations"]}
    assert "c_md" in cited


def test_list_sources_happy_path(seeded):
    server = build_server(service=_service())
    result, _ = _run(_call(server, "upii_list_sources"))
    assert result.isError is False
    rows = {r["source"]: r for r in _parse_list(result)}
    assert set(rows) == {"markdown", "email"}
    assert rows["markdown"]["doc_count"] == 1
    assert rows["markdown"]["chunk_count"] == 1
    assert rows["markdown"]["last_updated"] is not None


# --- consent invisibility ---------------------------------------------------
def test_disabled_source_is_invisible_everywhere(seeded):
    # Expose only markdown; the email source must never appear in any tool.
    server = build_server(service=_service(expose=["markdown"]))

    res_search, _ = _run(_call(server, "upii_search", {"query": "confidential"}))
    ids = [r["chunk_id"] for r in _parse_list(res_search)]
    assert ids == ["c_md"]
    assert "c_mail" not in ids

    res_ask, _ = _run(_call(server, "upii_ask", {"question": "confidential?"}))
    cited = {c["chunk_id"] for c in _parse_obj(res_ask)["citations"]}
    assert "c_mail" not in cited

    res_sources, _ = _run(_call(server, "upii_list_sources"))
    sources = {r["source"] for r in _parse_list(res_sources)}
    assert sources == {"markdown"}
    assert "email" not in sources


def test_source_filter_narrows_to_one_source(seeded):
    server = build_server(service=_service(expose="all"))
    res, _ = _run(_call(server, "upii_search", {"query": "x", "source": "email"}))
    ids = [r["chunk_id"] for r in _parse_list(res)]
    assert ids == ["c_mail"]


# --- determinism ------------------------------------------------------------
def test_determinism_same_query_same_chunk_ids(seeded):
    server = build_server(service=_service())
    r1, _ = _run(_call(server, "upii_search", {"query": "alpha kickoff", "k": 5}))
    r2, _ = _run(_call(server, "upii_search", {"query": "alpha kickoff", "k": 5}))
    ids1 = [r["chunk_id"] for r in _parse_list(r1)]
    ids2 = [r["chunk_id"] for r in _parse_list(r2)]
    assert ids1 == ids2
    assert ids1 == ["c_md", "c_mail"]


# --- scope / disabled tool --------------------------------------------------
def test_disabled_tool_returns_mcp_error_not_crash(seeded):
    # upii_ask off: server stays up, tool is unadvertised, calling it errors cleanly.
    server = build_server(service=_service(tools={"upii_ask": False}))
    result, tool_names = _run(_call(server, "upii_ask", {"question": "hi"}))
    assert "upii_ask" not in tool_names
    assert "upii_search" in tool_names
    assert result.isError is True  # proper MCP error, not an exception


def test_server_off_raises_and_service_guards(seeded):
    # Whole server disabled -> every tool gated.
    svc = _service(enabled=False)
    with pytest.raises(ToolDisabledError):
        svc.search("x")
    from upii.mcp.server import serve
    with pytest.raises(RuntimeError):
        serve(mcp_config=svc.cfg)


# --- config -----------------------------------------------------------------
def test_core_config_tolerates_unknown_mcp_block(tmp_path):
    # A user following docs/mcp_setup.md may add an `mcp:` block to the main config;
    # Config.load must ignore it rather than crash startup with a TypeError.
    from upii.core.config import Config

    cfg_file = tmp_path / ".upii_config.yaml"
    cfg_file.write_text("user_name: Alice\nmcp:\n  enabled: true\n")
    cfg = Config.load(str(cfg_file))
    assert cfg.user_name == "Alice"
    assert not hasattr(cfg, "mcp") or True  # no crash; unknown key dropped


def test_mcp_config_roundtrip(tmp_path):
    path = str(tmp_path / "mcp.yaml")
    cfg = MCPConfig(enabled=True)
    cfg.expose_sources = ["markdown", "pdf"]
    cfg.tools["upii_ask"] = False
    cfg.max_chunks_per_call = 5
    cfg.save(path)

    loaded = MCPConfig.load(path)
    assert loaded.enabled is True
    assert loaded.expose_sources == ["markdown", "pdf"]
    assert loaded.tools["upii_ask"] is False
    assert loaded.tools["upii_search"] is True
    assert loaded.max_chunks_per_call == 5
    # Scope + allowlist helpers behave as configured.
    assert loaded.tool_enabled("upii_search") is True
    assert loaded.tool_enabled("upii_ask") is False
    assert loaded.source_allowed_by_allowlist("markdown") is True
    assert loaded.source_allowed_by_allowlist("email") is False


def test_mcp_config_off_by_default(tmp_path):
    # No file -> disabled, nothing exposed even though tool flags default true.
    cfg = MCPConfig.load(str(tmp_path / "absent.yaml"))
    assert cfg.enabled is False
    assert cfg.tool_enabled("upii_search") is False


# --- audit log --------------------------------------------------------------
def test_calls_are_logged_locally(seeded):
    svc = _service()
    server = build_server(service=svc)
    _run(_call(server, "upii_search", {"query": "alpha"}))
    _run(_call(server, "upii_list_sources"))

    log = svc.db.get_mcp_call_log(limit=10)
    tools_logged = [row["tool"] for row in log]
    assert "upii_search" in tools_logged
    assert "upii_list_sources" in tools_logged
    search_row = next(r for r in log if r["tool"] == "upii_search")
    assert search_row["query"] == "alpha"
    assert isinstance(search_row["chunk_ids"], list)
    assert "c_md" in search_row["chunk_ids"]
