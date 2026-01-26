import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Event, Source

logger = logging.getLogger(__name__)


class Storage:
    """Handles loading and saving of event data, using an Umbrella Index architecture.

    The root file (e.g. mtbo_events.json) acts as an index pointing
    to partitioned data files.
    """

    def __init__(self, root_path: str, data_dir: str = "data/events"):
        """Initializes the Storage instance.

        Args:
            root_path: The path to the Umbrella Index file (e.g. 'mtbo_events.json').
            data_dir: Base directory for event data files (default: 'data/events').
        """
        self.index_file = Path(root_path)
        # Default data root if not specified in index
        self.default_data_dir = Path(data_dir)

    def _load_index(self) -> dict[str, Any]:
        """Loads the index file if it exists."""
        if not self.index_file.exists():
            return {}

        try:
            with open(self.index_file, encoding="utf-8") as f:
                return json.load(f)  # type: ignore
        except Exception as e:
            logger.error(f"Failed to load index file: {e}")
            return {}

    def load(self) -> dict[str, dict[str, Any]]:
        """Loads events from all partitions defined in the index.

        Returns:
            A dictionary mapping event IDs to their raw dictionary representations.
        """
        index_data = self._load_index()
        events_map = {}

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
                        logger.error(f"Failed to load partition {full_path}: {e}")

        return events_map

    def save(self, events_by_source: dict[str, list[Event]]) -> list[dict[str, Any]]:
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
            new_ids = {e.id for e in source_events}

            # Special handling for MAN: Sync deletions
            if source_name == "MAN":
                current_manual_ids = [
                    eid
                    for eid in existing_map.keys()
                    if eid.startswith("MAN_") or "-" in eid  # Basic manual ID pattern
                ]

                # Refine heuristic: identify what actually identifies as MAN
                def _heuristic_is_man(eid: str) -> bool:
                    if (
                        eid.startswith("SWE_")
                        or eid.startswith("NOR_")
                        or eid.startswith("IOF_")
                    ):
                        return False
                    return True

                current_manual_ids = [
                    eid for eid in existing_map.keys() if _heuristic_is_man(eid)
                ]

                for eid in current_manual_ids:
                    if eid not in new_ids:
                        logger.info(f"Removing deleted manual event: {eid}")
                        del existing_map[eid]
                        source_changed = True

            for event in source_events:
                event_dict = event.to_dict()
                existing_event = existing_map.get(event.id)

                if existing_event != event_dict:
                    source_changed = True
                    existing_map[event.id] = event_dict

                all_new_events.append(event)

            # Update Source Metadata in Index
            meta = source_meta.get(source_name, {})
            last_updated = meta.get("last_updated_at", now_iso)

            if source_changed:
                last_updated = now_iso

            source_meta[source_name] = {
                "count": 0,  # Will calculate total below
                "last_updated_at": last_updated,
            }

        # 3. Group by Year and Calculate Source Totals
        events_by_year: dict[str, list[dict[str, Any]]] = {}
        source_counts: dict[str, int] = {name: 0 for name in source_meta.keys()}

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
                # If MAN is not in config but events found, initialize it?
                # Actually, main.py should have MAN in configs.
                source_counts["MAN"] = 1
            else:
                # Fallback: if source not in config, we don't track its meta here
                # but we could. For now, just focus on configured sources.
                pass

            # Year grouping
            start_time = e_data.get("start_time", "")
            if start_time:
                year = start_time[:4]
            else:
                logger.error(f"Event {e_id} has no start_time.")
                raise ValueError(f"Event {e_id} has no start_time")

            if year not in events_by_year:
                events_by_year[year] = []
            events_by_year[year].append(e_data)

        # Update final counts in source_meta
        for name, count in source_counts.items():
            if name in source_meta:
                source_meta[name]["count"] = count

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

            # Sort
            sorted_events = sorted(
                year_events,
                key=lambda x: (x.get("start_time", ""), x.get("id", "")),
            )

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
                logger.info(f"Updated partition {year} at {file_path}")

            # Update Partition Metadata in Index
            # Preserve last_updated_at if no change, else update it
            existing_meta = partitions.get(year, {})
            last_updated = existing_meta.get("last_updated_at", now_iso)

            if content_changed:
                last_updated = now_iso

            partitions[year] = {
                "path": str(file_path),
                "count": len(sorted_events),
                "last_updated_at": last_updated,
            }

            all_saved_events.extend(sorted_events)

        # 6. Save Umbrella Index
        # Update always to record "last_scraped_at" (Consumer requirement)
        new_index = {
            "schema_version": "2.0",
            "last_scraped_at": now_iso,
            "data_root": str(self.default_data_dir),
            "partitions": partitions,
            "sources": source_meta,
        }

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(new_index, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info(f"Updated index file at {self.index_file}")

        return all_saved_events
