import os

import pytest

from src.models import Event, Organiser
from src.sources.eventor_parser import EventorParser


def load_test_file(filename: str) -> str:
    """Loads a test file."""
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def parser() -> EventorParser:
    return EventorParser()


def test_parse_swe_46200_race_urls(parser: EventorParser) -> None:
    """Test SWE-46200: Verify start_list_url and result_list_url are populated
    for each race"""
    html = load_test_file("SWE_46200_main.html")
    event = Event(
        id="SWE-46200",
        name="O-Ringen Jönköping, MTBO",
        start_time="2025-07-21",
        end_time="2025-07-26",
        status="Active",
        original_status="Active",
        organisers=[Organiser(name="Svensk Orientering Events", country_code="SWE")],
        races=[],
    )

    parsed_event = parser.parse_event_details(html, event)

    # Should have 5 races
    assert len(parsed_event.races) == 5, (
        f"Expected 5 races, got {len(parsed_event.races)}"
    )

    # Expected race IDs based on the HTML
    expected_race_ids = ["47850", "47851", "47852", "47853", "47854"]
    expected_race_names = ["Etapp 1", "Etapp 2", "Etapp 3", "Etapp 4", "Etapp 5"]

    for i, race in enumerate(parsed_event.races):
        # Verify race name
        assert race.name == expected_race_names[i], (
            f"Race {i + 1} name mismatch: expected '{expected_race_names[i]}', "
            f"got '{race.name}'"
        )

        # Verify race ID is set
        assert race._internal_eventor_id == expected_race_ids[i], (
            f"Race {i + 1} race_id mismatch: expected '{expected_race_ids[i]}', "
            f"got '{race._internal_eventor_id}'"
        )

        # Verify start_list_url is populated in race.urls
        start_urls = [u.url for u in race.urls if u.type == "StartList"]
        assert len(start_urls) > 0, (
            f"Race {i + 1} ({race.name}) should have StartList URL in .urls"
        )
        assert f"eventRaceId={expected_race_ids[i]}" in start_urls[0], (
            f"Race {i + 1} start_list_url should contain "
            f"eventRaceId={expected_race_ids[i]}"
        )

        # Verify result_list_url is populated in race.urls
        result_urls = [u.url for u in race.urls if u.type == "ResultList"]
        assert len(result_urls) > 0, (
            f"Race {i + 1} ({race.name}) should have ResultList URL in .urls"
        )
        assert f"eventRaceId={expected_race_ids[i]}" in result_urls[0], (
            f"Race {i + 1} result_list_url should contain "
            f"eventRaceId={expected_race_ids[i]}"
        )
