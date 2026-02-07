#!/usr/bin/env python3
"""Quick start example for the MTBO Scraper.

This script demonstrates basic usage of the scraper to fetch MTBO events
from Eventor instances and save them to JSON.

This is a minimal, fast-running example that scrapes just a few recent events.
"""

import sys
from pathlib import Path

# Add parent directory to path to allow importing src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sources.eventor_source import EventorSource
from src.storage import Storage


def main() -> None:
    """Run a simple scraping example."""
    start_date = "2025-07-21"
    end_date = "2025-07-31"

    print(f"Scraping MTBO events from {start_date} to {end_date}")

    # Initialize storage
    storage = Storage("example_events.json")

    # Scrape from Eventor source
    source = EventorSource(country="SWE", base_url="https://eventor.orientering.se")

    # Fetch event list
    events = source.fetch_event_list(start_date, end_date)
    print(f"Found {len(events)} events from SWE")

    # Fetch details for the first event
    if events:
        detailed = source.fetch_event_details(events[0])
        if detailed:
            print(f"  - {detailed.name}")

            # Save to JSON
            storage.save({"SWE": [detailed]})
            print("\nSaved 1 event to example_events.json")


if __name__ == "__main__":
    main()
