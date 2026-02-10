import json
from datetime import UTC, datetime
from pathlib import Path

import structlog

from .models import (
    Event,
    EventDict,
    IndexDict,
    IndexPartitionDict,
    IndexSourceDict,
    RaceDict,
    Source,
    Url,
    UrlDict,
)

logger = structlog.get_logger(__name__)


class Storage:
    """Handles loading and saving of event data, using an Umbrella Index architecture.

    The root file (e.g. data/events/mtbo_events.json) acts as an index pointing
    to partitioned data files.
    """

    def __init__(self, root_path: str, data_dir: str = "data/events"):
        """Initializes the Storage instance.

        Args:
            root_path: Path to the Umbrella Index file
                (e.g. 'data/events/mtbo_events.json').
            data_dir: Base directory for event data files (default: 'data/events').
        """
        self.index_file = Path(root_path)
        # Default data root if not specified in index
        self.default_data_dir = Path(data_dir)
        self.schema_version = "2.0"

    def _load_index(self) -> IndexDict:
        """Loads the index file if it exists."""
        if not self.index_file.exists():
            return IndexDict(
                schema_version="2.0",
                last_scraped_at="",
                data_root=str(self.default_data_dir),
                partitions={},
                sources={},
            )

        try:
            with open(self.index_file, encoding="utf-8") as f:
                return json.load(f)  # type: ignore
        except Exception as e:
            logger.error("index_load_failed", error=str(e), path=str(self.index_file))
            return IndexDict(
                schema_version=self.schema_version,
                last_scraped_at="",
                data_root=str(self.default_data_dir),
                partitions={},
                sources={},
            )

    def load(self) -> dict[str, EventDict]:
        """Loads events from all partitions defined in the index.

        Returns:
            A dictionary mapping event IDs to their raw dictionary representations.
        """
        index_data = self._load_index()
        events_map: dict[str, EventDict] = {}

        # Handle Umbrella Index
        if "partitions" in index_data:
            for _, meta in index_data["partitions"].items():
                path_str = meta.get("path")
                if not path_str:
                    continue

                full_path = Path(path_str)
                # If path is relative, it is relative to CWD
                if full_path.exists():
                    try:
                        with open(full_path, encoding="utf-8") as f:
                            partition_data = json.load(f)
                            # Expecting {"events": [...]}
                            p_events = partition_data.get("events", [])
                            for e in p_events:
                                if "id" in e:
                                    events_map[e["id"]] = e
                    except Exception as e:
                        logger.error(
                            "partition_load_failed", error=str(e), path=str(full_path)
                        )

        return events_map

    def save(self, events_by_source: dict[str, list[Event]]) -> list[EventDict]:
        """Saves events, splitting them into year-based partitions and updating
        the Index.

        Args:
            events_by_source: A dictionary mapping source names to lists of events.

        Returns:
            A list of all newly merged and sorted event dictionaries.
        """
        # 1. Load existing state
        existing_map = self.load()
        now_iso = datetime.now(UTC).isoformat()
        current_index = self._load_index()

        # Track which sources have changed
        source_meta = current_index.get("sources", {})

        # 2. Process each source
        all_new_events = []
        for source_name, source_events in events_by_source.items():
            source_changed = False

            for event in source_events:
                existing_event = existing_map.get(event.id)

                try:
                    self._process_event_timestamps(event, existing_event)
                except Exception as e:
                    logger.error(
                        "timestamp_merge_failed", event_id=event.id, error=str(e)
                    )
                    raise

                event_dict = event.to_dict()
                if existing_event != event_dict:
                    source_changed = True
                    existing_map[event.id] = event_dict

            all_new_events.extend(source_events)

            # Update Source Metadata in Index
            meta = source_meta.get(source_name) or IndexSourceDict(
                count=0, last_updated_at=now_iso
            )
            last_updated = meta.get("last_updated_at", now_iso)

            if source_changed:
                last_updated = now_iso

            source_meta[source_name] = {
                "count": 0,  # Will calculate total below
                "last_updated_at": last_updated,
            }

        # 3. Group by Year and Calculate Source Totals
        events_by_year: dict[str, list[EventDict]] = {}
        source_counts: dict[str, int] = dict.fromkeys(source_meta.keys(), 0)

        def _identify_source(eid: str) -> str:
            if eid.startswith("SWE_"):
                return "SWE"
            if eid.startswith("NOR_"):
                return "NOR"
            if eid.startswith("IOF_"):
                return "IOF"
            return "MAN"

        for e_id, e_data in existing_map.items():
            # Source counting
            src = _identify_source(e_id)
            if src in source_counts:
                source_counts[src] += 1
            elif src == "MAN" and "MAN" not in source_counts:
                # Track MAN count even if not explicitly in active config for this run
                source_counts["MAN"] = 1
            else:
                # Do not track metadata for unconfigured sources
                pass

            # Year grouping
            start_time = e_data.get("start_time", "")
            if start_time:
                year = start_time[:4]
            else:
                logger.error("event_missing_start_time", event_id=e_id)
                raise ValueError(f"Event {e_id} has no start_time")

            if year not in events_by_year:
                events_by_year[year] = []
            events_by_year[year].append(e_data)

        # Update final counts in source_meta
        for name, count in source_counts.items():
            if name in source_meta:
                source_meta[name] = IndexSourceDict(
                    count=count, last_updated_at=source_meta[name]["last_updated_at"]
                )

        # 4. Prepare Index Structure
        # Ensure 'partitions' dict exists
        partitions = current_index.get("partitions", {})

        # 5. Process Each Partition
        all_saved_events = []

        # Common Metadata for wrappers
        sources_meta = [
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

        for year, year_events in events_by_year.items():
            year_dir = self.default_data_dir / year
            year_dir.mkdir(parents=True, exist_ok=True)
            file_path = year_dir / "events.json"

            # Sort by ID for stable git diffs
            sorted_events = sorted(year_events, key=lambda x: x.get("id", ""))

            # Minimal wrapper as per plan: just data + meta, NO timestamps in child file
            output_dict = {
                "schema_version": "2.0",
                "meta": {
                    "sources": [
                        {"country_code": s.country_code, "name": s.name, "url": s.url}
                        for s in sources_meta
                    ]
                },
                "events": sorted_events,
            }

            # Check for changes
            content_changed = False
            if file_path.exists():
                try:
                    with open(file_path, encoding="utf-8") as f:
                        old_content = json.load(f)
                    if old_content != output_dict:
                        content_changed = True
                except Exception:
                    content_changed = True
            else:
                content_changed = True

            if content_changed:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(output_dict, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                logger.info(
                    "partition_updated",
                    year=year,
                    path=str(file_path),
                    count=len(sorted_events),
                )

            # Update Partition Metadata in Index
            # Preserve last_updated_at if no change, else update it
            existing_meta = partitions.get(year) or IndexPartitionDict(
                path=str(file_path), count=0, last_updated_at=""
            )
            last_updated = existing_meta.get("last_updated_at", now_iso)

            if content_changed:
                last_updated = now_iso

            partitions[year] = IndexPartitionDict(
                path=str(file_path),
                count=len(sorted_events),
                last_updated_at=last_updated,
            )

            all_saved_events.extend(sorted_events)

        # 6. Save Umbrella Index
        # Update always to record "last_scraped_at" (Consumer requirement)
        new_index = IndexDict(
            schema_version="2.0",
            last_scraped_at=now_iso,
            data_root=str(self.default_data_dir),
            partitions=partitions,
            sources=source_meta,
        )

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(new_index, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info("index_updated", path=str(self.index_file))

        return all_saved_events

    def purge(self, event_ids: list[str]) -> list[str]:
        """Removes events by ID from partitioned data and updates the index.

        Also deletes associated startlist YAML files.

        Args:
            event_ids: List of event IDs to remove (e.g. ["SWE_1351"]).

        Returns:
            List of event IDs that were actually found and removed.
        """
        ids_to_remove = set(event_ids)
        removed: list[str] = []
        index_data = self._load_index()
        partitions = index_data.get("partitions", {})
        now_iso = datetime.now(UTC).isoformat()

        for year, meta in partitions.items():
            path_str = meta.get("path")
            if not path_str:
                continue

            full_path = Path(path_str)
            if not full_path.exists():
                continue

            with open(full_path, encoding="utf-8") as f:
                partition_data = json.load(f)

            events = partition_data.get("events", [])
            original_count = len(events)
            filtered = [e for e in events if e.get("id") not in ids_to_remove]
            purged_ids = [e["id"] for e in events if e.get("id") in ids_to_remove]

            if len(filtered) < original_count:
                removed.extend(purged_ids)
                partition_data["events"] = filtered
                with open(full_path, "w", encoding="utf-8") as f:
                    json.dump(partition_data, f, indent=2, ensure_ascii=False)
                    f.write("\n")

                # Update partition metadata
                partitions[year] = IndexPartitionDict(
                    path=path_str,
                    count=len(filtered),
                    last_updated_at=now_iso,
                )
                logger.info(
                    "events_purged",
                    year=year,
                    purged=purged_ids,
                    remaining=len(filtered),
                )

        # Delete associated startlist YAML files
        for eid in removed:
            for yaml_dir in self.default_data_dir.rglob(f"{eid}_startlist_*.yaml"):
                yaml_dir.unlink()
                logger.info("startlist_deleted", path=str(yaml_dir))

        # Update index
        index_data["partitions"] = partitions
        index_data["last_scraped_at"] = now_iso
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        return removed

    def _process_event_timestamps(
        self, event: Event, existing_event: EventDict | None
    ) -> None:
        """Updates timestamps for the event and its races using existing data."""
        # Event URLs
        old_event_urls = existing_event.get("urls", []) if existing_event else []
        event.urls = self._merge_url_timestamps(event.urls, old_event_urls)

        # Merge Race URLs, build a map of races by race_number and
        # then merge their urls
        old_races: dict[int, RaceDict] = {}
        if existing_event:
            for old_race in existing_event.get("races", []):
                race_num = old_race.get("race_number")
                if race_num is not None:
                    old_races[race_num] = old_race

        for race in event.races:
            old_r_dict = old_races.get(race.race_number)
            old_urls = old_r_dict.get("urls", []) if old_r_dict else []
            race.urls = self._merge_url_timestamps(race.urls, old_urls)

    def _merge_url_timestamps(
        self, new_url_objs: list[Url], old_url_dicts: list[UrlDict]
    ) -> list[Url]:
        """Merges timestamps from old URLs into new Url objects if content matches.

        Match criteria: Type AND Url AND Title.
        If matched, copy last_updated_at from old to new.
        If not matched (or new is None), set to now.
        """
        now_iso = datetime.now(UTC).isoformat()

        for new_u in new_url_objs:
            # If the parser/source already set a timestamp (e.g. local file), keep it.
            if new_u.last_updated_at:
                continue

            # Look for match in old_url_dicts
            matched_old = None
            for old_u in old_url_dicts:
                if (
                    old_u.get("type") == new_u.type
                    and old_u.get("url") == new_u.url
                    and old_u.get("title") == new_u.title
                ):
                    matched_old = old_u
                    break

            if matched_old:
                # Only copy old timestamp if it's not null
                old_ts = matched_old.get("last_updated_at")
                new_u.last_updated_at = old_ts if old_ts else now_iso
            else:
                new_u.last_updated_at = now_iso

        return new_url_objs
