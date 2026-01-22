import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from .models import Event, EventListWrapper, Meta, Source

logger = logging.getLogger(__name__)


class Storage:
    """Handles loading and saving of event data to a JSON file."""

    def __init__(self, filepath: str):
        """Initializes the Storage instance.

        Args:
            filepath: The path to the JSON file.
        """
        self.filepath = filepath

    def load(self) -> dict[str, dict[str, Any]]:
        """Loads raw event dicts from the JSON file.

        Returns:
            A dictionary mapping event IDs to their raw dictionary representations.
            Returns an empty dictionary if the file does not exist or fails to load.

        Example:
            >>> storage = Storage("mtbo_events.json")
            >>> events_map = storage.load()
            >>> if events_map:
            ...     print(f"Loaded {len(events_map)} events")
        """
        if not os.path.exists(self.filepath):
            return {}

        try:
            with open(self.filepath, encoding="utf-8") as f:
                data = json.load(f)

                events_map = {}

                # Check if new format (dict)
                if isinstance(data, dict) and "events" in data:
                    for item in data["events"]:
                        if "id" in item:
                            events_map[item["id"]] = item

                return events_map
        except Exception as e:
            logger.error(f"Failed to load storage: {e}")
            return {}

    def save(self, events: list[Event]) -> list[dict[str, Any]]:
        """Saves a list of Event objects to the JSON file, merging with existing data.

        Args:
            events: A list of Event objects to save.

        Returns:
            A list of dicts representing all events (merged and broken down)
            currently in storage. Returns an empty list on failure.

        Example:
            >>> from src.models import Event
            >>> storage = Storage("mtbo_events.json")
            >>> events = [Event(id="SWE_123", name="Test Event", ...)]
            >>> saved_events = storage.save(events)
            >>> print(f"Saved {len(saved_events)} events")
        """
        existing_map = self.load()

        # Load existing create_time to preserve if no changes happen
        original_create_time = datetime.now(UTC).isoformat()
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, encoding="utf-8") as f:
                    data = json.load(f)
                    if "create_time" in data:
                        original_create_time = data["create_time"]
            except Exception:
                pass

        # Update/Overwrite with new scraped objects
        # We assume that simply overwriting with new data is what we want.
        # Detection of "meaningful change" is done by comparing the final JSON output.
        for event in events:
            existing_map[event.id] = event.to_dict()

        # Convert to list and sort
        sorted_events_list = sorted(
            existing_map.values(),
            key=lambda x: (x.get("start_time", ""), x.get("id", "")),
        )

        # Sources to scrape
        sources = [
            Source(
                country_code="SWE",
                name="Swedish Eventor",
                url="https://eventor.orientering.se",
            ),
            Source(
                country_code="IOF",
                name="IOF Eventor",
                url="https://eventor.orienteering.org",
            ),
            Source(
                country_code="NOR",
                name="Norwegian Eventor",
                url="https://eventor.orientering.no",
            ),
        ]

        # Tentatively use CURRENT time as create_time
        now_iso = datetime.now(UTC).isoformat()

        # Construct proposed output
        wrapper = EventListWrapper(
            schema_version="1.0",
            create_time=now_iso,
            creator="MTBO Scraper",
            meta=Meta(sources=sources),
            events=[],
        )
        output_dict = wrapper.to_dict()
        output_dict["events"] = sorted_events_list

        # Compare with existing file content
        try:
            current_content = ""
            if os.path.exists(self.filepath):
                with open(self.filepath, encoding="utf-8") as f:
                    current_content = f.read()

            # Check if ONLY time changed
            # To do this robustly, we can revert 'create_time' to original and compare.
            if os.path.exists(self.filepath):
                # Try generating content with ORIGINAL time
                wrapper.create_time = original_create_time
                output_dict["create_time"] = original_create_time
                test_content = (
                    json.dumps(output_dict, indent=2, ensure_ascii=False) + "\n"
                )

                if test_content == current_content:
                    logger.info("No content changes detected. Skipping file update.")
                    return sorted_events_list

            # If we are here, there ARE content changes.
            # We must save using the NEW time (now_iso), which we set
            # initially but reverted for the test. So reset it back.
            output_dict["create_time"] = now_iso
            new_content_with_new_time = (
                json.dumps(output_dict, indent=2, ensure_ascii=False) + "\n"
            )

            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(new_content_with_new_time)
            logger.info(f"Saved {len(sorted_events_list)} events to {self.filepath}")
            return sorted_events_list
        except Exception as e:
            logger.error(f"Failed to save storage: {e}")
            return []
