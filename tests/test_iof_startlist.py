from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models import Event
from src.sources.eventor_source import EventorSource


@pytest.fixture
def iof_7490_main_html(test_data_dir: Path) -> str:
    return (test_data_dir / "IOF_7490_main.html").read_text(encoding="utf-8")


@pytest.fixture
def iof_7490_race2_main_html(test_data_dir: Path) -> str:
    return (test_data_dir / "IOF_7490_race2_main.html").read_text(encoding="utf-8")


@pytest.fixture
def iof_7490_race2_start_list_html(test_data_dir: Path) -> str:
    return (test_data_dir / "IOF_7490_race2_start_list.html").read_text(
        encoding="utf-8"
    )


def test_iof_startlist_download(
    iof_7490_main_html: str,
    iof_7490_race2_main_html: str,
    iof_7490_race2_start_list_html: str,
    temp_event_data_dir: Path,
) -> None:
    """Test IOF International events classification and download logic."""
    # Setup - use temp_event_data_dir fixture from conftest.py
    source = EventorSource(
        "IOF", "https://eventor.orienteering.org", output_dir=str(temp_event_data_dir)
    )

    # Mock Scraper
    mock_scraper = MagicMock()
    source.scraper = mock_scraper

    # Define side effect for get
    def get_side_effect(url: str, params: dict | None = None) -> MagicMock | None:
        print(f"Mock GET called with: {url}")
        mock_resp = MagicMock()
        if "events/show/7490" in url.lower():
            mock_resp.text = iof_7490_main_html
            return mock_resp
        elif "startlist" in url.lower():
            mock_resp.text = iof_7490_race2_start_list_html
            return mock_resp
        # For IOF International, we should NOT fetch entry/result lists
        elif "entrylist" in url.lower() or "resultlist" in url.lower():
            pytest.fail(
                f"Should not fetch entry/result lists for IOF International: {url}"
            )
        return None

    mock_scraper.get.side_effect = get_side_effect

    # Create Event object (mimic what fetch_event_list would produce)
    event = Event(
        id="IOF_7490",
        name="CX80 World MTB Orienteering Championships 2025",
        start_time="2025-08-11",
        end_time="2025-08-17",
        status="Sanctioned",
        original_status="Active",
        url="/Events/Show/7490",
        types=["Test event"],
        races=[],
    )

    # Fetch event details
    updated_event = source.fetch_event_details(event)

    assert updated_event is not None
    assert len(updated_event.races) > 0

    # Verify types were extracted (contains "World Championships")
    assert "World Championships" in updated_event.types

    # Verify download logic
    assert source._should_download_start_list(updated_event) is True
    assert source._should_fetch_counts(updated_event) is False

    print("✅ IOF event classified as International")
    print(
        f"✅ Startlist download enabled: "
        f"{source._should_download_start_list(updated_event)}"
    )
    print(
        f"✅ Count fetching disabled: {not source._should_fetch_counts(updated_event)}"
    )
