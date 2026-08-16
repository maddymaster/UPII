"""Mailbox ingest: every message survives, and mail is never swept up by a folder.

Regression cover for two defects shipped in v0.8.0:

1. **Silent data loss.** Every message in an `.mbox` was mapped to the mbox file's
   own path with its own content hash, so the edit-cleanup rule in
   `ingestion/pipeline.py` (audit finding F3) read same-path-different-hash as "this
   file was edited" and purged the previous message. Ingesting N messages left 1 —
   the last — while the CLI reported success.
2. **Mail swept up by a directory ingest.** `.mbox` was an accepted extension during
   the recursive walk, so `upii ingest ~/Documents` pulled whole mailboxes into
   durable memory without the user ever naming them.

Drives the real SQLite store and a real LanceDB vector store through the shared
pipeline, as tests/test_incremental.py does. A deterministic fake embedder keeps it
CI-safe.
"""

import hashlib
import os

import pytest
from unittest.mock import patch

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
def env(tmp_path):
    db_path = str(tmp_path / "upii.db")
    vec_path = str(tmp_path / "vectors")
    with patch("upii.core.config.config.db_path", db_path), \
         patch("upii.core.config.config.vector_store_path", vec_path):
        db = DB()
        db.init_db()
        vec = LocalVectorStore()
        yield db, vec


def _message(n, *, subject=None, body=None, message_id=None):
    subject = subject if subject is not None else f"Distinct subject number {n}"
    body = body if body is not None else f"Unique body of email {n}. Alpha bravo charlie {n}."
    mid = message_id if message_id is not None else f"<msg{n}@example.com>"
    return (
        f"From sender{n}@example.com Mon Jan  1 00:0{n}:00 2026\n"
        f"From: Sender {n} <sender{n}@example.com>\n"
        f"To: me@example.com\n"
        f"Bcc: secret{n}@example.com\n"
        f"Subject: {subject}\n"
        + (f"Message-ID: {mid}\n" if mid else "")
        + f"Date: Mon, 0{n} Jan 2026 00:00:00 +0000\n"
        f"\n"
        f"{body}\n"
    )


def _write_mbox(path, messages):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(messages))
    return str(path)


def _ingest_all(db, vec, path):
    """Run every document the loader yields through the real pipeline."""
    chunker = RecursiveChunker()
    embedder = FakeEmbedder()
    results = []
    for doc in LocalLoader().load(path):
        results.append(ingest_document(doc, db, vec, embedder, chunker))
    return results


def _docs(db):
    conn = db.get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT content_hash, source_path FROM documents").fetchall()
    conn.close()
    return rows


def _subjects_in_memory(db):
    conn = db.get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT text FROM chunks").fetchall()
    conn.close()
    return {
        line.split("Subject: ", 1)[1].strip()
        for (text,) in rows
        for line in text.splitlines()
        if line.startswith("Subject: ")
    }


def test_every_message_in_an_mbox_survives_ingest(env, tmp_path):
    """The headline regression: 3 messages in => 3 documents durable, not 1."""
    db, vec = env
    mbox = _write_mbox(tmp_path / "inbox.mbox", [_message(n) for n in (1, 2, 3)])

    results = _ingest_all(db, vec, mbox)

    assert len(results) == 3, "loader must yield one document per message"
    assert [r.status for r in results] == ["ingested"] * 3, \
        f"no message may replace another; got {[r.status for r in results]}"
    assert len(_docs(db)) == 3
    assert _subjects_in_memory(db) == {
        "Distinct subject number 1",
        "Distinct subject number 2",
        "Distinct subject number 3",
    }


def test_each_message_gets_its_own_virtual_path(env, tmp_path):
    """Paths must be distinct per message and anchored on the real mbox file."""
    db, vec = env
    mbox = _write_mbox(tmp_path / "inbox.mbox", [_message(n) for n in (1, 2, 3)])

    docs = list(LocalLoader().load(mbox))
    paths = [d.path for d in docs]

    assert len(set(paths)) == 3, "every message needs a distinct path"
    assert all(p.startswith(os.path.realpath(mbox) + "#") for p in paths), paths
    # Message-ID drives the key, so the path does not move when content does.
    assert paths[0].endswith("#msg1@example.com")
    assert all(d.metadata["mbox_path"] == os.path.realpath(mbox) for d in docs)


def test_reingesting_an_unchanged_mbox_is_a_no_op(env, tmp_path):
    """Dedup still holds per message — the Phase 2 guarantee, now per document."""
    db, vec = env
    mbox = _write_mbox(tmp_path / "inbox.mbox", [_message(n) for n in (1, 2, 3)])

    _ingest_all(db, vec, mbox)
    before = set(_docs(db))
    again = _ingest_all(db, vec, mbox)

    assert [r.status for r in again] == ["skipped"] * 3
    assert set(_docs(db)) == before


def test_editing_one_message_replaces_only_that_message(env, tmp_path):
    """A stable Message-ID means an edited message replaces its own prior version."""
    db, vec = env
    path = tmp_path / "inbox.mbox"
    _write_mbox(path, [_message(n) for n in (1, 2, 3)])
    _ingest_all(db, vec, str(path))

    _write_mbox(path, [
        _message(1),
        _message(2, body="Rewritten body for email 2. Delta echo foxtrot."),
        _message(3),
    ])
    results = _ingest_all(db, vec, str(path))

    statuses = [r.status for r in results]
    assert statuses.count("skipped") == 2, statuses
    assert statuses.count("updated") == 1, statuses
    assert len(_docs(db)) == 3, "the edit must replace, not accumulate"
    assert _subjects_in_memory(db) == {
        "Distinct subject number 1",
        "Distinct subject number 2",
        "Distinct subject number 3",
    }


def test_messages_without_a_message_id_still_get_distinct_paths(env, tmp_path):
    """Fallback identity is the content hash — stable under reordering."""
    db, vec = env
    mbox = _write_mbox(
        tmp_path / "inbox.mbox",
        [_message(n, message_id="") for n in (1, 2, 3)],
    )

    docs = list(LocalLoader().load(mbox))
    assert len({d.path for d in docs}) == 3

    reordered = _write_mbox(
        tmp_path / "reordered.mbox",
        [_message(n, message_id="") for n in (3, 1, 2)],
    )
    keys = {d.path.rsplit("#", 1)[1] for d in docs}
    reordered_keys = {d.path.rsplit("#", 1)[1] for d in LocalLoader().load(reordered)}
    assert keys == reordered_keys, "message keys must not depend on position"


def test_directory_ingest_never_sweeps_up_a_mailbox(env, tmp_path):
    """Consent gate: mail enters durable memory only when named explicitly."""
    db, vec = env
    folder = tmp_path / "Documents"
    folder.mkdir()
    _write_mbox(folder / "inbox.mbox", [_message(n) for n in (1, 2, 3)])
    with open(folder / "notes.md", "w", encoding="utf-8") as f:
        f.write("# Notes\n\nAn ordinary document that should be ingested.\n")

    docs = list(LocalLoader().load(str(folder)))

    assert [d.source_type for d in docs] == ["text"] or all(
        d.source_type != "email" for d in docs
    ), f"a folder ingest must not yield mail: {[d.source_type for d in docs]}"
    assert len(docs) == 1
    assert docs[0].path.endswith("notes.md")


def test_naming_the_mailbox_explicitly_still_ingests_it(env, tmp_path):
    """The gate blocks sweeping, not deliberate use."""
    db, vec = env
    folder = tmp_path / "Documents"
    folder.mkdir()
    mbox = _write_mbox(folder / "inbox.mbox", [_message(n) for n in (1, 2)])

    docs = list(LocalLoader().load(mbox))

    assert len(docs) == 2
    assert all(d.source_type == "email" for d in docs)
