
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
    api = _api(monkeypatch, Answer(text="It is in [2].", found=True, cited=[2]),
               {"d1": "/notes/a.md", "d2": "/notes/b.md", "d3": "/notes/c.md"})
    out = api.query("q")
    assert out["sources"] == [{"n": 2, "path": "/notes/b.md", "excerpt": "Passage 2 with spaces"}]
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


def test_daemon_logic():
    """Verify daemon toggle logic."""
    mock_app = MagicMock()
    mock_app.window = MagicMock()
    
    daemon = HotkeyDaemon(mock_app)
    
    # 1. Start Visible
    daemon.visible = True
    
    # 2. Trigger - Should Hide
    daemon.on_activate()
    mock_app.window.hide.assert_called_once()
    assert daemon.visible == False
    
    # 3. Trigger Again - Should Show
    daemon.on_activate()
    mock_app.window.show.assert_called_once()
    assert daemon.visible == True

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
    test_daemon_logic()
    print("All tests passed manually.")
