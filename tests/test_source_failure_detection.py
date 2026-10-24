"""Tests for detecting and reporting source extraction failures."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.main import main
from src.scraper import Scraper
from src.sources.base_source import EventListFetchError
from src.sources.eventor_source import EventorSource


def test_eventor_source_raises_event_list_fetch_error() -> None:
    """EventorSource.fetch_event_list should raise EventListFetchError on failure."""
    mock_scraper = MagicMock(spec=Scraper)
    mock_scraper.get.return_value = None

    source = EventorSource(
        country="SWE",
        base_url="https://eventor.orientering.se",
        scraper=mock_scraper,
    )

    with pytest.raises(EventListFetchError) as exc_info:
        source.fetch_event_list("2026-05-01", "2026-05-31")

    assert "Failed to fetch event list for SWE" in str(exc_info.value)
    assert exc_info.value.country == "SWE"


def test_eventor_source_raises_on_empty_response_body() -> None:
    """EventorSource.fetch_event_list should raise if response body is empty."""
    mock_scraper = MagicMock(spec=Scraper)
    mock_response = MagicMock()
    mock_response.text = "   "
    mock_scraper.get.return_value = mock_response

    source = EventorSource(
        country="SWE",
        base_url="https://eventor.orientering.se",
        scraper=mock_scraper,
    )

    with pytest.raises(EventListFetchError) as exc_info:
        source.fetch_event_list("2026-05-01", "2026-05-31")

    assert "Failed to fetch event list for SWE" in str(exc_info.value)


def test_eventor_parser_raises_on_unrecognized_page_structure() -> None:
    """EventorParser.parse_event_list should raise if eventList container missing."""
    from src.sources.eventor_parser import EventorParser

    parser = EventorParser()
    challenge_html = (
        "<html><head><title>Just a moment...</title></head>"
        "<body><div>Checking your browser</div></body></html>"
    )

    with pytest.raises(EventListFetchError) as exc_info:
        parser.parse_event_list(challenge_html, "SWE")

    assert "Invalid or unrecognized event list page structure" in str(exc_info.value)
    assert exc_info.value.country == "SWE"


def test_eventor_parser_returns_empty_list_for_recognized_empty_page() -> None:
    """EventorParser.parse_event_list returns [] when eventList container is present."""
    from src.sources.eventor_parser import EventorParser

    parser = EventorParser()
    empty_html = (
        "<html><body><div id='eventList'>"
        "<table><tbody></tbody></table>"
        "</div></body></html>"
    )

    events = parser.parse_event_list(empty_html, "SWE")
    assert events == []


@patch("src.main.split_range_by_year")
@patch("src.main.irregular_chunk_date_range")
@patch("src.sources.eventor_source.EventorSource.fetch_event_list")
@patch("src.storage.Storage.load")
@patch("src.storage.Storage.save")
def test_main_cli_exits_nonzero_on_source_failure(
    mock_save: MagicMock,
    mock_load: MagicMock,
    mock_fetch_list: MagicMock,
    mock_chunks: MagicMock,
    mock_split: MagicMock,
    tmp_path: Path,
) -> None:
    """main() must terminate with exit code 2 when any source event listing fails."""
    mock_load.return_value = {}
    mock_save.return_value = []
    mock_split.return_value = [("2026-05-01", "2026-05-07")]
    mock_chunks.return_value = [("2026-05-01", "2026-05-07")]
    mock_fetch_list.side_effect = EventListFetchError(
        "Cloudflare blocked", country="SWE"
    )

    commit_msg_file = tmp_path / ".commit_msg"
    commit_msg_file.write_text("Old commit msg")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-07",
            "--source",
            "SWE",
            "--commit-msg-file",
            str(commit_msg_file),
            "--fetch-listing",
            "--no-shuffle",
        ],
    )

    assert result.exit_code == 2
    assert not commit_msg_file.exists()
    mock_save.assert_not_called()


@patch("src.main.split_range_by_year")
@patch("src.main.irregular_chunk_date_range")
@patch("src.sources.eventor_source.EventorSource.fetch_event_list")
@patch("src.storage.Storage.load")
@patch("src.storage.Storage.save")
def test_main_cli_allows_partial_with_flag(
    mock_save: MagicMock,
    mock_load: MagicMock,
    mock_fetch_list: MagicMock,
    mock_chunks: MagicMock,
    mock_split: MagicMock,
    tmp_path: Path,
) -> None:
    """main() should complete when --allow-partial is explicitly passed."""
    mock_load.return_value = {}
    mock_save.return_value = []
    mock_split.return_value = [("2026-05-01", "2026-05-07")]
    mock_chunks.return_value = [("2026-05-01", "2026-05-07")]
    mock_fetch_list.side_effect = EventListFetchError(
        "Cloudflare blocked", country="SWE"
    )

    commit_msg_file = tmp_path / ".commit_msg"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-07",
            "--source",
            "SWE",
            "--commit-msg-file",
            str(commit_msg_file),
            "--fetch-listing",
            "--allow-partial",
            "--no-shuffle",
        ],
    )

    assert result.exit_code == 0
