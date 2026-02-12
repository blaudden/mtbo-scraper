from pathlib import Path

from src.models import Event, Organiser
from src.sources.eventor_parser import EventorParser


def test_parse_event_details_updates_date(test_data_dir: Path) -> None:
    """
    Test that the parser updates the event start/end time from the 'Date' field
    in the event details page.

    Using existing test data: SWE_54361_single.html which has "Sunday 10 May 2026".
    """
    parser = EventorParser()

    # Initialize event with incorrect date (simulating list view data)
    event = Event(
        id="SWE_54361",
        name="Test Event",
        start_time="2026-05-09",  # Incorrect date (e.g. from listing)
        end_time="2026-05-09",  # Incorrect date
        organisers=[Organiser(name="TestOrg")],
        status="Applied",
        original_status="Applied",
        races=[],
    )

    # Load the specific test file
    html_file = test_data_dir / "SWE_54361_single.html"
    html_content = html_file.read_text(encoding="utf-8")

    # Parse proper details
    parser.parse_event_details(html_content, event)

    # Verify date is updated to 2026-05-10
    assert event.start_time == "2026-05-10", (
        f"Expected 2026-05-10, but stuck with {event.start_time}"
    )
    assert event.end_time == "2026-05-10", (
        f"Expected 2026-05-10, but stuck with {event.end_time}"
    )
