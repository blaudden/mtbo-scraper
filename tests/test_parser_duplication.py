from src.models import Event, Official, Url
from src.sources.eventor_parser import EventorParser


def test_duplication_on_rescrape() -> None:
    """Verify that parsing details into an existing event doesn't duplicate data."""
    parser = EventorParser()

    # 1. Setup an event that ALREADY has officials and URLs (simulating load from disk)
    event = Event(
        id="SWE_123",
        name="Test Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Planned",
        original_status="Applied",
        races=[],
        # Existing data
        officials=[Official(role="Event Director", name="John Doe")],
        urls=[Url(type="Website", url="http://example.com")],
        documents=[],
    )

    # 2. Mock HTML that contains the SAME data
    html = """
    <html>
    <body>
        <div id="content">
            <table>
                <caption>Contact information</caption>
                <tr>
                    <th>Event Director</th>
                    <td>John Doe</td>
                </tr>
                <tr>
                    <th>Website</th>
                    <td><a href="http://example.com">Link</a></td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """

    # 3. Parse details
    parser.parse_event_details(html, event, base_url="https://eventor.orientering.se")

    # 4. Assert NO duplication
    # Fails if logic just appends
    assert len(event.officials) == 1
    assert event.officials[0].name == "John Doe"

    assert len(event.urls) == 1
    assert event.urls[0].url == "http://example.com"
