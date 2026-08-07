"""Seeding order calculation for MTBO Svenska Cupen according to competition rules."""

from typing import TypedDict

import structlog

from src.models import CupEntry, CupStandings, SeedingEntry, SeedingOrder
from src.utils.date_and_time import get_current_utc_iso

logger = structlog.get_logger(__name__)


class _SeedingCandidate(TypedDict):
    name: str
    club: str
    seed_val: int
    current_rank: int | None
    previous_rank: int | None


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
