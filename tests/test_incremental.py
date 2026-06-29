"""T1.2 — incremental ingest: dedup (no-op), edit (re-chunk + purge stale), delete.

Drives the real SQLite metadata store and a real LanceDB vector store (both in a
temp dir) through the shared pipeline, asserting counts in upii.db AND the vector
store. A deterministic fake embedder keeps it CI-safe (no model download).
"""

import hashlib
import os

import pytest
from unittest.mock import patch

from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.ingestion.loader import LocalLoader
from upii.ingestion.chunker import RecursiveChunker
from upii.ingestion.identity import doc_id_for
from upii.ingestion.pipeline import ingest_document, remove_document


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
def env(tmp_path):
    db_path = str(tmp_path / "upii.db")
    vec_path = str(tmp_path / "vectors")
    with patch("upii.core.config.config.db_path", db_path), \
         patch("upii.core.config.config.vector_store_path", vec_path):
        db = DB()
        db.init_db()
        vec = LocalVectorStore()
        yield db, vec


def _counts(db, vec):
    conn = db.get_connection()
    cur = conn.cursor()
    docs = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return {"docs": docs, "chunks": chunks, "vectors": vec.count()}


def _db_chunk_ids(db):
    conn = db.get_connection()
    cur = conn.cursor()
    ids = {r[0] for r in cur.execute("SELECT chunk_id FROM chunks").fetchall()}
    conn.close()
    return ids


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _load_one(path):
    return next(iter(LocalLoader().load(path)))


def _ingest(path, db, vec, **kw):
    return ingest_document(_load_one(path), db, vec, FakeEmbedder(), RecursiveChunker(), **kw)


# Distinct ~1KB windows so there are no legitimate chunk-hash collisions.
def _unique_body(tag, n):
    return "".join(f"[{tag} chunk {i:04d}] lorem ipsum dolor sit amet consectetur adipiscing. " for i in range(n))


def test_unchanged_reingest_is_noop(env, tmp_path):
    db, vec = env
    p = str(tmp_path / "note.md")
    _write(p, _unique_body("v1", 80))

    r1 = _ingest(p, db, vec)
    assert r1.status == "ingested"
    after_first = _counts(db, vec)
    assert after_first["docs"] == 1
    assert after_first["chunks"] > 1
    assert after_first["vectors"] == after_first["chunks"]

    r2 = _ingest(p, db, vec)
    assert r2.status == "skipped"
    assert r2.n_chunks == 0
    # No new docs / chunks / vectors written.
    assert _counts(db, vec) == after_first


def test_edit_rechunks_only_changed_and_purges_stale(env, tmp_path):
    db, vec = env
    p = str(tmp_path / "note.md")

    body = _unique_body("v1", 80)
    _write(p, body)
    r1 = _ingest(p, db, vec)
    v1_ids = {c.chunk_hash for c in r1.chunks}
    assert _db_chunk_ids(db) == v1_ids

    # Append a distinct block: early full windows are byte-identical (stable hashes),
    # the tail changes.
    _write(p, body + _unique_body("appended", 20))
    r2 = _ingest(p, db, vec)
    assert r2.status == "updated"
    v2_ids = {c.chunk_hash for c in r2.chunks}

    # Untouched chunks keep stable hashes ...
    assert v1_ids & v2_ids, "expected some unchanged chunk hashes to survive the edit"
    # ... and the edit introduced genuinely new chunks.
    assert v2_ids - v1_ids, "expected new chunk hashes from the appended content"

    # The store now holds EXACTLY the new version — no stale chunks, one doc per path.
    counts = _counts(db, vec)
    assert counts["docs"] == 1
    assert _db_chunk_ids(db) == v2_ids
    assert counts["chunks"] == len(v2_ids)
    assert counts["vectors"] == len(v2_ids)
    # Stale-only chunks are gone from both stores.
    stale = v1_ids - v2_ids
    assert stale and not (stale & _db_chunk_ids(db))


def test_delete_removes_chunks_vectors_and_metadata(env, tmp_path):
    db, vec = env
    p = str(tmp_path / "note.md")
    _write(p, _unique_body("v1", 80))
    _ingest(p, db, vec)
    assert _counts(db, vec)["docs"] == 1

    purged = remove_document(db, vec, path=p)
    assert purged > 0
    assert _counts(db, vec) == {"docs": 0, "chunks": 0, "vectors": 0}


def test_doc_id_and_chunk_link_are_deterministic(env, tmp_path):
    db, vec = env
    p = str(tmp_path / "note.md")
    _write(p, _unique_body("v1", 80))

    r1 = _ingest(p, db, vec)
    # Forced re-ingest of identical bytes -> identical doc_id and chunk ids, no dupes.
    r2 = _ingest(p, db, vec, force=True)

    assert r1.doc_id == r2.doc_id == doc_id_for(r1.content_hash)
    assert {c.chunk_hash for c in r1.chunks} == {c.chunk_hash for c in r2.chunks}
    counts = _counts(db, vec)
    assert counts["docs"] == 1
    assert counts["vectors"] == counts["chunks"]  # no duplicate vector rows
    # Every chunk points at the deterministic doc_id.
    assert all(c.doc_hash == r1.doc_id for c in r2.chunks)
