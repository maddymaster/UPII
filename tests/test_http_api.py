"""The local HTTP API (`upii serve`) drives the real ingest + retrieval stack.

Runs against a real temporary SQLite DB, LanceDB store and staging.db; only the
embedding model is replaced by deterministic hash vectors (offline-safe, as in
test_batch_ingest.py), the Ollama probe in /health is stubbed, and Ollama/Gemini
calls are mocked, so no network is touched and the real upii.db is never opened.
"""
import hashlib
import os
import time
from dataclasses import fields
from unittest.mock import patch

import numpy as np
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from upii.ambient.storage import StagingDB  # noqa: E402
from upii.analysis.diagnostics import Doctor  # noqa: E402
from upii.analysis.embeddings import Embedder  # noqa: E402
from upii.api.server import create_app, use_data_dir  # noqa: E402
from upii.core.config import Config, config  # noqa: E402

BASE_URL = "http://127.0.0.1"
ALPHA = "# Alpha\n\nProject Alpha kickoff is on Monday with the platform team.\n"
BETA = "# Beta\n\nThe Beta release notes cover the new export feature.\n"
GAMMA = "Gamma staged capture: the procurement review moved to Thursday.\n"


class FakeModel:
    """Stands in for the SentenceTransformer behind Embedder: 8-d hash vectors."""

    DIM = 8

    def _vec(self, text):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [digest[i] / 255.0 for i in range(self.DIM)]

    def encode(self, texts, **_):
        if isinstance(texts, str):
            return np.array(self._vec(texts))
        return np.array([self._vec(t) for t in texts])


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Empty data dir for every store, a notes folder, and no API env set."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.chdir(data)
    for var in ("UPII_API_KEY", "UPII_ALLOWED_ORIGINS", "UPII_ALLOWED_HOSTS",
                "UPII_API_ALLOW_REMOTE", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(Embedder, "_instance", FakeModel())
    monkeypatch.setattr(Doctor, "check_model", lambda self: "OK (stubbed)")
    monkeypatch.setattr(config, "db_path", str(data / "upii.db"))
    monkeypatch.setattr(config, "vector_store_path", str(data / "vectors"))
    monkeypatch.setattr(config, "staging_db_path", str(data / "staging.db"))
    monkeypatch.setattr(config, "gemini_api_key", "")
    yield tmp_path, data


def _client():
    return TestClient(create_app(), base_url=BASE_URL)


def _notes(root):
    notes = root / "notes"
    notes.mkdir()
    # Bytes, not text: write_text turns \n into \r\n on Windows and changes the hash.
    (notes / "alpha.md").write_bytes(ALPHA.encode("utf-8"))
    (notes / "beta.md").write_bytes(BETA.encode("utf-8"))
    return notes


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_error(resp, status, code):
    body = resp.json()
    return resp.status_code == status and set(body) == {"error", "detail"} and body["error"] == code


def _stage(path, content):
    """Stage a capture the way the ambient watcher does: event + pinned content."""
    stg = StagingDB()
    stg.init_db()
    event_id = stg.add_event("created", str(path))
    stg.add_staging_doc(event_id, str(path), content, _sha(content), {})
    return event_id


# -- health -------------------------------------------------------------------
def test_health_on_empty_folder_is_ready(workspace):
    _, data = workspace
    resp = _client().get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "READY"
    assert body["version"]
    for check in ("sqlite", "vector_db", "ingestion"):
        assert body["checks"][check]["status"] == "READY", body["checks"][check]
    assert all(c["status"] != "FAIL" for c in body["checks"].values())
    model = body["answer_model"]
    assert model["default"] == "local" and model["local"]["provider"] == "ollama"
    assert model["remote"] == {"provider": "gemini", "name": config.gemini_model,
                               "key_configured": False, "allowed": False}
    # Health never creates the memory store; only the audit trail (staging.db) appears.
    assert not (data / "upii.db").exists() and not (data / "vectors").exists()


# -- ingest / search / ask ----------------------------------------------------
def test_ingest_then_search_and_ask_return_hashes(workspace):
    root, _ = workspace
    notes = _notes(root)
    client = _client()

    resp = client.post("/ingest", json={"path": str(notes), "recursive": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"] == {"ingested": 2, "updated": 0, "skipped": 0, "error": 0}
    by_name = {os.path.basename(f["path"]): f for f in body["files"]}
    assert set(by_name) == {"alpha.md", "beta.md"}
    assert by_name["alpha.md"]["document_hash"] == _sha(ALPHA)
    assert by_name["beta.md"]["document_hash"] == _sha(BETA)
    assert all(f["chunks"] >= 1 and f["status"] == "ingested" for f in body["files"])

    expected = {_sha(ALPHA), _sha(BETA)}

    search = client.post("/search", json={"query": "Project Alpha kickoff", "limit": 10}).json()
    assert search["weights"] == config.fusion_weights()
    results = search["results"]
    assert {r["document_hash"] for r in results} == expected
    for r in results:
        assert r["text"] and r["document_path"].endswith(".md") and r["chunk_hash"]
        assert set(r["scores"]) == {"semantic", "temporal", "relational", "fused"}
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1))

    ask = client.post("/ask", json={"question": "When is the Alpha kickoff?", "no_answer": True}).json()
    assert ask["answer"] is None and ask["model"] is None
    assert {s["document_hash"] for s in ask["sources"]} == expected
    assert all(s["passage"] and s["document_path"] and s["chunk_hash"] for s in ask["sources"])
    assert all("scores" not in s for s in ask["sources"])

    debug = client.post("/ask", json={"question": "Alpha", "no_answer": True, "debug": True}).json()
    assert all("fused" in s["scores"] for s in debug["sources"])

    docs = client.get("/sources").json()["documents"]
    assert {d["document_hash"] for d in docs} == expected
    assert all(d["path"] and d["ingestion_time"] for d in docs)


def test_reingest_reports_skipped(workspace):
    root, _ = workspace
    notes = _notes(root)
    client = _client()
    client.post("/ingest", json={"path": str(notes)})
    again = client.post("/ingest", json={"path": str(notes)}).json()
    assert again["summary"] == {"ingested": 0, "updated": 0, "skipped": 2, "error": 0}
    assert {f["status"] for f in again["files"]} == {"skipped"}


def test_ingest_non_recursive_skips_subfolders(workspace):
    root, _ = workspace
    notes = _notes(root)
    (notes / "sub").mkdir()
    (notes / "sub" / "gamma.md").write_text("# Gamma\n\nNested note.\n", encoding="utf-8")
    body = _client().post("/ingest", json={"path": str(notes), "recursive": False}).json()
    assert sorted(os.path.basename(f["path"]) for f in body["files"]) == ["alpha.md", "beta.md"]


def test_ingest_missing_path_and_no_supported_files(workspace):
    root, _ = workspace
    client = _client()
    assert _is_error(client.post("/ingest", json={"path": str(root / "nope")}), 400, "path_not_found")

    empty = root / "pictures"
    empty.mkdir()
    (empty / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    assert _is_error(client.post("/ingest", json={"path": str(empty)}), 422, "no_supported_files")


def test_background_ingest_job(workspace):
    root, _ = workspace
    client = _client()
    resp = client.post("/ingest", json={"path": str(_notes(root)), "background": True})
    assert resp.status_code == 202
    url = resp.json()["status_url"]
    deadline = time.time() + 30
    while (job := client.get(url).json())["status"] == "running" and time.time() < deadline:
        time.sleep(0.05)
    assert job["status"] == "done", job
    assert job["result"]["summary"]["ingested"] == 2
    assert _is_error(client.get("/ingest/jobs/unknown"), 404, "job_not_found")


def test_validation_errors_use_error_shape(workspace):
    resp = _client().post("/search", json={"query": "secret words", "limit": 0})
    assert _is_error(resp, 422, "validation_error")
    assert "secret words" not in resp.text  # the input is never echoed back


# -- inbox ----------------------------------------------------------------------
def test_inbox_approve_makes_capture_searchable(workspace):
    root, _ = workspace
    client = _client()
    event_id = _stage(root / "gamma.txt", GAMMA)

    items = client.get("/inbox").json()["items"]
    assert [(i["id"], i["type"], i["hash"]) for i in items] == [(event_id, "created", _sha(GAMMA))]
    assert items[0]["path"].endswith("gamma.txt") and items[0]["time"]

    # Pending captures are not in memory yet.
    assert client.post("/search", json={"query": "procurement review"}).json()["results"] == []

    resp = client.post(f"/inbox/{event_id}/approve")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "approved" and body["in_memory"] and body["chunks"] >= 1
    assert body["document_hash"] == _sha(GAMMA)

    results = client.post("/search", json={"query": "procurement review"}).json()["results"]
    assert [r["document_hash"] for r in results] == [_sha(GAMMA)]
    assert client.get("/inbox").json()["items"] == []

    again = client.post(f"/inbox/{event_id}/approve").json()
    assert again["outcome"] == "already_approved" and again["in_memory"]
    assert _is_error(client.post(f"/inbox/{event_id}/reject"), 409, "already_approved")


def test_inbox_reject_and_unknown_ids(workspace):
    root, _ = workspace
    client = _client()
    event_id = _stage(root / "gamma.txt", GAMMA)

    assert client.post(f"/inbox/{event_id}/reject").json()["outcome"] == "rejected"
    assert _is_error(client.post(f"/inbox/{event_id}/approve"), 409, "already_rejected")
    assert client.post("/search", json={"query": "procurement review"}).json()["results"] == []
    # The API wants the full id; the CLI's prefix matching does not apply.
    assert _is_error(client.post(f"/inbox/{event_id[:8]}/approve"), 404, "event_not_found")


# -- security -----------------------------------------------------------------
def test_api_key_required_when_set(workspace, monkeypatch):
    monkeypatch.setenv("UPII_API_KEY", "s3cret")
    client = _client()
    assert _is_error(client.get("/health"), 401, "unauthorized")
    assert client.post("/search", json={"query": "x"}).status_code == 401
    assert client.get("/audit").status_code == 401
    assert client.get("/health", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/health", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_cors_rejects_unlisted_origins(workspace, monkeypatch):
    monkeypatch.setenv("UPII_ALLOWED_ORIGINS", "http://localhost:3000")
    client = _client()
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
    preflight = client.options("/search", headers={"Origin": "https://evil.example",
                                                   "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_no_cors_headers_when_no_origins_configured(workspace):
    resp = _client().get("/health", headers={"Origin": "http://localhost:3000"})
    assert "access-control-allow-origin" not in resp.headers


def test_non_loopback_host_header_rejected(workspace):
    # DNS-rebinding guard: a page on attacker.example resolving to 127.0.0.1 still
    # sends Host: attacker.example, which must not reach the API.
    client = TestClient(create_app(), base_url="http://attacker.example")
    assert _is_error(client.get("/health"), 400, "invalid_host")


# -- answer model routing -----------------------------------------------------
def test_ask_local_only_never_calls_remote(workspace, monkeypatch):
    root, _ = workspace
    client = _client()
    client.post("/ingest", json={"path": str(_notes(root))})
    monkeypatch.setattr(config, "gemini_api_key", "AIza-real-looking-key")
    monkeypatch.setenv("UPII_API_ALLOW_REMOTE", "1")  # even with remote allowed server-side
    client = _client()

    with patch("upii.analysis.llm.LocalLLM._call_gemini") as gemini, \
         patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate", return_value={"response": "local answer"}):
        default = client.post("/ask", json={"question": "Alpha?"})
        explicit = client.post("/ask", json={"question": "Alpha?", "local_only": True})
    gemini.assert_not_called()
    for resp in (default, explicit):
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["answer"] == "local answer"
        assert body["model"] == {"name": config.llm_model, "provider": "ollama", "location": "local"}
        assert body["sources"]


def test_ask_local_only_errors_instead_of_mock_fallback(workspace, monkeypatch):
    root, _ = workspace
    client = _client()
    client.post("/ingest", json={"path": str(_notes(root))})
    monkeypatch.setattr(config, "gemini_api_key", "AIza-real-looking-key")

    with patch("upii.analysis.llm.LocalLLM._call_gemini") as gemini, \
         patch("upii.analysis.llm.ollama.list", side_effect=ConnectionError("offline")):
        offline = client.post("/ask", json={"question": "Alpha?"})
    assert _is_error(offline, 503, "local_model_unavailable")

    # Ollama reachable but generation fails: still an error, never a mock answer.
    with patch("upii.analysis.llm.LocalLLM._call_gemini") as gemini2, \
         patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate", side_effect=RuntimeError("model not pulled")):
        failed = client.post("/ask", json={"question": "Alpha?"})
    assert _is_error(failed, 503, "local_model_unavailable")
    gemini.assert_not_called()
    gemini2.assert_not_called()


def test_ask_remote_needs_client_opt_in_and_server_permission(workspace, monkeypatch):
    root, _ = workspace
    client = _client()
    client.post("/ingest", json={"path": str(_notes(root))})
    monkeypatch.setattr(config, "gemini_api_key", "AIza-real-looking-key")

    with patch("upii.analysis.llm.LocalLLM._call_gemini") as gemini:
        denied = _client().post("/ask", json={"question": "Alpha?", "local_only": False})
    assert _is_error(denied, 403, "remote_not_allowed")
    gemini.assert_not_called()

    monkeypatch.setenv("UPII_API_ALLOW_REMOTE", "1")
    with patch("upii.analysis.llm.LocalLLM._call_gemini", return_value="remote answer"):
        body = _client().post("/ask", json={"question": "Alpha?", "local_only": False}).json()
    assert body["model"]["location"] == "remote" and body["model"]["provider"] == "gemini"
    assert body["answer"] == "remote answer"


# -- audit --------------------------------------------------------------------
def test_audit_records_api_calls_by_hash_only(workspace, monkeypatch):
    root, data = workspace
    monkeypatch.setenv("UPII_API_KEY", "s3cret")
    client = _client()
    key = {"X-API-Key": "s3cret"}
    client.post("/ingest", json={"path": str(_notes(root))}, headers=key)
    question = "a very private question about Alpha"
    client.post("/ask", json={"question": question, "no_answer": True}, headers=key)
    client.get("/sources")  # rejected: no key
    event_id = _stage(root / "gamma.txt", GAMMA)
    client.post(f"/inbox/{event_id}/approve", headers=key)

    entries = client.get("/audit", headers=key).json()["entries"]
    api = [e for e in entries if e["source"] == "api"]
    assert [e["action"] for e in api[:4]] == [
        "POST /inbox/{event_id}/approve", "GET /sources", "POST /ask", "POST /ingest"]
    assert api[0]["details"]["event_id"] == event_id
    assert api[1]["details"]["status"] == 401
    ask = api[2]["details"]
    assert ask["query_sha256"] == _sha(question) and ask["status"] == 200 and ask["results"] == 2
    # The inbox's own approval entry sits in the same trail.
    assert any(e["source"] == "inbox" and e["action"] == "approve" for e in entries)

    # Each /audit call is audited too, so the second read sees one extra row on top.
    newest = client.get("/audit?limit=3", headers=key).json()["entries"]
    page = client.get("/audit?limit=2&offset=2", headers=key).json()
    assert page["limit"] == 2 and page["offset"] == 2
    assert [e["id"] for e in page["entries"]] == [e["id"] for e in newest[1:3]]

    for name in ("staging.db", "upii.db"):
        with open(data / name, "rb") as f:
            raw = f.read()
        assert question.encode("utf-8") not in raw and b"s3cret" not in raw


# -- data dir -----------------------------------------------------------------
def test_use_data_dir_matches_cli_folder_semantics(tmp_path, monkeypatch):
    saved = {f.name: getattr(config, f.name) for f in fields(Config)}
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "memory"
    folder.mkdir()
    (folder / ".upii_config.yaml").write_text("llm_model: tinyllama\ndb_path: mem.db\n", encoding="utf-8")
    try:
        root = use_data_dir(str(folder))
        assert root == str(folder.resolve()) or os.path.samefile(root, folder)
        assert os.path.samefile(os.getcwd(), folder)
        assert config.llm_model == "tinyllama"
        assert os.path.isabs(config.db_path) and os.path.basename(config.db_path) == "mem.db"
        assert os.path.dirname(config.vector_store_path) == os.path.dirname(config.db_path)
        assert os.path.basename(config.staging_db_path) == "staging.db"
    finally:
        for name, value in saved.items():
            setattr(config, name, value)
