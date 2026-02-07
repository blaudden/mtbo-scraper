from pathlib import Path

from src.models import Event
from src.sources.eventor_parser import EventorParser


def test_series_extraction_swe_46200() -> None:
    # Load test data
    file_path = Path("tests/data/SWE_46200_main.html")
    with open(file_path, encoding="utf-8") as f:
        html_content = f.read()

    # Create dummy event object to hold results
    # ID matches filename convention
    event = Event(
        id="SWE_46200",
        name="Test",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Planned",
        original_status="Planned",
        types=["Test event"],
        races=[],
    )

    # Init parser and parse details
    parser = EventorParser()
    updated_event = parser.parse_event_details(html_content, event)

    # Debug print urls
    print("Found URLs:")
    for u in updated_event.urls:
        print(f"  {u.type}: {u.url}")

    # Check for Series link
    series_links = [u for u in updated_event.urls if u.type == "Series"]
    assert len(series_links) > 0, "No 'Series' type URL found"

    assert "/Standings/View/Series/1438" in series_links[0].url
    assert series_links[0].title == "Svenska VeteranCupen MTBO 2025"
    print("\nSUCCESS: Found Series URL.")


if __name__ == "__main__":
    test_series_extraction_swe_46200()
