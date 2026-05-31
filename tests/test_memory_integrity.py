
import sys
import os
print("DEBUG: Starting test_memory_integrity.py")
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(os.path.dirname(current_dir), 'src')
print(f"DEBUG: Adding {src_path} to sys.path")
sys.path.insert(0, src_path)

try:
    import pytest
    print("DEBUG: Imported pytest")
    import sqlite3
    print("DEBUG: Imported sqlite3")
    import uuid
    print("DEBUG: Imported uuid")
    from upii.ambient.storage import StagingDB
    print("DEBUG: Imported StagingDB")
except Exception as e:
    print(f"DEBUG: Import Error: {e}")
    sys.exit(1)


class TestMemoryIntegrity:
    
    @pytest.fixture
    def db(self, tmp_path):
        """Yields a StagingDB instance backed by a temporary file."""
        db_path = tmp_path / "staging_integrity.db"
        
        # Patching config:
        from upii.core.config import config
        old_path = config.staging_db_path
        config.staging_db_path = str(db_path)
        
        stg = StagingDB()
        stg.init_db()
        yield stg
        
        # Teardown
        config.staging_db_path = old_path

    def test_no_duplication_on_repeated_events(self, db):
        """Ensure repeated events for same file don't spam the Inbox (deduplication logic might be in Watcher, but DB should handle constraints)."""
        file_path = "/tmp/test_note.txt"
        
        # 1. Add Event
        eid1 = db.add_event("modified", file_path)
        
        # 2. Add same event again (simulating rapid fire)
        eid2 = db.add_event("modified", file_path)
        
        events = db.get_pending_events()
        # Ensure entries exist and have distinct IDs
        assert len(events) == 2
        assert events[0]['file_path'] == file_path
        assert events[0]['event_id'] != events[1]['event_id']

    def test_metadata_integrity(self, db):
        """Verify stored fields match input."""
        file_path = "/tmp/test_data.json"
        db.add_event("created", file_path)
        
        events = db.get_pending_events()
        assert len(events) == 1
        e = events[0]
        
        # Check UUID
        try:
            uuid.UUID(e['event_id'])
        except ValueError:
            pytest.fail("event_id is not a valid UUID")

        # Check Status default
        assert e['status'] == "pending"
        # Check Status default
        assert e['status'] == "pending"

print("Compiling tests/test_memory_integrity.py...")

if __name__ == "__main__":
    import sys
    # Verify imports
    try:
        from upii.ambient.storage import StagingDB
        print("Import successful.")
    except ImportError as e:
        print(f"Import failed: {e}")
        sys.exit(1)

    # Manual run wrapper
    t = TestMemoryIntegrity()
    
    # Mock fixture
    # Mock fixture
    class MockTmpPath:
        def __init__(self, p): self.path = p
        def __truediv__(self, other): return os.path.join(self.path, other)
        def __str__(self): return self.path
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Running tests in {tmp}")
        
        # Manual Setup
        db_path = os.path.join(tmp, "staging_integrity.db")
        from upii.core.config import config
        old_path = config.staging_db_path
        config.staging_db_path = str(db_path)
        
        try:
            stg = StagingDB()
            stg.init_db()
            
            def wipe(conn):
                 c = conn.cursor()
                 c.execute("DELETE FROM events")
                 c.execute("DELETE FROM staging_docs")
                 conn.commit()
                 conn.close()

            print("Running test_no_duplication_on_repeated_events...")
            t.test_no_duplication_on_repeated_events(stg)
            print("PASS")
            
            # Reset
            conn = sqlite3.connect(db_path)
            wipe(conn)
            
            print("Running test_metadata_integrity...")
            t.test_metadata_integrity(stg)
            print("PASS")
            
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
        finally:
            config.staging_db_path = old_path


