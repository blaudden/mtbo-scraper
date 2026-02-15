import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.html_cache import HtmlCache


class TestHtmlCache:
    """Tests for the HtmlCache class."""

    def test_cache_put_and_get(self) -> None:
        """Test writing HTML to cache and reading it back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"
            html = "<html><body>Test Event</body></html>"

            # Put HTML into cache
            cache.put(year, prefix, url, html)

            # Get HTML from cache
            cached_html = cache.get(year, prefix, url)

            assert cached_html == html

    def test_cache_miss_returns_none(self) -> None:
        """Test that looking up a non-existent URL returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/9999"

            result = cache.get(year, prefix, url)

            assert result is None

    def test_cache_creates_year_directory(self) -> None:
        """Test that the year directory is auto-created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"
            html = "<html><body>Test</body></html>"

            cache.put(year, prefix, url, html)

            year_dir = Path(tmpdir) / year
            assert year_dir.exists()
            assert year_dir.is_dir()

    def test_cache_path_deterministic(self) -> None:
        """Test that the same URL always produces the same cache path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"

            path1 = cache.cache_path(year, prefix, url)
            path2 = cache.cache_path(year, prefix, url)

            assert path1 == path2

    def test_cache_different_urls_different_files(self) -> None:
        """Test that two different URLs produce different cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url1 = "https://eventor.orientering.se/Events/Show/5115"
            url2 = "https://eventor.orientering.se/Events/Show/5116"

            path1 = cache.cache_path(year, prefix, url1)
            path2 = cache.cache_path(year, prefix, url2)

            assert path1 != path2

    def test_scraper_skips_sleep_on_cache_hit(self) -> None:
        """Test that _wait_for_rate_limit is NOT called when cache hits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.scraper import Scraper

            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"
            html = "<html><body>Cached Event</body></html>"

            # Pre-populate cache
            cache.put(year, prefix, url, html)

            # Create scraper with cache enabled
            scraper = Scraper(html_cache=cache)

            # Mock _wait_for_rate_limit to track if it's called
            with patch.object(scraper, "_wait_for_rate_limit") as mock_wait:
                response = scraper.get(url, cache_key_prefix=prefix, cache_year=year)

                # Should NOT have called _wait_for_rate_limit
                mock_wait.assert_not_called()

                # Should return cached HTML
                assert response is not None
                assert response.text == html

    def test_scraper_sleeps_on_cache_miss(self) -> None:
        """Test that _wait_for_rate_limit IS called on cache miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.scraper import Scraper

            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"

            # Create scraper with cache enabled
            scraper = Scraper(html_cache=cache)

            # Mock _wait_for_rate_limit and the actual HTTP request
            with patch.object(scraper, "_wait_for_rate_limit") as mock_wait:
                with patch.object(scraper.scraper, "get") as mock_get:
                    # Mock successful response
                    mock_response = MagicMock()
                    mock_response.text = "<html><body>Fresh</body></html>"
                    mock_response.status_code = 200
                    mock_get.return_value = mock_response

                    scraper.get(url, cache_key_prefix=prefix, cache_year=year)

                    # Should have called _wait_for_rate_limit
                    mock_wait.assert_called_once()

    def test_scraper_writes_to_cache_after_fetch(self) -> None:
        """Test that HTML is saved to cache after successful fetch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.scraper import Scraper

            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"
            html = "<html><body>Fresh Event</body></html>"

            # Create scraper with cache enabled
            scraper = Scraper(html_cache=cache)

            # Mock the actual HTTP request
            with patch.object(scraper.scraper, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.text = html
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                scraper.get(url, cache_key_prefix=prefix, cache_year=year)

                # Verify HTML was written to cache
                cached_html = cache.get(year, prefix, url)
                assert cached_html == html

    def test_cache_disabled_in_standard_mode(self) -> None:
        """Test that cache is not used when html_cache=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from src.scraper import Scraper

            cache = HtmlCache(base_dir=tmpdir)
            year = "2024"
            prefix = "SWE_5115"
            url = "https://eventor.orientering.se/Events/Show/5115"
            html = "<html><body>Cached Event</body></html>"

            # Pre-populate cache
            cache.put(year, prefix, url, html)

            # Create scraper with cache DISABLED
            scraper = Scraper(html_cache=None)

            # Mock the actual HTTP request
            with patch.object(scraper.scraper, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.text = "<html><body>Fresh</body></html>"
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                response = scraper.get(url, cache_key_prefix=prefix, cache_year=year)

                # Should have made actual HTTP request
                mock_get.assert_called_once()

                # Should return fresh content, not cached
                assert response is not None
                assert response.text == "<html><body>Fresh</body></html>"
