from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.models import Event, Race, Url
from src.storage import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    root_path = tmp_path / "mtbo_events.json"
    data_dir = tmp_path / "data" / "events"
    return Storage(str(root_path), str(data_dir))


def create_event_with_url(
    event_id: str,
    url_path: str,
    last_updated: str | None = None,
    title: str | None = None,
) -> Event:
    event = Event(
        id=event_id,
        name="Test Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Sanctioned",
        original_status="Active",
        races=[
            Race(
                race_number=1,
                name="Race 1",
                datetimez="2025-01-01T10:00:00+00:00",
                discipline="Middle",
            )
        ],
    )
    event.urls.append(
        Url(type="Website", url=url_path, last_updated_at=last_updated, title=title)
    )
    return event


def test_save_preserves_timestamp_for_unchanged_url(storage: Storage) -> None:
    # 1. Save initial event with a timestamp
    old_time = "2024-01-01T12:00:00+00:00"
    event1 = create_event_with_url(
        "TEST_1", "http://example.com", last_updated=old_time, title="Old Title"
    )
    storage.save({"TEST": [event1]})

    # 2. Verify it saved
    loaded = storage.load()
    print(f"DEBUG: Loaded data: {loaded}")
    assert "TEST_1" in loaded
    assert loaded["TEST_1"]["urls"][0]["last_updated_at"] == old_time

    # 3. Save "new" version of event (same URL, no timestamp from parser)
    # The parser now returns None for last_updated_at
    event2 = create_event_with_url(
        "TEST_1", "http://example.com", last_updated=None, title="Old Title"
    )
    storage.save({"TEST": [event2]})

    # 4. Verify timestamp is PRESERVED
    loaded_again = storage.load()
    assert loaded_again["TEST_1"]["urls"][0]["last_updated_at"] == old_time


def test_save_updates_timestamp_for_changed_url(storage: Storage) -> None:
    # 1. Save initial event
    old_time = "2024-01-01T12:00:00+00:00"
    event1 = create_event_with_url(
        "TEST_2", "http://example.com/old", last_updated=old_time
    )
    storage.save({"TEST": [event1]})

    # 2. Save update with DIFFERENT URL
    event2 = create_event_with_url(
        "TEST_2", "http://example.com/new", last_updated=None
    )
    storage.save({"TEST": [event2]})

    # 3. Verify timestamp is UPDATED (not old_time)
    loaded = storage.load()
    new_time = loaded["TEST_2"]["urls"][0]["last_updated_at"]
    assert new_time is not None
    assert new_time != old_time
    # Should be close to now
    assert new_time.startswith(datetime.now(UTC).strftime("%Y-%m-%d"))


def test_save_updates_timestamp_for_changed_title(storage: Storage) -> None:
    # 1. Save initial event
    old_time = "2024-01-01T12:00:00+00:00"
    event1 = create_event_with_url(
        "TEST_3", "http://example.com", last_updated=old_time, title="Old Title"
    )
    storage.save({"TEST": [event1]})

    # 2. Save update with SAME URL but DIFFERENT TITLE
    event2 = create_event_with_url(
        "TEST_3", "http://example.com", last_updated=None, title="New Title"
    )
    storage.save({"TEST": [event2]})

    # 3. Verify timestamp is UPDATED
    loaded = storage.load()
    new_time = loaded["TEST_3"]["urls"][0]["last_updated_at"]
    assert new_time is not None
    assert new_time != old_time
    assert loaded["TEST_3"]["urls"][0]["title"] == "New Title"


def test_save_sets_timestamp_for_new_url(storage: Storage) -> None:
    # 1. Save event with NO urls
    event1 = Event(
        id="TEST_4",
        name="Test Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )
    storage.save({"TEST": [event1]})

    # 2. Update with NEW URL
    event2 = create_event_with_url(
        "TEST_4", "http://example.com/brand_new", last_updated=None
    )
    storage.save({"TEST": [event2]})

    # 3. Verify timestamp is set
    loaded = storage.load()
    new_time = loaded["TEST_4"]["urls"][0]["last_updated_at"]
    assert new_time is not None


def test_race_url_timestamps(storage: Storage) -> None:
    # Verify logic applies to Race URLs too
    old_time = "2024-01-01T12:00:00+00:00"

    # 1. Initial race with URL
    e1 = create_event_with_url("TEST_RACE", "http://event.com")  # dummy event url
    e1.races[0].urls.append(
        Url(
            type="StartList",
            url="http://start.com",
            last_updated_at=old_time,
            title="Start",
        )
    )
    storage.save({"TEST": [e1]})

    # 2. Update race URL (same)
    e2 = create_event_with_url("TEST_RACE", "http://event.com")
    e2.races[0].urls.append(
        Url(
            type="StartList",
            url="http://start.com",
            last_updated_at=None,
            title="Start",
        )
    )
    storage.save({"TEST": [e2]})

    loaded = storage.load()
    assert loaded["TEST_RACE"]["races"][0]["urls"][0]["last_updated_at"] == old_time

    # 3. Update race URL (change)
    e3 = create_event_with_url("TEST_RACE", "http://event.com")
    e3.races[0].urls.append(
        Url(
            type="StartList",
            url="http://start.com/new",
            last_updated_at=None,
            title="Start",
        )
    )
    storage.save({"TEST": [e3]})

    loaded = storage.load()
    new_time = loaded["TEST_RACE"]["races"][0]["urls"][0]["last_updated_at"]
    assert new_time != old_time


def test_series_url_timestamps(storage: Storage) -> None:
    """Verify timestamp preservation works for Series type URLs."""
    old_time = "2024-01-01T12:00:00+00:00"

    # 1. Save event with Series URL
    event1 = Event(
        id="TEST_SERIES",
        name="Series Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )
    event1.urls.append(
        Url(type="Series", url="http://series.com", last_updated_at=old_time)
    )
    storage.save({"TEST": [event1]})

    # 2. Save again with same URL but no timestamp (as parser would)
    event2 = Event(
        id="TEST_SERIES",
        name="Series Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )
    event2.urls.append(
        Url(type="Series", url="http://series.com", last_updated_at=None)
    )
    storage.save({"TEST": [event2]})

    # 3. Verify timestamp is preserved
    loaded = storage.load()
    assert loaded["TEST_SERIES"]["urls"][0]["last_updated_at"] == old_time
