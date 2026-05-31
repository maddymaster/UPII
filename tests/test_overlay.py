
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
        def rehydrate(self, query, limit=5):
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

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", MockRehydrator)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", MockLLM)

    api = OverlayAPI()
    result = api.query("test query")
    
    assert "answer" in result
    assert result["answer"] == "Simulated Answer"
    assert "ranking" in result
    assert len(result["ranking"]) == 1
    assert result["ranking"][0]["source"] == "vector"

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
