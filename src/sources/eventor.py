import logging
from typing import List, Optional
from src.sources.base import BaseSource
from src.models import Event
from src.scraper import Scraper
from src.parsers import EventorParser

logger = logging.getLogger(__name__)

class EventorSource(BaseSource):
    """
    Source implementation for Eventor (SWE, NOR, IOF, etc.).
    """
    
    def __init__(self, country: str, base_url: str):
        self.country = country
        self.base_url = base_url.rstrip('/')
        self.scraper = Scraper()
        self.parser = EventorParser()

    def fetch_event_list(self, start_date: str, end_date: str) -> List[Event]:
        logger.info(f"Scraping {self.country} ({self.base_url})...")
        
        params = {
            "disciplines": "MountainBike",
            "startDate": start_date,
            "endDate": end_date,
            "map": "false",
            "mode": "List",
            "showMyEvents": "true",
            "cancelled": "true", # Always include cancelled events
            "isExpanded": "true"
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

    def fetch_event_details(self, event: Event) -> Optional[Event]:
        if not event.url:
            logger.error(f"Event {event.event_id} ({event.name}) has no URL. Skipping detail scrape.")
            return None
        
        detail_url = f"{self.base_url}{event.url}"
        
        detail_response = self.scraper.get(detail_url)
        if detail_response:
            try:
                event = self.parser.parse_event_details(detail_response.text, event)
                
                # Post-processing: Parse dates to ISO format
                event.start_date = self.parser.parse_date_to_iso(event.start_date)
                event.end_date = self.parser.parse_date_to_iso(event.end_date)
                
                # For multi-day events, calculate end_date from last race
                if event.races and len(event.races) > 0:
                    # Find the latest race date
                    race_dates = [r.date for r in event.races if r.date]
                    if race_dates:
                        # Dates are already in ISO format from parsing
                        event.end_date = max(race_dates)
                
                # Fetch and parse lists for each race
                for race in event.races:
                    # Fetch and parse Entry List
                    if race.entry_list_url:
                        entry_url = f"{self.base_url}{race.entry_list_url}" if race.entry_list_url.startswith('/') else race.entry_list_url
                        entry_resp = self.scraper.get(entry_url)
                        if entry_resp:
                            race.entry_list = self.parser.parse_list_count(entry_resp.text)

                    # Fetch and parse Start List
                    if race.start_list_url:
                        start_url = f"{self.base_url}{race.start_list_url}" if race.start_list_url.startswith('/') else race.start_list_url
                        start_resp = self.scraper.get(start_url)
                        if start_resp:
                            race.start_list = self.parser.parse_list_count(start_resp.text)

                    # Fetch and parse Result List
                    if race.result_list_url:
                        result_url = f"{self.base_url}{race.result_list_url}" if race.result_list_url.startswith('/') else race.result_list_url
                        result_resp = self.scraper.get(result_url)
                        if result_resp:
                            race.result_list = self.parser.parse_list_count(result_resp.text)
                
                return event
            except Exception as e:
                logger.error(f"Failed to parse details for {event.event_id}: {e}")
                return None
        else:
            logger.error(f"Failed to fetch details for {event.event_id}")
            return None
