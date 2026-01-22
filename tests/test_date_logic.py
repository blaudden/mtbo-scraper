from datetime import datetime, timedelta

from src.main import determine_date_range


def test_default_end_date() -> None:
    start = "2024-01-01"
    # Expected end date matches default logic:
    # start + 183 days -> year + 1 -> 12-31
    # 2024-01-01 + 183 days is ~July 2024. Year+1 is 2025.
    expected_end = "2025-12-31"

    actual_start, actual_end = determine_date_range(start, None)

    assert actual_start == start
    assert actual_end == expected_end


def test_explicit_valid_date() -> None:
    start = "2024-01-01"
    end = "2024-02-01"

    actual_start, actual_end = determine_date_range(start, end)

    assert actual_start == start
    assert actual_end == end


def test_default_start_date() -> None:
    # If no start date is provided, it should safeguard to ~4 weeks ago
    actual_start, _ = determine_date_range(None, None)

    expected_start = (datetime.now() - timedelta(weeks=4)).strftime("%Y-%m-%d")
    assert actual_start == expected_start
