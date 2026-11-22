"""`upii overlay`: a clear message when the extra is missing; otherwise it starts the overlay."""
import importlib.util
import sys
from unittest.mock import MagicMock

from typer.testing import CliRunner

from upii.cli import app


def test_overlay_without_extra_says_how_to_install(monkeypatch):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: None if name in ("webview", "pynput") else real(name, *a))
    r = CliRunner().invoke(app, ["overlay"])
    assert r.exit_code == 1
    assert 'upii[overlay]' in r.output and "pywebview" in r.output and "pynput" in r.output


def test_overlay_with_extra_starts_it(monkeypatch, tmp_path):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: object() if name in ("webview", "pynput") else real(name, *a))
    for mod in ("webview", "pynput", "pynput.keyboard"):
        monkeypatch.setitem(sys.modules, mod, MagicMock())
    started = MagicMock()
    import upii.overlay.daemon as daemon
    monkeypatch.setattr(daemon, "run_overlay", started)
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(app, ["overlay"])
    assert r.exit_code == 0, r.output
    started.assert_called_once()
    assert str(tmp_path) in " ".join(r.output.split()).replace(" ", "") or "Memory folder" in r.output


def test_overlay_extra_declares_both_packages():
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    from pathlib import Path
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    extra = " ".join(data["project"]["optional-dependencies"]["overlay"])
    assert "pywebview" in extra and "pynput" in extra


def test_serve_without_extra_shows_the_extra_name(monkeypatch):
    # Rich used to swallow "[api]" as markup, printing `pip install "upii"`.
    monkeypatch.setitem(sys.modules, "uvicorn", None)  # import uvicorn -> ImportError
    r = CliRunner().invoke(app, ["serve"])
    assert r.exit_code == 1
    assert 'upii[api]' in r.output


def test_help_shows_the_extras():
    for cmd, extra in (("overlay", "upii[overlay]"), ("serve", "upii[api]")):
        out = " ".join(CliRunner().invoke(app, [cmd, "--help"]).output.split())
        assert extra in out, (cmd, out)
