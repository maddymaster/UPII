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

    # add_watch_path stores os.path.abspath(path); use an already-absolute,
    # platform-native path and compare against the normalised form so this holds on
    # Windows too (where abspath("/tmp/test") becomes "D:\\tmp\\test").
    watch = str(tmp_path / "watched")
    expected = os.path.abspath(watch)

    ff.enable("ambient_memory")
    ff.add_watch_path(watch)

    # Check memory
    assert ff.is_enabled("ambient_memory") is True
    assert expected in ff.get_watch_paths()

    # Check disk
    assert os.path.exists(ff.msg_path)
    with open(ff.msg_path) as f:
        data = yaml.safe_load(f)
        assert data["features"]["ambient_memory"] is True
        assert expected in data["features"]["watch_paths"]


# --- T-004: demo mode removed ---

from typer.testing import CliRunner
from upii.cli import app
import re


def test_help_no_demo():
    runner = CliRunner()
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for line in r.output.splitlines():
        if re.search(r"^\s*│?\s*demo\b", line):
            pytest.fail(f"'upii --help' lists demo command: {line!r}")


def test_demo_investor_exits_nonzero():
    runner = CliRunner()
    r = runner.invoke(app, ["demo", "investor"])
    assert r.exit_code != 0, f"'upii demo investor' should exit non-zero, got {r.exit_code}; output: {r.output[:500]!r}"
    assert "No such command" in r.output, f"'upii demo investor' should be unknown command; output: {r.output!r}"
