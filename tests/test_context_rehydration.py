
import pytest
from datetime import datetime
from upii.analysis.rehydration import ContextRehydrator
from upii.core.types import RankedChunk
from upii.storage.db import DB

def test_rehydrator_structure(monkeypatch):
    """Test standard flow logic with mocks."""
    
    # Mock Vector Store Search
    class MockVectorResults:
        @property
        def empty(self): return False
        def iterrows(self):
            # doc_id, chunk_id, text, chunk_index
            data = [
                {"doc_id": "doc1", "chunk_id": "c1", "text": "Vector match 1", "chunk_index": 0},
                {"doc_id": "doc2", "chunk_id": "c2", "text": "Vector match 2", "chunk_index": 0}
            ]
            import pandas as pd
            return pd.DataFrame(data).iterrows()

    class MockVectorStore:
        def search(self, *args, **kwargs):
            return MockVectorResults()

    monkeypatch.setattr("upii.analysis.rehydration.LocalVectorStore", lambda: MockVectorStore())
    
    # Mock Embedder
    class MockEmbedder:
        def encode(self, *args):
            import numpy as np
            return np.zeros(384)
    monkeypatch.setattr("upii.analysis.rehydration.Embedder.get_instance", lambda: MockEmbedder())

    # Mock DB Interactions (Calendar/Entities)
    class MockDB:
        def init_db(self): pass
        def get_calendar_events(self, *args, **kwargs):
            return [{
                "event_id": "evt1",
                "title": "Meeting with Alice", 
                "start_time": datetime.now().isoformat(),
                "participants": ["Alice"]
            }]
        def get_entity_edges(self, *args, **kwargs):
            return []

    monkeypatch.setattr("upii.analysis.rehydration.DB", lambda: MockDB)

    rehydrator = ContextRehydrator()
    
    # Test 1: Simple Vector + Temporal Boost
    results = rehydrator.rehydrate("Did I have a meeting yesterday?")
    
    # Expect: 2 Vector + 1 Calendar = 3
    assert len(results) >= 3
    
    # Check Calendar Boost
    cal_chunk = next((c for c in results if c.source_signal == "calendar"), None)
    assert cal_chunk is not None
    assert cal_chunk.score > 1.0 # Should be boosted
    assert "temporal" in cal_chunk.boost_reason

def test_deduplication():
    rehydrator = ContextRehydrator()
    
    # Create conflicting chunks
    c1 = RankedChunk(
        doc_hash="d1", chunk_hash="h1", text="Foo", start_char=0, end_char=3,
        source_signal="vector", score=0.5
    )
    c2 = RankedChunk(
        doc_hash="d1", chunk_hash="h1", text="Foo", start_char=0, end_char=3,
        source_signal="entity", score=1.2 # Higher score
    )
    
    candidates = [c1, c2]
    final = rehydrator._deduplicate_and_rank(candidates, limit=5)
    
    assert len(final) == 1
    assert final[0].score == 1.2
    assert final[0].source_signal == "entity"
