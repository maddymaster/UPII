"""`upii ask --no-answer` must be retrieval-only and deterministic.

The flag exists so the Phase 3 demo is reproducible take-to-take: the LLM answer
is stochastic, so a demo that shows it can never be byte-identical run to run.
The guarantee that makes that work is simply that generation never runs — this
test pins exactly that, without needing an embedder or an index.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from upii.cli import app
from upii.core.types import RankedChunk

runner = CliRunner()


def _fake_results():
    c = RankedChunk(doc_hash="doc-abc", chunk_hash="c1", text="The Q3 budget is $50k.",
                    start_char=0, end_char=0)
    return [c]


@patch("upii.analysis.llm.LocalLLM")
@patch("upii.analysis.search.SearchEngine")
def test_no_answer_skips_generation_and_shows_context(mock_engine, mock_llm):
    mock_engine.return_value.search.return_value = _fake_results()

    result = runner.invoke(app, ["ask", "What is the Q3 budget?", "--no-answer"])

    assert result.exit_code == 0
    # The LLM is never constructed or called.
    mock_llm.assert_not_called()
    # The retrieved context (and its citation) is shown instead.
    assert "Retrieved context" in result.stdout
    assert "doc-abc" in result.stdout
    assert "Answer:" not in result.stdout


@patch("upii.analysis.llm.LocalLLM")
@patch("upii.analysis.search.SearchEngine")
def test_ask_without_flag_still_generates(mock_engine, mock_llm):
    mock_engine.return_value.search.return_value = _fake_results()
    mock_llm.return_value.answer_with_citations.return_value = "It is $50k [1]."

    result = runner.invoke(app, ["ask", "What is the Q3 budget?"])

    assert result.exit_code == 0
    mock_llm.return_value.answer_with_citations.assert_called_once()
    assert "Answer:" in result.stdout


@patch("upii.analysis.llm.LocalLLM")
@patch("upii.analysis.search.SearchEngine")
def test_no_answer_with_no_results(mock_engine, mock_llm):
    mock_engine.return_value.search.return_value = []

    result = runner.invoke(app, ["ask", "anything", "--no-answer"])

    assert result.exit_code == 0
    mock_llm.assert_not_called()
    assert "No relevant context" in result.stdout
