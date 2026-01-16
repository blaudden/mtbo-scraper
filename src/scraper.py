import logging
import time
import random
import cloudscraper
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self, delay_range=(1.0, 3.0)):
        """
        Initialize the Scraper with cloudscraper as primary and
        undetected-chromedriver as fallback for Cloudflare managed challenges.
        
        :param delay_range: Tuple (min, max) seconds to sleep between requests.
        """
        # Primary: cloudscraper with disabled buggy features
        self.scraper = cloudscraper.create_scraper(
            auto_refresh_on_403=False,  # Disable buggy 403 auto-refresh
            enable_stealth=False,       # Disable stealth mode (causes infinite loop)
        )
        
        self.delay_range = delay_range
        self.last_request_time = 0
        
        # Track domains where we've obtained browser cookies
        self._browser_cookies_obtained = set()
        
        # Set default headers to request English content
        self.scraper.headers.update({
            'Accept-Language': 'en-GB,en;q=0.9'
        })

    def _wait_for_rate_limit(self):
        """Sleeps for a random amount of time to respect rate limits."""
        elapsed = time.time() - self.last_request_time
        wait_time = random.uniform(*self.delay_range)
        if elapsed < wait_time:
            sleep_time = wait_time - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _get_domain(self, url):
        """Extract domain from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def _is_managed_challenge(self, response):
        """Check if response is a Cloudflare managed challenge."""
        if response is None:
            return False
        if response.status_code != 403:
            return False
        if 'cloudflare' not in response.headers.get('Server', '').lower():
            return False
        if "cType: 'managed'" in response.text or 'Just a moment' in response.text:
            return True
        return False

    def _obtain_browser_cookies(self, url):
        """
        Use undetected-chromedriver to bypass Cloudflare and obtain cookies.
        Opens a real browser window (or virtual display in headless environments),
        waits for challenge to resolve, then extracts cookies and applies them 
        to the cloudscraper session.
        
        Returns True if cookies were obtained successfully, False otherwise.
        """
        import undetected_chromedriver as uc
        from urllib.parse import urlparse
        import os
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}/"
        
        logger.info(f"Opening browser to obtain cookies for: {parsed.netloc}")
        
        # Check if we have a display (for cron/headless environments)
        has_display = os.environ.get('DISPLAY') is not None
        virtual_display = None
        
        if not has_display:
            try:
                from pyvirtualdisplay import Display
                logger.info("No display detected, starting virtual display (Xvfb)...")
                virtual_display = Display(visible=False, size=(1920, 1080))
                virtual_display.start()
            except Exception as e:
                logger.warning(f"Could not start virtual display: {e}")
                logger.warning("Install Xvfb with: sudo apt-get install xvfb")
        
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # Non-headless mode required for Cloudflare bypass
        
        driver = None
        try:
            driver = uc.Chrome(options=options)
            driver.get(base_url)
            
            # Wait for Cloudflare challenge to resolve
            logger.info("Waiting for Cloudflare challenge to resolve...")
            max_wait = 30
            for i in range(max_wait):
                time.sleep(1)
                title = driver.title
                if 'Just a moment' not in title and 'Checking' not in title:
                    break
                if i % 5 == 0:
                    logger.debug(f"Still waiting... ({i}/{max_wait}s)")
            
            # Check if challenge was solved
            if 'Just a moment' in driver.title:
                logger.error("Browser fallback failed - challenge not solved")
                return False
            
            # Extract cookies and apply to cloudscraper session
            cookies = driver.get_cookies()
            for cookie in cookies:
                self.scraper.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/')
                )
            
            # Also update user-agent to match the browser
            user_agent = driver.execute_script("return navigator.userAgent;")
            self.scraper.headers.update({'User-Agent': user_agent})
            
            logger.info(f"Browser bypass successful! Got {len(cookies)} cookies for {parsed.netloc}")
            return True
            
        except Exception as e:
            logger.error(f"Browser fallback error: {e}")
            return False
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            if virtual_display:
                try:
                    virtual_display.stop()
                except:
                    pass

    def get(self, url, params=None, retries=3):
        """
        Perform a GET request with rate limiting and retries.
        Falls back to browser automation for Cloudflare managed challenges.
        After obtaining cookies from browser, uses cloudscraper for remaining requests.
        
        :param url: Target URL.
        :param params: Query parameters.
        :param retries: Number of retries on failure.
        :return: Response object or None if failed.
        """
        self._wait_for_rate_limit()
        
        # Ensure culture parameter is set to en-GB for English content
        if params is None:
            params = {}
        if 'culture' not in params:
            params['culture'] = 'en-GB'
        
        domain = self._get_domain(url)
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    logger.info(f"Fetching URL: {url} (Attempt {attempt + 1}/{retries})")
                else:
                    logger.info(f"Fetching URL: {url}")
                
                response = self.scraper.get(url, params=params)
                
                # Check for Cloudflare managed challenge
                if self._is_managed_challenge(response):
                    # Only use browser if we haven't already obtained cookies for this domain
                    if domain not in self._browser_cookies_obtained:
                        logger.warning(f"Cloudflare managed challenge detected for {domain}")
                        
                        if self._obtain_browser_cookies(url):
                            self._browser_cookies_obtained.add(domain)
                            # Retry the request with the new cookies
                            logger.info(f"Retrying request with browser cookies...")
                            response = self.scraper.get(url, params=params)
                            
                            if self._is_managed_challenge(response):
                                logger.error(f"Still blocked after obtaining cookies")
                                return None
                        else:
                            logger.error(f"Failed to obtain browser cookies for {domain}")
                            return None
                    else:
                        # We already have cookies but still getting challenged
                        logger.error(f"Cookies expired for {domain}, need to refresh")
                        self._browser_cookies_obtained.discard(domain)
                        
                        if self._obtain_browser_cookies(url):
                            self._browser_cookies_obtained.add(domain)
                            response = self.scraper.get(url, params=params)
                            if self._is_managed_challenge(response):
                                logger.error(f"Still blocked after refreshing cookies")
                                return None
                        else:
                            return None
                
                response.raise_for_status()
                return response
                
            except RequestException as e:
                logger.warning(f"Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts.")
                    return None
