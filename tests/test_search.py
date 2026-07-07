import numpy as np
import pytest
from datetime import datetime

from upii.analysis.search import SearchEngine
from upii.analysis.rehydration import ContextRehydrator
from upii.core.types import Chunk


class _MockEmbedder:
    def encode(self, text):
        return np.zeros(384)


def _mock_rehydrator_env(monkeypatch, hits, calendar=None, edges=None, capture=None):
    """Patch the rehydrator's collaborators so search runs without a real model/index.

    ``hits`` is what the vector store's ``search_scored`` returns.
    """
    monkeypatch.setattr(
        "upii.analysis.rehydration.Embedder.get_instance", lambda: _MockEmbedder()
    )

    class MockVS:
        def __init__(self, *a, **k):
            pass

        def search_scored(self, vec, limit=5, where_clause=None):
            if capture is not None:
                capture["where_clause"] = where_clause
                capture["limit"] = limit
            return hits

    monkeypatch.setattr("upii.analysis.rehydration.LocalVectorStore", MockVS)

    class MockDB:
        def init_db(self):
            pass

        def get_calendar_events(self, *a, **k):
            return calendar or []

        def get_entity_edges(self, *a, **k):
            return edges or []

    monkeypatch.setattr("upii.analysis.rehydration.DB", lambda: MockDB())


def test_search_returns_semantic_hit(monkeypatch):
    hits = [
        {
            "chunk": Chunk(doc_hash="d1", chunk_hash="c1", text="match", start_char=0, end_char=5),
            "distance": 0.1,
            "timestamp": datetime.now().isoformat(),
        }
    ]
    _mock_rehydrator_env(monkeypatch, hits)

    results = SearchEngine().search("query")

    assert len(results) == 1
    r = results[0]
    assert r.doc_hash == "d1"
    # v2 fusion: the chunk carries a per-signal breakdown, semantic is dominant.
    assert r.source_signal == "semantic"
    assert r.signals["semantic"] > 0
    assert r.contributions["semantic"] > 0
    assert r.score == pytest.approx(sum(r.contributions.values()))


def test_search_weight_override_changes_score(monkeypatch):
    hits = [
        {
            "chunk": Chunk(doc_hash="d1", chunk_hash="c1", text="match", start_char=0, end_char=5),
            "distance": 0.1,
            "timestamp": datetime.now().isoformat(),
        }
    ]
    _mock_rehydrator_env(monkeypatch, hits)

    base = SearchEngine().search("query")[0]
    boosted = SearchEngine().search("query", weights={"semantic": 2.0})[0]

    # Doubling the semantic weight doubles its contribution (signal is unchanged).
    assert boosted.contributions["semantic"] == pytest.approx(2 * base.contributions["semantic"])


def test_time_filter_builds_where_clause(monkeypatch):
    capture = {}
    _mock_rehydrator_env(monkeypatch, hits=[], capture=capture)

    SearchEngine().search("query", time_filter="last_week")

    where = capture.get("where_clause")
    assert where is not None
    assert where.startswith("timestamp >= '")
    cutoff = datetime.fromisoformat(where.split("'")[1])
    diff_days = (datetime.now() - cutoff).days
    assert 6 <= diff_days <= 7


def test_build_time_filter_helper():
    # Pure helper — construct without loading the embedding model.
    r = ContextRehydrator.__new__(ContextRehydrator)
    assert r._build_time_filter(None) is None
    wc = r._build_time_filter("last_week")
    assert wc.startswith("timestamp >= '")
