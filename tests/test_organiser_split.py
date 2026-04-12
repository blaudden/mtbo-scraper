import pytest

from src.models import Event, Race
from src.sources.eventor_parser import EventorParser
from src.utils.date_and_time import format_iso_datetime


@pytest.fixture
def parser() -> EventorParser:
    return EventorParser()


def create_base_event(id: str, name: str, date: str, country: str = "IOF") -> Event:
    iso_race_dt = format_iso_datetime(date, None, country)
    return Event(
        id=id,
        name=name,
        start_time=date,
        end_time=date,
        status="Sanctioned",
        original_status="Active",
        races=[
            Race(race_number=1, name=name, datetimez=iso_race_dt, discipline="Other")
        ],
        organisers=[],
    )


def test_iof_organiser_multiple_clubs_split(parser: EventorParser) -> None:
    """Test that multiple clubs in the IOF Organising club field are split."""
    html = """
    <table>
        <caption>General information</caption>
        <tr><th>Organising federation</th><td>Hungary</td></tr>
        <tr><th>Organising club</th><td>Balatonfuredi Sport Club\nHangya SZKE</td></tr>
        <tr><th>Date</th><td>2026-03-20</td></tr>
    </table>
    """
    event = create_base_event("IOF_12345", "Test IOF Event", "2026-03-20")

    # We call parse_event_details but focus on organizer extraction
    updated_event = parser.parse_event_details(html, event)

    organisers = updated_event.organisers
    organiser_names = [o.name for o in organisers]

    # Expected: ["Hungary", "Balatonfuredi Sport Club", "Hangya SZKE"]
    # Current behavior should result in successful split

    assert "Hungary" in organiser_names
    assert "Balatonfuredi Sport Club" in organiser_names
    assert "Hangya SZKE" in organiser_names
    assert len(organisers) == 3


def test_event_list_organiser_split(parser: EventorParser) -> None:
    """Test that organizers in the event list table are split on newline."""
    html = """
    <div id="eventList">
        <table>
            <tbody>
                <tr>
                    <td><span data-date="2026-03-20T10:00:00Z">2026-03-20</span></td>
                    <td><a href="/Events/Show/12345">Test Event</a></td>
                    <td>Balatonfuredi Sport Club<br>Hangya SZKE</td>
                    <td>Active</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    events = parser.parse_event_list(html, "HUN", base_url="https://eventor.org")

    assert len(events) == 1
    event = events[0]
    organiser_names = [o.name for o in event.organisers]

    assert "Balatonfuredi Sport Club" in organiser_names
    assert "Hangya SZKE" in organiser_names
    assert len(event.organisers) == 2
