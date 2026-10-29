"""`upii doctor` on a fresh install reports READY, not FAIL.

The SQLite DB and the vector store are only created on first ingest, so an empty
memory is a valid state. Doctor must say so, must never create those files itself,
and must still FAIL on a genuinely broken store.
"""

import hashlib
import os

import pytest
from unittest.mock import patch
from typer.testing import CliRunner

from upii.analysis.diagnostics import Doctor
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
