"""`upii doctor` on a fresh install reports READY, not FAIL.

The SQLite DB and the vector store are only created on first ingest, so an empty
memory is a valid state. Doctor must say so, must never create those files itself,
and must still FAIL on a genuinely broken store.
"""

import hashlib
import os
import subprocess
import sys

import pytest
from unittest.mock import patch
from typer.testing import CliRunner

from upii.analysis.diagnostics import Doctor, remediation
from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.ingestion.loader import LocalLoader
from upii.ingestion.chunker import RecursiveChunker
from upii.ingestion.pipeline import ingest_document


class FakeEmbedder:
    """Deterministic 8-d vectors derived from the chunk text — no model needed."""

    DIM = 8

    def embed(self, texts, batch_size=32):
        out = []
        for t in texts:
            digest = hashlib.sha256(t.encode("utf-8")).digest()
            out.append([digest[i] / 255.0 for i in range(self.DIM)])
        return out


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Point the DB and vector store into an empty tmp dir, and run from there."""
    db_path = os.path.join(str(tmp_path), "upii.db")
    vec_path = os.path.join(str(tmp_path), "vectors")
    monkeypatch.chdir(tmp_path)
    with patch("upii.core.config.config.db_path", db_path), \
         patch("upii.core.config.config.vector_store_path", vec_path):
        yield tmp_path, db_path, vec_path


def _snapshot(root):
    return sorted(
        os.path.relpath(os.path.join(d, f), str(root))
        for d, _, files in os.walk(str(root))
        for f in files
    ) + sorted(
        os.path.relpath(os.path.join(d, sub), str(root))
        for d, subs, _ in os.walk(str(root))
        for sub in subs
    )


def test_fresh_install_reports_ready_and_creates_nothing(paths):
    root, db_path, vec_path = paths
    before = _snapshot(root)

    doc = Doctor()
    results = {
        "sqlite": doc.check_sqlite(),
        "vector_db": doc.check_vector_db(),
        "ingestion": doc.check_last_ingestion(),
    }

    for name, result in results.items():
        assert result.startswith("READY"), f"{name}: {result}"
        assert "FAIL" not in result, f"{name}: {result}"
    # embedding may be OK or WARN (depends on whether model is cached), never FAIL.
    embedding = doc.check_embedding()
    assert "FAIL" not in embedding, f"embedding: {embedding}"

    assert not os.path.exists(db_path)
    assert not os.path.exists(vec_path)
    assert _snapshot(root) == before


def test_doctor_command_on_fresh_install_creates_nothing(paths):
    root, db_path, vec_path = paths
    before = _snapshot(root)

    from upii.cli import app
    with patch.object(Doctor, "check_model", return_value="OK (mocked)"):
        result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "READY" in result.output
    assert "FAIL" not in result.output
    assert not os.path.exists(db_path)
    assert not os.path.exists(vec_path)
    # The CLI callback opens upii.log for every command (core/logger.py); that is
    # global CLI behaviour, not doctor's. Nothing else may appear.
    assert [p for p in _snapshot(root) if p != "upii.log"] == before


def test_after_one_ingest_reports_ok(paths):
    root, db_path, vec_path = paths
    note = os.path.join(str(root), "note.md")
    with open(note, "w", encoding="utf-8") as f:
        f.write("# Standup\n\nShipped the doctor fix for fresh installs.\n")

    db = DB()
    db.init_db()
    vec = LocalVectorStore()
    docs = list(LocalLoader().load(note))
    assert len(docs) == 1
    ingest_document(docs[0], db, vec, FakeEmbedder(), RecursiveChunker())

    doc = Doctor()
    assert doc.check_sqlite() == "OK"
    assert doc.check_vector_db().startswith("OK")
    ingestion = doc.check_last_ingestion()
    assert ingestion.startswith("OK (Last: ")
    assert ingestion != "OK (Last: None)"


def test_corrupt_db_fails(paths):
    root, db_path, vec_path = paths
    with open(db_path, "wb") as f:
        f.write(b"this is not a sqlite database" * 200)

    result = Doctor().check_sqlite()

    assert result.startswith("FAIL")
    assert "unreadable or corrupt" in result


# --- embedding check tests ---

def test_embedding_ok_when_cached(paths, monkeypatch):
    root, db_path, vec_path = paths
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("SENTENCE_TRANSFORMERS_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    cache = root / "hub"
    snap = cache / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "modules.json").write_text("[]")
    (snap / "model.safetensors").write_bytes(b"\0")

    monkeypatch.setenv("HF_HUB_CACHE", str(cache))
    doc = Doctor()
    assert doc.check_embedding() == "OK"


def test_embedding_warn_when_not_cached(monkeypatch):
    # Use a model name that is definitely not cached on any machine.
    monkeypatch.setattr(
        "upii.core.config.config.embedding_model",
        "nonexistent-model-nowhere-xyz-42",
    )
    doc = Doctor()
    result = doc.check_embedding()
    assert result.startswith("WARN"), f"Expected WARN, got: {result}"
    assert "not cached" in result


# --- CLI exit-code tests ---

def test_corrupt_db_exits_1_with_hint(paths):
    root, db_path, vec_path = paths
    with open(db_path, "wb") as f:
        f.write(b"this is not a sqlite database" * 200)

    from upii.cli import app
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "doctor: FAIL" in result.output
    # Hints appear under WARN/FAIL lines.
    assert "Move the damaged database file aside" in result.output


def test_doctor_cli_passes_on_fresh_install(paths):
    root, db_path, vec_path = paths

    from upii.cli import app
    with patch.object(Doctor, "check_model", return_value="OK (mocked)"):
        # Patch check_embedding to be OK so we get a clean PASS.
        with patch.object(Doctor, "check_embedding", return_value="OK"):
            result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "doctor: PASS" in result.output


# --- remediation hint tests ---

def test_remediation_returns_hint_for_warn_fail():
    for name, key in [("sqlite", "sqlite"), ("vector_db", "vector_db"),
                       ("disk", "disk"), ("embedding", "embedding"),
                       ("ingestion", "ingestion")]:
        assert remediation(name, f"WARN: test") != ""
        assert remediation(name, f"FAIL: test") != ""


# --- offline import safety tests ---

def test_doctor_imports_no_transformer():
    """Importing diagnostics must not pull in sentence_transformers / huggingface_hub / torch."""
    code = (
        "import sys\n"
        "import upii.analysis.model_cache\n"
        "import upii.analysis.diagnostics\n"
        "import upii.cli\n"
        "_bad = [m for m in sorted(sys.modules.keys()) if\n"
        "  m == 'sentence_transformers' or m.startswith('sentence_transformers.') or\n"
        "  m == 'huggingface_hub' or m.startswith('huggingface_hub.') or\n"
        "  m == 'torch' or m.startswith('torch.')]\n"
        "print(','.join(_bad))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        env={k: v for k, v in os.environ.items()}, timeout=30,
    )
    assert out.returncode == 0, out.stderr
    loaded = [m for m in out.stdout.strip().split(",") if m] if out.stdout.strip() else []
    assert len(loaded) == 0, f"Heavy modules loaded: {loaded}"


def test_one_model_cache_implementation():
    """Both callers must use the single implementation, not a copy."""
    from upii.analysis import model_cache, diagnostics, embeddings

    assert diagnostics._model_is_cached is model_cache.model_is_cached
    assert embeddings.model_is_cached is model_cache.model_is_cached


def test_model_is_cached_behaviour(tmp_path, monkeypatch):
    """Model-cache logic works correctly in an isolated cache."""
    from upii.analysis import model_cache as mc

    for var in ("SENTENCE_TRANSFORMERS_HOME", "HF_HUB_CACHE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    hub = tmp_path / "hub"
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    cached_snap = hub / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "abc123"
    cached_snap.mkdir(parents=True)
    (cached_snap / "modules.json").write_text("[]")

    assert mc.model_is_cached("all-MiniLM-L6-v2") is False  # no weights yet
    (cached_snap / "model.safetensors").touch()
    assert mc.model_is_cached("all-MiniLM-L6-v2") is True   # cached snapshot
    assert mc.model_is_cached(str(tmp_path)) is True         # a local folder
    assert mc.model_is_cached("someone/missing-model") is False  # not cached

# --- FAILSAFE in a WARN text stays PASS (item 2 review fix) ---

def test_warn_with_FAILSAFE_text_gives_pass():
    """A check returning 'WARN: ... FAILSAFE ...' must not count as FAIL."""
    from upii.cli import app
    with patch.object(Doctor, "check_sqlite", return_value="OK"):
        with patch.object(Doctor, "check_vector_db", return_value="OK"):
            with patch.object(Doctor, "check_disk", return_value="OK"):
                with patch.object(Doctor, "check_model", return_value="WARN: FAILSAFE test"):
                    with patch.object(Doctor, "check_embedding", return_value="OK"):
                        with patch.object(Doctor, "check_last_ingestion", return_value="OK"):
                            result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "doctor: PASS" in result.output


# --- model hint per-branch tests (item 3) ---

@patch("upii.analysis.diagnostics.ollama")
def test_model_hint_ollama_offline(mock_ollama):
    mock_ollama.list.return_value = {"models": []}
    doc = Doctor()
    # Mock LLM path: check_model returns WARN with "offline" or "mock".
    res = "WARN: Ollama offline (Using Mock LLM)"
    assert remediation("model", res).startswith("Start Ollama")


@patch("upii.analysis.llm.ollama.list", return_value={"models": []})  # LocalLLM sees Ollama up
@patch("upii.analysis.diagnostics.ollama")
def test_model_hint_connection_error(mock_ollama, _llm_list):
    mock_ollama.list.side_effect = ConnectionError("connection refused")
    doc = Doctor()
    result = doc.check_model()
    assert result.startswith("FAIL:")
    assert "connection error" in result.lower()
    # The remediation hint for connection error should be the start-Ollama hint.
    hint = remediation("model", result)
    assert hint.startswith("Start Ollama")


@patch("upii.analysis.diagnostics.ollama")
def test_model_hint_not_found(mock_ollama):
    mock_ollama.list.return_value = {"models": []}
    doc = Doctor()
    # Simulate the not-found path result (no exception, just WARN).
    from upii.core.config import config
    model_name = getattr(config, "llm_model", "llama3.2")
    result = f"WARN: Model {model_name} not found in Ollama list: []"
    hint = remediation("model", result)
    assert f"ollama pull {model_name}" in hint


@patch("upii.analysis.diagnostics.ollama")
def test_model_hint_remote_fail(mock_ollama):
    mock_ollama.list.return_value = {"models": []}
    doc = Doctor()
    # Simulate remote FAIL (no key set).
    from upii.core.config import config
    result = "FAIL: GEMINI_API_KEY not set"
    hint = remediation("model", result)
    assert "llm_provider" in hint or "GEMINI_API_KEY" in hint
