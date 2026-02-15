import hashlib
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class HtmlCache:
    """Manages disk-based HTML cache for scraped pages.

    Files are stored at: {base_dir}/{year}/{prefix}_{url_hash}.html
    where url_hash is the first 8 characters of the MD5 hash of the full URL.
    """

    def __init__(self, base_dir: str = "cache") -> None:
        """Initialize the HTML cache.

        Args:
            base_dir: Base directory for cache storage (default: "cache").
        """
        self.base_dir = Path(base_dir)

    def _hash_url(self, url: str) -> str:
        """Generate an 8-character hash from a URL.

        Args:
            url: The full URL to hash.

        Returns:
            First 8 characters of MD5 hex digest.
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]

    def cache_path(self, year: str, key_prefix: str, url: str) -> Path:
        """Compute the cache file path for a URL.

        Args:
            year: Year for partitioning (e.g. "2024").
            key_prefix: Event key prefix (e.g. "SWE_5115").
            url: The full URL.

        Returns:
            Path to the cache file.
        """
        url_hash = self._hash_url(url)
        filename = f"{key_prefix}_{url_hash}.html"
        return self.base_dir / year / filename

    def get(self, year: str, key_prefix: str, url: str) -> str | None:
        """Look up cached HTML by URL.

        Args:
            year: Year for partitioning.
            key_prefix: Event key prefix.
            url: The full URL.

        Returns:
            Cached HTML content, or None if not found.
        """
        path = self.cache_path(year, key_prefix, url)
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning("cache_read_failed", path=str(path), error=str(e))
            return None

    def put(self, year: str, key_prefix: str, url: str, html: str) -> None:
        """Save HTML to cache.

        Args:
            year: Year for partitioning.
            key_prefix: Event key prefix.
            url: The full URL.
            html: HTML content to cache.
        """
        path = self.cache_path(year, key_prefix, url)

        # Create year directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.debug("cache_write_success", path=str(path))
        except Exception as e:
            logger.warning("cache_write_failed", path=str(path), error=str(e))
