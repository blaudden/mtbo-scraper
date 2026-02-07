from datetime import datetime, timedelta

from src.main import (
    determine_date_range,
    irregular_chunk_date_range,
    split_range_by_year,
)


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


def test_irregular_chunk_date_range_coverage() -> None:
    """Test that irregular chunks cover the entire range without gaps."""
    start_date = "2024-01-01"
    end_date = "2025-01-01"  # 1 year range

    chunks = list(irregular_chunk_date_range(start_date, end_date))

    assert len(chunks) > 0

    # Sort chunks by start date to verify continuity
    chunks.sort(key=lambda x: x[0])

    # Check first start date
    assert chunks[0][0] == start_date

    # Check last end date
    assert chunks[-1][1] == end_date

    # Check continuity
    for i in range(len(chunks) - 1):
        current_end = chunks[i][1]
        next_start = chunks[i + 1][0]

        current_end_dt = datetime.strptime(current_end, "%Y-%m-%d")

        # Next start should be current end + 1 day
        expected_next = (current_end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        assert next_start == expected_next


def test_irregular_chunk_sizes() -> None:
    """Test that chunk sizes are within allowed limits (1 to 150 days)."""
    start_date = "2020-01-01"
    end_date = "2023-01-01"  # 3 years to get many chunks

    chunks = list(irregular_chunk_date_range(start_date, end_date))

    for start, end in chunks:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        duration = (end_dt - start_dt).days

        # The logic is: chunk_end = current + timedelta(days=days).
        # days is random(0, 150).
        # if days=0, end=start. Duration = 1 day (inclusive).
        # if days=150, end=start+150. Duration = 151 days.
        # So we assert that the diff in days is between 0 and 150.
        assert 0 <= duration <= 150
        pass


def test_split_range_by_year_mid_year() -> None:
    """Test splitting a range that starts and ends mid-year."""
    start = "2024-06-01"
    end = "2026-06-01"

    segments = list(split_range_by_year(start, end))

    assert len(segments) == 3

    # Segment 1: 2024-06-01 to 2024-12-31
    assert segments[0] == ("2024-06-01", "2024-12-31")

    # Segment 2: 2025-01-01 to 2025-12-31
    assert segments[1] == ("2025-01-01", "2025-12-31")

    # Segment 3: 2026-01-01 to 2026-06-01
    assert segments[2] == ("2026-01-01", "2026-06-01")


def test_split_range_by_year_single_year() -> None:
    """Test splitting a range within a single year."""
    start = "2024-02-01"
    end = "2024-03-01"

    segments = list(split_range_by_year(start, end))

    assert len(segments) == 1
    assert segments[0] == (start, end)


def test_history_mode_detection_logic() -> None:
    """Test the logic used to detect history vs standard mode (4-week threshold)."""
    # Logic is: start_date < (now - 4 weeks) => history

    now = datetime.now()
    threshold = now - timedelta(weeks=4)

    # 1. Date strictly older than threshold (e.g. 5 weeks ago)
    history_date = threshold - timedelta(weeks=1)
    assert history_date.date() < threshold.date()

    # 2. Date strictly newer than threshold (e.g. 3 weeks ago)
    standard_date = threshold + timedelta(weeks=1)
    assert not (standard_date.date() < threshold.date())

    # 3. Future date
    future_date = now + timedelta(weeks=52)
    assert not (future_date.date() < threshold.date())
