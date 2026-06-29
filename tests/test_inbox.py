import os
import uuid
import pytest

from upii.ambient.storage import StagingDB
from upii.ambient.watcher import PollingWatcher, FileSystemSource
from upii.core.features import features


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Point all three stores (LTM db, vectors, staging) at a temp dir."""
    from upii.core.config import config

    monkeypatch.setattr(config, "db_path", str(tmp_path / "upii.db"))
    monkeypatch.setattr(config, "vector_store_path", str(tmp_path / "vectors"))
    monkeypatch.setattr(config, "staging_db_path", str(tmp_path / "staging.db"))

    stg = StagingDB()
    stg.init_db()

    from upii.storage.db import DB
    db = DB()
    db.init_db()

    yield tmp_path, stg, db


def _ltm_chunk_texts(db):
    conn = db.get_connection()
    rows = conn.execute("SELECT text FROM chunks").fetchall()
    conn.close()
    return [r[0] for r in rows]


def test_inbox_approve_uses_staged_content(isolated_env):
    """Approve must promote the PINNED staged content, not a fresh disk read."""
    tmp_path, stg, db = isolated_env
    from upii.cli import inbox

    # Stage an event whose pinned content differs from what's on disk.
    file_path = str(tmp_path / "doc.md")
    with open(file_path, "w") as f:
        f.write("DISK VERSION that must NOT be ingested")

    event_id = stg.add_event("created", file_path)
    stg.add_staging_doc(
        event_id, file_path,
        content="STAGED VERSION the operator reviewed",
        content_hash="hash_staged_" + uuid.uuid4().hex,
        metadata={"author": "Maddy"},
    )

    inbox(approve=event_id[:8], reject=None, list_all=False)

    texts = " ".join(_ltm_chunk_texts(db))
    assert "STAGED VERSION" in texts
    assert "DISK VERSION" not in texts

    # Event + staging doc both flipped to approved.
    ev = next(e for e in stg.get_all_events() if e["event_id"] == event_id)
    assert ev["status"] == "approved"

    # Idempotent: re-approving is a no-op (still exactly one promotion).
    before = len(_ltm_chunk_texts(db))
    inbox(approve=event_id[:8], reject=None, list_all=False)
    assert len(_ltm_chunk_texts(db)) == before


def test_inbox_idempotent_approve(isolated_env):
    """Approving an already-approved event is a clean no-op (no double insert)."""
    tmp_path, stg, db = isolated_env
    from upii.cli import inbox

    file_path = str(tmp_path / "note.md")
    event_id = stg.add_event("created", file_path)
    stg.add_staging_doc(event_id, file_path, "Some staged note content", "h_note", {})

    inbox(approve=event_id[:8], reject=None, list_all=False)
    first = _ltm_chunk_texts(db)
    assert len(first) >= 1
    assert next(e for e in stg.get_all_events() if e["event_id"] == event_id)["status"] == "approved"

    # Re-approve twice more — LTM must not grow, no exception raised.
    inbox(approve=event_id[:8], reject=None, list_all=False)
    inbox(approve=event_id[:8], reject=None, list_all=False)
    assert _ltm_chunk_texts(db) == first


def test_inbox_reject(isolated_env):
    """Reject flips status + audits, keeps rows, never enters LTM."""
    tmp_path, stg, db = isolated_env
    from upii.cli import inbox

    file_path = str(tmp_path / "junk.md")
    event_id = stg.add_event("created", file_path)
    stg.add_staging_doc(event_id, file_path, "junk content", "h_junk", {})

    inbox(approve=None, reject=event_id[:8], list_all=False)

    ev = next(e for e in stg.get_all_events() if e["event_id"] == event_id)
    assert ev["status"] == "rejected"

    # Rows survive for the audit trail.
    sdoc = stg.get_staging_doc_by_event(event_id)
    assert sdoc is not None and sdoc["status"] == "rejected"

    # Audit log records the rejection.
    actions = [l["action"] for l in stg.get_audit_logs()]
    assert "reject" in actions

    # Nothing landed in LTM.
    assert _ltm_chunk_texts(db) == []


def test_inbox_approve_deleted_event_does_not_crash(isolated_env):
    tmp_path, stg, db = isolated_env
    from upii.cli import inbox

    event_id = stg.add_event("deleted", str(tmp_path / "gone.md"))
    inbox(approve=event_id[:8], reject=None, list_all=False)  # must not raise

    ev = next(e for e in stg.get_all_events() if e["event_id"] == event_id)
    assert ev["status"] == "acknowledged"
    assert _ltm_chunk_texts(db) == []


def test_watch_registers_with_filesystem_source(tmp_path, monkeypatch):
    """features.add_watch_path must wire through to the running FileSystemSource."""
    watch_dir = tmp_path / "w"
    watch_dir.mkdir()

    # Reset feature flags to a known state and redirect persistence to tmp.
    monkeypatch.setattr(features, "msg_path", str(tmp_path / "features.yaml"))
    monkeypatch.setitem(features.flags, "watch_paths", [])
    features.add_watch_path(str(watch_dir))

    watcher = PollingWatcher(interval=0.1)
    assert isinstance(watcher.source, FileSystemSource)
    assert os.path.abspath(str(watch_dir)) in watcher.watch_paths
