import os
from unittest.mock import MagicMock

import pytest

from src.models import Event, Race
from src.sources.eventor_source import EventorSource


def load_test_file(filename: str) -> str:
    """Loads a test file from the tests/data directory."""
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def source() -> EventorSource:
    """Creates an EventorSource instance with a mocked scraper."""
    src = EventorSource(country="IOF", base_url="https://eventor.orienteering.org")
    src.scraper = MagicMock()
    return src


@pytest.mark.parametrize(
    "filename, event_id, expected_start, expected_end, setup_races, "
    "expected_race_dates",
    [
        (
            "SWE_54361_single.html",
            "SWE_54361",
            "2026-05-10",
            "2026-05-10",
            True,  # Setup a stub race because parser updates existing one for singles
            # SWE_54361 is a single race event.
            # Verification showed the stub race now gets backfilled with the event date.
            ["2026-05-10"],
        ),
        (
            "SWE_50597_multi.html",
            "SWE_50597",
            "2026-07-20",
            "2026-07-25",
            False,  # Parser creates races from table
            [
                "2026-07-20",
                "2026-07-21",
                "2026-07-23",
                "2026-07-24",
                "2026-07-25",
            ],
        ),
        (
            "IOF_8558_single.html",
            "IOF_8558",
            "2026-05-22",
            "2026-05-28",
            True,
            ["2026-05-22"],  # Similar to SWE_54361, backfilled from start date
        ),
        (
            "IOF_8277_multi.html",
            "IOF_8277",
            "2026-08-25",
            "2026-08-30",
            False,
            ["2026-08-26", "2026-08-27", "2026-08-29", "2026-08-30"],
        ),
    ],
)
def test_source_date_logic_scenarios(
    source: EventorSource,
    filename: str,
    event_id: str,
    expected_start: str,
    expected_end: str,
    setup_races: bool,
    expected_race_dates: list[str],
) -> None:
    """
    Verifies that EventorSource correctly fetches event details and:
    1. Preserves the event start/end dates parsed from metadata (no overwriting).
    2. Correctly includes ALL expected races with their dates.
    """

    # Load Real HTML
    html_content = load_test_file(filename)

    # Mock Response
    mock_response = MagicMock()
    mock_response.text = html_content
    source.scraper.get.return_value = mock_response  # type: ignore[attr-defined]

    # Adjust base URL
    if "SWE" in event_id:
        source.base_url = "https://eventor.orientering.se"

    # Initial Event Stub
    races = []
    if setup_races:
        # Create a stub race with EMPTY date to see if parser fills it (or leaves it)
        races = [Race(race_number=1, name="Stub", datetimez="", discipline="MTBO")]

    event = Event(
        id=event_id,
        name="Test Stub",
        start_time="",
        end_time="",
        status="Active",
        original_status="Active",
        races=races,
        url=f"/Events/Show/{event_id.split('_')[1]}",
    )

    # Execution
    result_event = source.fetch_event_details(event)

    # Assertions
    assert result_event is not None

    # 1. Check Event Dates
    assert result_event.start_time == expected_start, (
        f"Start time mismatch for {event_id}"
    )
    assert result_event.end_time == expected_end, f"End time mismatch for {event_id}"

    # 2. Check Races Dates
    # Extract dates (YYYY-MM-DD) from result races
    # If datetimez is empty, keep it empty string
    actual_race_dates = []
    for r in result_event.races:
        if r.datetimez:
            actual_race_dates.append(r.datetimez.split("T")[0])
        else:
            actual_race_dates.append("")

    # Allow partial match if stub race names differ, but here we expect full dates list
    # For generated races (Multi), order typically follows table order.
    # We compare sorted lists or exact lists? Table order is usually chronological.
    # Let's try exact list match first.

    # Filter out stubs if parser ADDS races instead of replacing?
    # Logic: Parser typically appends or replaces.
    # For SWE_50597, we passed empty races, so it appended.
    # For SWE_54361, we passed 1 race, it updated it (or didn't).

    # Note: If parser appends to existing list, and we provided none,
    # we get parsed ones. If we provided one, and it didn't find any table,
    # we get our one back.

    assert len(result_event.races) >= 1, f"Event {event_id} has no races"

    assert len(actual_race_dates) == len(expected_race_dates), (
        f"Race count mismatch for {event_id}. "
        f"Got {len(actual_race_dates)} races: {actual_race_dates}"
    )

    assert actual_race_dates == expected_race_dates, (
        f"Race dates mismatch for {event_id}.\nExpected: {expected_race_dates}\n"
        f"Actual:   {actual_race_dates}"
    )


def test_preliminary_date_range_derivation() -> None:
    """Verifies that 'Date is preliminary' in IOF Date attribute is detected,
    flagged on event, and stripped so date range is parsed cleanly."""
    from src.sources.eventor_parser import EventorParser

    parser = EventorParser()

    # Scenario 1: Multi-day range with preliminary note (like IOF 8559)
    event1 = Event(
        id="IOF_8559",
        name="CX80 World MTB Orienteering Championships 2027",
        start_time="2027-06-09",
        end_time="2027-06-09",
        status="Sanctioned",
        original_status="Active",
        races=[
            Race(
                race_number=1,
                name="CX80 World MTB Orienteering Championships 2027",
                datetimez="2027-06-09T21:00:00+00:00",
                discipline="Other",
            )
        ],
    )
    attributes1 = {"Date": "10 June 2027 - 16 June 2027 (Date is preliminary)"}
    parser._derive_event_dates(event1, attributes1, venue_country="LVA")

    assert event1.is_date_preliminary is True
    assert event1.start_time == "2027-06-10"
    assert event1.end_time == "2027-06-16"
    assert event1.races[0].datetimez == "2027-06-10T00:00:00+03:00"

    # Scenario 2: Single date with preliminary note
    event2 = Event(
        id="IOF_9999",
        name="Preliminary Single Day",
        start_time="",
        end_time="",
        status="Planned",
        original_status="Planned",
        races=[
            Race(
                race_number=1,
                name="Race 1",
                datetimez="",
                discipline="MTBO",
            )
        ],
    )
    attributes2 = {"Date": "15 July 2027 (Date is preliminary)"}
    parser._derive_event_dates(event2, attributes2, venue_country="SWE")

    assert event2.is_date_preliminary is True
    assert event2.start_time == "2027-07-15"
    assert event2.end_time == "2027-07-15"
    assert event2.races[0].datetimez == "2027-07-15T00:00:00+02:00"

    # Scenario 3: Standard range without preliminary note
    event3 = Event(
        id="IOF_1234",
        name="Normal Range",
        start_time="",
        end_time="",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )
    attributes3 = {"Date": "10 June 2027 - 16 June 2027"}
    parser._derive_event_dates(event3, attributes3, venue_country="LVA")

    assert event3.is_date_preliminary is False
    assert event3.start_time == "2027-06-10"
    assert event3.end_time == "2027-06-16"
