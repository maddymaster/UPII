"""scripts/bench/ask_startup.py: summary, report and the memory-folder check (no ML run)."""
import importlib.util
import os
import sys

import pytest

PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "bench", "ask_startup.py")


def load():
    spec = importlib.util.spec_from_file_location("ask_startup", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_summary_median_min_max():
    s = load().summary([4.7, 4.6, 7.8, 4.9, 4.6])
    assert s == {"median": 4.7, "min": 4.6, "max": 7.8, "n": 5}


def test_report_lists_runs_phases_and_warm():
    out = load().report([4.6, 4.7], {"phases": [["import torch", 0.58], ["answer", 0.25]],
                                      "warm": [0.24, 0.27]})
    assert "upii ask, new process, 2 runs: median 4.65 s" in out
    assert "580 ms  import torch" in out
    assert "2 more questions (search + answer): median 255 ms, max 270 ms" in out


def test_uses_this_interpreter_not_path():
    assert load().upii_cmd() == [sys.executable, "-m", "upii.cli"]


def test_refuses_outside_memory_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as e:
        load().main(["--runs", "0", "--no-phases"])
    assert "No upii.db here" in str(e.value)
    assert os.listdir(tmp_path) == []
