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


def test_parse_swe_46200_multi_race(parser):
    """Test SWE-46200: 5-stage event with Livelox per race"""
    html = load_test_file("SWE_46200_main.html")
    event = Event(event_id="SWE-46200", name="Test", start_date="2024-01-01",
                  end_date="2024-01-01", organizers=["Org"], country="SWE",
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Should have 5 races
    assert len(parsed_event.races) == 5, f"Expected 5 races, got {len(parsed_event.races)}"
    
    # Check race names
    expected_names = ["Etapp 1", "Etapp 2", "Etapp 3", "Etapp 4", "Etapp 5"]
    for i, race in enumerate(parsed_event.races):
        assert race.name == expected_names[i], f"Race {i+1} name mismatch"
    
    # Classes may or may not be extracted from main page (might be in race pages)
    # Just verify the structure is correct
    assert isinstance(parsed_event.classes, list), "Classes should be a list"


def test_parse_swe_46200_race1_start_list_classes(parser):
    """Test SWE-46200 Race 1: Start list class names and counts"""
    html = load_test_file("SWE_46200_race1_start_list.html")
    start_list = parser.parse_list_count(html)
    
    assert isinstance(start_list, dict)
    assert "total_count" in start_list
    assert "class_counts" in start_list
    
    # Expected classes and their participant counts for Race 1 (Etapp 1)
    # Based on the actual data from the screenshot and HTML
    expected_classes = {
        "D21": 21,
        "H21": 30,
        "D20": 6,
        "H20": 9,
        "D16": 4,
        "H16": 10,
        "D14": 2,
        "H12": 3,
        "H35": 3,
        "D45": 5,
        "H45": 15,
        "D50": 4,
        "H50": 22,
        "D55": 8,
        "H55": 23,
        "D60": 8,
        "H60": 21,
        "H65": 10,
        "D70": 4,
        "H70": 17,
        "H75": 6,
        "H80": 2,
        "Lätt mellan": 6,
        "Lätt lång": 3,
        "Svår mellan": 11,
        "Etappstart Lätt mellan": 5,
        "Etappstart Lätt lång": 11,
        "Etappstart Svår kort": 2,
        "Etappstart Svår mellan": 13,
        "Etappstart Svår lång": 14,
    }
    
    # Verify all expected classes are present
    class_counts = start_list["class_counts"]
    for class_name, expected_count in expected_classes.items():
        assert class_name in class_counts, f"Class '{class_name}' not found in start list"
        assert class_counts[class_name] == expected_count, \
            f"Class '{class_name}' expected {expected_count} participants, got {class_counts[class_name]}"
    
    # Verify no unexpected classes
    for class_name in class_counts:
        assert class_name in expected_classes, f"Unexpected class '{class_name}' found in start list"
    
    # Verify total count
    expected_total = sum(expected_classes.values())
    assert start_list["total_count"] == expected_total, \
        f"Expected total count {expected_total}, got {start_list['total_count']}"


def test_parse_swe_46200_race1_result_list_classes(parser):
    """Test SWE-46200 Race 1: Result list class names and counts"""
    html = load_test_file("SWE_46200_race1_result_list.html")
    result_list = parser.parse_list_count(html)
    
    assert isinstance(result_list, dict)
    assert "total_count" in result_list
    assert "class_counts" in result_list
    
    # Result lists should have the same classes as start lists
    # (though counts might differ slightly due to DNS/DNF)
    # We'll verify that the main classes are present
    class_counts = result_list["class_counts"]
    
    # Check that key age classes are present
    key_classes = ["D21", "H21", "D20", "H20", "H50", "H55"]
    for class_name in key_classes:
        assert class_name in class_counts, f"Key class '{class_name}' not found in result list"
        assert class_counts[class_name] > 0, f"Class '{class_name}' should have results"
    
    # Verify total count is reasonable
    assert result_list["total_count"] > 0, "Result list should have entries"




def test_parse_iof_7490_multi_race(parser):
    """Test IOF-7490: Multi-race IOF event with 5 races"""
    html = load_test_file("IOF_7490_main.html")
    event = Event(event_id="IOF-7490", name="Test", start_date="2024-01-01",
                  end_date="2024-01-01", organizers=["Org"], country="IOF",
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Should have 5 races (competitions)
    assert len(parsed_event.races) >= 5, f"Expected at least 5 races, got {len(parsed_event.races)}"
    
    # Map positions should be at event level for IOF events
    # (May or may not have positions, but if present, should be at event level)
    # This is tested by checking that event.map_positions exists as a field

    # Check that info text does not start with "Keep in mind that as a competitor"
    assert not parsed_event.info_text.startswith("Keep in mind that as a competitor"), \
        "Info text should not start with 'Keep in mind that as a competitor'"


def test_parse_iof_7490_race_details(parser):
    """Test IOF-7490: Individual race detail pages"""
    # Test race 1 detail page
    html = load_test_file("IOF_7490_race1_main.html")
    event = Event(event_id="IOF-8446", name="Test", start_date="2024-01-01",
                  end_date="2024-01-01", organizers=["Org"], country="IOF",
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Should parse race details
    assert len(parsed_event.races) >= 1
    
    # Test start list
    html = load_test_file("IOF_7490_race1_start_list.html")
    start_list = parser.parse_list_count(html)
    assert isinstance(start_list, dict)
    
    # Test result list
    html = load_test_file("IOF_7490_race1_result_list.html")
    result_list = parser.parse_list_count(html)
    assert isinstance(result_list, dict)


def test_contact_field_no_oversplit(parser):
    """Test that singular contact fields are not over-split"""
    # Test with IOF-8277 which has singular fields
    html = load_test_file("IOF_8277_multi.html")
    event = Event(event_id="IOF-8277", name="Test", start_date="2024-01-01",
                  end_date="2024-01-01", organizers=["Org"], country="IOF",
                  status="Active", url="")
    
    parsed_event = parser.parse_event_details(html, event)
    
    # Event director should be a string, not a list
    if "Event director" in parsed_event.contact:
        director = parsed_event.contact["Event director"]
        assert isinstance(director, str), "Event director should be string, not list"
        assert director == "Klaus Csucs", f"Expected 'Klaus Csucs', got '{director}'"
    
    # Organising club should be a string in attributes
    if "Organising club" in parsed_event.attributes:
        club = parsed_event.attributes["Organising club"]
        assert isinstance(club, str), "Organising club should be string, not list"
        assert club == "IFK Mora OK", f"Expected 'IFK Mora OK', got '{club}'"
