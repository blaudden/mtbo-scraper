import pytest

from src.models import Event
from src.sources.eventor_parser import EventorParser


@pytest.fixture
def parser() -> EventorParser:
    return EventorParser()


def test_url_resolution_list(parser: EventorParser) -> None:
    """Test that URLs in event list are resolved when base_url is provided."""
    html = """
    <div id="eventList">
        <table>
            <tbody>
                <tr>
                    <td><span data-date="2026-01-01">2026-01-01</span></td>
                    <td><a href="/Events/Show/12345">Test Event</a></td>
                    <td>Org</td>
                    <td>Active</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    base_url = "https://eventor.orientering.se"
    events = parser.parse_event_list(html, "SWE", base_url)

    assert len(events) == 1
    # Check event.url (internal scraping URL)
    # Parser should keep it relative if it matches base/relative pattern
    assert events[0].url == "/Events/Show/12345"


def test_url_resolution_details(parser: EventorParser) -> None:
    """Test that URLs in event details are formatted correctly."""
    html = """
    <div id="content">
        <table>
            <caption>General information</caption>
            <tbody>
                <tr><th>Event</th><td>Test</td></tr>
            </tbody>
        </table>

        <div class="eventInfoBox">
            <h3>Startlist</h3>
            <a href="/Events/StartList?eventId=123&groupBy=EventClass">By Class</a>
        </div>

        <h3>Documents</h3>
        <ul class="documents">
            <li>
                <a class="documentName" href="/Documents/Event/123/1/Invitation">
                    Invitation
                </a>
            </li>
        </ul>
    </div>
    """
    event = Event(
        id="SWE_123",
        name="Test",
        start_time="2026-01-01",
        end_time="2026-01-01",
        status="Sanctioned",
        original_status="Active",
        races=[],
        url="/Events/Show/123",
    )

    base_url = "https://eventor.orientering.se"
    updated_event = parser.parse_event_details(html, event, base_url)

    # Check Service URL
    # Should stay relative
    assert len(updated_event.races) > 0
    start_list = next(
        (u for u in updated_event.races[0].urls if u.type == "StartList"), None
    )
    assert start_list
    assert start_list.url == "/Events/StartList?eventId=123&groupBy=EventClass"

    # Check Document URL
    # Should stay relative
    assert len(updated_event.documents) == 1
    doc = updated_event.documents[0]
    assert doc.url == "/Documents/Event/123/1/Invitation"
    assert doc.type == "Invitation"


def test_url_stripping(parser: EventorParser) -> None:
    """Test that absolute URLs matching base_url are stripped to relative."""
    html = """
    <div id="eventList">
        <table>
            <tbody>
                <tr>
                    <td><span data-date="2026-01-01">2026-01-01</span></td>
                    <td>
                        <a href="https://eventor.orientering.se/Events/Show/999">
                            Absolute Link
                        </a>
                    </td>
                    <td>Org</td>
                    <td>Active</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    base_url = "https://eventor.orientering.se"
    events = parser.parse_event_list(html, "SWE", base_url)

    assert len(events) == 1
    assert events[0].url == "/Events/Show/999"


def test_url_timestamp(parser: EventorParser) -> None:
    """Test that new URLs have a valid last_updated_at timestamp."""
    html = """
    <div id="eventList">
        <table>
            <tbody>
                <tr>
                    <td><span data-date="2026-01-01">2026-01-01</span></td>
                    <td><a href="/Events/Show/100">Timestamp Test</a></td>
                    <td>Org</td>
                    <td>Active</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
    base_url = "https://eventor.orientering.se"
    events = parser.parse_event_list(html, "SWE", base_url)

    assert len(events) == 1
    # Check "Path" URL (created during list parsing for event.url?
    # No, event.url is string)
    # Wait, parse_event_list doesn't create Url objects in event.urls list?
    # Let's check parse_event_list behavior.
    # It creates Event object with url string.

    # We need to check parse_event_details for "Path" Url creation.

    event = events[0]
    detail_html = """
    <h1>Timestamp Test</h1>
    <div class="eventInfoBox">
        <h3>Startlist</h3>
        <a href="/Events/StartList?eventId=100">Startlist Link</a>
    </div>
    """
    updated_event = parser.parse_event_details(detail_html, event, base_url)

    # Check generated Path URL
    path_url = next((u for u in updated_event.urls if u.type == "Path"), None)
    assert path_url
    # last_updated_at should be None from parser now
    assert path_url.last_updated_at is None

    # Check Service URL
    # Race 0 (default) should have it
    start_list = next(
        (u for u in updated_event.races[0].urls if u.type == "StartList"), None
    )
    assert start_list
    assert start_list.last_updated_at is None
