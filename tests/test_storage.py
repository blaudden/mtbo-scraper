import json
import time
from pathlib import Path

from src.models import Event
from src.storage import Storage


def test_storage_index_and_timestamps(
    tmp_path: Path, temp_event_data_dir: Path
) -> None:
    # 1. Setup Environment
    root_file = tmp_path / "mtbo_events.json"
    data_dir = temp_event_data_dir

    # Init storage
    storage = Storage(str(root_file))
    # Override default data dir for test
    storage.default_data_dir = data_dir

    # 2. Test Save New Event
    new_event = Event(
        id="NEW_1",
        name="New Event",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Planned",
        original_status="Planned",
        types=["Test event"],
        races=[],
    )

    storage.save({"MAN": [new_event]})

    # 3. Verify Index Structure
    with open(root_file) as f:
        index = json.load(f)

    assert index["schema_version"] == "2.0"
    assert "last_scraped_at" in index
    assert "partitions" in index
    assert "2025" in index["partitions"]

    # Verify partition paths
    p2025 = index["partitions"]["2025"]
    assert str(data_dir / "2025/events.json") == p2025["path"]

    # 4. Verify Partition Content
    file_2025 = Path(p2025["path"])
    assert file_2025.exists()

    with open(file_2025) as f:
        p_data = json.load(f)
        assert p_data["schema_version"] == "2.0"
        assert "create_time" not in p_data
        assert len(p_data["events"]) == 1
        assert p_data["events"][0]["id"] == "NEW_1"

    # 5. Test Timestamp Logic (Conditional Update)
    # Get current partition timestamp
    ts_2025_initial = p2025["last_updated_at"]
    ts_scraped_initial = index["last_scraped_at"]

    # Wait a bit to ensure readable potential timestamp diff
    time.sleep(1.1)

    # Save NO changes
    storage.save({"MAN": [new_event]})

    with open(root_file) as f:
        index_v2 = json.load(f)

    # last_scraped_at SHOULD update unconditionally
    assert index_v2["last_scraped_at"] != ts_scraped_initial

    # last_updated_at for 2025 SHOULD NOT update
    assert index_v2["partitions"]["2025"]["last_updated_at"] == ts_2025_initial

    # 6. Test Content Change
    time.sleep(1.1)
    modified_event = Event(
        id="NEW_1",
        name="New Event MODIFIED",
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Planned",
        original_status="Planned",
        types=["Test event"],
        races=[],
    )

    storage.save({"MAN": [modified_event]})

    with open(root_file) as f:
        index_v3 = json.load(f)

    # last_updated_at for 2025 SHOULD update
    assert index_v3["partitions"]["2025"]["last_updated_at"] != ts_2025_initial

    # Verify content changed on disk
    with open(file_2025) as f:
        p_data_v3 = json.load(f)
        assert p_data_v3["events"][0]["name"] == "New Event MODIFIED"
