"""Tests for Scraper retry logic, resource handling, and Cloudflare bypass."""

from unittest.mock import ANY, MagicMock, patch

import pytest
from curl_cffi.requests import RequestsError, Response

from src.scraper import Scraper


@pytest.fixture()
def scraper() -> Scraper:
    """Create a Scraper instance with zero delay for fast tests."""
    return Scraper(delay_range=(0, 0))


@patch("curl_cffi.requests.Session.get")
def test_retry_on_503(mock_get: MagicMock, scraper: Scraper) -> None:
    """Test that the scraper retries on 503 errors."""
    # Mock a 503 Service Unavailable, then a 200 success
    err_resp = MagicMock(spec=Response)
    err_resp.status_code = 503

    mock_error = RequestsError("Service Unavailable")
    mock_error.response = err_resp

    success_resp = MagicMock(spec=Response)
    success_resp.status_code = 200
    success_resp.text = "Success"
    success_resp.headers = {}

    mock_get.side_effect = [mock_error, success_resp]

    resp = scraper.get("http://example.com", retries=2)

    assert resp is not None
    assert resp.status_code == 200
    assert mock_get.call_count == 2


@patch("curl_cffi.requests.Session.get")
def test_no_retry_on_404(mock_get: MagicMock, scraper: Scraper) -> None:
    """Test that the scraper does not retry on 404 errors."""
    # Mock a 404 Not Found — non-retryable status
    err_resp = MagicMock(spec=Response)
    err_resp.status_code = 404

    mock_error = RequestsError("Not Found")
    mock_error.response = err_resp

    mock_get.side_effect = [mock_error]

    resp = scraper.get("http://example.com", retries=3)

    assert resp is None
    assert mock_get.call_count == 1


@patch("src.scraper.logger")
@patch("curl_cffi.requests.Session.get")
def test_too_many_open_files_handling(
    mock_get: MagicMock, mock_logger: MagicMock, scraper: Scraper
) -> None:
    """Test handling of 'Too many open files' error."""
    # Mock errno 24 — system file descriptor limit exceeded
    mock_error = RequestsError("Too many open files")
    mock_get.side_effect = mock_error

    resp = scraper.get("http://example.com")
    assert resp is None

    # Verify structured error log with resource_limit_reached event
    mock_logger.error.assert_any_call(
        "resource_limit_reached",
        error="Too many open files (errno 24)",
        suggestion=ANY,
    )


@patch("src.scraper.Scraper._obtain_browser_cookies")
@patch("curl_cffi.requests.Session.get")
def test_cloudflare_bypass_refresh(
    mock_get: MagicMock, mock_obtain: MagicMock, scraper: Scraper
) -> None:
    """Test that Cloudflare bypass is triggered on challenge."""
    # Mock a Cloudflare 403 managed challenge response
    challenge_resp = MagicMock(spec=Response)
    challenge_resp.status_code = 403
    challenge_resp.headers = {"Server": "cloudflare"}
    challenge_resp.text = "Just a moment"

    # After bypass, the retry succeeds with 200
    success_resp = MagicMock(spec=Response)
    success_resp.status_code = 200

    mock_get.side_effect = [challenge_resp, success_resp]
    mock_obtain.return_value = True

    resp = scraper.get("http://cloudflare-protected.com")

    assert resp is not None
    assert mock_obtain.call_count == 1
    assert mock_get.call_count == 2
