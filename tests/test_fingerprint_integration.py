from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from src.models import Event
from src.sources.eventor_source import EventorSource


@pytest.fixture
def swe_46200_html(test_data_dir: Path) -> str:
    return (test_data_dir / "SWE_46200_main.html").read_text(encoding="utf-8")


@pytest.fixture
def swe_46200_start_list_html(test_data_dir: Path) -> str:
    # Use race1 start list as representative
    return (test_data_dir / "SWE_46200_race1_start_list.html").read_text(
        encoding="utf-8"
    )


def test_fingerprint_and_yaml_saving(
    swe_46200_html: str, swe_46200_start_list_html: str, tmp_path: Path
) -> None:
    # Setup - use tmp_path for output instead of real data directory
    source = EventorSource(
        "SWE",
        "https://eventor.orientering.se",
        output_dir=str(tmp_path / "data" / "events"),
    )

    # Mock Scraper
    mock_scraper = MagicMock()
    source.scraper = mock_scraper

    # Define side effect for get
    def get_side_effect(url: str, params: dict | None = None) -> MagicMock | None:
        print(f"Mock GET called with: {url}")
        mock_resp = MagicMock()
        if "events/show/46200" in url.lower():
            mock_resp.text = swe_46200_html
            return mock_resp
        elif "startlist" in url.lower():
            mock_resp.text = swe_46200_start_list_html
            return mock_resp
        return None

    mock_scraper.get.side_effect = get_side_effect

    # Create Event object (mimic what fetch_event_list would produce)
    event = Event(
        id="SWE_46200",
        name="O-Ringen Jönköping, MTBO",
        start_time="2025-07-21",
        end_time="2025-07-26",
        status="Planned",
        original_status="Planned",
        url="/Events/Show/46200",
        types=["Test event"],
        races=[],
    )

    # I will verify the fingerprints first.
    updated_event = source.fetch_event_details(event)

    assert updated_event is not None
    assert len(updated_event.races) > 0

    race1 = updated_event.races[0]

    # Check fingerprints
    # SWE_46200_race1_start_list.html has Anke Dannowski
    assert race1.fingerprints is not None
    assert len(race1.fingerprints) > 0
    print(f"Fingerprints found: {len(race1.fingerprints)}")

    # Verify YAML creation in tmp_path (not real data directory)
    test_output_dir = tmp_path / "data" / "events" / "2025"
    yaml_files_created = list(test_output_dir.glob("SWE_46200_startlist_*.yaml"))

    if yaml_files_created:
        print(f"YAML files created successfully: {len(yaml_files_created)}")
        # Check first one
        content = yaml.safe_load(yaml_files_created[0].read_text(encoding="utf-8"))
        assert "race_number" in content
        assert "participants" in content
        assert len(content["participants"]) > 0

        # Files are in tmp_path, so they'll be auto-cleaned by pytest
    else:
        pytest.fail("No YAML files matching SWE_46200_startlist_*.yaml were created.")
