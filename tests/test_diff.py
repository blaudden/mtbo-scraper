from typing import cast

from src.models import EventDict
from src.utils.diff import calculate_stats


def test_calculate_stats_no_changes() -> None:
    data = [cast(EventDict, {"id": "1", "val": "a"})]
    msg = calculate_stats(data, data, "2024-01-01", "2024-12-31")
    assert "New: 0, Changed: 0, Deleted: 0" in msg


def test_calculate_stats_changes() -> None:
    old_data = [
        cast(EventDict, {"id": "1", "val": "a"}),
        cast(EventDict, {"id": "2", "val": "b"}),  # Deleted
    ]
    new_data = [
        cast(EventDict, {"id": "1", "val": "modified"}),  # Changed
        cast(EventDict, {"id": "3", "val": "c"}),  # New
    ]
    msg = calculate_stats(old_data, new_data, "2024-01-01", "2024-12-31")
    assert "New: 1, Changed: 1, Deleted: 1" in msg


def test_calculate_stats_empty() -> None:
    msg = calculate_stats([], [], "2024-01-01", "2024-12-31")
    assert "New: 0, Changed: 0, Deleted: 0" in msg

    msg = calculate_stats(
        [], [cast(EventDict, {"id": "1"})], "2024-01-01", "2024-12-31"
    )
    assert "New: 1" in msg
