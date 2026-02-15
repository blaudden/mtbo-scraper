"""Tests for _get_local_events() helper function."""

from src.main import _get_local_events
from src.models import EventDict, RaceDict


def _make_event_dict(
    event_id: str, start_time: str, end_time: str | None = None
) -> EventDict:
    """Create a minimal EventDict for testing."""
    return EventDict(
        id=event_id,
        name=f"Test Event {event_id}",
        start_time=start_time,
        end_time=end_time or start_time,
        status="Completed",
        original_status="Completed",
        types=[],
        tags=[],
        form=None,
        organisers=[],
        officials=[],
        classes=[],
        urls=[],
        information=None,
        region=None,
        punching_system=None,
        races=[
            RaceDict(
                race_number=1,
                name="Race 1",
                datetimez=f"{start_time}T10:00:00+02:00",
                discipline="Middle",
                night_or_day=None,
                position=None,
                areas=[],
                urls=[],
                documents=[],
                entry_counts=None,
                start_counts=None,
                result_counts=None,
                fingerprints=[],
            )
        ],
        documents=[],
        entry_deadlines=[],
    )


def test_filters_by_country() -> None:
    """Only returns events matching the requested country."""
    events = {
        "SWE_100": _make_event_dict("SWE_100", "2024-06-15"),
        "NOR_200": _make_event_dict("NOR_200", "2024-06-15"),
        "SWE_300": _make_event_dict("SWE_300", "2024-06-20"),
    }
    result = _get_local_events(events, "SWE", "2024-06-01", "2024-06-30")
    ids = [e.id for e in result]
    assert ids == ["SWE_100", "SWE_300"]


def test_filters_by_date_range() -> None:
    """Only returns events whose start_time is within the date range."""
    events = {
        "SWE_100": _make_event_dict("SWE_100", "2024-05-31"),
        "SWE_200": _make_event_dict("SWE_200", "2024-06-01"),
        "SWE_300": _make_event_dict("SWE_300", "2024-06-15"),
        "SWE_400": _make_event_dict("SWE_400", "2024-06-30"),
        "SWE_500": _make_event_dict("SWE_500", "2024-07-01"),
    }
    result = _get_local_events(events, "SWE", "2024-06-01", "2024-06-30")
    ids = [e.id for e in result]
    assert ids == ["SWE_200", "SWE_300", "SWE_400"]


def test_returns_empty_for_no_matches() -> None:
    """Returns empty list when no events match."""
    events = {
        "NOR_100": _make_event_dict("NOR_100", "2024-06-15"),
    }
    result = _get_local_events(events, "SWE", "2024-06-01", "2024-06-30")
    assert result == []


def test_returns_event_objects_with_url() -> None:
    """Returned Event objects have url field populated for scraping."""
    events = {
        "SWE_5115": _make_event_dict("SWE_5115", "2024-06-15"),
    }
    result = _get_local_events(events, "SWE", "2024-06-01", "2024-06-30")
    assert len(result) == 1
    event = result[0]
    assert event.id == "SWE_5115"
    assert event.url == "/Events/Show/5115"


def test_empty_events_dict() -> None:
    """Handles empty events dict gracefully."""
    result = _get_local_events({}, "SWE", "2024-06-01", "2024-06-30")
    assert result == []
