#!/usr/bin/env python3
"""Startlist bib lookup tool.

Searches event start lists by date (or date range) and bib number,
returning matching participants with competition name, distance, date, and details.

Usage:
    python scripts/startlist_bibs.py <date> <number>
    python scripts/startlist_bibs.py 2026-08-26 280
    python scripts/startlist_bibs.py 2026-08-25..2026-08-30 330
"""

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import yaml


@dataclass
class BibMatch:
    """Represents a matched participant in a start list."""

    event_id: str
    competition_name: str
    race_number: int
    race_name: str
    distance: str
    date: str
    start_time: str | None
    start_number: int | str
    name: str
    club: str | None
    class_name: str


def _parse_date_bounds(date_arg: str) -> tuple[date, date]:
    """Parse a date string, month prefix, or range into (start_date, end_date)."""
    # Range with .. or : (e.g. 2026-08-25..2026-08-30)
    range_match = re.match(
        r"^(\d{4}-\d{2}-\d{2})(?:\.\.|\:)(\d{4}-\d{2}-\d{2})$", date_arg
    )
    if range_match:
        d1 = datetime.strptime(range_match.group(1), "%Y-%m-%d").date()
        d2 = datetime.strptime(range_match.group(2), "%Y-%m-%d").date()
        return (min(d1, d2), max(d1, d2))

    # Single full date (YYYY-MM-DD)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_arg):
        try:
            d = datetime.strptime(date_arg, "%Y-%m-%d").date()
            return (d, d)
        except ValueError as err:
            raise ValueError(
                f"Invalid date format '{date_arg}'. Expected valid calendar date."
            ) from err

    # Year-Month (YYYY-MM)
    if re.match(r"^\d{4}-\d{2}$", date_arg):
        year, month = map(int, date_arg.split("-"))
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year, 12, 31)
        else:
            last_day = date(year, month + 1, 1).replace(day=1)
            # Day before first day of next month:
            from datetime import timedelta

            last_day = date(year, month + 1, 1) - timedelta(days=1)
        return (first_day, last_day)

    # Full year (YYYY)
    if re.match(r"^\d{4}$", date_arg):
        year = int(date_arg)
        return (date(year, 1, 1), date(year, 12, 31))

    raise ValueError(
        f"Invalid date format '{date_arg}'. Expected YYYY-MM-DD, YYYY-MM, "
        "or YYYY-MM-DD..YYYY-MM-DD."
    )


def _extract_race_date(
    race_obj: dict[str, object], event_obj: dict[str, object]
) -> date | None:
    """Extract race date from race object or fallback to event start time."""
    dt_str = race_obj.get("datetimez")
    if isinstance(dt_str, str) and dt_str:
        try:
            return datetime.fromisoformat(dt_str).date()
        except ValueError:
            pass

    # Fallback to event start time
    start_str = event_obj.get("start_time")
    if isinstance(start_str, str) and start_str:
        try:
            return datetime.strptime(start_str[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


def search_bibs(
    data_dir: Path,
    start_bound: date,
    end_bound: date,
    bib_number: int | str,
) -> list[BibMatch]:
    """Search for a bib number across all start lists within the date bounds."""
    matches: list[BibMatch] = []
    target_bib_str = str(bib_number).strip()

    # Determine which years to search
    years_to_search = range(start_bound.year, end_bound.year + 1)

    for year in years_to_search:
        events_json_path = data_dir / str(year) / "events.json"
        if not events_json_path.exists():
            continue

        try:
            with events_json_path.open("r", encoding="utf-8") as f:
                event_data = json.load(f)
        except (json.JSONDecodeError, OSError) as err:
            print(f"Warning: Failed to load {events_json_path}: {err}", file=sys.stderr)
            continue

        events_list = event_data.get("events", [])
        for event in events_list:
            event_id = str(event.get("id", ""))
            event_name = str(event.get("name", ""))
            races = event.get("races", [])

            if not races:
                # Event with no specific races defined: check if event date matches
                ev_date_str = event.get("start_time")
                if isinstance(ev_date_str, str) and ev_date_str:
                    try:
                        ev_d = datetime.strptime(ev_date_str[:10], "%Y-%m-%d").date()
                        if start_bound <= ev_d <= end_bound:
                            matches.extend(
                                _check_startlist_file(
                                    data_dir / str(year),
                                    event_id,
                                    1,
                                    event_name,
                                    "Standard",
                                    "Standard",
                                    ev_d.isoformat(),
                                    None,
                                    target_bib_str,
                                )
                            )
                    except ValueError:
                        pass
                continue

            for race in races:
                race_num = int(race.get("race_number", 1))
                race_name = str(race.get("name", f"Race {race_num}"))
                discipline = str(race.get("discipline") or "Standard")
                race_d = _extract_race_date(race, event)

                if race_d is None or not (start_bound <= race_d <= end_bound):
                    continue

                start_time_str = race.get("datetimez")
                race_matches = _check_startlist_file(
                    data_dir / str(year),
                    event_id,
                    race_num,
                    event_name,
                    race_name,
                    discipline,
                    race_d.isoformat(),
                    str(start_time_str) if start_time_str else None,
                    target_bib_str,
                )
                matches.extend(race_matches)

    return matches


def _check_startlist_file(
    year_dir: Path,
    event_id: str,
    race_number: int,
    competition_name: str,
    race_name: str,
    distance: str,
    date_str: str,
    start_time_str: str | None,
    target_bib: str,
) -> list[BibMatch]:
    """Inspect a specific start list YAML file for the target bib number."""
    filename = f"{event_id}_startlist_{race_number}.yaml"
    file_path = year_dir / filename
    if not file_path.exists():
        # Fallback to _startlist_1.yaml if race_number != 1 but only 1 exists
        file_path = year_dir / f"{event_id}_startlist_1.yaml"
        if not file_path.exists():
            return []

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return []

    if not isinstance(data, dict):
        return []

    participants = data.get("participants", [])
    if not isinstance(participants, list):
        return []

    results: list[BibMatch] = []
    for participant in participants:
        if not isinstance(participant, dict):
            continue

        raw_bib = (
            participant.get("start_number")
            or participant.get("bib")
            or participant.get("start_no")
        )
        if raw_bib is None:
            continue

        if str(raw_bib).strip() == target_bib:
            results.append(
                BibMatch(
                    event_id=event_id,
                    competition_name=competition_name,
                    race_number=race_number,
                    race_name=race_name,
                    distance=distance,
                    date=date_str,
                    start_time=participant.get("start_time") or start_time_str,
                    start_number=raw_bib,
                    name=str(participant.get("name", "")),
                    club=str(participant.get("club"))
                    if participant.get("club")
                    else None,
                    class_name=str(participant.get("class", "")),
                )
            )

    return results


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Lookup athletes in MTBO start lists by date range and bib number."
    )
    parser.add_argument(
        "date",
        help=(
            "Date or range: YYYY-MM-DD, YYYY-MM, or YYYY-MM-DD..YYYY-MM-DD "
            "(e.g. 2026-08-26)"
        ),
    )
    parser.add_argument(
        "number",
        help="Bib / start number to look up (e.g. 280)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data/events directory (auto-detected if omitted)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact single-line JSON instead of formatted JSON",
    )

    args = parser.parse_args()

    # Find data directory
    if args.data_dir:
        data_dir = args.data_dir
    else:
        # Default relative to this script: ../data/events
        script_dir = Path(__file__).resolve().parent
        data_dir = script_dir.parent / "data" / "events"

    if not data_dir.exists():
        print(f"Error: Data directory not found at {data_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        start_d, end_d = _parse_date_bounds(args.date)
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    matches = search_bibs(data_dir, start_d, end_d, args.number)

    output_data = [asdict(m) for m in matches]
    indent = None if args.compact else 2
    print(json.dumps(output_data, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
