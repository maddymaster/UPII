"""T-061: an answer that cites nothing shows the closest passage, labelled as not cited.

The model does not always put [n] in its answer. Then `upii ask` must not print
"Sources used" (nothing was cited) and must not invent a citation; it shows the passage
retrieval ranked first, labelled "Closest passage (not cited by the model)".
"""
from unittest.mock import patch

from typer.testing import CliRunner

from upii.analysis.llm import Answer
from upii.cli import UNCITED_LABEL, app
from upii.core.types import RankedChunk

runner = CliRunner()


def _results():
    return [RankedChunk(doc_hash=f"doc-{n}", chunk_hash=f"c{n}", text=text, start_char=0, end_char=0)
            for n, text in (("top", "We are allocating $20k for team offsites."),
                            ("second", "Operating costs remained flat."))]


def _ask(answer):
    with patch("upii.analysis.search.SearchEngine") as engine, patch("upii.analysis.llm.LocalLLM") as llm:
        engine.return_value.search.return_value = _results()
        llm.return_value.answer.return_value = answer
        llm.return_value.model_label.return_value = "llama3.2 (ollama, local)"
        return runner.invoke(app, ["ask", "How much is budgeted for team offsites?"])


def test_uncited_answer_shows_closest_passage_labelled():
    r = _ask(Answer(text="$20k is budgeted for team offsites.", found=True, cited=[]))
    assert r.exit_code == 0, r.output
    out = " ".join(r.stdout.split())
    assert UNCITED_LABEL == "Closest passage (not cited by the model)"
    assert UNCITED_LABEL + ":" in out
    assert "doc-top" in out and "allocating $20k" in out  # the top-ranked passage only
    assert "doc-second" not in out
    assert "Sources used" not in out
    assert "[1]" not in out  # no invented citation number


def test_cited_answer_unchanged():
    r = _ask(Answer(text="$20k [1].", found=True, cited=[1]))
    out = " ".join(r.stdout.split())
    assert "Sources used" in out and "[1] doc-top" in out
    assert UNCITED_LABEL not in out


def test_abstention_shows_no_passage():
    r = _ask(Answer(text="Not found in your memory.", found=False, cited=[]))
    out = " ".join(r.stdout.split())
    assert UNCITED_LABEL not in out and "Sources used" not in out and "doc-top" not in out
