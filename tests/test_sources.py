import time
import pytest
from upii.ambient.sources import registry, Source
from upii.ambient.storage import StagingDB
from upii.core.features import features

class MockSource(Source):
    """Test source."""
    def __init__(self, name):
        super().__init__(name, "Test description")
        self.captures = 0
        
    def start(self):
        self.is_running = True
        
    def stop(self):
        self.is_running = False
        
    def capture(self):
        if self.is_running:
            self.captures += 1
            self.storage.log_audit(self.name, "capture", {"count": self.captures})

@pytest.fixture
def source_env(tmp_path):
    # Temp DB
    db_path = tmp_path / "staging_test.db"
    from upii.core.config import config
    old_path = config.staging_db_path
    config.staging_db_path = str(db_path)
    
    # Reset registry
    registry.sources = {}
    registry.enabled_state = {}
    registry.config_path = str(tmp_path / "sources.yaml")
    
    # Init DB
    db = StagingDB()
    db.init_db()
    
    yield db
    
    config.staging_db_path = old_path

def test_registry_lifecycle(source_env):
    src = MockSource("test_src")
    registry.register(src)
    
    # Default: disabled
    assert not src.is_running
    assert not registry.is_enabled("test_src")
    
    # Enable
    registry.enable("test_src")
    assert src.is_running
    assert registry.is_enabled("test_src")
    
    # Capture (Simulate loop)
    src.capture()
    assert src.captures == 1
    
    # Disable
    registry.disable("test_src")
    assert not src.is_running
    
    # Ensure capture blocked (logic in Source subclass usually, here mocked check)
    src.capture() 
    assert src.captures == 1 # Shouldn't increment if checked logic is correct (here manual check)

def test_audit_log(source_env):
    src = MockSource("audit_src")
    registry.register(src)
    registry.enable("audit_src") # logs 'enable'
    time.sleep(1.1)
    
    src.capture() # logs 'capture'
    time.sleep(1.1)
    src.capture()
    time.sleep(1.1)
    
    registry.disable("audit_src") # logs 'disable'
    
    logs = source_env.get_audit_logs()
    
    # Check log order (DESC)
    assert len(logs) == 4 # enable, cap, cap, disable
    assert logs[0]['action'] == 'disable'
    assert logs[0]['source_name'] == 'audit_src'
    assert logs[1]['action'] == 'capture'
    assert logs[3]['action'] == 'enable'
