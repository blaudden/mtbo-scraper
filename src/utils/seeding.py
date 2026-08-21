"""Seeding order calculation for MTBO Svenska Cupen according to competition rules."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypedDict

import structlog

from src.models import (
    CupEntry,
    CupStandings,
    Event,
    EventDict,
    SeedingEntry,
    SeedingOrder,
)
from src.sources.eventor_parser import EventorParser
from src.utils.date_and_time import get_current_utc_iso

if TYPE_CHECKING:
    from src.scraper import Scraper
    from src.storage import Storage

logger = structlog.get_logger(__name__)


class _SeedingCandidate(TypedDict):
    name: str
    club: str
    seed_val: int
    current_rank: int | None
    previous_rank: int | None


def _is_svenska_cupen_title(title: str) -> bool:
    """Checks whether the series title matches Svenska Cupen MTBO."""
    t = title.lower()
    return "svenska cupen mtbo" in t and "veteran" not in t


def _normalize_url(url: str, base_url: str) -> str:
    """Ensures a series URL is absolute."""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return f"{base_url.rstrip('/')}{url}"
    return f"{base_url.rstrip('/')}/{url}"


def find_svenska_cupen_series_url(
    events: Sequence[Event | EventDict],
    base_url: str = "https://eventor.orientering.se",
) -> str | None:
    """Finds the Svenska Cupen MTBO series URL from a sequence of events.

    Args:
        events: List or sequence of Event objects or EventDict dictionaries.
        base_url: Base URL for Swedish Eventor (default: https://eventor.orientering.se).

    Returns:
        Full series URL if found, else None.
    """
    for event in events:
        if isinstance(event, dict):
            event_id = event.get("id", "")
            if not isinstance(event_id, str) or not event_id.startswith("SWE_"):
                continue
            urls = event.get("urls", [])
            for url_dict in urls:
                title = url_dict.get("title")
                if (
                    url_dict.get("type") == "Series"
                    and isinstance(title, str)
                    and _is_svenska_cupen_title(title)
                ):
                    raw_url = url_dict.get("url") or ""
                    if raw_url:
                        return _normalize_url(raw_url, base_url)
        else:
            if not event.id.startswith("SWE_"):
                continue
            for url_obj in event.urls:
                if (
                    url_obj.type == "Series"
                    and url_obj.title
                    and _is_svenska_cupen_title(url_obj.title)
                ):
                    raw_url = url_obj.url or ""
                    if raw_url:
                        return _normalize_url(raw_url, base_url)
    return None


def _build_rider_map(
    entries: list[CupEntry], period: str, class_name: str
) -> dict[str, CupEntry]:
    """Builds a normalised-name → CupEntry map, warning on duplicates.

    Args:
        entries: List of cup entries for a single class.
        period: Label for log messages (e.g. "current", "previous").
        class_name: Class name for log messages.

    Returns:
        Dictionary keyed by lowercased, stripped rider name.
    """
    rider_map: dict[str, CupEntry] = {}
    for e in entries:
        key = e.name.strip().lower()
        if key in rider_map:
            logger.warning(
                "Duplicate rider entry in cup standings",
                period=period,
                class_name=class_name,
                name=e.name,
            )
        rider_map[key] = e
    return rider_map


def calculate_seeding_order(
    current_cup: CupStandings | None,
    previous_cup: CupStandings | None,
    year: int,
    target_classes: tuple[str, ...] = ("H21", "D21", "H17-20", "D17-20"),
) -> SeedingOrder:
    """Calculates seeding order based on current & previous cup standings.

    Seed number = min(previous_year_rank, current_year_rank).
    Tie-breaking prefers current year rank, then previous year rank.
    Top riders (up to 8) form the seeded group.

    Args:
        current_cup: Current year's cup standings (if available).
        previous_cup: Previous year's cup standings (if available).
        year: Target year for the seeding order.
        target_classes: Classes to calculate seeding for.

    Returns:
        SeedingOrder containing seeding lists per class.
    """
    seeding_classes: dict[str, list[SeedingEntry]] = {}

    curr_classes = current_cup.classes if current_cup else {}
    prev_classes = previous_cup.classes if previous_cup else {}

    for class_name in target_classes:
        curr_entries = curr_classes.get(class_name, [])
        prev_entries = prev_classes.get(class_name, [])

        curr_map = _build_rider_map(curr_entries, "current", class_name)
        prev_map = _build_rider_map(prev_entries, "previous", class_name)

        # Collect unique rider names (preserve display formatting)
        all_riders: dict[str, tuple[str, str]] = {}
        for e in curr_entries:
            all_riders[e.name.strip().lower()] = (e.name, e.club)
        for e in prev_entries:
            key = e.name.strip().lower()
            if key not in all_riders:
                all_riders[key] = (e.name, e.club)

        class_seeding: list[_SeedingCandidate] = []
        for norm_name, (display_name, club) in all_riders.items():
            curr_entry = curr_map.get(norm_name)
            prev_entry = prev_map.get(norm_name)

            curr_rank = curr_entry.rank if curr_entry else None
            prev_rank = prev_entry.rank if prev_entry else None

            valid_ranks = [r for r in [curr_rank, prev_rank] if r is not None]
            if not valid_ranks:
                continue

            seed_val = min(valid_ranks)

            class_seeding.append(
                _SeedingCandidate(
                    name=display_name,
                    club=club,
                    seed_val=seed_val,
                    current_rank=curr_rank,
                    previous_rank=prev_rank,
                )
            )

        def sort_key(
            item: _SeedingCandidate,
        ) -> tuple[int, int, int, str]:
            c_tb = item["current_rank"] if item["current_rank"] is not None else 99999
            p_tb = item["previous_rank"] if item["previous_rank"] is not None else 99999
            return (item["seed_val"], c_tb, p_tb, item["name"])

        class_seeding.sort(key=sort_key)

        seeded_limit = min(8, len(class_seeding))

        result_entries: list[SeedingEntry] = []
        for idx, item in enumerate(class_seeding, start=1):
            result_entries.append(
                SeedingEntry(
                    seed_rank=idx,
                    name=item["name"],
                    club=item["club"],
                    seed_val=item["seed_val"],
                    current_rank=item["current_rank"],
                    previous_rank=item["previous_rank"],
                    is_seeded=(idx <= seeded_limit),
                )
            )

        seeding_classes[class_name] = result_entries

    current_url = current_cup.url if current_cup else None
    previous_url = previous_cup.url if previous_cup else None

    return SeedingOrder(
        year=year,
        generated_at=get_current_utc_iso(),
        current_cup_url=current_url,
        previous_cup_url=previous_url,
        classes=seeding_classes,
    )


def fetch_and_update_svenska_cupen_seeding(
    scraper: "Scraper",
    storage: "Storage",
    year: int,
    base_url: str = "https://eventor.orientering.se",
) -> SeedingOrder | None:
    """Discovers, fetches, and saves Svenska Cupen standings and calculates seeding.

    Args:
        scraper: Scraper instance for HTTP requests.
        storage: Storage instance for loading events and saving cup files.
        year: Target year (e.g. current year).
        base_url: Swedish Eventor base URL.

    Returns:
        Generated SeedingOrder if successful, else None.
    """
    logger.info("Updating Svenska Cupen seeding", year=year)
    all_events_map = storage.load()
    all_events = list(all_events_map.values())

    curr_events = [
        e for e in all_events if e.get("start_time", "").startswith(str(year))
    ]
    prev_events = [
        e for e in all_events if e.get("start_time", "").startswith(str(year - 1))
    ]

    curr_series_url = find_svenska_cupen_series_url(curr_events, base_url)
    prev_series_url = find_svenska_cupen_series_url(prev_events, base_url)

    parser = EventorParser()
    curr_cup: CupStandings | None = None
    prev_cup: CupStandings | None = None

    if curr_series_url:
        logger.info("Fetching current year cup standings", url=curr_series_url)
        resp = scraper.get(curr_series_url)
        if resp and resp.text:
            try:
                curr_cup = parser.parse_series_standings(resp.text, curr_series_url)
                storage.save_cup_standings(curr_cup)
            except Exception as e:
                logger.error(
                    "Failed to parse current year cup standings",
                    error=str(e),
                    url=curr_series_url,
                )
        else:
            logger.warning(
                "Failed to fetch current year cup standings HTML", url=curr_series_url
            )

    if prev_series_url:
        logger.info("Fetching previous year cup standings", url=prev_series_url)
        resp = scraper.get(prev_series_url)
        if resp and resp.text:
            try:
                prev_cup = parser.parse_series_standings(resp.text, prev_series_url)
                storage.save_cup_standings(prev_cup)
            except Exception as e:
                logger.error(
                    "Failed to parse previous year cup standings",
                    error=str(e),
                    url=prev_series_url,
                )
        else:
            logger.warning(
                "Failed to fetch previous year cup standings HTML", url=prev_series_url
            )

    if not curr_cup and not prev_cup:
        logger.warning("No cup standings available to calculate seeding", year=year)
        return None

    seeding = calculate_seeding_order(curr_cup, prev_cup, year=year)
    storage.save_seeding_order(seeding)
    logger.info("Successfully updated Svenska Cupen seeding order", year=year)
    return seeding
