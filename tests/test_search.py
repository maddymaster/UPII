import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from upii.analysis.search import SearchEngine
from upii.core.types import Chunk

# Test Fixtures
@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

@patch("upii.analysis.search.LocalVectorStore")
@patch("upii.analysis.search.Embedder")
def test_search_basic(MockEmbedder, MockVS):
    # Setup Mocks
    mock_vs_instance = MockVS.return_value
    mock_embedder_instance = MockEmbedder.get_instance.return_value
    
    # Mock Embedder to return dummy vector with tolist()
    mock_vec = MagicMock()
    mock_vec.tolist.return_value = [0.1, 0.2]
    mock_embedder_instance.encode.return_value = mock_vec
    
    # Mock VectorStore to return dummy chunks
    mock_vs_instance.search.return_value = [
        Chunk(doc_hash="d1", chunk_hash="c1", text="match", start_char=0, end_char=5)
    ]
    
    engine = SearchEngine()
    results = engine.search("query")
    
    assert len(results) == 1
    assert results[0].doc_hash == "d1"
    
    # Verify calls
    mock_embedder_instance.encode.assert_called_with("query")
    mock_vs_instance.search.assert_called_with([0.1, 0.2], limit=5, where_clause=None)

@patch("upii.analysis.search.LocalVectorStore")
@patch("upii.analysis.search.Embedder")
def test_search_time_filter(MockEmbedder, MockVS):
    # Setup Mocks
    mock_vs_instance = MockVS.return_value
    mock_embedder_instance = MockEmbedder.get_instance.return_value
    mock_vec = MagicMock()
    mock_vec.tolist.return_value = [0.1]
    mock_embedder_instance.encode.return_value = mock_vec
    
    engine = SearchEngine()
    
    # Test last_week
    engine.search("query", time_filter="last_week")
    
    # Verify where_clause passed to VS
    # We can't predict exact timestamp string, but we can check format
    call_args = mock_vs_instance.search.call_args
    _, kwargs = call_args
    where_clause = kwargs.get('where_clause')
    
    assert where_clause is not None
    assert where_clause.startswith("timestamp >= '")
    
    # Basic check calculation
    cutoff_str = where_clause.split("'")[1]
    cutoff_dt = datetime.fromisoformat(cutoff_str)
    now = datetime.now()
    diff = now - cutoff_dt
    assert 6 <= diff.days <= 7 # Should be approx 7 days
