
import logging
import random
import time
import os
import threading
import uuid
import psutil
import pytest
from upii.ambient.storage import StagingDB

# Simulation Constants
SIMULATION_DURATION_SEC = 5  # For automated test, keep short (e.g. 5s = 5 hours "simulated" if accelerated)
# In real scenario, set to 3600*24
ACTION_DELAY = 0.1 # 100ms between actions

class TestLongRunningStability:

    @pytest.fixture
    def staging_db(self, tmp_path):
        db_path = tmp_path / "long_run_staging.db"
        from upii.core.config import config
        old_path = config.staging_db_path
        config.staging_db_path = str(db_path)
        
        stg = StagingDB()
        stg.init_db()
        yield stg
        
        config.staging_db_path = old_path

    def test_stability_simulation(self, staging_db):
        """
        Simulate constant activity for a period and check memory/integrity.
        """
        start_time = time.time()
        process = psutil.Process(os.getpid())
        
        initial_memory = process.memory_info().rss
        
        iteration = 0
        actions = ["create", "modify", "delete"]
        
        print(f"Starting Stability Sim for {SIMULATION_DURATION_SEC}s...")
        
        while time.time() - start_time < SIMULATION_DURATION_SEC:
            action = random.choice(actions)
            file_id = random.randint(1, 100) # operate on 100 "virtual" files
            file_path = f"/virtual/path/doc_{file_id}.txt"
            
            # Simulate DB Write
            try:
                if action == "create":
                    staging_db.add_event("created", file_path)
                elif action == "modify":
                    staging_db.add_event("modified", file_path)
                elif action == "delete":
                    # StagingDB currently might not have delete logic exposed for 'add_event'
                    # Assuming we log it regardless
                    staging_db.add_event("deleted", file_path)
            except Exception as e:
                pytest.fail(f"DB Write failed at iteration {iteration}: {e}")
            
            iteration += 1
            if iteration % 100 == 0:
                 # Check Memory Growth
                 current_memory = process.memory_info().rss
                 # Allow some growth (DB WAL), but not crazy. 
                 # Python GC is lazy, so strict checking is hard.
                 # Just logging for now, or asserting not > 2x
                 pass
            
            time.sleep(ACTION_DELAY / 100) # Speed up simulation

        end_memory = process.memory_info().rss
        growth_mb = (end_memory - initial_memory) / 1024 / 1024
        
        print(f"Simulation ended. Iterations: {iteration}. Memory Growth: {growth_mb:.2f}MB")
        
        # Verify DB is readable
        try:
            events = staging_db.get_pending_events()
            assert len(events) > 0 # Should have accumulated
            # Ideally verify count matches iteration roughly (unless pruning)
        except Exception as e:
            pytest.fail(f"DB Corrupt after simulation: {e}")
            
        # Assert memory growth is reasonable (e.g. < 50MB for this short run)
        assert growth_mb < 50
