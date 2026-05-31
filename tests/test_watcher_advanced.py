import os
import time
import pytest
from upii.ambient.watcher import FileSystemSource
from upii.ambient.storage import StagingDB
from upii.core.features import features

@pytest.fixture
def watcher_env(tmp_path):
    # Setup paths
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    
    # DB
    db_path = tmp_path / "staging.db"
    from upii.core.config import config
    old_db = config.staging_db_path
    config.staging_db_path = str(db_path)
    
    # Init DB
    db = StagingDB()
    db.init_db()
    
    # Setup Source
    source = FileSystemSource()
    source.configure({
        "watch_paths": [str(watch_dir)],
        "interval": 0.1 # Fast poll for tests
    })
    source.debounce_seconds = 0.2
    
    yield source, watch_dir, db
    
    source.stop()
    config.staging_db_path = old_db

def test_ignored_files(watcher_env):
    source, watch_dir, db = watcher_env
    source.start()
    
    # Create ignored files
    (watch_dir / ".hidden.txt").write_text("secret")
    (watch_dir / "temp.tmp").write_text("temp")
    
    time.sleep(0.5)
    
    events = db.get_pending_events()
    assert len(events) == 0

def test_debounce_and_staging(watcher_env):
    source, watch_dir, db = watcher_env
    source.start()
    
    target = watch_dir / "note.md"
    target.write_text("Draft 1")
    
    # Wait > debounce
    time.sleep(0.5)
    
    events = db.get_pending_events()
    assert len(events) == 1
    assert events[0]['event_type'] == 'created'
    
    # Check staging doc
    # We need to query staging_docs directly via SQL or add helper method in DB
    # Let's inspect DB raw or rely on implementation correctness if event is staged?
    # The source code calls add_staging_doc. Let's verify it logged 'capture' in audit.
    logs = db.get_audit_logs()
    assert logs[0]['action'] == 'capture'
    assert 'Draft 1' in str(logs) or 'created' in str(logs)

def test_delete_handling(watcher_env):
    source, watch_dir, db = watcher_env
    target = watch_dir / "delete_me.md"
    target.write_text("Hello")
    
    source.start()
    time.sleep(0.5)
    
    # Verify created
    events = db.get_pending_events()
    assert len(events) == 1
    
    # Now Delete
    os.remove(target)
    time.sleep(0.5)
    
    # Should see delete event
    # We need to re-fetch events. status='pending' might show both if not handled?
    # Or just check audit log for sequence
    logs = db.get_audit_logs()
    # Most recent should be delete
    assert logs[0]['action'] == 'capture'
    assert 'deleted' in str(logs[0]['details'])

def test_rename_behavior(watcher_env):
    # Rename = Delete old + Create new
    source, watch_dir, db = watcher_env
    src = watch_dir / "old.md"
    src.write_text("Content")
    
    source.start()
    time.sleep(0.5)
    
    # Rename
    dest = watch_dir / "new.md"
    os.rename(src, dest)
    time.sleep(0.5)
    
    logs = db.get_audit_logs(limit=5)
    # Expect: [capture(created new), capture(deleted old), capture(created old)...]
    # Check for both delete and create
    actions = [l['action'] for l in logs]
    details = [str(l['details']) for l in logs]
    
    assert 'deleted' in str(details)
    assert 'created' in str(details)
    assert 'new.md' in str(details)
