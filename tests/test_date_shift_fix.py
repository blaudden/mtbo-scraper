from pathlib import Path

from src.models import Event, Organiser, Race
from src.sources.eventor_parser import EventorParser
from src.utils.date_and_time import format_iso_datetime


def test_utc_to_local_conversion() -> None:
    """Tests that format_iso_datetime converts UTC 'data-date' format correctly."""
    # Scenario: Saturday 2025-08-30 00:00:00 (Local) is 2025-08-29 22:00:00 (UTC)
    utc_date_str = "2025-08-29 22:00:00"
    # Stockholm is UTC+2 in August (DST)
    local_iso = format_iso_datetime(utc_date_str, None, "SWE")
    assert local_iso == "2025-08-30T00:00:00+02:00"


def test_utc_to_local_conversion_afternoon() -> None:
    """Tests that format_iso_datetime converts UTC 'data-date' for afternoon events."""
    # Scenario: Saturday 2025-05-24 15:00:00 (Local) is 2025-05-24 13:00:00 (UTC)
    utc_date_str = "2025-05-24 13:00:00"
    # Stockholm is UTC+2 in May (DST)
    local_iso = format_iso_datetime(utc_date_str, None, "SWE")
    assert local_iso == "2025-05-24T15:00:00+02:00"


def test_parser_updates_polluted_race_date(test_data_dir: Path) -> None:
    """
    Test that the parser updates a race date if it was incorrectly set
    (e.g. from UTC naive split) but the details page has a correct textual date.
    """
    parser = EventorParser()

    event = Event(
        id="SWE_51338",
        name="Test",
        start_time="2025-08-29",
        end_time="2025-08-29",
        status="Sanctioned",
        original_status="Active",
        organisers=[Organiser(name="OK Skogsfalken", country_code="SWE")],
        races=[
            Race(
                race_number=1,
                name="Race 1",
                datetimez="2025-08-29T00:00:00+02:00",
                discipline="MTBO",
            )
        ],
    )

    html_content = (test_data_dir / "SWE_51338_main.html").read_text(encoding="utf-8")

    parser.parse_event_details(html_content, event)

    assert event.start_time == "2025-08-30"
    assert event.end_time == "2025-08-30"
    assert event.races[0].datetimez.startswith("2025-08-30")
