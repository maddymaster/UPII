
import pytest
from datetime import datetime
from upii.analysis.rehydration import ContextRehydrator
from upii.core.types import RankedChunk
from upii.storage.db import DB

def test_rehydrator_fuses_semantic_and_temporal(monkeypatch):
    """v2 fusion: vector hits + a calendar event are fused into one ranked list."""
    from datetime import timedelta
    from upii.core.types import Chunk

    class MockEmbedder:
        def encode(self, *args):
            import numpy as np
            return np.zeros(384)
    monkeypatch.setattr("upii.analysis.rehydration.Embedder.get_instance", lambda: MockEmbedder())

    now = datetime.now()

    class MockVectorStore:
        def __init__(self, *a, **k):
            pass
        def search_scored(self, vec, limit=5, where_clause=None):
            return [
                {"chunk": Chunk("doc1", "c1", "Vector match 1", 0, 0), "distance": 0.2,
                 "timestamp": now.isoformat()},
                {"chunk": Chunk("doc2", "c2", "Vector match 2", 0, 0), "distance": 0.6,
                 "timestamp": now.isoformat()},
            ]
    monkeypatch.setattr("upii.analysis.rehydration.LocalVectorStore", MockVectorStore)

    event_time = (now - timedelta(days=3)).isoformat()

    class MockDB:
        def init_db(self): pass
        def get_calendar_events(self, *args, **kwargs):
            return [{
                "event_id": "evt1",
                "title": "Meeting with Alice",
                "start_time": event_time,
                "end_time": event_time,
                "participants": ["Alice"],
            }]
        def get_entity_edges(self, *args, **kwargs):
            return []
    monkeypatch.setattr("upii.analysis.rehydration.DB", lambda: MockDB())

    rehydrator = ContextRehydrator()
    results = rehydrator.rehydrate("Did I have a meeting yesterday?", limit=5)

    # 2 vector hits + 1 calendar event, all fused into the result set.
    assert len(results) == 3

    # The calendar event is surfaced by the temporal signal.
    cal = next(c for c in results if c.doc_hash == "calendar")
    assert "Meeting with Alice" in cal.text
    assert cal.source_signal == "temporal"
    assert cal.contributions["temporal"] > 0
    assert cal.signals["semantic"] == 0.0

    # Vector hits are ranked above by the (dominant) semantic signal.
    top = results[0]
    assert top.source_signal == "semantic"
    assert top.contributions["semantic"] > 0
    # Fused score is exactly the sum of the per-signal contributions.
    assert top.score == pytest.approx(sum(top.contributions.values()))


def test_relational_fuses_onto_semantic_hit(monkeypatch):
    """A chunk found semantically AND linked to a query entity gets both signals."""
    from upii.core.types import Chunk

    class MockEmbedder:
        def encode(self, *args):
            import numpy as np
            return np.zeros(384)
    monkeypatch.setattr("upii.analysis.rehydration.Embedder.get_instance", lambda: MockEmbedder())

    class MockVectorStore:
        def __init__(self, *a, **k):
            pass
        def search_scored(self, vec, limit=5, where_clause=None):
            # "c_shared" is also an entity edge below -> should fuse.
            return [
                {"chunk": Chunk("d1", "c_shared", "Project Omega status", 0, 0), "distance": 0.3,
                 "timestamp": datetime.now().isoformat()},
            ]
    monkeypatch.setattr("upii.analysis.rehydration.LocalVectorStore", MockVectorStore)

    class MockDB:
        def init_db(self): pass
        def get_calendar_events(self, *a, **k): return []
        def get_entity_edges(self, name):
            return [{"chunk_hash": "c_shared", "text": "Omega details", "doc_id": "d1",
                     "context": "Omega details", "confidence": 1.0}]
    monkeypatch.setattr("upii.analysis.rehydration.DB", lambda: MockDB())

    rehydrator = ContextRehydrator()
    results = rehydrator.rehydrate("What is the status of Project Omega?", limit=5)

    fused = next(c for c in results if c.chunk_hash == "c_shared")
    assert fused.contributions["semantic"] > 0
    assert fused.contributions["relational"] > 0  # both signals contributed

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
