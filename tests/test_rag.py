import pytest
from unittest.mock import patch
from upii.analysis.llm import LocalLLM
from upii.core.types import Chunk

MOCK_MARKER = "simulated AI response"


@pytest.fixture(autouse=True)
def force_local_path(monkeypatch):
    """Pin every test to the local Ollama path.

    LocalLLM prefers Gemini whenever config.gemini_api_key is non-empty, and that
    key is read from the environment. Without this, a developer with GEMINI_API_KEY
    exported would send these test prompts to the real API.
    """
    monkeypatch.setattr("upii.analysis.llm.config.gemini_api_key", "")


@patch("upii.analysis.llm.ollama")
def test_llm_generate(mock_ollama):
    mock_ollama.generate.return_value = {'response': 'Test answer'}
    llm = LocalLLM()
    resp = llm.generate("Prompt")
    assert resp == 'Test answer'
    mock_ollama.generate.assert_called()


@patch("upii.analysis.llm.ollama")
def test_answer_with_citations_flow(mock_ollama):
    mock_ollama.generate.return_value = {'response': 'Answer with [1]'}
    llm = LocalLLM()

    chunks = [
        Chunk(doc_hash="d1", chunk_hash="c1", text="Context 1", start_char=0, end_char=5),
        Chunk(doc_hash="d2", chunk_hash="c2", text="Context 2", start_char=0, end_char=5)
    ]

    answer = llm.answer_with_citations("Question", chunks)

    # Check prompt construction
    prompt = mock_ollama.generate.call_args.kwargs['prompt']

    assert "User/My Query: Question" in prompt
    assert "Source [1] (ID: d1):" in prompt
    assert "Context 1" in prompt
    assert "Source [2] (ID: d2):" in prompt
    assert "CITE YOUR SOURCES" in prompt

    assert answer == "Answer with [1]"


@patch("upii.analysis.llm.ollama")
def test_answer_no_context(mock_ollama):
    """With no retrieved chunks the model is still asked, but the prompt says so."""
    mock_ollama.generate.return_value = {'response': 'Answer without sources'}
    llm = LocalLLM()

    answer = llm.answer_with_citations("Question", [])

    prompt = mock_ollama.generate.call_args.kwargs['prompt']
    assert "No specific local files found." in prompt
    assert "Source [1]" not in prompt
    assert answer == 'Answer without sources'


@patch("upii.analysis.llm.ollama")
def test_generate_falls_back_to_mock_when_ollama_fails(mock_ollama):
    """A failing backend degrades to a mock answer rather than raising: the system
    always responds. It retries once on CPU before giving up."""
    mock_ollama.generate.side_effect = Exception("Ollama down")
    llm = LocalLLM()

    answer = llm.generate("Prompt")

    assert MOCK_MARKER in answer
    assert llm.is_mock is True
    assert mock_ollama.generate.call_count == 2  # GPU attempt, then CPU-only retry


@patch("upii.analysis.llm.ollama")
def test_generate_retries_on_cpu_before_falling_back(mock_ollama):
    """If the CPU-only retry succeeds, that answer is used and mock mode stays off."""
    mock_ollama.generate.side_effect = [
        Exception("GPU unavailable"),
        {'response': 'CPU answer'},
    ]
    llm = LocalLLM()

    assert llm.generate("Prompt") == 'CPU answer'
    assert llm.is_mock is False
    assert mock_ollama.generate.call_args.kwargs['options'] == {'num_gpu': 0}


@patch("upii.analysis.llm.ollama")
def test_mock_mode_when_ollama_unreachable_at_startup(mock_ollama):
    """No Ollama daemon at construction time => mock mode, and no generate call."""
    mock_ollama.list.side_effect = Exception("connection refused")
    llm = LocalLLM()

    assert llm.is_mock is True
    assert MOCK_MARKER in llm.generate("Prompt")
    mock_ollama.generate.assert_not_called()
