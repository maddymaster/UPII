import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from upii.analysis.embeddings import Embedder
from upii.storage.vector import LocalVectorStore
from upii.core.types import Chunk

# Test Fixtures
@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

def test_embedder_singleton():
    e1 = Embedder.get_instance()
    e2 = Embedder.get_instance()
    assert e1 is e2

def test_embedder_batching():
    # Mock SentenceTransformer to avoid loading real model
    with patch("upii.analysis.embeddings.SentenceTransformer") as mock_cls:
        mock_model = MagicMock()
        mock_cls.return_value = mock_model
        # Mock encode to return dummy object with tolist
        mock_res = MagicMock()
        mock_res.tolist.return_value = [[0.1, 0.2]] * 5
        mock_model.encode.return_value = mock_res
        
        # Reset singleton to ensure mock is used
        Embedder._instance = None 
        
        e = Embedder()
        texts = ["hello"] * 5
        vecs = e.embed(texts, batch_size=2)
        
        mock_model.encode.assert_called_with(texts, batch_size=2, show_progress_bar=False)
        assert len(vecs) == 5
        assert len(vecs[0]) == 2

def test_vector_store_add_search(temp_dir):
    # Patch config path
    with patch("upii.core.config.config.vector_store_path", os.path.join(temp_dir, "vectors")):
        vs = LocalVectorStore()
        
        chunks = [
            Chunk(
                doc_hash="doc1",
                chunk_hash="c1",
                text="apple",
                start_char=0,
                end_char=5,
                embedding=[1.0, 0.0]
            ),
            Chunk(
                doc_hash="doc2",
                chunk_hash="c2",
                text="banana",
                start_char=0,
                end_char=6,
                embedding=[0.0, 1.0]
            )
        ]
        
        vs.add(chunks)
        assert vs.count() == 2
        
        # Search
        results = vs.search([1.0, 0.0], limit=1)
        assert len(results) == 1
        assert results[0].text == "apple"
        assert results[0].chunk_hash == "c1"

def test_vector_store_metadata(temp_dir):
    with patch("upii.core.config.config.vector_store_path", os.path.join(temp_dir, "vectors_meta")):
        vs = LocalVectorStore()
        chunks = [Chunk(doc_hash="d1", chunk_hash="c1", text="t", start_char=0, end_char=1, embedding=[0.1])]
        vs.add(chunks)
        
        # Verify timestamp implied by successful add without error
        # In integration test, we would query LanceDB directly to verify column exists
        stats = vs.get_stats()
        assert stats["count"] == 1
