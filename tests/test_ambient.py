import os
import time
import pytest
from upii.ambient.watcher import PollingWatcher
from upii.core.features import features
from upii.ambient.storage import StagingDB

@pytest.fixture
def ambient_env(tmp_path):
    # Setup test env
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    
    # Enable features
    features.flags["ambient_memory"] = True
    features.flags["watch_paths"] = [str(watch_dir)]
    
    # Redirect DB
    db_path = tmp_path / "staging.db"
    
    # Patch Config singleton? Or just instance storage with path?
    # StagingDB reads config.staging_db_path. 
    # Valid way: Patch config
    from upii.core.config import config
    old_path = config.staging_db_path
    config.staging_db_path = str(db_path)
    
    yield watch_dir, db_path
    
    # Teardown
    features.flags["ambient_memory"] = False
    features.flags["watch_paths"] = []
    config.staging_db_path = old_path

def test_watcher_lifecycle(ambient_env):
    watch_dir, db_path = ambient_env
    
    watcher = PollingWatcher(interval=0.1)
    watcher.start()
    
    # Create file
    test_file = watch_dir / "note.md"
    test_file.write_text("Hello Ambient")
    
    # Wait for scan
    time.sleep(0.5)
    
    # Check DB
    db = StagingDB()
    events = db.get_pending_events()
    assert len(events) >= 1
    assert events[0]['event_type'] == 'created'
    assert events[0]['file_path'] == str(test_file)
    
    watcher.stop()
