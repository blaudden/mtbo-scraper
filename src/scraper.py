import json
import os
import random
import shutil
import subprocess
import time
from typing import cast

import curl_cffi.requests as requests
import structlog
from curl_cffi.requests import RequestsError, Response

logger = structlog.get_logger(__name__)


class Scraper:
    """Handles HTTP requests with curl-cffi (TLS impersonation) and browser fallback
    using undetected-chromedriver for Cloudflare bypass."""

    def __init__(
        self,
        delay_range: tuple[float, float] = (1.0, 3.0),
        default_timeout: int = 30,
    ):
        """Initialize the Scraper.

        Uses curl-cffi as primary engine (with TLS/JA3 impersonation) and
        undetected-chromedriver as fallback for Cloudflare managed challenges.

        Args:
            delay_range: Tuple (min, max) seconds to sleep between requests.
            default_timeout: Default timeout in seconds for requests.
        """
        # Primary: curl-cffi session with browser impersonation
        self.scraper: requests.Session = requests.Session(impersonate="chrome120")

        self.delay_range = delay_range
        self.default_timeout = default_timeout
        self.last_request_time: float = 0.0

        # Track domains where we've obtained browser cookies
        self._browser_cookies_obtained: set[str] = set()

        # Set default headers to request English content and desktop version
        self.scraper.headers.update(
            {
                "Accept-Language": "en-GB,en;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

        # Cookie persistence
        self.cookie_file = ".cookies.json"
        self._load_cookies()

    def _load_cookies(self) -> None:
        """Loads cookies from disk if they exist."""
        if not os.path.exists(self.cookie_file):
            return

        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                cookies = json.load(f)
                for cookie_dict in cookies:
                    # Apply each cookie to the curl-cffi session cookies
                    self.scraper.cookies.set(
                        cookie_dict["name"],
                        cookie_dict["value"],
                        domain=cookie_dict.get("domain", ""),
                        path=cookie_dict.get("path", "/"),
                    )
                    # Pre-populate obtained domains so we can track reuse
                    if "domain" in cookie_dict:
                        # Strip leading dot for consistency if present
                        domain = cookie_dict["domain"]
                        if domain.startswith("."):
                            domain = domain[1:]
                        self._browser_cookies_obtained.add(domain)
            logger.info("cookies_loaded_from_disk", count=len(cookies))
        except Exception as e:
            logger.warning("cookie_load_failed", error=str(e))

    def _save_cookies(self) -> None:
        """Saves current session cookies to disk."""
        try:
            cookies = []
            for cookie in self.scraper.cookies.jar:
                # Convert cookie objects to a JSON-serializable format
                cookies.append(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                    }
                )
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            logger.info("cookies_saved_to_disk", count=len(cookies))
        except Exception as e:
            logger.warning("cookie_save_failed", error=str(e))

    def _wait_for_rate_limit(self) -> None:
        """Sleeps for a random amount of time to respect rate limits."""
        elapsed = time.time() - self.last_request_time
        wait_time = random.uniform(*self.delay_range)
        if elapsed < wait_time:
            sleep_time = wait_time - elapsed
            logger.debug("rate_limiting_sleep", sleep_time=round(sleep_time, 2))
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        return urlparse(url).netloc

    def _is_managed_challenge(self, response: Response | None) -> bool:
        """Check if response is a Cloudflare managed challenge."""
        if response is None:
            return False
        if response.status_code != 403:
            return False
        if "cloudflare" not in response.headers.get("Server", "").lower():
            return False
        if "cType: 'managed'" in response.text or "Just a moment" in response.text:
            return True
        return False

    def _get_chrome_info(self) -> tuple[str | None, int | None]:
        """Detect Chrome/Chromium binary and its major version."""
        # Common binary names in order of preference
        binaries = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        ]

        # Check explicitly known paths first if they exist
        known_paths = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]
        for path in known_paths:
            if os.path.exists(path):
                version = self._get_binary_version(path)
                if version:
                    return path, version

        # Search in PATH
        for binary in binaries:
            binary_path = shutil.which(binary)
            if binary_path:
                version = self._get_binary_version(binary_path)
                if version:
                    return binary_path, version

        return None, None

    def _get_binary_version(self, path: str) -> int | None:
        """Get major version of a Chrome/Chromium binary."""
        try:
            output = subprocess.check_output([path, "--version"], text=True)
            # Output format: "Google Chrome 120.0.6099.109" or "Chromium 120.0.6099.109"
            parts = output.strip().split()
            for part in parts:
                if "." in part:
                    major = part.split(".")[0]
                    if major.isdigit():
                        return int(major)
        except Exception as e:
            logger.debug("version_check_failed", path=path, error=str(e))
        return None

    def _obtain_browser_cookies(self, url: str, retries: int = 2) -> bool:
        """Use undetected-chromedriver to bypass Cloudflare and obtain cookies.

        Opens a real browser window (or virtual display in headless environments),
        waits for challenge to resolve, then extracts cookies and applies them
        to the curl-cffi session.

        Args:
            url: The target URL that triggered the challenge.
            retries: Number of retries for browser initialization/solving.

        Returns:
            True if cookies were obtained successfully, False otherwise.
        """
        from urllib.parse import urlparse

        import undetected_chromedriver as uc

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}/"

        for attempt in range(retries + 1):
            logger.info(
                "opening_browser_for_cookies",
                domain=parsed.netloc,
                attempt=attempt + 1,
                max_attempts=retries + 1,
            )

            # Check if we have a display (for cron/headless environments)
            has_display = os.environ.get("DISPLAY") is not None
            virtual_display = None

            if not has_display:
                try:
                    from pyvirtualdisplay import Display

                    logger.info("virtual_display_starting", reason="no_display")
                    virtual_display = Display(visible=False, size=(1920, 1080))
                    virtual_display.start()
                except Exception as e:
                    logger.warning("virtual_display_start_failed", error=str(e))
                    logger.warning("Install Xvfb with: sudo apt-get install xvfb")

            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            # Detect browser path and version dynamically
            browser_path, browser_version = self._get_chrome_info()
            if browser_path:
                logger.info(
                    "detected_browser", path=browser_path, version=browser_version
                )
            else:
                logger.warning("no_browser_detected_falling_back_to_defaults")

            driver = None
            try:
                driver = uc.Chrome(
                    options=options,
                    browser_executable_path=browser_path,
                    version_main=browser_version,
                )
                driver.get(base_url)

                # Wait for Cloudflare challenge to resolve
                logger.info("waiting_for_cloudflare_challenge")
                max_wait = 30
                for i in range(max_wait):
                    time.sleep(1)
                    title = driver.title
                    if "Just a moment" not in title and "Checking" not in title:
                        break
                    if i % 5 == 0:
                        logger.debug(
                            "cloudflare_challenge_wait_progress",
                            seconds=i,
                            max_wait=max_wait,
                        )

                # Check if challenge was solved
                if "Just a moment" in driver.title:
                    logger.error("browser_fallback_failed_challenge_not_solved")
                    if attempt < retries:
                        continue
                    return False

                # Extract cookies and apply to curl-cffi session
                cookies = driver.get_cookies()
                for cookie in cookies:
                    self.scraper.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=cookie.get("domain", ""),
                        path=cookie.get("path", "/"),
                    )

                # Save new cookies to disk
                self._save_cookies()

                # Also update user-agent to match the browser
                user_agent = driver.execute_script("return navigator.userAgent;")
                self.scraper.headers.update({"User-Agent": user_agent})

                logger.info(
                    "browser_bypass_successful",
                    cookie_count=len(cookies),
                    domain=parsed.netloc,
                )
                return True

            except Exception as e:
                logger.error(
                    "browser_fallback_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < retries:
                    time.sleep(5)  # Wait before retry
                    continue
                return False
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                if virtual_display:
                    try:
                        virtual_display.stop()
                    except Exception:
                        pass

        return False

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        retries: int = 3,
        timeout: int | None = None,
    ) -> Response | None:
        """Perform a GET request with rate limiting and retries.

        Primary: uses curl-cffi with 'chrome120' impersonation to bypass TLS-based
        detection.
        Fallback: uses undetected-chromedriver for managed challenges (Turnstile).

        Args:
            url: Target URL.
            params: Query parameters.
            retries: Number of retries on failure.
            timeout: Timeout in seconds for this request
                     (defaults to self.default_timeout).

        Returns:
            Response object or None if failed.
        """
        self._wait_for_rate_limit()

        # Ensure culture parameter is set to en-GB for English content
        if params is None:
            params = {}
        if "culture" not in params:
            params["culture"] = "en-GB"

        domain = self._get_domain(url)

        for attempt in range(retries):
            try:
                if attempt > 0:
                    logger.debug(
                        "fetching_url",
                        url=url,
                        attempt=attempt + 1,
                        max_retries=retries,
                    )
                else:
                    logger.debug("fetching_url", url=url)

                # curl-cffi handles most Cloudflare cases automatically
                # via TLS impersonation
                response = self.scraper.get(
                    url,
                    params=params,
                    timeout=timeout or self.default_timeout,
                )

                # Check for Cloudflare managed challenge (fallback to real browser)
                if self._is_managed_challenge(response):
                    # Only use browser if we haven't already obtained cookies for this
                    # domain
                    if domain not in self._browser_cookies_obtained:
                        logger.warning("cloudflare_challenge_detected", domain=domain)

                        if self._obtain_browser_cookies(url):
                            self._browser_cookies_obtained.add(domain)
                            # Retry the request with the new browser cookies
                            logger.info("Retrying request with browser cookies...")
                            response = self.scraper.get(url, params=params)

                            if self._is_managed_challenge(response):
                                logger.error("Still blocked after obtaining cookies")
                                return None
                        else:
                            logger.error("browser_cookies_fetch_failed", domain=domain)
                            return None
                    else:
                        # We already have cookies but still getting challenged
                        # (expired or invalidated)
                        logger.error("cloudflare_cookies_expired", domain=domain)
                        self._browser_cookies_obtained.discard(domain)

                        if self._obtain_browser_cookies(url):
                            self._browser_cookies_obtained.add(domain)
                            response = self.scraper.get(url, params=params)
                            if self._is_managed_challenge(response):
                                logger.error("Still blocked after refreshing cookies")
                                return None
                        else:
                            return None

                # If first attempt succeeds without challenge and we had cookies, log it
                if attempt == 0 and domain in self._browser_cookies_obtained:
                    # Double check it's not a challenge before logging success
                    if not self._is_managed_challenge(response):
                        logger.info("cookie_reuse_bypass_successful", domain=domain)

                response.raise_for_status()
                return cast(Response, response)

            except RequestsError as e:
                logger.warning("request_failed", error=str(e))
                if attempt < retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    logger.error(
                        "request_failed_max_attempts", url=url, retries=retries
                    )
                    return None

        return None
