from pathlib import Path

from src.models import Event, Organiser
from src.sources.eventor_parser import EventorParser


def test_parse_event_details_handles_date_range(test_data_dir: Path) -> None:
    """
    Test that the parser correctly handles a date range in the 'Date' field.

    Using existing test data: SWE_46200_main.html which has:
    "Monday 21 July 2025 - Saturday 26 July 2025"
    """
    parser = EventorParser()

    # Initialize event
    event = Event(
        id="SWE_46200",
        name="O-Ringen Jönköping, MTBO",
        start_time="2025-07-21",  # Initial
        end_time="2025-07-21",  # Initial
        organisers=[Organiser(name="TestOrg")],
        status="Applied",
        original_status="Applied",
        races=[],
    )

    # Load the specific test file
    html_file = test_data_dir / "SWE_46200_main.html"
    html_content = html_file.read_text(encoding="utf-8")

    # Parse proper details
    parser.parse_event_details(html_content, event)

    # Verify both start and end dates are updated correctly from the range
    # Expected: Start = 2025-07-21, End = 2025-07-26
    assert event.start_time == "2025-07-21", (
        f"Expected start 2025-07-21, got {event.start_time}"
    )
    assert event.end_time == "2025-07-26", (
        f"Expected end 2025-07-26, got {event.end_time}"
    )
