from abc import ABC, abstractmethod
from typing import List, Optional
from src.models import Event

class BaseSource(ABC):
    """
    Abstract base class for event sources.
    """
    
    @abstractmethod
    def fetch_event_list(self, start_date: str, end_date: str) -> List[Event]:
        """
        Fetch the list of events for the given date range.
        
        :param start_date: Start date in YYYY-MM-DD format.
        :param end_date: End date in YYYY-MM-DD format.
        :return: List of Event objects (basic info).
        """
        pass

    @abstractmethod
    def fetch_event_details(self, event: Event) -> Optional[Event]:
        """
        Fetch detailed information for a specific event.
        
        :param event: The Event object to enrich.
        :return: The updated Event object with details, or None if failed.
        """
        pass
