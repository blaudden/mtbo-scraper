"""Event quality report tool.

Analyzes event data for anomalies, groups O-Ringen events with
their dedicated MTBO counterparts, and shows entry statistics.

Usage:
    uv run python scripts/event_report.py
    uv run python scripts/event_report.py --start-date 2020-01-01
    uv run python scripts/event_report.py --all
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.event_filter import (
    MTBO_KEYWORDS,
    SKIP_LIST,
    TAG_CLASSES_FILTERED,
    TAG_EVENT_SKIP,
)


@dataclass
class EventSummary:
    """Lightweight event summary for reporting."""

    event_id: str
    name: str
    start_time: str
    tags: list[str]
    types: list[str]
    classes: list[str]
    total_entries: int
    total_starts: int
    total_results: int
    link: str


def _eventor_link(event_id: str) -> str:
    """Build an Eventor link from an event ID."""
    parts = event_id.split("_", 1)
    if len(parts) != 2:
        return ""
    prefix, numeric_id = parts
    base_urls = {
        "SWE": "https://eventor.orientering.se/Events/Show/",
        "NOR": "https://eventor.orientering.no/Events/Show/",
        "IOF": "https://eventor.orienteering.org/Events/Show/",
    }
    base = base_urls.get(prefix, "")
    if not base:
        return ""
    return f"{base}{numeric_id}"


def _sum_counts(counts: dict[str, int] | None) -> int:
    """Sum all values in a counts dict, returning 0 if None."""
    if not counts:
        return 0
    return sum(counts.values())


def _load_events(data_dir: Path) -> list[dict[str, object]]:
    """Load all events from year-partitioned JSON files."""
    all_events: list[dict[str, object]] = []
    for year_dir in sorted(data_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        events_file = year_dir / "events.json"
        if not events_file.exists():
            continue
        with open(events_file) as f:
            data = json.load(f)
        for ev in data.get("events", []):
            all_events.append(ev)
    return all_events


def _to_summary(ev: dict[str, object]) -> EventSummary:
    """Convert a raw event dict to an EventSummary.

    For O-Ringen umbrella events (has tags + O-Ringen in name), infers
    ClassesFiltered/EventSkip status by checking if any classes contain
    MTBO keywords — even if the tags haven't been applied yet.
    """
    event_id = str(ev.get("id", ""))
    name = str(ev.get("name", ""))
    races = ev.get("races", [])
    total_entries = 0
    total_starts = 0
    total_results = 0
    if isinstance(races, list):
        for race in races:
            if isinstance(race, dict):
                total_entries += _sum_counts(race.get("entry_counts"))
                total_starts += _sum_counts(race.get("start_counts"))
                total_results += _sum_counts(race.get("result_counts"))

    tags = ev.get("tags", [])
    tags = list(tags) if isinstance(tags, list) else []
    classes = ev.get("classes", [])
    classes = list(classes) if isinstance(classes, list) else []
    types = ev.get("types", [])

    # Infer O-Ringen umbrella status from classes if tags not yet applied
    if (
        _is_oringen(name)
        and tags
        and TAG_CLASSES_FILTERED not in tags
        and TAG_EVENT_SKIP not in tags
    ):
        mtbo_classes = [
            c for c in classes if any(kw in c.lower() for kw in MTBO_KEYWORDS)
        ]
        if mtbo_classes:
            tags = tags + [TAG_CLASSES_FILTERED]
        elif classes:
            tags = tags + [TAG_EVENT_SKIP]
        else:
            # No classes at all — can't determine
            tags = tags + [TAG_EVENT_SKIP]

    return EventSummary(
        event_id=event_id,
        name=name,
        start_time=str(ev.get("start_time", "")),
        tags=tags,
        types=types if isinstance(types, list) else [],
        classes=classes,
        total_entries=total_entries,
        total_starts=total_starts,
        total_results=total_results,
        link=_eventor_link(event_id),
    )


def _is_oringen(name: str) -> bool:
    """Check if an event name is an O-Ringen event."""
    return bool(re.search(r"o-ringen|oringen", name, re.IGNORECASE))


def _has_mtbo_signal(s: EventSummary) -> bool:
    """Check MTBO signal from an EventSummary."""
    name_lower = s.name.lower()
    if any(kw in name_lower for kw in MTBO_KEYWORDS):
        return True
    classes_lower = " ".join(c.lower() for c in s.classes)
    return any(kw in classes_lower for kw in MTBO_KEYWORDS)


def _format_counts(s: EventSummary) -> str:
    """Format entry/start/result counts as a compact string."""
    parts: list[str] = []
    if s.total_entries:
        parts.append(f"entries={s.total_entries}")
    if s.total_starts:
        parts.append(f"starts={s.total_starts}")
    if s.total_results:
        parts.append(f"results={s.total_results}")
    return ", ".join(parts) if parts else "no counts"


def _print_event(s: EventSummary, indent: str = "  ") -> None:
    """Print a single event summary."""
    markers: list[str] = []
    if s.event_id in SKIP_LIST:
        markers.append("[SKIP]")
    if TAG_CLASSES_FILTERED in s.tags:
        markers.append("[ClassesFiltered]")
    if TAG_EVENT_SKIP in s.tags:
        markers.append("[EventSkip]")
    if _has_mtbo_signal(s):
        markers.append("✓MTBO")

    marker_str = " ".join(markers)
    print(f"{indent}{s.event_id} {marker_str}")
    print(f"{indent}  {s.name}")
    print(f"{indent}  date={s.start_time}  tags={s.tags}  types={s.types}")
    print(f"{indent}  {_format_counts(s)}")
    if s.classes:
        preview = s.classes[:8]
        suffix = f" ... +{len(s.classes) - 8} more" if len(s.classes) > 8 else ""
        print(f"{indent}  classes={preview}{suffix}")
    if s.link:
        print(f"{indent}  {s.link}")
    print()


def _print_oringen_tree(summaries: list[EventSummary]) -> None:
    """Print O-Ringen events grouped by year."""
    oringen = [s for s in summaries if _is_oringen(s.name)]
    if not oringen:
        return

    print("=" * 70)
    print("O-RINGEN TREE VIEW")
    print("=" * 70)

    by_year: dict[str, list[EventSummary]] = {}
    for s in oringen:
        year = s.start_time[:4] if s.start_time else "????"
        by_year.setdefault(year, []).append(s)

    for year in sorted(by_year.keys()):
        events = by_year[year]

        # Classify into mutually exclusive categories
        event_skip: list[EventSummary] = []
        classes_filtered: list[EventSummary] = []
        mtbo: list[EventSummary] = []

        for e in events:
            if TAG_EVENT_SKIP in e.tags:
                event_skip.append(e)
            elif TAG_CLASSES_FILTERED in e.tags:
                classes_filtered.append(e)
            else:
                mtbo.append(e)

        print(f"\n── {year} {'─' * 60}")

        for e in event_skip:
            _print_event(e, indent="  ⛔ ")
        for e in classes_filtered:
            _print_event(e, indent="  📋 ")
        for m in mtbo:
            _print_event(m, indent="  🚲 ")

    print()


def _print_skip_list_report(summaries: list[EventSummary]) -> None:
    """Print events in the skip list."""
    skipped = [s for s in summaries if s.event_id in SKIP_LIST]
    if not skipped:
        return

    print("=" * 70)
    print(f"SKIP LIST ({len(skipped)} events excluded from scrape)")
    print("=" * 70)
    for s in sorted(skipped, key=lambda x: x.start_time):
        _print_event(s)


def _detect_anomaly(s: EventSummary) -> bool:
    """Check if an event summary is anomalous."""
    if not s.tags:
        return False
    if TAG_CLASSES_FILTERED in s.tags or TAG_EVENT_SKIP in s.tags:
        return False
    return not _has_mtbo_signal(s)


def _print_anomaly_report(summaries: list[EventSummary]) -> None:
    """Print suspect events not in skip list and not O-Ringen."""
    anomalies = [
        s
        for s in summaries
        if _detect_anomaly(s)
        and s.event_id not in SKIP_LIST
        and not _is_oringen(s.name)
    ]
    if not anomalies:
        print("No anomalous events found.\n")
        return

    print("=" * 70)
    print(f"ANOMALOUS EVENTS ({len(anomalies)} suspects)")
    print("=" * 70)

    has_mtb: list[EventSummary] = []
    has_cykel: list[EventSummary] = []
    multisport: list[EventSummary] = []
    other: list[EventSummary] = []

    for s in anomalies:
        name_lower = s.name.lower()
        classes_lower = " ".join(c.lower() for c in s.classes)
        combined = name_lower + " " + classes_lower

        if "mtb" in combined and "mtbo" not in combined and "mtb-o" not in combined:
            has_mtb.append(s)
        elif "cykel" in combined or "sykkel" in combined:
            has_cykel.append(s)
        elif any(
            kw in name_lower
            for kw in ["multisport", "rogaining", "adventure", "triatlon"]
        ):
            multisport.append(s)
        else:
            other.append(s)

    for label, group in [
        (f"MTB in name/classes ({len(has_mtb)})", has_mtb),
        (f"Cykel/Sykkel ({len(has_cykel)})", has_cykel),
        (f"Multisport/Rogaining/Adventure ({len(multisport)})", multisport),
        (f"Other/Ambiguous ({len(other)})", other),
    ]:
        if group:
            print(f"\n── {label} ──")
            for s in sorted(group, key=lambda x: x.start_time):
                _print_event(s)


def main() -> None:
    """Run the event quality report."""
    parser = argparse.ArgumentParser(
        description="Generate an event quality report for MTBO data.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Filter events from this date (YYYY-MM-DD). Default: 1 year ago.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all events regardless of date.",
    )
    args = parser.parse_args()

    if args.all:
        start_date = None
    elif args.start_date:
        start_date = args.start_date
    else:
        one_year_ago = datetime.now() - timedelta(days=365)
        start_date = one_year_ago.strftime("%Y-%m-%d")

    data_dir = Path(__file__).resolve().parent.parent / "data" / "events"
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    raw_events = _load_events(data_dir)
    all_summaries = [_to_summary(ev) for ev in raw_events]

    if start_date:
        summaries = [s for s in all_summaries if s.start_time >= start_date]
        print(f"Filtering events from {start_date} onwards.\n")
    else:
        summaries = all_summaries
        print("Showing ALL events (no date filter).\n")

    # Stats
    total = len(summaries)
    pure = sum(1 for s in summaries if not s.tags)
    skipped = sum(1 for s in summaries if s.event_id in SKIP_LIST)
    cf = sum(1 for s in summaries if TAG_CLASSES_FILTERED in s.tags)
    es = sum(1 for s in summaries if TAG_EVENT_SKIP in s.tags)
    anomalies = sum(1 for s in summaries if _detect_anomaly(s))

    print("=" * 70)
    print("EVENT QUALITY REPORT")
    print("=" * 70)
    print(f"  Total events:              {total}")
    print(f"  Pure MTBO (no tags):       {pure}")
    print(f"  ClassesFiltered:           {cf}")
    print(f"  EventSkip:                 {es}")
    print(f"  In skip list:              {skipped}")
    print(f"  Anomalous (suspect):       {anomalies}")
    print()

    # O-Ringen tree (always full history)
    _print_oringen_tree(all_summaries)

    # Skip list
    _print_skip_list_report(summaries)

    # Anomalies
    _print_anomaly_report(summaries)


if __name__ == "__main__":
    main()
