import logging
import time
import random
import cloudscraper
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self, delay_range=(1.0, 3.0)):
        """
        Initialize the Scraper with cloudscraper to bypass Cloudflare.
        
        :param delay_range: Tuple (min, max) seconds to sleep between requests.
        """
        self.scraper = cloudscraper.create_scraper()
        self.delay_range = delay_range
        self.last_request_time = 0
        
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

    def get(self, url, params=None, retries=3):
        """
        Perform a GET request with rate limiting and retries.
        Always requests English content via culture parameter.
        
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
        
        for attempt in range(retries):
            try:
                # Only log retries (Attempt 2+)
                if attempt > 0:
                    logger.info(f"Fetching URL: {url} (Attempt {attempt + 1}/{retries})")
                else:
                    logger.info(f"Fetching URL: {url}")
                
                response = self.scraper.get(url, params=params)
                response.raise_for_status()
                return response
            except RequestException as e:
                logger.warning(f"Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts.")
                    return None
