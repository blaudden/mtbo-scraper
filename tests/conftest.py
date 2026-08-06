"""Shared pytest fixtures for MTBO scraper tests."""

from pathlib import Path
from typing import Any

import pytest

from src.models import CupStandings
from src.sources.eventor_parser import EventorParser


@pytest.fixture
def test_data_dir() -> Path:
    """Returns the path to the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_event_html(test_data_dir: Path) -> Any:
    """Loads sample event list HTML for testing."""
    html_file = test_data_dir / "SWE_2024-01-01_2024-12-31_event_list.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return None


@pytest.fixture
def temp_json_file(tmp_path: Path) -> Path:
    """Provides a temporary JSON file path for testing storage."""
    return tmp_path / "test_events.json"


@pytest.fixture
def temp_event_data_dir(tmp_path: Path) -> Path:
    """Provides a temporary directory structure for testing event data storage."""
    data_dir = tmp_path / "data" / "events"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="module")
def cup_2026() -> CupStandings:
    """Parses Svenska cupen MTBO 2026 standings from test fixture."""
    parser = EventorParser()
    data_dir = Path(__file__).parent / "data"
    with open(data_dir / "series_1539.html", encoding="utf-8") as f:
        return parser.parse_series_standings(
            f.read(),
            "https://eventor.orientering.se/Standings/View/Series/1539",
        )


@pytest.fixture(scope="module")
def cup_2025() -> CupStandings:
    """Parses Svenska Cupen MTBO 2025 standings from test fixture."""
    parser = EventorParser()
    data_dir = Path(__file__).parent / "data"
    with open(data_dir / "series_1418.html", encoding="utf-8") as f:
        return parser.parse_series_standings(
            f.read(),
            "https://eventor.orientering.se/Standings/View/Series/1418",
        )
