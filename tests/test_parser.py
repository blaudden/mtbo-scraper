import os
import pytest
from src.parsers import EventorParser
from src.models import Event, Race

def load_test_file(filename):
    """Loads a test file."""
    path = os.path.join(os.path.dirname(__file__), 'data', filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

@pytest.fixture
def parser():
    return EventorParser()

def test_parse_swe_single(parser):
    html = load_test_file("SWE_54361_single.html")
    event = Event(event_id="SWE-54361", name="Test", start_date="2025-01-01", end_date="2025-01-01", organizers=["Org"], country="SWE", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Map positions
    assert parsed_event.races, "Should have at least one race"
    assert parsed_event.races[0].map_positions, "Should find map positions in race"
    mp = parsed_event.races[0].map_positions[0]
    assert mp.lat != 0
    assert mp.lon != 0
    assert hasattr(mp, 'raceid')
    
    # General info attributes
    assert parsed_event.attributes, "Should extract general info"
    assert "Race distance" in parsed_event.attributes
    assert parsed_event.attributes["Race distance"] == "Long"
    assert "Time of event" in parsed_event.attributes
    assert parsed_event.attributes["Time of event"] == "day"
    
    # Check that Discipline is split
    assert "Discipline" in parsed_event.attributes
    assert "MTBO" in parsed_event.attributes["Discipline"]
    
    # Contact details
    assert parsed_event.contact, "Should extract contact info"
    assert "Contact person" in parsed_event.contact
    assert parsed_event.contact["Contact person"] == "Ilana Jode"
    
    # Classes (this event has no classes)
    assert isinstance(parsed_event.classes, list)
    
    # Races (single event has 1 default race)
    assert isinstance(parsed_event.races, list)
    assert len(parsed_event.races) == 1
    
    # Documents (this event has no documents)
    assert isinstance(parsed_event.documents, list)

def test_parse_swe_multi(parser):
    html = load_test_file("SWE_50597_multi.html")
    event = Event(event_id="SWE-50597", name="Test Multi", start_date="2025-01-01", end_date="2025-01-03", organizers=["Org"], country="SWE", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Map positions
    # Check that at least one race has map positions
    assert any(r.map_positions for r in parsed_event.races), "Should find map positions in races"
    
    # Races (multi-day event should have races)
    assert parsed_event.races, "Should extract races for multi-day event"
    assert len(parsed_event.races) == 5, "Should have 5 races (Etapp 1-5)"
    
    # Verify specific race details
    race1 = parsed_event.races[0]
    assert race1.name == "Etapp 1"  # Swedish Eventor uses Etapp even in English
    assert race1.distance == "Long"
    assert race1.date == "2026-07-20"
    assert race1.night_or_day == "day"
    
    race3 = parsed_event.races[2]
    assert race3.name == "Etapp 3"
    assert race3.distance == "Sprint"
    assert race3.date == "2026-07-23"
    
    # General info
    assert parsed_event.attributes
    assert "Event classification" in parsed_event.attributes
    assert parsed_event.attributes["Event classification"] == "National event"

def test_parse_nor_single(parser):
    html = load_test_file("NOR_21169_single.html")
    event = Event(event_id="NOR-21169", name="Test NOR Single", start_date="2025-01-01", end_date="2025-01-01", organizers=["Org"], country="NOR", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Map positions
    assert parsed_event.races[0].map_positions, "Should find map positions for NOR"
    mp = parsed_event.races[0].map_positions[0]
    assert mp.lat != 0
    
    # Contact
    assert parsed_event.contact
    assert "Contact person" in parsed_event.contact
    assert parsed_event.contact["Contact person"] == "Leif Eriksson"
    assert parsed_event.contact["Contact phone number"] == "+4797627672"
    
    # Classes
    assert parsed_event.classes, "Should extract classes"
    assert len(parsed_event.classes) == 3
    assert "Lang" in parsed_event.classes
    assert "Mellom" in parsed_event.classes
    assert "Kort" in parsed_event.classes
    
    # Attributes - Discipline (singular) should be a string, not a list
    assert "Discipline" in parsed_event.attributes
    discipline = parsed_event.attributes["Discipline"]
    # Singular form should be a string
    assert isinstance(discipline, str), "Singular 'Discipline' should be string"
    assert discipline == "MTBO"
    
    # Documents
    assert parsed_event.documents, "Should extract documents"
    assert len(parsed_event.documents) >= 1
    assert parsed_event.documents[0].name == "Innbydelse"
    assert parsed_event.documents[0].type == "pdf"

def test_parse_iof_single(parser):
    html = load_test_file("IOF_8558_single.html")
    event = Event(event_id="IOF-8558", name="Test IOF Single", start_date="2025-01-01", end_date="2025-01-01", organizers=["Org"], country="IOF", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Map positions
    assert parsed_event.races[0].map_positions, "Should find map positions for IOF Single"
    
    # IOF Country extraction
    assert parsed_event.country == "Portugal", "Should extract country from Organising federation"
    
    # General info
    assert parsed_event.attributes
    assert "Organising federation" in parsed_event.attributes
    assert parsed_event.attributes["Organising federation"] == "Portugal"
    assert "Discipline" in parsed_event.attributes
    # Should be split/cleaned
    assert "MTBO" in parsed_event.attributes["Discipline"]
    
    # Documents
    assert parsed_event.documents, "Should extract documents"
    assert len(parsed_event.documents) >= 2
    doc_names = [d.name for d in parsed_event.documents]
    assert "Embargoed areas" in doc_names
    assert "Bulletin 2" in doc_names

def test_parse_iof_multi(parser):
    html = load_test_file("IOF_8277_multi.html")
    event = Event(event_id="IOF-8277", name="Test IOF Multi", start_date="2025-01-01", end_date="2025-01-05", organizers=["Org"], country="IOF", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Map positions
    assert any(r.map_positions for r in parsed_event.races)
    
    # IOF Country extraction
    assert parsed_event.country == "Sweden", "Should extract country from Organising federation"
    
    # Races (IOF multi should have competitions)
    assert parsed_event.races, "Should extract races/competitions"
    assert len(parsed_event.races) >= 4, "Should have at least 4 competitions"
    
    # Check specific races
    race_names = [r.name for r in parsed_event.races]
    assert "Middle" in race_names
    assert "Long" in race_names
    assert "Sprint" in race_names
    assert "Relay" in race_names
    
    # Verify a specific race details if possible (order might vary, so find by name)
    long_race = next((r for r in parsed_event.races if r.name == "Long"), None)
    assert long_race
    assert long_race.date == "2026-08-27"
    
    # Contact
    assert parsed_event.contact
    assert "Contact person" in parsed_event.contact
    assert parsed_event.contact["Contact person"] == "Klaus Csucs"
    
    # Classes
    assert parsed_event.classes
    assert len(parsed_event.classes) >= 2
    
    # Documents
    assert parsed_event.documents, "Should extract documents"
    assert len(parsed_event.documents) >= 2

def test_parse_skinkloppet(parser):
    html = load_test_file("SWE_56468_main.html")
    event = Event(event_id="SWE-56468", name="Skinkloppet", start_date="2025-11-30", end_date="2025-11-30", organizers=["OK Vivill"], country="SWE", status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Info Text
    assert parsed_event.info_text
    assert "Klubbaktivitet för medlemmar" in parsed_event.info_text
    assert "Lars R" in parsed_event.info_text
    
    # Splitting
    assert "Disciplines" in parsed_event.attributes
    disciplines = parsed_event.attributes["Disciplines"]
    assert "FootO" in disciplines
    assert "MTBO" in disciplines
    assert "SkiO" in disciplines
    # Attributes - should be lists for multi-value fields
    assert "Event attributes" in parsed_event.attributes
    attrs = parsed_event.attributes["Event attributes"]
    assert isinstance(attrs, list)
    assert "Orientering Terräng" in attrs
    assert "Instruktör på plats" in attrs
    
    # Race
    assert len(parsed_event.races) == 1
    race = parsed_event.races[0]
    assert race.name == "Skinkloppet"
    assert race.distance == "TempO"
    assert race.night_or_day == "day"
    
    # Map positions
    assert race.map_positions

def test_parse_list_count(parser):
    """Test parsing result list and counting entries"""
    html = load_test_file("SWE_51338_result_list.html")
    result_list = parser.parse_list_count(html)
    
    assert isinstance(result_list, dict)
    assert "total_count" in result_list
    assert "class_counts" in result_list
    
    # The result list should have a significant number of entries
    assert result_list["total_count"] > 50, f"Expected >50 entries, got {result_list['total_count']}"
    
    # Check specific class count if known (e.g. D21)
    # From previous inspection: D21 had 9 starting competitors
    if "D21" in result_list["class_counts"]:
        assert result_list["class_counts"]["D21"] > 0

def test_parse_start_list_count(parser):
    """Test parsing start list and counting entries"""
    html = load_test_file("SWE_51338_start_list.html")
    start_list = parser.parse_list_count(html)
    
    assert isinstance(start_list, dict)
    assert start_list["total_count"] > 0, f"Expected >0 entries in start list, got {start_list['total_count']}"

def test_parse_entries_list_count(parser):
    """Test parsing entries list and counting entries"""
    html = load_test_file("SWE_51338_entries.html")
    entry_list = parser.parse_list_count(html)
    
    assert isinstance(entry_list, dict)
    assert entry_list["total_count"] > 0, f"Expected >0 entries in entries list, got {entry_list['total_count']}"


def test_list_url_extraction(parser):
    """Test extraction of list URLs from event page and assignment to races"""
    # Use a known event that has lists
    # SWE_51338_main.html should have links to lists
    html = load_test_file("SWE_51338_main.html")
    event = Event(event_id="SWE-51338", name="Test", start_date="2025-08-30", 
                  end_date="2025-08-30", organizers=["Org"], country="SWE", 
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Check that at least one race has list URLs
    # Note: Not all events have all lists, but result list is most common
    has_list_url = any(
        race.entry_list_url or race.start_list_url or race.result_list_url
        for race in parsed_event.races
    )
    assert has_list_url, "Expected at least one race to have list URLs"

def test_parse_livelox_links(parser):
    """Test extraction of Livelox links from event main page"""
    html = load_test_file("SWE_51338_main.html")
    
    # Create a dummy event with one race to test assignment
    event = Event(event_id="SWE-51338", name="Test", start_date="2025-08-30", 
                  end_date="2025-08-30", organizers=["Org"], country="SWE", 
                  status="Active", url="")
    # Add a race
    race = Race(race_id="1", name="Race 1", date="2025-08-30", time="", distance="")
    event.races.append(race)
    
    # Parse details
    parsed_event = parser.parse_event_details(html, event)
    
    # Check if Livelox links were assigned to the race
    assert len(parsed_event.races[0].livelox_links) > 0, "Expected Livelox links in race"
    
    first_link = parsed_event.races[0].livelox_links[0]
    assert "name" in first_link
    assert "url" in first_link
    assert "Livelox" in first_link["name"] or "Livelox" in first_link["url"]
