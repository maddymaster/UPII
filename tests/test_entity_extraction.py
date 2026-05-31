
import pytest
import os
from upii.analysis.entity_extractor import EntityExtractor
from upii.storage.db import DB
from upii.analysis.search import SearchEngine
from upii.core.types import Chunk

def test_extraction_logic():
    extractor = EntityExtractor()
    text = "We are starting Project Omega next week. Team Alpha is leading it."
    
    entities = extractor.extract(text)
    assert len(entities) == 2
    
    names = {e.name for e in entities}
    assert "Omega" in names
    assert "Alpha" in names
    
    omega = next(e for e in entities if e.name == "Omega")
    assert omega.category == "PROJECT"
    assert "starting Project Omega next" in omega.context

def test_db_entity_storage():
    db = DB()
    db.init_db()
    
    # Add Entity
    eid = db.add_entity("Project Zero", "PROJECT")
    assert eid is not None
    
    # Retrieve same entity logic (idempotence)
    eid2 = db.add_entity("Project Zero", "PROJECT")
    assert eid == eid2
    
    # Add Edge
    db.add_entity_edge(eid, "hash123", "doc1", "Context about Zero")
    
    # Retrieve Edges
    edges = db.get_entity_edges("Project Zero")
    assert len(edges) == 1
    assert edges[0]['chunk_hash'] == "hash123"

def test_search_integration(monkeypatch):
    # Mock Embedder to avoid downloading models
    class MockEmbedder:
        def encode(self, text):
            import numpy as np
            return np.zeros(384)
            
    monkeypatch.setattr("upii.analysis.embeddings.Embedder.get_instance", lambda: MockEmbedder())
    
    # Setup Logic
    db = DB()
    db.init_db()
    
    # 1. Add Data
    eid = db.add_entity("Project Secret", "PROJECT")
    db.add_entity_edge(eid, "h_secret", "doc_secret", "The secret project launch is delayed.")
    
    # 2. Search
    engine = SearchEngine()
    # Force mock embedder on instance
    engine.embedder = MockEmbedder()
    
    results = engine.search("What is the status of Project Secret?")
    
    # 3. Verify Synthetic Chunk
    found = False
    for chunk in results:
        if chunk.category == "entity_recall":
            if "Secret" in chunk.text:
                found = True
                break
    
    assert found, "Entity chunk should have been injected into search results"
