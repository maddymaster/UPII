
import sys
import os
print("DEBUG: Starting test_metrics.py")
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(os.path.dirname(current_dir), 'src')
sys.path.insert(0, src_path)

import pytest
import sqlite3
import json
from upii.analysis.metrics import MetricsCollector
from upii.storage.db import DB

class TestMetrics:
    
    @pytest.fixture
    def db(self, tmp_path):
        """Use a temp DB for metrics testing."""
        db_path = tmp_path / "metrics_test.db"
        from upii.core.config import config
        old_path = config.db_path
        config.db_path = str(db_path)
        
        db = DB()
        db.init_db()
        
        # Reset Singleton for test
        MetricsCollector._instance = None
        
        yield db
        
        config.db_path = old_path
        MetricsCollector._instance = None

    def test_metrics_collection(self, db):
        collector = MetricsCollector()
        
        # 1. Track Events
        collector.track_query()
        collector.track_query()
        collector.track_explicit_ingest(5)
        
        # 2. Verify DB
        rows = collector.get_history()
        assert len(rows) == 1
        today = rows[0]
        
        assert today["queries_count"] == 2
        assert today["explicit_ingest_count"] == 5
        assert today["passive_ingest_count"] == 0
        
    def test_snapshot(self, db):
        collector = MetricsCollector()
        
        # Mock some docs
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO documents (doc_id, source_path, source_type, content_hash) VALUES ('d1', 'p1', 'file', 'h1')")
        conn.commit()
        conn.close()
        
        collector.update_db_snapshot()
        
        rows = collector.get_history()
        assert rows[0]["total_docs_count"] == 1
        # Size might be tiny but > 0
        assert rows[0]["db_size_mb"] >= 0.0

    def test_upsert_increment(self, db):
        """Ensure counters accumulate."""
        collector = MetricsCollector()
        collector.track_query()
        
        # Simulate new instance / later call
        collector.track_query()
        
        rows = collector.get_history()
        assert rows[0]["queries_count"] == 2

if __name__ == "__main__":
    # Manual run support
    import sys
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            print(f"Running metrics tests in {tmp}")
            
            # Manual Setup
            db_path = os.path.join(tmp, "metrics_test.db")
            from upii.core.config import config
            old_path = config.db_path
            config.db_path = str(db_path)
            
            db = DB()
            db.init_db()
            
            def wipe_metrics(conn):
                 c = conn.cursor()
                 c.execute("DELETE FROM daily_metrics")
                 conn.commit()
                 conn.close()

            # Reset Singleton
            MetricsCollector._instance = None
            
            t = TestMetrics()
            
            try:
                print("Running test_metrics_collection...")
                t.test_metrics_collection(db)
                print("test_metrics_collection PASS")
                
                # Reset
                wipe_metrics(sqlite3.connect(db_path))
                MetricsCollector._instance = None
                
                print("Running test_snapshot...")
                t.test_snapshot(db)
                print("test_snapshot PASS")
                
                # Reset
                wipe_metrics(sqlite3.connect(db_path))
                MetricsCollector._instance = None
                
                print("Running test_upsert_increment...")
                t.test_upsert_increment(db)
                print("test_upsert_increment PASS")
                
            finally:
                config.db_path = old_path
                MetricsCollector._instance = None
                
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
