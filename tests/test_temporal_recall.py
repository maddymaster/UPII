import pytest
import datetime
from upii.storage.db import DB
from upii.analysis.search import SearchEngine
from upii.core.config import config

@pytest.fixture
def temporal_env(tmp_path):
    # Isolate BOTH the metadata DB and the vector store so the test doesn't read
    # the developer's real corpus (which would flood out the calendar event under
    # v2 fusion). With an empty vector store, the temporal signal is what surfaces
    # the seeded event — exactly what these tests assert.
    config.db_path = str(tmp_path / "upii_test.db")
    config.vector_store_path = str(tmp_path / "vectors")

    # Init DB
    db = DB()
    db.init_db()
    
    # Inject Calendar Event (LAST WEEK)
    last_week = datetime.datetime.now() - datetime.timedelta(days=4)
    db.add_calendar_event({
        "title": "Secret Meeting with Alice",
        "start_time": last_week.isoformat(),
        "end_time": (last_week + datetime.timedelta(hours=1)).isoformat(),
        "participants": ["alice@example.com", "Bob"]
    })
    
    yield db
    
    # Cleanup done by tmp_path

def test_who_did_i_talk_to(temporal_env):
    engine = SearchEngine()
    
    # Query with temporal keyword
    results = engine.search("Who did I talk to last week?", limit=5)
    
    # Check if we got Synthetic Calendar Chunk
    found_calendar = False
    for chunk in results:
        if chunk.doc_hash == "calendar":
            print(f"DEBUG: Found Calendar Chunk: {chunk.text}")
            if "Secret Meeting" in chunk.text and "Alice" in chunk.text:
                found_calendar = True
                
    assert found_calendar, "Search results did not contain the seeded calendar event from last week."

def test_ignore_future(temporal_env):
    # Inject Future Event
    future = datetime.datetime.now() + datetime.timedelta(days=10)
    temporal_env.add_calendar_event({
        "title": "Future Plan",
        "start_time": future.isoformat(),
        "end_time": future.isoformat(),
        "participants": ["FutureMan"]
    })
    
    engine = SearchEngine()
    # Query for "last week" should NOT show future event
    results = engine.search("Who did I talk to last week?")
    
    for chunk in results:
        if chunk.doc_hash == "calendar":
            assert "Future Plan" not in chunk.text
