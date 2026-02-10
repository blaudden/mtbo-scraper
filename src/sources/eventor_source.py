import os
from datetime import UTC, datetime
from typing import TypedDict

import structlog

from src.event_filter import OringenFilter
from src.models import Event, Race, Url
from src.scraper import Scraper
from src.sources.base_source import BaseSource
from src.sources.eventor_parser import EventorParser
from src.utils.date_and_time import parse_date_to_iso
from src.utils.fingerprint import Participant

logger = structlog.get_logger(__name__)

# Type aliases for YAML start list export.
# Cannot use TypedDict because the YAML key "class" is a Python reserved word.
StartListParticipant = dict[str, str | int | None]


class StartListData(TypedDict):
    """Dictionary representation of a race start list for YAML export."""

    race_number: int
    participants: list[StartListParticipant]


class EventorSource(BaseSource):
    """Source implementation for Eventor (SWE, NOR, IOF, etc.)."""

    def __init__(
        self,
        country: str,
        base_url: str,
        output_dir: str = "data/events",
        known_fingerprints: dict[str, set[str]] | None = None,
        refresh: bool = False,
        scraper: Scraper | None = None,
    ):
        """Initializes the EventorSource.

        Args:
            country: The country code (e.g. "SWE").
            base_url: The base URL of the Eventor instance.
            output_dir: Base directory for output files (default: "data/events").
            known_fingerprints: Dictionary mapping year (str) to set of existing
                fingerprints.
            refresh: Whether to force refresh of startlists.
            scraper: An optional shared Scraper instance.
        """
        self.country = country
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir
        self.known_fingerprints = known_fingerprints or {}
        self.refresh = refresh
        self.scraper = scraper or Scraper()
        self.parser = EventorParser()

    def fetch_event_list(self, start_date: str, end_date: str) -> list[Event]:
        """Fetches the list of events for the given date range.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            A list of Event objects with basic information found on the list page.
        """
        logger.info("scraping_source", country=self.country, base_url=self.base_url)

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
            logger.error("event_list_fetch_failed", country=self.country)
            return []

        events = self.parser.parse_event_list(
            response.text, self.country, self.base_url
        )
        logger.info("events_found", count=len(events), country=self.country)
        return events

    def _fetch_race_list_items(self, race: Race, list_type: str) -> list[Participant]:
        """Fetches and parses a specific list type (Entry/Start/Result) for a race."""
        url_obj = next((u for u in race.urls if u.type == list_type), None)
        if not url_obj:
            return []

        full_url = (
            f"{self.base_url}{url_obj.url}"
            if url_obj.url.startswith("/")
            else url_obj.url
        )

        resp = self.scraper.get(full_url)
        if not resp:
            return []

        return self.parser.parse_participant_list(resp.text)

    def _update_race_counts(
        self, race: Race, list_type: str, items: list[Participant]
    ) -> None:
        """Aggregates class counts and updates the race object."""
        counts: dict[str, int] = {}
        for i in items:
            c = i.get("class_name", "Unknown")
            counts[c] = counts.get(c, 0) + 1

        if list_type == "EntryList":
            race.entry_counts = counts
        elif list_type == "StartList":
            race.start_counts = counts
        elif list_type == "ResultList":
            race.result_counts = counts

    def _generate_race_fingerprints(
        self,
        race: Race,
        lists: list[list[Participant]],
        allowed_classes: set[str] | None = None,
    ) -> None:
        """Generates fingerprints for the race based on participant lists.

        Args:
            race: The race to update.
            lists: Participant lists (entries, starts, results).
            allowed_classes: If provided, only fingerprint participants
                whose class_name is in this set.
        """
        from src.utils.fingerprint import Fingerprinter

        if not lists:
            return

        unique_participants = Fingerprinter.merge_participants(lists)

        # Filter to allowed classes (e.g. MTBO only for O-Ringen)
        if allowed_classes is not None:
            unique_participants = [
                p
                for p in unique_participants
                if p.get("class_name", "") in allowed_classes
            ]

        if not unique_participants:
            return

        # Use known fingerprints for the current year if available
        year = race.datetimez[:4]
        known_hashes = self.known_fingerprints.get(year)

        race.fingerprints = Fingerprinter.generate_fingerprints(
            unique_participants, known_hashes
        )

    def _collect_start_list_data(
        self, race: Race, starts: list[Participant]
    ) -> StartListData:
        """Formats start list data for YAML export."""
        return StartListData(
            race_number=race.race_number,
            participants=[
                StartListParticipant(
                    start_number=p.get("start_number"),
                    name=p.get("name", ""),
                    club=p.get("club", ""),
                    **{"class": p.get("class_name", "")},
                )
                for p in starts
            ],
        )

    def _save_start_list_yaml(
        self, event: Event, race_number: int, race_data: StartListData
    ) -> tuple[bool, str]:
        """Saves a single race's start list to YAML and returns (changed, filepath)."""
        import yaml

        year = event.start_time[:4] if event.start_time else "unknown"
        output_dir = f"{self.output_dir}/{year}"
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{event.id}_startlist_{race_number}.yaml"
        filepath = os.path.join(output_dir, filename)

        # Serialize to string for comparison
        # allow_unicode=True is important for Swedish names
        new_yaml_str = yaml.dump(race_data, allow_unicode=True)

        content_changed = True
        if os.path.exists(filepath):
            try:
                with open(filepath, encoding="utf-8") as f:
                    old_yaml_str = f.read()
                if old_yaml_str == new_yaml_str:
                    content_changed = False
            except Exception:
                pass

        if content_changed:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_yaml_str)

        return content_changed, filepath

    def _update_local_file_url(self, race: Race, filepath: str, changed: bool) -> None:
        """Updates or adds the LocalStartList URL for the race."""
        now_iso = datetime.now(UTC).isoformat()

        local_url_obj = next((u for u in race.urls if u.type == "LocalStartList"), None)

        if not local_url_obj:
            local_url_obj = Url(
                type="LocalStartList",
                url=filepath,
                last_updated_at=now_iso,
            )
            race.urls.append(local_url_obj)
        elif changed:
            local_url_obj.last_updated_at = now_iso

    def _should_download_start_list(self, event: Event) -> bool:
        """Determines if a local start list in YAML format should be generated."""
        # Swedish Cup events
        if self.country == "SWE":
            series_link = next((u for u in event.urls if u.type == "Series"), None)
            if series_link and series_link.title:
                title = series_link.title.lower()
                if "svenska" in title and "cup" in title:
                    return True

        # IOF events with specific championship types
        if self.country == "IOF":
            # Download for: Junior World Championships, World Championships,
            # World Cup, World Masters
            championship_types = {
                "Junior World Championships",
                "World Championships",
                "World Cup",
                "World Masters",
            }
            # Check if any championship type is in event.types
            if any(t in championship_types for t in event.types):
                return True

        return False

    def _should_fetch_counts(self, event: Event) -> bool:
        """Determines if entry/start/result counts should be fetched.

        IOF International events only download startlists, no counts/fingerprints.
        All other events fetch counts.
        """
        if self.country == "IOF":
            # IOF events with these types only download startlists
            championship_types = {
                "Junior World Championships",
                "World Championships",
                "World Cup",
                "World Masters",
            }
            if any(t in championship_types for t in event.types):
                return False
        return True

    def fetch_and_process_lists(
        self, event: Event, allowed_classes: set[str] | None = None
    ) -> None:
        """Fetches Start/Result/Entry lists, updates counts, fingerprints,
        and saves YAML.

        Args:
            event: The event to process.
            allowed_classes: If provided, only fingerprint participants
                whose class_name is in this set (used for O-Ringen filtering).
        """
        # Determine if we should save Start Lists to YAML
        save_yaml = self._should_download_start_list(event)
        # Determine if we should fetch counts/fingerprints
        fetch_counts = self._should_fetch_counts(event)

        for race in event.races:
            # 1. Fetch Lists
            starts = None
            if save_yaml:
                # Decide if we need to fetch starts from Eventor or if local is enough
                local_url = next(
                    (u for u in race.urls if u.type == "LocalStartList"), None
                )

                # Fetch if refresh requested OR no local file
                # OR recent event (within 7 days of start)
                should_fetch = self.refresh or not local_url

                if not should_fetch:
                    # Check if "recent"
                    try:
                        # race.datetimez is ISO: YYYY-MM-DDTHH:MM:SS+HH:MM
                        race_date = datetime.fromisoformat(race.datetimez)
                        now = datetime.now(race_date.tzinfo)
                        # Fetch if event is in the future or started < 7 days ago
                        if (race_date - now).days > -7:
                            should_fetch = True
                    except Exception:
                        should_fetch = True  # Fallback to fetch if date parsing fails

                if should_fetch:
                    starts = self._fetch_race_list_items(race, "StartList")

            # Only fetch entry/result lists if we need counts
            if fetch_counts:
                entries = self._fetch_race_list_items(race, "EntryList")
                results = self._fetch_race_list_items(race, "ResultList")

                # 2. Update Counts
                if entries:
                    self._update_race_counts(race, "EntryList", entries)
                # Ensure 'starts' are available for counts and fingerprints
                # (even if YAML generation is skipped for this race).
                if not starts and fetch_counts:
                    starts = self._fetch_race_list_items(race, "StartList")

                if starts:
                    self._update_race_counts(race, "StartList", starts)
                if results:
                    self._update_race_counts(race, "ResultList", results)

                # 3. Fingerprinting (SWE and NOR)
                if self.country in ("SWE", "NOR"):
                    valid_lists = [lst for lst in [entries, starts, results] if lst]
                    self._generate_race_fingerprints(
                        race, valid_lists, allowed_classes=allowed_classes
                    )

            # 4. Save Start List YAML for this race
            if save_yaml and starts:
                race_data = self._collect_start_list_data(race, starts)
                changed, filepath = self._save_start_list_yaml(
                    event, race.race_number, race_data
                )
                self._update_local_file_url(race, filepath, changed)

    def fetch_event_details(self, event: Event) -> Event | None:
        """Fetches detailed information for a specific event.

        Args:
            event: The Event object to enrich.

        Returns:
            The enriched Event object, or None if fetching details failed.
        """
        if not event.url:
            logger.error(
                "event_missing_url",
                event_id=event.id,
                event_name=event.name,
            )
            return None

        detail_url = f"{self.base_url}{event.url}"

        detail_response = self.scraper.get(detail_url)
        if detail_response:
            try:
                event = self.parser.parse_event_details(
                    detail_response.text, event, self.base_url
                )

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
                # Step 1: Filter O-Ringen umbrella classes before
                # counts/fingerprints so participants are scoped correctly.
                of = OringenFilter(event)
                of.filter_classes()
                # Fetch and process lists (counts, fingerprints, YAML)
                self.fetch_and_process_lists(event, allowed_classes=of.allowed_classes)
                # Step 2: Filter counts and add tags.
                of.finalize()

                return event
            except Exception as e:
                logger.error(
                    "event_details_parse_failed",
                    event_id=event.id,
                    error=str(e),
                )
                return None
        else:
            logger.error("event_details_fetch_failed", event_id=event.id)
            return None
