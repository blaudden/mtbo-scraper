import logging
import traceback

from src.models import Event
from src.scraper import Scraper
from src.sources.base_source import BaseSource
from src.sources.eventor_parser import EventorParser
from src.utils.date_and_time import parse_date_to_iso

logger = logging.getLogger(__name__)


class EventorSource(BaseSource):
    """Source implementation for Eventor (SWE, NOR, IOF, etc.)."""

    def __init__(self, country: str, base_url: str):
        """Initializes the EventorSource.

        Args:
            country: The country code (e.g. "SWE").
            base_url: The base URL of the Eventor instance.
        """
        self.country = country
        self.base_url = base_url.rstrip("/")
        self.scraper = Scraper()
        self.parser = EventorParser()

    def fetch_event_list(self, start_date: str, end_date: str) -> list[Event]:
        """Fetches the list of events for the given date range.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            A list of Event objects with basic information found on the list page.
        """
        logger.info(f"Scraping {self.country} ({self.base_url})...")

        params = {
            "disciplines": "MountainBike",
            "startDate": start_date,
            "endDate": end_date,
            "map": "false",
            "mode": "List",
            "showMyEvents": "true",
            "cancelled": "true",  # Always include cancelled events
            "isExpanded": "true",
        }

        if self.country == "SWE":
            params["excludeAttributes"] = "11"
        elif self.country == "NOR":
            params["excludeAttributes"] = "2"
        # IOF has no excludeAttributes in the provided URL

        list_url = f"{self.base_url}/Events"

        response = self.scraper.get(list_url, params=params)
        if not response:
            logger.error(f"Failed to fetch event list for {self.country}")
            return []

        events = self.parser.parse_event_list(response.text, self.country)
        logger.info(f"Found {len(events)} events for {self.country}")
        return events

    def fetch_event_details(self, event: Event) -> Event | None:
        """Fetches detailed information for a specific event.

        Args:
            event: The Event object to enrich.

        Returns:
            The enriched Event object, or None if fetching details failed.
        """
        if not event.url:
            logger.error(
                f"Event {event.id} ({event.name}) has no URL. Skipping detail scrape."
            )
            return None

        detail_url = f"{self.base_url}{event.url}"

        detail_response = self.scraper.get(detail_url)
        if detail_response:
            try:
                event = self.parser.parse_event_details(detail_response.text, event)

                # Post-processing: Parse dates to ISO format
                event.start_time = parse_date_to_iso(event.start_time)
                event.end_time = parse_date_to_iso(event.end_time)

                # For multi-day events, calculate end_date from last race
                if event.races and len(event.races) > 0:
                    # Find the latest race date
                    race_dates = [r.datetimez for r in event.races if r.datetimez]
                    if race_dates:
                        # Dates are already in ISO format from parsing
                        # But event level end_time should be a plain date
                        event.end_time = max(race_dates).split("T")[0]

                # Fetch and parse lists for each race
                for race in event.races:
                    # Fetch and parse Entry List
                    entry_url = next(
                        (u.url for u in race.urls if u.type == "EntryList"), None
                    )
                    if entry_url:
                        full_url = (
                            f"{self.base_url}{entry_url}"
                            if entry_url.startswith("/")
                            else entry_url
                        )
                        resp = self.scraper.get(full_url)
                        if resp:
                            race.entry_counts = self.parser.parse_list_count(resp.text)

                    # Fetch and parse Start List
                    start_url = next(
                        (u.url for u in race.urls if u.type == "StartList"), None
                    )
                    if start_url:
                        full_url = (
                            f"{self.base_url}{start_url}"
                            if start_url.startswith("/")
                            else start_url
                        )
                        resp = self.scraper.get(full_url)
                        if resp:
                            race.start_counts = self.parser.parse_list_count(resp.text)

                    # Fetch and parse Result List
                    result_url = next(
                        (u.url for u in race.urls if u.type == "ResultList"), None
                    )
                    if result_url:
                        full_url = (
                            f"{self.base_url}{result_url}"
                            if result_url.startswith("/")
                            else result_url
                        )
                        resp = self.scraper.get(full_url)
                        if resp:
                            race.result_counts = self.parser.parse_list_count(resp.text)

                return event
            except Exception as e:
                logger.error(f"Failed to parse details for {event.id}: {e}")
                traceback.print_exc()
                return None
        else:
            logger.error(f"Failed to fetch details for {event.id}")
            return None
