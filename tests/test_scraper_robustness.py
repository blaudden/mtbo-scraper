"""Tests for Scraper retry logic, resource handling, and Cloudflare bypass."""

from pathlib import Path
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest
from curl_cffi.requests import RequestsError, Response

from src.scraper import CachedResponse, Scraper


@pytest.fixture()
def scraper(tmp_path: Path) -> Scraper:
    """Create a Scraper with zero delay and isolated cookie file for tests."""
    cookie_path = tmp_path / "test_cookies.json"
    return Scraper(delay_range=(0, 0), cookie_file=str(cookie_path))


@patch("curl_cffi.requests.Session.get")
def test_retry_on_503(mock_get: MagicMock, scraper: Scraper) -> None:
    """Test that the scraper retries on 503 errors."""
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
    mock_error = RequestsError("Too many open files")
    mock_get.side_effect = mock_error

    resp = scraper.get("http://example.com")
    assert resp is None

    mock_logger.error.assert_any_call(
        "resource_limit_reached",
        error="Too many open files (errno 24)",
        suggestion=ANY,
    )


@patch("src.scraper.Scraper._fetch_via_browser")
@patch("curl_cffi.requests.Session.get")
def test_cloudflare_bypass_triggers_browser_fetch(
    mock_get: MagicMock, mock_fetch: MagicMock, scraper: Scraper
) -> None:
    """Test that Cloudflare 403 managed challenge triggers direct browser retrieval."""
    challenge_resp = MagicMock(spec=Response)
    challenge_resp.status_code = 403
    challenge_resp.headers = {"Server": "cloudflare"}
    challenge_resp.text = "Just a moment"

    mock_fetch.return_value = CachedResponse(
        text="<html><table class='eventList'></table></html>", status_code=200
    )
    mock_get.return_value = challenge_resp

    resp = scraper.get("http://cloudflare-protected.com")

    assert resp is not None
    assert resp.status_code == 200
    assert "eventList" in resp.text
    assert mock_fetch.call_count == 1
    assert mock_get.call_count == 1


@patch("undetected_chromedriver.Chrome")
@patch("src.scraper.Scraper._get_chrome_info")
def test_obtain_browser_cookies_cdp_click_and_clearance(
    mock_get_chrome: MagicMock,
    mock_uc_chrome: MagicMock,
    scraper: Scraper,
) -> None:
    """Test Turnstile CDP click dispatch and clearance detection."""
    mock_get_chrome.return_value = ("/usr/bin/google-chrome", 135)

    mock_driver = MagicMock()
    mock_uc_chrome.return_value = mock_driver

    cookie_record = [
        {
            "name": "cf_clearance",
            "value": "abc123clearance",
            "domain": ".orientering.se",
            "path": "/",
        }
    ]
    mock_driver.title = "Eventor - Tävlingskalender"
    mock_driver.page_source = "<html>eventList content</html>"
    mock_driver.get_cookies.return_value = cookie_record

    def mock_exec(script: str) -> Any:
        if "userAgent" in script:
            return "Mozilla/5.0 TestBrowser"
        return {"x": 10, "y": 200, "width": 300, "height": 65}

    mock_driver.execute_script.side_effect = mock_exec

    with patch("time.sleep"):
        resp = scraper._fetch_via_browser(
            "https://eventor.orientering.se/Events", retries=0
        )

    assert resp is not None
    assert resp.text == "<html>eventList content</html>"
    assert scraper.scraper.cookies.get("cf_clearance") == "abc123clearance"
    assert scraper.scraper.headers.get("User-Agent") == "Mozilla/5.0 TestBrowser"


def test_cookie_persistence_with_user_agent(tmp_path: Path) -> None:
    """Test saving and reloading cookies and User-Agent in structured format."""
    cookie_path = tmp_path / "custom_cookies.json"
    s1 = Scraper(delay_range=(0, 0), cookie_file=str(cookie_path))
    s1.scraper.cookies.set(
        "cf_clearance", "testclearancevalue", domain=".orientering.se"
    )
    s1.scraper.headers.update({"User-Agent": "Custom-Agent/1.0"})
    s1._save_cookies()

    assert cookie_path.exists()

    s2 = Scraper(delay_range=(0, 0), cookie_file=str(cookie_path))
    assert s2.scraper.cookies.get("cf_clearance") == "testclearancevalue"
    assert s2.scraper.headers.get("User-Agent") == "Custom-Agent/1.0"


def test_browser_lifecycle_and_cleanup(tmp_path: Path) -> None:
    """Test that close_browser and context manager properly terminate resources."""
    cookie_path = tmp_path / "test_cookies.json"
    mock_driver = MagicMock()
    mock_disp = MagicMock()

    with Scraper(delay_range=(0, 0), cookie_file=str(cookie_path)) as s:
        s._driver = mock_driver
        s._virtual_display = mock_disp
        s._domains_cleared.add("orientering.se")

    mock_driver.quit.assert_called_once()
    mock_disp.stop.assert_called_once()
    assert s._driver is None
    assert s._virtual_display is None
    assert len(s._domains_cleared) == 0
