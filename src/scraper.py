import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import curl_cffi.requests as requests
import structlog
from curl_cffi.requests import RequestsError, Response

if TYPE_CHECKING:
    from src.html_cache import HtmlCache

logger = structlog.get_logger(__name__)


@dataclass
class CachedResponse:
    """Response-like object for cached HTML or browser page source."""

    text: str
    status_code: int = 200

    def raise_for_status(self) -> None:
        """No-op for cached responses (always successful)."""
        pass


class Scraper:
    """Handles HTTP requests with curl-cffi (TLS impersonation) and browser fallback
    using undetected-chromedriver for Cloudflare bypass."""

    def __init__(
        self,
        delay_range: tuple[float, float] = (1.0, 3.0),
        default_timeout: int = 30,
        html_cache: "HtmlCache | None" = None,
        cookie_file: str = ".cookies.json",
    ):
        """Initialize the Scraper.

        Uses curl-cffi as primary engine (with TLS/JA3 impersonation) and
        undetected-chromedriver as fallback for Cloudflare managed challenges.

        Args:
            delay_range: Tuple (min, max) seconds to sleep between requests.
            default_timeout: Default timeout in seconds for requests.
            html_cache: HtmlCache instance for caching HTML responses.
            cookie_file: Path to cookie persistence file.
        """
        # Primary: curl-cffi session with browser impersonation
        self.scraper: requests.Session = requests.Session(impersonate="chrome")

        self.delay_range = delay_range
        self.default_timeout = default_timeout
        self.last_request_time: float = 0.0

        # HTML caching
        self.html_cache = html_cache

        # Track domains where we have obtained browser cookies
        self._browser_cookies_obtained: set[str] = set()

        # Browser fallback state
        self._driver: Any | None = None
        self._virtual_display: Any | None = None
        self._domains_cleared: set[str] = set()

        # Set default headers to request English content and desktop version
        self.scraper.headers.update(
            {
                "Accept-Language": "en-GB,en;q=0.9",
            }
        )

        # Cookie persistence
        self.cookie_file = cookie_file
        self._load_cookies()

    def _load_cookies(self) -> None:
        """Loads cookies and user-agent from disk if they exist."""
        if not os.path.exists(self.cookie_file):
            return

        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                data = json.load(f)
                cookies: list[dict[str, Any]] = []
                if isinstance(data, dict):
                    cookies = data.get("cookies", [])
                    user_agent = data.get("user_agent")
                    if user_agent and isinstance(user_agent, str):
                        self.scraper.headers.update({"User-Agent": user_agent})
                elif isinstance(data, list):
                    cookies = data

                for cookie_dict in cookies:
                    self.scraper.cookies.set(
                        cookie_dict["name"],
                        cookie_dict["value"],
                        domain=cookie_dict.get("domain", ""),
                        path=cookie_dict.get("path", "/"),
                    )
                    if "domain" in cookie_dict:
                        domain = cookie_dict["domain"]
                        if domain.startswith("."):
                            domain = domain[1:]
                        self._browser_cookies_obtained.add(domain)
            logger.info("cookies_loaded_from_disk", count=len(cookies))
        except Exception as e:
            logger.warning("cookie_load_failed", error=str(e))

    def _save_cookies(self) -> None:
        """Saves current session cookies and User-Agent to disk."""
        try:
            cookies = []
            for cookie in self.scraper.cookies.jar:
                cookies.append(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                    }
                )
            payload = {
                "user_agent": self.scraper.headers.get("User-Agent", ""),
                "cookies": cookies,
            }
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info("cookies_saved_to_disk", count=len(cookies))
        except Exception as e:
            logger.warning("cookie_save_failed", error=str(e))

    def _wait_for_rate_limit(self) -> None:
        """Sleeps for a random amount of time to respect rate limits."""
        elapsed = time.time() - self.last_request_time
        wait_time = random.SystemRandom().uniform(*self.delay_range)
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
        binaries = [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
        ]

        known_paths = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]
        for path in known_paths:
            if os.path.exists(path):
                version = self._get_binary_version(path)
                if version:
                    return path, version

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
            output = subprocess.check_output([path, "--version"], text=True)  # noqa: S603
            parts = output.strip().split()
            for part in parts:
                if "." in part:
                    major = part.split(".")[0]
                    if major.isdigit():
                        return int(major)
        except Exception as e:
            logger.debug("version_check_failed", path=path, error=str(e))
        return None

    def _init_browser(self) -> Any:
        """Initializes undetected-chromedriver with virtual display if needed."""
        if self._driver is not None:
            return self._driver

        has_display = os.environ.get("DISPLAY") is not None
        if not has_display and self._virtual_display is None:
            try:
                from pyvirtualdisplay import Display

                logger.info("virtual_display_starting", reason="no_display")
                self._virtual_display = Display(visible=False, size=(1920, 1080))
                self._virtual_display.start()
            except Exception as e:
                logger.warning("virtual_display_start_failed", error=str(e))
                logger.warning("Install Xvfb with: sudo apt-get install xvfb")

        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-gpu-blocklist")
        options.add_argument("--enable-webgl")
        options.add_argument("--disable-features=WebGPU")
        options.add_argument("--window-size=1920,1080")

        browser_path, browser_version = self._get_chrome_info()
        if browser_path:
            logger.info("detected_browser", path=browser_path, version=browser_version)
        else:
            logger.warning("no_browser_detected_falling_back_to_defaults")

        # Monkey-patch undetected_chromedriver to re-sign binary on macOS
        import sys

        import undetected_chromedriver.patcher

        if not hasattr(undetected_chromedriver.patcher.Patcher, "_is_patched_for_mac"):
            original_patch = undetected_chromedriver.patcher.Patcher.patch_exe

            def patched_patch_exe(
                patcher_self: Any, original_patch: Any = original_patch
            ) -> Any:
                original_patch(patcher_self)
                if sys.platform.startswith("darwin"):
                    try:
                        logger.info("Codesigning patched executable for macOS")
                        subprocess.check_call(  # noqa: S603
                            ["codesign", "-f", "-s", "-", patcher_self.executable_path]  # noqa: S607
                        )
                    except Exception as err:
                        logger.warning("codesign_failed", error=str(err))

            undetected_chromedriver.patcher.Patcher.patch_exe = patched_patch_exe
            undetected_chromedriver.patcher.Patcher._is_patched_for_mac = True

        self._driver = uc.Chrome(
            options=options,
            browser_executable_path=browser_path,
            version_main=browser_version,
        )
        return self._driver

    def close_browser(self) -> None:
        """Closes active browser and virtual display if running."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception as e:
                logger.debug("exception_during_driver_quit", error=str(e))
            self._driver = None
        if self._virtual_display is not None:
            try:
                self._virtual_display.stop()
            except Exception as e:
                logger.debug("exception_during_display_stop", error=str(e))
            self._virtual_display = None
        self._domains_cleared.clear()

    def close(self) -> None:
        """Closes all browser and driver resources."""
        self.close_browser()

    def __enter__(self) -> "Scraper":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _click_turnstile(
        self, driver: Any, click_x: int = 533, click_y: int = 336
    ) -> bool:
        """Dispatches CDP mouse events directly to Turnstile widget coordinates."""
        try:
            logger.info("dispatching_turnstile_cdp_click", x=click_x, y=click_y)
            driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseMoved",
                    "x": click_x,
                    "y": click_y,
                    "pointerType": "mouse",
                },
            )
            time.sleep(0.15)
            driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {
                    "type": "mousePressed",
                    "button": "left",
                    "buttons": 1,
                    "clickCount": 1,
                    "x": click_x,
                    "y": click_y,
                    "pointerType": "mouse",
                },
            )
            time.sleep(0.15)
            driver.execute_cdp_cmd(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseReleased",
                    "button": "left",
                    "buttons": 0,
                    "clickCount": 1,
                    "x": click_x,
                    "y": click_y,
                    "pointerType": "mouse",
                },
            )
            return True
        except Exception as e:
            logger.debug("turnstile_click_attempt_failed", error=str(e))
            return False

    def _fetch_via_browser(
        self,
        url: str,
        params: dict[str, str] | None = None,
        retries: int = 2,
    ) -> CachedResponse | None:
        """Fetches page directly using undetected-chromedriver when challenged.

        Navigates to base domain first if not already cleared to solve Turnstile,
        then navigates to target URL and returns page HTML as CachedResponse.
        """
        from urllib.parse import urlencode, urlparse

        full_url = url
        if params:
            delim = "&" if "?" in url else "?"
            full_url = f"{url}{delim}{urlencode(params)}"

        parsed = urlparse(full_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}/"
        domain = parsed.netloc

        for attempt in range(retries + 1):
            try:
                driver = self._init_browser()

                # Step 1: Ensure root domain is cleared
                if domain not in self._domains_cleared:
                    logger.info(
                        "clearing_cloudflare_on_root_domain",
                        domain=domain,
                        base_url=base_url,
                    )
                    driver.get(base_url)
                    time.sleep(5)  # Wait for Turnstile telemetry initialization

                    if "Just a moment" in driver.title or "Checking" in driver.title:
                        self._click_turnstile(driver)
                        # Wait for resolution
                        for _ in range(15):
                            time.sleep(1)
                            title = driver.title
                            if "Just a moment" not in title and "Checking" not in title:
                                logger.info(
                                    "root_domain_turnstile_cleared",
                                    domain=domain,
                                    title=title,
                                )
                                self._domains_cleared.add(domain)
                                break
                        if domain not in self._domains_cleared:
                            logger.error(
                                "root_domain_turnstile_failed_to_clear",
                                domain=domain,
                            )
                            if attempt < retries:
                                self.close_browser()
                                continue
                            return None
                    else:
                        self._domains_cleared.add(domain)

                # Step 2: Navigate to target URL
                logger.info("browser_navigating_to_target", url=full_url)
                driver.get(full_url)
                time.sleep(2)

                # Step 3: Check if deep URL challenged
                if "Just a moment" in driver.title or "Checking" in driver.title:
                    logger.warning(
                        "target_url_challenged_attempting_click", url=full_url
                    )
                    time.sleep(2)
                    self._click_turnstile(driver)
                    for _ in range(15):
                        time.sleep(1)
                        if (
                            "Just a moment" not in driver.title
                            and "Checking" not in driver.title
                        ):
                            break

                if "Just a moment" in driver.title:
                    logger.error("browser_fetch_failed_still_challenged", url=full_url)
                    if attempt < retries:
                        self.close_browser()
                        continue
                    return None

                # Step 4: Extract page source and session cookies
                page_source = driver.page_source
                try:
                    cookies = driver.get_cookies()
                    for cookie in cookies:
                        self.scraper.cookies.set(
                            cookie["name"],
                            cookie["value"],
                            domain=cookie.get("domain", ""),
                            path=cookie.get("path", "/"),
                        )
                    user_agent = driver.execute_script("return navigator.userAgent;")
                    if user_agent and isinstance(user_agent, str):
                        self.scraper.headers.update({"User-Agent": user_agent})
                    self._save_cookies()
                except Exception as ce:
                    logger.debug("cookie_sync_failed", error=str(ce))

                logger.info(
                    "browser_page_fetch_successful",
                    url=full_url,
                    length=len(page_source),
                )
                return CachedResponse(text=page_source, status_code=200)

            except Exception as e:
                logger.error(
                    "browser_fetch_exception",
                    error=str(e),
                    attempt=attempt + 1,
                    url=full_url,
                )
                self.close_browser()
                if attempt < retries:
                    time.sleep(3)
                    continue
                return None

        return None

    def _obtain_browser_cookies(self, url: str, retries: int = 2) -> bool:
        """Legacy helper: bypass Cloudflare and obtain cookies.

        Delegates to _fetch_via_browser and returns True if successful.
        """
        resp = self._fetch_via_browser(url, retries=retries)
        return resp is not None

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        retries: int = 3,
        timeout: int | None = None,
        cache_key_prefix: str | None = None,
        cache_year: str | None = None,
    ) -> Response | CachedResponse | None:
        """Perform a GET request with rate limiting and retries.

        Primary: uses curl-cffi with browser impersonation to bypass TLS checks.
        Fallback: uses undetected-chromedriver for managed challenges (Turnstile).

        Args:
            url: Target URL.
            params: Query parameters.
            retries: Number of retries on failure.
            timeout: Timeout in seconds for this request
                     (defaults to self.default_timeout).
            cache_key_prefix: Event key prefix for cache (e.g. "SWE_5115").
            cache_year: Year for cache partitioning (e.g. "2024").

        Returns:
            Response object or None if failed.
        """
        # Build full URL for cache lookup
        full_url = url
        if params:
            from urllib.parse import urlencode

            delim = "&" if "?" in url else "?"
            full_url = f"{url}{delim}{urlencode(params)}"

        # Check cache before rate limiting (if enabled)
        if self.html_cache and cache_key_prefix and cache_year:
            cached_html = self.html_cache.get(cache_year, cache_key_prefix, full_url)
            if cached_html:
                logger.debug(
                    "cache_hit",
                    url=url,
                    prefix=cache_key_prefix,
                    year=cache_year,
                )
                return CachedResponse(text=cached_html)

        # Cache miss or cache disabled - proceed with rate limiting
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
                    logger.warning(
                        "cloudflare_challenge_detected",
                        domain=domain,
                        url=full_url,
                    )
                    browser_response = self._fetch_via_browser(url, params=params)
                    if browser_response is not None:
                        response = browser_response
                    else:
                        logger.error("browser_fallback_failed", url=full_url)
                        return None

                response.raise_for_status()

                # Save to cache if enabled
                if self.html_cache and cache_key_prefix and cache_year:
                    self.html_cache.put(
                        cache_year, cache_key_prefix, full_url, response.text
                    )

                return cast(Response | CachedResponse, response)

            except RequestsError as e:
                # Handle "Too many open files" specifically
                if "too many open files" in str(e).lower() or (
                    hasattr(e, "errno") and e.errno == 24
                ):
                    logger.error(
                        "resource_limit_reached",
                        error="Too many open files (errno 24)",
                        suggestion=(
                            "Increase system file limits (ulimit -n) "
                            "or reduce concurrency/session usage."
                        ),
                    )
                    return None

                status_code = getattr(e, "response", None)
                if status_code:
                    status_code = status_code.status_code

                # Determine if it is retryable
                retryable = True
                if status_code in (400, 401, 403, 404):
                    retryable = False

                logger.warning(
                    "request_failed",
                    url=url,
                    status_code=status_code,
                    error=str(e),
                    attempt=attempt + 1,
                    retryable=retryable,
                )

                if retryable and attempt < retries - 1:
                    wait_time = (2**attempt) + random.SystemRandom().uniform(0, 1)
                    time.sleep(wait_time)  # Exponential backoff with jitter
                else:
                    if not retryable:
                        logger.error(
                            "request_failed_non_retryable", url=url, status=status_code
                        )
                    else:
                        logger.error(
                            "request_failed_max_attempts", url=url, retries=retries
                        )
                    return None

            except Exception:
                logger.exception("unexpected_request_error", url=url)
                return None

        return None
