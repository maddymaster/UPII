import os
import yaml
import pytest
from upii.core.features import FeatureFlags

@pytest.fixture
def clean_flags(tmp_path):
    # Mock config path
    config_dir = tmp_path / ".upii"
    config_dir.mkdir()
    
    # We need to trick the singleton or patch where it looks
    # Since it uses config.db_path, let's patch that validation logic or just use the class logic directly
    # Ideally we patch config.db_path
    pass

def test_defaults(tmp_path):
    # We can't easily reset the singleton if it's already loaded in other tests, 
    # but for this specific test run we can just instantiate a fresh instance if we didn't use __new__ singleton logic strictness
    # or just use the global instance but ensure we direct its path to tmp
    
    # Let's manually init for test
    ff = FeatureFlags()
    ff.msg_path = str(tmp_path / "features.yaml")
    ff._load() # Reload from non-existent file -> defaults
    
    assert ff.is_enabled("ambient_memory") is False
    assert ff.is_enabled("auto_commit") is False
    assert ff.get_watch_paths() == []

def test_persistence(tmp_path):
    ff = FeatureFlags()
    ff.msg_path = str(tmp_path / "features.yaml")
    ff._load()
    
    ff.enable("ambient_memory")
    ff.add_watch_path("/tmp/test")
    
    # Check memory
    assert ff.is_enabled("ambient_memory") is True
    assert "/tmp/test" in ff.get_watch_paths()
    
    # Check disk
    assert os.path.exists(ff.msg_path)
    with open(ff.msg_path) as f:
        data = yaml.safe_load(f)
        assert data["features"]["ambient_memory"] is True
        assert "/tmp/test" in data["features"]["watch_paths"]
