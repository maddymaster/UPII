import pytest
from unittest.mock import MagicMock, patch
from upii.analysis.llm import LocalLLM
from upii.core.types import Chunk
from upii.core.errors import ModelError

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
    call_args = mock_ollama.generate.call_args
    prompt = call_args.kwargs['prompt']
    
    assert "Question: Question" in prompt
    assert "Source [1] (ID: d1):" in prompt
    assert "Context 1" in prompt
    assert "Source [2] (ID: d2):" in prompt
    assert "CITE YOUR SOURCES" in prompt
    
    assert answer == "Answer with [1]"

def test_answer_no_context():
    llm = LocalLLM()
    answer = llm.answer_with_citations("Question", [])
    assert "I don't know" in answer
    assert "no relevant context" in answer

@patch("upii.analysis.llm.ollama")
def test_llm_error(mock_ollama):
    mock_ollama.generate.side_effect = Exception("Ollama down")
    llm = LocalLLM()
    with pytest.raises(ModelError):
        llm.generate("Prompt")
