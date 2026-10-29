"""Graph edges store the extractor rule's confidence, and relational scoring uses it.

Before this, every edge was written with a hardcoded 1.0 regardless of which rule
matched (project trigger 0.95, titled person 0.9, corporate suffix 0.9, acronym org
0.70, known given name 0.75), so the relational signal could not tell a sure match
from a weak one.
"""
import hashlib
from datetime import datetime

import numpy as np
import pytest

from upii.analysis.embeddings import Embedder
from upii.core.config import config
from upii.core.types import Document

TEXT = ("Project Omega review with Dr. Sivan from Meridian Systems. "
        "NASA sent data; Priya will follow up.\n")


class FakeModel:
    def _vec(self, text):
        d = hashlib.sha256(text.encode()).digest()
        v = np.array([d[i] / 255.0 for i in range(8)])
        return v / np.linalg.norm(v)

    def encode(self, texts, **_):
        return self._vec(texts) if isinstance(texts, str) else np.array([self._vec(t) for t in texts])


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(Embedder, "_instance", FakeModel())
    monkeypatch.setattr(config, "db_path", str(tmp_path / "upii.db"))
    monkeypatch.setattr(config, "vector_store_path", str(tmp_path / "vectors"))
    from upii.storage.db import DB

    db = DB()
    db.init_db()
    return db


def _ingest(db, path, text):
    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.pipeline import ingest_document
    from upii.storage.vector import LocalVectorStore

    doc = Document(path=path, content_hash=hashlib.sha256(text.encode()).hexdigest(), content=text,
                   created_at=datetime(2026, 1, 1), source_type="md")
    return ingest_document(doc, db, LocalVectorStore(), Embedder(), RecursiveChunker())


def _edge_confidences(db):
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT e.name, e.category, ed.confidence FROM entity_edges ed "
        "JOIN entities e ON e.entity_id = ed.entity_id"
    ).fetchall()
    conn.close()
    return {(name, cat): conf for name, cat, conf in rows}


def test_acronym_org_edge_is_stored_at_070(store):
    _ingest(store, "/notes/review.md", TEXT)
    assert _edge_confidences(store)[("NASA", "ORG")] == pytest.approx(0.70)


def test_each_rule_confidence_is_stored(store):
    _ingest(store, "/notes/review.md", TEXT)
    assert _edge_confidences(store) == pytest.approx({
        ("Project Omega", "PROJECT"): 0.95,
        ("Dr. Sivan", "PERSON"): 0.90,
        ("Meridian Systems", "ORG"): 0.90,
        ("NASA", "ORG"): 0.70,
        ("Priya", "PERSON"): 0.75,
    })
    # get_entity_edges (what the relational signal reads) returns the stored value.
    assert [e["confidence"] for e in store.get_entity_edges("NASA")] == pytest.approx([0.70])


def test_duplicate_link_keeps_highest_confidence_in_any_order(store):
    for order in ([0.7, 0.9], [0.9, 0.7]):
        mentions = [("Orion", "ORG", "chunk-1", "ctx", c) for c in order]
        store.write_entities_for_doc("doc-1", mentions)
        assert _edge_confidences(store)[("Orion", "ORG")] == pytest.approx(0.9)
    # Legacy 4-tuples still work and default to 1.0.
    store.write_entities_for_doc("doc-2", [("Vega", "ORG", "chunk-2", "ctx")])
    assert _edge_confidences(store)[("Vega", "ORG")] == pytest.approx(1.0)


def test_relational_signal_prefers_the_surer_link(store, monkeypatch):
    # Two chunks, each linked to one of the query's entities: Project Omega via the
    # project rule (0.95) and NASA via the acronym rule (0.70).
    _ingest(store, "/notes/omega.md", "Project Omega milestones were reviewed.\n")
    _ingest(store, "/notes/nasa.md", "NASA delivered the calibration files.\n")

    from upii.analysis.rehydration import ContextRehydrator

    monkeypatch.setattr(ContextRehydrator, "_collect_semantic", lambda *a, **k: None)
    ranked = ContextRehydrator().rehydrate("Project Omega and NASA", limit=5,
                                           weights={"semantic": 0, "temporal": 0, "relational": 1})
    by_text = {r.text.split("] ", 1)[1].strip(): r.signals["relational"] for r in ranked}
    assert by_text["Project Omega milestones were reviewed."] == pytest.approx(1.0)
    assert by_text["NASA delivered the calibration files."] == pytest.approx(0.70 / 0.95)
    assert ranked[0].text.endswith("Project Omega milestones were reviewed.\n")
