import logging
import os

import yaml

from src.models import (
    Document,
    EntryDeadline,
    Event,
    Official,
    Organiser,
    Position,
    Race,
    Url,
)
from src.utils.date_and_time import format_iso_datetime

logger = logging.getLogger(__name__)


class ManualSource:
    """Source for manually added events from YAML files."""

    def __init__(self, base_dir: str):
        """Initializes the ManualSource.

        Args:
            base_dir: Base directory to scan for 'event.yaml' files.
        """
        self.base_dir = base_dir

    def load_events(self) -> list[Event]:
        """Recursively scans base_dir for event.yaml files and loads them.

        Returns:
            A list of Event objects parsed from YAML files.
        """
        events: list[Event] = []
        if not os.path.exists(self.base_dir):
            logger.warning(f"Manual events directory not found: {self.base_dir}")
            return events

        for root, _dirs, files in os.walk(self.base_dir):
            if "event.yaml" in files:
                yaml_path = os.path.join(root, "event.yaml")
                try:
                    event = self._parse_event_yaml(yaml_path)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.error(f"Failed to parse manual event at {yaml_path}: {e}")

        logger.info(f"Loaded {len(events)} manual events from {self.base_dir}")
        return events

    def _parse_event_yaml(self, yaml_path: str) -> Event | None:
        """Parses a single event.yaml file.

        Args:
            yaml_path: Path to the YAML file.

        Returns:
            The parsed Event object, or None if parsing fails or data is empty.
        """
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Resolve document paths relative to the yaml file
        event_dir = os.path.dirname(yaml_path)
        event_country = data.get("country")
        event_lat = data.get("lat")
        event_lon = data.get("lon")

        # Top-level URL becomes a "Website" in urls list
        urls = []
        if "url" in data and data["url"]:
            urls.append(Url(type="Website", url=data["url"]))

        documents = []
        for doc_data in data.get("documents", []):
            url = doc_data.get("url", "")
            if url.startswith("file://"):
                filename = url.replace("file://", "")
                # Path resolution: paths are resolved relative to the YAML file
                # to maintain portability within the manual_events directory.
                # But to serve it, we might need to know where it is.
                # Let's verify it exists
                file_path = os.path.join(event_dir, filename)
                if not os.path.exists(file_path):
                    logger.warning(f"Document not found: {file_path}")
                # We can store the full path for now, or relative path
                # from repo root. Using relative path from working directory
                # is safer for portability if running from root
                rel_path = os.path.relpath(file_path, os.getcwd())
                url = f"file://{rel_path}"

            documents.append(
                Document(
                    type=doc_data.get("type", "Other"),
                    title=doc_data.get("name", ""),
                    url=url,
                )
            )

        races = []
        for race_data in data.get("races", []):
            race_date = race_data.get("date")
            race_time = race_data.get("time")  # No default 00:00

            race_datetime = format_iso_datetime(race_date, race_time, event_country)

            race = Race(
                race_number=int(
                    race_data.get("race_number", 1)
                ),  # Default to 1 if missing
                name=race_data.get("name"),
                datetimez=race_datetime,
                discipline=race_data.get("discipline", "Middle"),  # Default discipline
                night_or_day=race_data.get("night_or_day", "day"),
            )

            # Race-level position if specified, else use event-level default
            if "lat" in race_data and "lon" in race_data:
                race.position = Position(
                    lat=float(race_data["lat"]), lng=float(race_data["lon"])
                )
            elif event_lat is not None and event_lon is not None:
                race.position = Position(lat=float(event_lat), lng=float(event_lon))

            races.append(race)

        organisers = []
        for org in data.get("organizers", []):
            if isinstance(org, str):
                organisers.append(Organiser(name=org, country_code=event_country))
            else:
                organisers.append(
                    Organiser(
                        name=org.get("name"),
                        country_code=org.get("country_code", event_country),
                    )
                )

        # Parse officials
        officials = []
        for off_data in data.get("officials", []):
            officials.append(
                Official(role=off_data.get("role"), name=off_data.get("name"))
            )

        # Parse entry deadlines
        deadlines = []
        for dl_data in data.get("entry_deadlines", []):
            deadlines.append(
                EntryDeadline(
                    type=dl_data.get("type", "normal"), datetimez=dl_data.get("date")
                )
            )

        start_date = data.get("start_date")
        end_date = data.get("end_date")

        event = Event(
            id=str(data.get("id")),
            name=data.get("name"),
            start_time=start_date,
            end_time=end_date,
            organisers=organisers,
            status=data.get("status", "Sanctioned"),
            original_status="Planned",
            races=races,
            officials=officials,
            classes=data.get("classes", []),
            urls=urls,
            documents=documents,
            information=data.get("information", data.get("info_text", "")),
            region=None if event_country else data.get("country"),
            entry_deadlines=deadlines,
        )

        return event
