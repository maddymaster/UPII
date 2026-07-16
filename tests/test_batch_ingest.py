"""Batch ingest must be indistinguishable from per-document ingest.

``ingest_documents`` exists purely for speed: it amortises vector writes across a
batch instead of appending once per document. That optimisation is only legitimate
if the resulting store is byte-for-byte the same one the per-document path builds,
and if buffered writes can never survive a deletion that happens mid-batch.
"""

import hashlib

import pytest
from unittest.mock import patch

from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.ingestion.chunker import RecursiveChunker
from upii.ingestion.loader import LocalLoader
from upii.ingestion.pipeline import ingest_document, ingest_documents


class FakeEmbedder:
    DIM = 8

    def embed(self, texts, batch_size=32):
        return [
            [hashlib.sha256(t.encode("utf-8")).digest()[i] / 255.0 for i in range(self.DIM)]
            for t in texts
        ]


def _store(tmp_path, name):
    db_path = str(tmp_path / f"{name}.db")
    vec_path = str(tmp_path / f"{name}_vectors")
    with patch("upii.core.config.config.db_path", db_path), \
         patch("upii.core.config.config.vector_store_path", vec_path):
        db = DB()
        db.init_db()
        yield db, LocalVectorStore()


def _counts(db, vec):
    conn = db.get_connection()
    cur = conn.cursor()
    docs = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return {"docs": docs, "chunks": chunks, "vectors": vec.count()}


def _chunk_ids(db):
    conn = db.get_connection()
    cur = conn.cursor()
    ids = {r[0] for r in cur.execute("SELECT chunk_id FROM chunks").fetchall()}
    conn.close()
    return ids


def _body(tag, n):
    return "".join(
        f"[{tag} chunk {i:04d}] lorem ipsum dolor sit amet consectetur adipiscing. "
        for i in range(n)
    )


def _corpus(tmp_path, n_docs, paras=30):
    d = tmp_path / "corpus"
    d.mkdir(exist_ok=True)
    paths = []
    for i in range(n_docs):
        p = d / f"doc_{i:03d}.md"
        p.write_text(_body(f"doc{i}", paras), encoding="utf-8")
        paths.append(str(p))
    return paths


def _load(paths):
    loader = LocalLoader()
    for p in paths:
        for doc in loader.load(p):
            yield doc


def test_batch_matches_per_document_store_exactly(tmp_path):
    """Same corpus, both paths -> identical counts and identical chunk hashes."""
    paths = _corpus(tmp_path, 12)
    chunker, embedder = RecursiveChunker(), FakeEmbedder()

    db_a, vec_a = next(_store(tmp_path, "a"))
    for doc in _load(paths):
        ingest_document(doc, db_a, vec_a, embedder, chunker)

    db_b, vec_b = next(_store(tmp_path, "b"))
    # batch_chunks small enough to force several flushes mid-corpus
    ingest_documents(_load(paths), db_b, vec_b, embedder, chunker, batch_chunks=5)

    assert _counts(db_a, vec_a) == _counts(db_b, vec_b)
    assert _chunk_ids(db_a) == _chunk_ids(db_b)


def test_batch_flushes_vectors_before_returning(tmp_path):
    """A partial final batch must still be written — vectors == chunks on return."""
    paths = _corpus(tmp_path, 7)
    db, vec = next(_store(tmp_path, "flush"))
    ingest_documents(_load(paths), db, vec, FakeEmbedder(), RecursiveChunker(),
                     batch_chunks=1000)  # far larger than the corpus: nothing flushes early
    c = _counts(db, vec)
    assert c["vectors"] == c["chunks"] > 0


def test_batch_edit_midway_does_not_resurrect_deleted_vectors(tmp_path):
    """An edit inside the same batch must not be undone by a buffered write.

    Ingesting v1 buffers its vectors; ingesting v2 of the same path deletes v1. If the
    buffer flushed afterwards, v1's vectors would reappear with no chunks behind them.
    """
    d = tmp_path / "c2"
    d.mkdir()
    p = d / "note.md"

    p.write_text(_body("v1", 30), encoding="utf-8")
    doc_v1 = next(iter(LocalLoader().load(str(p))))
    p.write_text(_body("v2-completely-different", 30), encoding="utf-8")
    doc_v2 = next(iter(LocalLoader().load(str(p))))

    db, vec = next(_store(tmp_path, "edit"))
    results = ingest_documents([doc_v1, doc_v2], db, vec, FakeEmbedder(), RecursiveChunker(),
                               batch_chunks=10_000)  # never flush on size: force the hazard

    assert [r.status for r in results] == ["ingested", "updated"]
    c = _counts(db, vec)
    assert c["docs"] == 1
    assert c["vectors"] == c["chunks"], "stale v1 vectors resurrected by a buffered write"


def test_batch_dedup_is_a_noop(tmp_path):
    paths = _corpus(tmp_path, 5)
    db, vec = next(_store(tmp_path, "dedup"))
    chunker, embedder = RecursiveChunker(), FakeEmbedder()

    ingest_documents(_load(paths), db, vec, embedder, chunker)
    before = _counts(db, vec)

    again = ingest_documents(_load(paths), db, vec, embedder, chunker)
    assert all(r.status == "skipped" for r in again)
    assert _counts(db, vec) == before


def test_batch_force_reingest_does_not_duplicate_vectors(tmp_path):
    """force=True re-adds the same doc_id; vectors must not accumulate."""
    paths = _corpus(tmp_path, 4)
    db, vec = next(_store(tmp_path, "force"))
    chunker, embedder = RecursiveChunker(), FakeEmbedder()

    ingest_documents(_load(paths), db, vec, embedder, chunker)
    before = _counts(db, vec)

    ingest_documents(_load(paths), db, vec, embedder, chunker, force=True)
    after = _counts(db, vec)
    assert after == before, "forced re-ingest duplicated rows"


def test_on_result_reports_every_document(tmp_path):
    paths = _corpus(tmp_path, 6)
    db, vec = next(_store(tmp_path, "cb"))
    seen = []
    ingest_documents(_load(paths), db, vec, FakeEmbedder(), RecursiveChunker(),
                     on_result=seen.append, batch_chunks=5)
    assert len(seen) == 6
    assert all(r.status == "ingested" for r in seen)
