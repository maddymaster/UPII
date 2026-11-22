
import pytest
from unittest.mock import MagicMock
import sys

# Mock libraries not available in headless env
sys.modules['webview'] = MagicMock()
sys.modules['pynput'] = MagicMock()
sys.modules['pynput.keyboard'] = MagicMock()

from upii.overlay.app import OverlayAPI, OverlayApp
from upii.overlay.daemon import HotkeyDaemon

def test_overlay_api_structure(monkeypatch):
    """Verify API exposes query correctly."""
    
    # Mock Rehydrator
    class MockRehydrator:
        def rehydrate(self, query, limit=5, **_):
            from upii.core.types import RankedChunk
            return [RankedChunk(
                doc_hash="d1", chunk_hash="c1", text="Simulated Result", 
                start_char=0, end_char=10, score=0.9, 
                boost_reason="simulated", source_signal="vector"
            )]
            
    # Mock LLM
    class MockLLM:
        def answer_with_citations(self, query, context):
            return "Simulated Answer"

        def answer(self, query, context):
            from upii.analysis.llm import Answer
            return Answer(text="Simulated Answer", found=True, cited=[])

        def model_info(self):
            return {"name": "mock", "provider": "mock", "location": "local"}

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", MockRehydrator)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", MockLLM)

    api = OverlayAPI()
    result = api.query("test query")
    
    assert "answer" in result
    assert result["answer"] == "Simulated Answer"
    assert "ranking" in result
    assert len(result["ranking"]) == 1
    assert result["ranking"][0]["source"] == "vector"
    assert result["sources"] == []  # the answer cites nothing, so no sources are listed

def _three_chunks():
    from upii.core.types import RankedChunk
    return [RankedChunk(doc_hash=f"d{i}", chunk_hash=f"c{i}", text=f"Passage   {i}\n with  spaces",
                        start_char=0, end_char=10, score=0.9 - i / 10,
                        boost_reason="semantic", source_signal="semantic") for i in (1, 2, 3)]


def _api(monkeypatch, answer, paths):
    from upii.analysis.llm import Answer

    class Rehydrator:
        def rehydrate(self, query, limit=5, **_):
            return _three_chunks()

    class LLM:
        def answer(self, query, context):
            return answer

        def model_info(self):
            return {"name": "m", "provider": "ollama", "location": "local"}

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", Rehydrator)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", LLM)
    monkeypatch.setattr("upii.storage.db.DB.get_document_by_id",
                        lambda self, doc_id: ({"source_path": paths[doc_id]} if doc_id in paths else None))
    return OverlayAPI()


def test_overlay_lists_only_cited_sources_with_paths(monkeypatch):
    from upii.analysis.llm import Answer
    import os
    root = os.path.abspath(os.sep + "notes")  # absolute on every OS (a drive on Windows)
    api = _api(monkeypatch, Answer(text="It is in [2].", found=True, cited=[2]),
               {f"d{i}": os.path.join(root, f"{c}.md") for i, c in ((1, "a"), (2, "b"), (3, "c"))})
    out = api.query("q")
    assert out["sources"] == [{"n": 2, "path": os.path.join("notes", "b.md"),
                               "full_path": os.path.join(root, "b.md"),
                               "excerpt": "Passage 2 with spaces"}]
    assert len(out["ranking"]) == 3  # still returned for debugging, not displayed


def test_overlay_lists_no_sources_when_model_abstains(monkeypatch):
    from upii.analysis.llm import Answer, NOT_FOUND_MESSAGE
    api = _api(monkeypatch, Answer(text=NOT_FOUND_MESSAGE, found=False, cited=[]),
               {"d1": "/notes/a.md"})
    out = api.query("q")
    assert out["found"] is False and out["sources"] == []


def test_overlay_source_without_document_falls_back_to_hash(monkeypatch):
    from upii.analysis.llm import Answer
    api = _api(monkeypatch, Answer(text="See [1].", found=True, cited=[1]), {})
    assert api.query("q")["sources"][0]["path"] == "d1"


def test_overlay_page_escapes_text():
    from upii.overlay.app import HTML_TEMPLATE
    # Answers and passages come from the user's documents: never inserted as raw HTML.
    assert "${data.answer" not in HTML_TEMPLATE
    assert "esc(data.answer)" in HTML_TEMPLATE and "esc(s.path)" in HTML_TEMPLATE


def test_daemon_hotkey_toggles_the_app():
    """The hotkey asks the app to toggle; the app owns the shown/hidden state."""
    mock_app = MagicMock()
    HotkeyDaemon(mock_app).on_activate()
    mock_app.toggle.assert_called_once()


def test_daemon_survives_a_window_error():
    mock_app = MagicMock()
    mock_app.toggle.side_effect = RuntimeError("no window")
    HotkeyDaemon(mock_app).on_activate()  # logged, not raised (the listener thread must live)


def _app(monkeypatch, **kw):
    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", MagicMock)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", MagicMock)
    return OverlayApp(**kw)


def test_escape_hides_and_hotkey_shows_again(monkeypatch):
    app = _app(monkeypatch)
    app.window = MagicMock()
    app.api.hide_window()  # what the page calls on Escape
    app.window.hide.assert_called_once()
    assert app.visible is False
    app.api.hide_window()  # already hidden: no second hide
    app.window.hide.assert_called_once()
    HotkeyDaemon(app).on_activate()
    app.window.show.assert_called_once()
    assert app.visible is True
    HotkeyDaemon(app).on_activate()
    assert app.window.hide.call_count == 2 and app.visible is False


class _NowTimer:
    """threading.Timer stand-in that runs at once, so the window check is synchronous."""
    def __init__(self, delay, fn):
        self.fn = fn
        self.daemon = True

    def start(self):
        self.fn()


def _window(visible_after):
    w = MagicMock()
    w.native.isVisible.side_effect = lambda: visible_after[0]
    return w


def test_toggle_warns_when_the_window_does_not_change(monkeypatch, capsys):
    monkeypatch.setattr("upii.overlay.app.threading.Timer", _NowTimer)
    app = _app(monkeypatch)
    app.window = _window([True])  # hide() asked, but the OS window stays on screen
    app.toggle("hotkey")
    out = capsys.readouterr().out
    assert "warning: hotkey asked to hide the window, but it is still visible" in out


def test_toggle_is_quiet_when_the_window_follows(monkeypatch, capsys):
    monkeypatch.setattr("upii.overlay.app.threading.Timer", _NowTimer)
    app = _app(monkeypatch)
    state = [False]
    app.window = _window(state)
    app.window.show.side_effect = lambda: state.__setitem__(0, True)
    app.toggle("hotkey")  # hide: window reports not visible
    app.toggle("hotkey")  # show: window reports visible
    assert capsys.readouterr().out == ""
    assert app.window.hide.call_count == 1 and app.window.show.call_count == 1


def test_debug_traces_each_toggle(monkeypatch, capsys):
    monkeypatch.setattr("upii.overlay.app.threading.Timer", _NowTimer)
    app = _app(monkeypatch, debug=True)
    app.window = _window([False])
    app.api.hide_window()
    assert "overlay: escape -> hide; window visible = False" in capsys.readouterr().out


def test_unknown_native_window_is_not_reported(monkeypatch, capsys):
    monkeypatch.setattr("upii.overlay.app.threading.Timer", _NowTimer)
    app = _app(monkeypatch)
    app.window = MagicMock()
    app.window.native = object()  # a backend without isVisible
    app.toggle("hotkey")
    assert app.native_visible() is None and capsys.readouterr().out == ""


def test_hide_before_the_window_exists_does_nothing(monkeypatch):
    app = _app(monkeypatch)
    app.api.hide_window()
    assert app.visible is True


def test_web_inspector_is_off_unless_asked(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr("upii.overlay.app.webview", fake)
    _app(monkeypatch).launch()
    fake.start.assert_called_once_with(debug=False)
    fake.reset_mock()
    _app(monkeypatch, debug=True).launch()
    fake.start.assert_called_once_with(debug=True)


def _pywebview_walk(obj, base="", seen=None, found=None, errors=None):
    """What pywebview does with js_api at launch (webview.util get_functions): every public
    attribute, recursing into objects; methods are exposed to the page."""
    import inspect
    seen, found, errors = seen if seen is not None else set(), found if found is not None else {}, \
        errors if errors is not None else []
    if id(obj) in seen:
        return found, errors
    seen.add(id(obj))
    for name in dir(obj):
        if name.startswith("_"):
            continue
        full = f"{base}.{name}" if base else name
        try:
            attr = getattr(obj, name)
            if inspect.ismethod(attr) or inspect.isfunction(attr):
                found[full] = attr
            elif inspect.isclass(attr) or (not callable(attr) and hasattr(attr, "__module__")):
                _pywebview_walk(attr, full, seen, found, errors)
        except Exception as e:
            errors.append(f"{full}: {e}")
    return found, errors


def test_page_api_exposes_only_query_and_hide_window(monkeypatch):
    class Engine:  # stands in for the rehydrator: nested objects with an attribute that raises
        class Store:
            @property
            def session(self):
                raise AttributeError("'AsyncConnection' object has no attribute 'session'")
        vector_store = Store()

        def rehydrate(self, *a, **k):
            return []

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", Engine)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", MagicMock)
    found, errors = _pywebview_walk(OverlayApp().api)
    assert sorted(found) == ["hide_window", "query"]
    assert errors == []  # nothing for pywebview to log at launch


def test_page_calls_only_the_exposed_methods():
    import re
    from upii.overlay.app import HTML_TEMPLATE
    assert sorted(set(re.findall(r"pywebview\.api\.(\w+)", HTML_TEMPLATE))) == ["hide_window", "query"]
    assert "e.key === 'Escape'" in HTML_TEMPLATE


def test_excerpt_strips_markdown():
    from upii.overlay.app import _excerpt
    text = "# Weekly Sync\nDate: 2025-10-22\n\n## Updates\n- Sarah fixed **the leak**.\n- [ ] Read [the doc](http://x)\n> `code` and *note*"
    assert _excerpt(text) == ("Weekly Sync · Date: 2025-10-22 · Updates · Sarah fixed the leak. · "
                              "Read the doc · code and note")


def test_excerpt_keeps_plain_text_and_identifiers():
    from upii.overlay.app import _excerpt
    assert _excerpt("A paragraph that\nwraps.\n\nNext one.") == "A paragraph that wraps. · Next one."
    assert _excerpt("snake_case_name and 2*3*4") == "snake_case_name and 2*3*4"


def test_short_path(monkeypatch, tmp_path):
    import os
    from upii.overlay.app import _short_path
    monkeypatch.chdir(tmp_path)
    assert _short_path(str(tmp_path / "notes" / "a.md")) == os.path.join("notes", "a.md")
    elsewhere = os.path.join(os.path.dirname(str(tmp_path)), "other", "demo_dataset", "team_sync.md")
    assert _short_path(elsewhere) == os.path.join("demo_dataset", "team_sync.md")
    assert _short_path("d1") == "d1"  # a hash, not a path


def test_page_full_path_attribute_is_escaped():
    from upii.overlay.app import HTML_TEMPLATE
    assert 'title="${escAttr(s.full_path)}"' in HTML_TEMPLATE
    assert "replace(/\"/g, '&quot;')" in HTML_TEMPLATE


if __name__ == "__main__":
    # Manually run if executed directly
    from unittest.mock import MagicMock
    import sys
    # Re-mock for direct run safety
    sys.modules['webview'] = MagicMock()
    sys.modules['pynput'] = MagicMock()
    sys.modules['pynput.keyboard'] = MagicMock()
    
    # We need a monkeypatch mock
    class MockMonkeyPatch:
        def setattr(self, target, value):
            module_name, attr = target.rsplit('.', 1)
            import importlib
            mod = importlib.import_module(module_name)
            setattr(mod, attr, value)
            
    test_overlay_api_structure(MockMonkeyPatch())
    test_daemon_hotkey_toggles_the_app()
    print("All tests passed manually.")
