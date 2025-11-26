import os
import pytest
from src.parsers import EventorParser
from src.models import Event

def load_test_file(filename):
    """Loads a test file."""
    path = os.path.join(os.path.dirname(__file__), 'data', filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

@pytest.fixture
def parser():
    return EventorParser()


def test_parse_swe_46200_race_urls(parser):
    """Test SWE-46200: Verify start_list_url and result_list_url are populated for each race"""
    html = load_test_file("SWE_46200_main.html")
    event = Event(event_id="SWE-46200", name="O-Ringen Jönköping, MTBO", start_date="2025-07-21",
                  end_date="2025-07-26", organizers=["Svensk Orientering Events"], country="SWE",
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Should have 5 races
    assert len(parsed_event.races) == 5, f"Expected 5 races, got {len(parsed_event.races)}"
    
    # Expected race IDs based on the HTML
    expected_race_ids = ["47850", "47851", "47852", "47853", "47854"]
    expected_race_names = ["Etapp 1", "Etapp 2", "Etapp 3", "Etapp 4", "Etapp 5"]
    
    for i, race in enumerate(parsed_event.races):
        # Verify race name
        assert race.name == expected_race_names[i], \
            f"Race {i+1} name mismatch: expected '{expected_race_names[i]}', got '{race.name}'"
        
        # Verify race ID is set
        assert race.race_id == expected_race_ids[i], \
            f"Race {i+1} race_id mismatch: expected '{expected_race_ids[i]}', got '{race.race_id}'"
        
        # Verify start_list_url is populated
        assert race.start_list_url, \
            f"Race {i+1} ({race.name}) should have start_list_url populated"
        assert f"eventRaceId={expected_race_ids[i]}" in race.start_list_url, \
            f"Race {i+1} start_list_url should contain eventRaceId={expected_race_ids[i]}"
        assert "/Events/StartList" in race.start_list_url, \
            f"Race {i+1} start_list_url should contain /Events/StartList"
        
        # Verify result_list_url is populated
        assert race.result_list_url, \
            f"Race {i+1} ({race.name}) should have result_list_url populated"
        assert f"eventRaceId={expected_race_ids[i]}" in race.result_list_url, \
            f"Race {i+1} result_list_url should contain eventRaceId={expected_race_ids[i]}"
        assert "/Events/ResultList" in race.result_list_url, \
            f"Race {i+1} result_list_url should contain /Events/ResultList"
