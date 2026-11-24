"""T-065: no literal ** in answers shown by `upii ask` and the overlay.

Some models bold key facts ("**15 December 2025**"). Both surfaces show plain text, so the
markers are removed for display; citations are kept and the raw answer is not changed.
"""
from unittest.mock import patch

from typer.testing import CliRunner

from upii.analysis.llm import Answer
from upii.cli import app, display_answer
from upii.core.types import RankedChunk

BOLD = "Firmware 2.0 is generally available on **15 December 2025** [1]."
PLAIN = "Firmware 2.0 is generally available on 15 December 2025 [1]."


def _results():
    return [RankedChunk(doc_hash="doc-1", chunk_hash="c1", text="GA is 15 December 2025.",
                        start_char=0, end_char=0, score=0.9, boost_reason="semantic",
                        source_signal="semantic")]


def test_display_answer_strips_bold_and_keeps_citations():
    assert display_answer(BOLD) == PLAIN
    assert display_answer("**a** and **b** [2][3]") == "a and b [2][3]"


def test_display_answer_leaves_plain_text_alone():
    assert display_answer(PLAIN) == PLAIN
    assert display_answer("2 * 3 = 6, see *notes*") == "2 * 3 = 6, see *notes*"
    assert display_answer(None) == ""


def test_upii_ask_prints_no_asterisks():
    with patch("upii.analysis.search.SearchEngine") as engine, patch("upii.analysis.llm.LocalLLM") as llm:
        engine.return_value.search.return_value = _results()
        llm.return_value.answer.return_value = Answer(text=BOLD, found=True, cited=[1])
        llm.return_value.model_label.return_value = "m (ollama, local)"
        out = CliRunner().invoke(app, ["ask", "When is firmware 2.0 generally available?"]).output
    assert "**" not in out
    assert "15 December 2025" in out and "Sources used" in out


def test_overlay_answer_has_no_asterisks(monkeypatch):
    from upii.overlay.app import OverlayAPI

    class Rehydrator:
        def rehydrate(self, query, limit=5, **_):
            return _results()

    class LLM:
        def answer(self, query, context):
            return Answer(text=BOLD, found=True, cited=[1])

        def model_info(self):
            return {"name": "m", "provider": "ollama", "location": "local"}

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", Rehydrator)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", LLM)
    monkeypatch.setattr("upii.storage.db.DB.get_document_by_id",
                        lambda self, doc_id: {"source_path": "/notes/a.md"})
    out = OverlayAPI().query("q")
    assert out["answer"] == PLAIN
    assert [s["n"] for s in out["sources"]] == [1]
