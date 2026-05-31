import pytest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
from upii.analysis.nlp import TaskExtractor
from upii.core.types import Chunk, Task
from upii.storage.db import DB
from upii.core.config import config

def test_task_extraction_patterns():
    extractor = TaskExtractor()
    
    # Test cases
    cases = [
        ("TODO: Fix the bug", "Fix the bug"),
        ("fixme: cleanup code", "cleanup code"),
        ("Action Item: Review PR", "Review PR"),
        ("- [ ] Buy milk", "Buy milk"),
        ("* [ ]  Call Mom ", "Call Mom"),
        ("Just a note", None), # Should not extract
        ("TODO: hi", None), # Too short (<=3 chars filtered?)
    ]
    
    for text, expected in cases:
        chunk = Chunk(doc_hash="d1", chunk_hash="c1", text=text, start_char=0, end_char=len(text))
        tasks = extractor.extract([chunk])
        
        if expected:
            assert len(tasks) == 1
            assert tasks[0].description == expected
            assert tasks[0].source_chunk_id == "c1"
        else:
            assert len(tasks) == 0

def test_categorization():
    extractor = TaskExtractor()
    
    c1 = Chunk("d1", "c1", "We Decided: go left", 0, 10)
    extractor.extract([c1])
    assert c1.category == "decision"
    
    c2 = Chunk("d1", "c2", "- [ ] Task here", 0, 10)
    extractor.extract([c2])
    assert c2.category == "task"
    
    c3 = Chunk("d1", "c3", "Just info", 0, 10)
    extractor.extract([c3])
    assert c3.category == "note"

@pytest.fixture
def temp_db():
    d = tempfile.mkdtemp()
    db_path = os.path.join(d, "test.db")
    with patch("upii.core.config.config.db_path", db_path):
        db = DB()
        db.init_db()
        yield db
    shutil.rmtree(d)

def test_db_task_persistence(temp_db):
    tasks = [
        Task(task_id="t1", description="Do work", status="pending", source_chunk_id="c1", source_doc_id="d1")
    ]
    temp_db.add_tasks(tasks)
    
    # Retrieve
    pending = temp_db.get_tasks(status="pending")
    assert len(pending) == 1
    assert pending[0].description == "Do work"
    
    # Update
    temp_db.update_task_status("t1", "done")
    done = temp_db.get_tasks(status="done")
    assert len(done) == 1
    
    # Search
    found = temp_db.get_tasks(search="work")
    assert len(found) == 1
    
    missing = temp_db.get_tasks(search="sleep")
    assert len(missing) == 0
