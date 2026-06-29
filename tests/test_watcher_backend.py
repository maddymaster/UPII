import os
import time
import pytest

from upii.ambient.watcher import FileSystemSource
from upii.ambient.storage import StagingDB


@pytest.fixture
def watch_env(tmp_path, monkeypatch):
    from upii.core.config import config
    monkeypatch.setattr(config, "staging_db_path", str(tmp_path / "staging.db"))
    # Don't let real features.yaml inject extra paths into start().
    from upii.core import features as feat_mod
    monkeypatch.setattr(feat_mod.features, "flags", {"watch_paths": []}, raising=False)

    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    StagingDB().init_db()
    yield watch_dir


def test_watcher_uses_watchdog(watch_env):
    """With watchdog installed, the native backend is selected and captures."""
    watch_dir = watch_env
    source = FileSystemSource()
    source.configure({"watch_paths": [str(watch_dir)]})
    source.debounce_seconds = 0.2
    source.start()
    try:
        assert source.backend == "watchdog"

        (watch_dir / "note.md").write_text("hello from watchdog")
        # Native event + debounce should stage within ~1s.
        deadline = time.time() + 3
        events = []
        while time.time() < deadline:
            events = StagingDB().get_pending_events()
            if events:
                break
            time.sleep(0.1)
        assert len(events) >= 1
        assert events[0]["event_type"] == "created"
    finally:
        source.stop()


def test_watcher_falls_back_to_polling_on_import_error(watch_env, monkeypatch):
    """If watchdog import fails, the watcher falls back to polling and still captures."""
    watch_dir = watch_env

    def boom(self):
        raise ImportError("simulated: watchdog not installed")

    monkeypatch.setattr(FileSystemSource, "_try_import_watchdog", boom)

    source = FileSystemSource()
    # Explicit fast interval so the fallback poll loop captures quickly in-test.
    source.configure({"watch_paths": [str(watch_dir)], "interval": 0.1})
    source.debounce_seconds = 0.1
    source.start()
    try:
        assert source.backend == "polling"

        (watch_dir / "note.md").write_text("hello from polling")
        deadline = time.time() + 3
        events = []
        while time.time() < deadline:
            events = StagingDB().get_pending_events()
            if events:
                break
            time.sleep(0.1)
        assert len(events) >= 1
        assert events[0]["event_type"] == "created"
    finally:
        source.stop()
