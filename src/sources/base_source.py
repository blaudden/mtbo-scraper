from abc import ABC, abstractmethod

from src.models import Event


class BaseSource(ABC):
    """Abstract base class for event sources."""

    @abstractmethod
    def fetch_event_list(self, start_date: str, end_date: str) -> list[Event]:
        """Fetches the list of events for the given date range.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            A list of Event objects (basic info).
        """
        pass

    @abstractmethod
    def fetch_event_details(self, event: Event) -> Event | None:
        """Fetches detailed information for a specific event.

        Args:
            event: The Event object to enrich.

        Returns:
            The updated Event object with details, or None if failed.
        """
        pass
