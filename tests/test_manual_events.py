
import os
import tempfile
import yaml
import pytest
from src.sources.manual import ManualSource
from src.models import Event

@pytest.fixture
def manual_events_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create a test event directory
        event_dir = os.path.join(tmpdirname, "TEST-EVENT-1")
        os.makedirs(event_dir)
        
        # Create event.yaml
        event_data = {
            "id": "TEST-EVENT-1",
            "name": "Test Manual Event",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "country": "TST",
            "organizers": ["Test Org"],
            "status": "Planned",
            "documents": [
                {"name": "Doc 1", "url": "file://bulletin.pdf", "type": "Bulletin"}
            ],
            "races": [
                {"name": "Race 1", "date": "2024-01-01", "distance": "Middle", "time": "10:00"}
            ]
        }
        
        with open(os.path.join(event_dir, "event.yaml"), "w") as f:
            yaml.dump(event_data, f)
            
        # Create dummy PDF
        with open(os.path.join(event_dir, "bulletin.pdf"), "w") as f:
            f.write("dummy content")
            
        yield tmpdirname

def test_load_manual_events(manual_events_dir):
    source = ManualSource(manual_events_dir)
    events = source.load_events()
    
    assert len(events) == 1
    event = events[0]
    assert event.event_id == "TEST-EVENT-1"
    assert event.name == "Test Manual Event"
    assert len(event.races) == 1
    assert event.races[0].name == "Race 1"
    assert len(event.documents) == 1
    # Check that URL was processed correctly (relative path resolved)
    assert event.documents[0].url.startswith("file://")
    assert "bulletin.pdf" in event.documents[0].url

def test_missing_directory():
    source = ManualSource("non_existent_dir")
    events = source.load_events()
    assert len(events) == 0
