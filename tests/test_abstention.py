"""Abstention: weak retrieval means "not found", and only cited sources are listed.

- ``rag_min_similarity`` is applied to the *absolute* cosine similarity before
  ranking; when nothing passes, ask paths return "not found" without calling a model.
- "Not found" from the model is a structured flag (the ``NOT_FOUND`` token parsed
  by ``LocalLLM.answer``), not phrase matching, and sources are listed only when the
  answer cites them.

Runs on a real temporary SQLite + LanceDB store. The embedder is a deterministic
keyword-bag model (unit vectors, like MiniLM): texts sharing content words are
similar, unrelated texts are orthogonal. Ollama is mocked.
"""
import hashlib
import re
from unittest.mock import patch

import numpy as np
import pytest
from typer.testing import CliRunner

from upii.analysis.embeddings import Embedder
from upii.analysis.llm import NOT_FOUND_MESSAGE, LocalLLM
from upii.core.config import config
from upii.core.types import Chunk

OMEGA = "Project Omega budget is two million rupees, approved by the steering committee.\n"
HIRING = "Hiring plan: two backend engineers join the platform team in March.\n"
RELATED = "What is the Project Omega budget?"
UNRELATED = "Capital city of France?"
STOP = {"what", "is", "the", "of", "a", "by", "in", "two", "plan"}


class BagModel:
    """Keyword-bag embeddings hashed into 64 dims and unit-normalised."""

    DIM = 64

    def _vec(self, text):
        v = np.zeros(self.DIM)
        for w in re.findall(r"[a-z]+", text.lower()):
            if w not in STOP:
                v[hashlib.sha256(w.encode()).digest()[0] % self.DIM] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def encode(self, texts, **_):
        if isinstance(texts, str):
            return self._vec(texts)
        return np.array([self._vec(t) for t in texts])


@pytest.fixture
def memory(tmp_path, monkeypatch):
    """Two ingested notes in an isolated store; Ollama mocked and observable."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Embedder, "_instance", BagModel())
    monkeypatch.setattr(config, "db_path", str(tmp_path / "upii.db"))
    monkeypatch.setattr(config, "vector_store_path", str(tmp_path / "vectors"))
    monkeypatch.setattr(config, "staging_db_path", str(tmp_path / "staging.db"))
    monkeypatch.setattr(config, "gemini_api_key", "")
    monkeypatch.setattr(config, "llm_provider", "local")
    monkeypatch.setattr(config, "rag_min_similarity", 0.30)

    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "omega.md").write_bytes(OMEGA.encode())
    (notes / "hiring.md").write_bytes(HIRING.encode())

    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.pipeline import ingest_documents
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore

    db = DB()
    db.init_db()
    ingest_documents(LocalLoader().load(str(notes)), db, LocalVectorStore(), Embedder(), RecursiveChunker())

    with patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate",
               return_value={"response": "The Omega budget is two million rupees [1]."}) as generate:
        yield generate


# -- retrieval threshold ------------------------------------------------------
def test_threshold_uses_absolute_similarity(memory):
    from upii.analysis.search import SearchEngine

    related = SearchEngine().search(RELATED, limit=5, min_similarity=0.30)
    assert [r.text.strip() for r in related] == [OMEGA.strip()]  # hiring note is filtered out
    assert related[0].similarity >= 0.30

    assert SearchEngine().search(UNRELATED, limit=5, min_similarity=0.30) == []
    # Search and the retrieval eval pass no threshold and keep ranking everything.
    assert len(SearchEngine().search(UNRELATED, limit=5)) == 2


# -- CLI ------------------------------------------------------------------------
def test_cli_unrelated_question_is_not_found_without_model_call(memory):
    from upii.cli import app

    result = CliRunner().invoke(app, ["ask", UNRELATED])
    assert result.exit_code == 0, result.output
    assert "Not found in your memory" in result.stdout
    assert "Sources used" not in result.stdout
    memory.assert_not_called()


def test_cli_relevant_question_answers_with_cited_sources(memory):
    from upii.cli import app

    result = CliRunner().invoke(app, ["ask", RELATED])
    assert result.exit_code == 0, result.output
    assert "two million rupees [1]" in result.stdout
    assert "Sources used" in result.stdout and "[1]" in result.stdout
    assert "[2]" not in result.stdout.split("Sources used")[1]
    memory.assert_called_once()


def test_cli_model_abstention_lists_no_sources(memory):
    from upii.cli import app

    memory.return_value = {"response": "NOT_FOUND"}
    result = CliRunner().invoke(app, ["ask", RELATED])
    assert NOT_FOUND_MESSAGE in result.stdout
    assert "Sources used" not in result.stdout


# -- HTTP API -----------------------------------------------------------------
def test_api_unrelated_not_found_and_relevant_answers(memory):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from upii.api.server import create_app

    client = TestClient(create_app(), base_url="http://127.0.0.1")
    miss = client.post("/ask", json={"question": UNRELATED}).json()
    assert miss["found"] is False and miss["sources"] == [] and miss["model"] is None
    assert miss["answer"] == NOT_FOUND_MESSAGE
    memory.assert_not_called()

    hit = client.post("/ask", json={"question": RELATED}).json()
    assert hit["found"] is True and hit["answer"].endswith("[1].")
    assert [s["passage"].strip() for s in hit["sources"]] == [OMEGA.strip()]

    retrieval_only = client.post("/ask", json={"question": UNRELATED, "no_answer": True}).json()
    assert retrieval_only["found"] is False and retrieval_only["sources"] == []


# -- answer step ----------------------------------------------------------------
def _ctx(n=2):
    return [Chunk(doc_hash=f"d{i}", chunk_hash=f"c{i}", text=f"ctx {i}", start_char=0, end_char=5)
            for i in range(n)]


@pytest.mark.parametrize("raw, found, cited", [
    ("Budget is 2M [1].", True, [1]),
    ("From [2] and [1], also [1] again.", True, [1, 2]),
    ("NOT_FOUND", False, []),
    ("  not in memory. NOT_FOUND ", False, []),
    ("I don't know.", True, []),          # no phrase matching: but nothing cited, so no sources
    ("I do not know [1]", True, [1]),     # wording is irrelevant; the citation is what counts
    ("Out of range [7] [0]", True, []),
])
def test_answer_flag_is_structured(raw, found, cited):
    with patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate", return_value={"response": raw}):
        ans = LocalLLM(provider="local").answer("q", _ctx())
    assert (ans.found, ans.cited) == (found, cited)
    if not found:
        assert ans.text == NOT_FOUND_MESSAGE


def test_answer_without_context_never_calls_model():
    with patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate") as generate:
        ans = LocalLLM(provider="local").answer("q", [])
    generate.assert_not_called()
    assert (ans.found, ans.cited, ans.text) == (False, [], NOT_FOUND_MESSAGE)
