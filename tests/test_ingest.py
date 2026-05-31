import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from upii.ingestion.loader import LocalLoader
from upii.ingestion.chunker import RecursiveChunker
from upii.storage.db import DB
from upii.core.types import Document

# Test Fixtures
@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)

@pytest.fixture
def sample_file(temp_dir):
    p = os.path.join(temp_dir, "test.txt")
    with open(p, "w") as f:
        f.write("Hello World. This is a test document.")
    return p

# Tests

def test_loader_txt(sample_file):
    loader = LocalLoader()
    docs = list(loader.load(sample_file))
    assert len(docs) == 1
    assert docs[0].content == "Hello World. This is a test document."
    assert docs[0].source_type == "txt"

def test_loader_empty(temp_dir):
    p = os.path.join(temp_dir, "empty.txt")
    with open(p, "w") as f:
        f.write("")
    loader = LocalLoader()
    docs = list(loader.load(p))
    assert len(docs) == 0 # Should skip empty

def test_loader_missing():
    loader = LocalLoader()
    docs = list(loader.load("non_existent_file.txt"))
    assert len(docs) == 0

def test_chunker_determinism():
    doc = Document(
        path="/tmp/test", 
        content_hash="abc", 
        content="Hello world " * 50, 
        created_at=None,
        source_type="txt"
    )
    chunker = RecursiveChunker(chunk_size=50, overlap=10)
    chunks1 = chunker.chunk(doc)
    chunks2 = chunker.chunk(doc)
    
    assert len(chunks1) == len(chunks2)
    assert chunks1[0].chunk_hash == chunks2[0].chunk_hash
    assert chunks1[0].text == chunks2[0].text

def test_db_operations(temp_dir):
    # Mock config to use temp DB
    with patch("upii.core.config.config.db_path", os.path.join(temp_dir, "test.db")):
        db = DB()
        db.init_db()
        
        doc = Document(
            path="/tmp/test", 
            content_hash="hash123", 
            content="abc", 
            created_at=None,
            source_type="txt",
            metadata={"foo": "bar"}
        )
        
        # Test Insert
        doc_id = "uuid-123"
        db.upsert_document(doc, doc_id)
        
        # Test Retrieve
        retrieved = db.get_document_by_hash("hash123")
        assert retrieved is not None
        assert retrieved.path == "/tmp/test"
        
        # Test Duplicate (should upsert/update)
        doc.path = "/tmp/test_moved"
        db.upsert_document(doc, doc_id)
        retrieved2 = db.get_document_by_hash("hash123")
        assert retrieved2.path == "/tmp/test_moved"

def test_corrupt_pdf(temp_dir):
    p = os.path.join(temp_dir, "bad.pdf")
    with open(p, "wb") as f:
        f.write(b"%PDF-1.4 garbage content")
    
    loader = LocalLoader()
    # Should not raise exception, just return empty generator or log error
    docs = list(loader.load(p))
    assert len(docs) == 0

def test_recursive_load(temp_dir):
    # Setup nested structure
    os.makedirs(os.path.join(temp_dir, "sub"))
    with open(os.path.join(temp_dir, "root.txt"), "w") as f: f.write("root")
    with open(os.path.join(temp_dir, "sub/child.md"), "w") as f: f.write("# child")
    
    loader = LocalLoader()
    docs = list(loader.load(temp_dir))
    assert len(docs) == 2
