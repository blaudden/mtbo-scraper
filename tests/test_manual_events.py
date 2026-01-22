import os
import tempfile
from collections.abc import Iterator

import pytest
import yaml

from src.sources.manual_source import ManualSource


@pytest.fixture
def manual_events_dir() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create a test event directory
        event_dir = os.path.join(tmpdirname, "TEST-EVENT-1")
        os.makedirs(event_dir)

        # Create event.yaml
        event_data = {
            "id": "TEST-EVENT-1",
            "name": "Test Manual Event",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "country": "SWE",  # Use SWE to test offset
            "organizers": ["Test Org"],
            "status": "Planned",
            "documents": [
                {"name": "Doc 1", "url": "file://bulletin.pdf", "type": "Bulletin"}
            ],
            "races": [
                {
                    "name": "Race 1",
                    "date": "2024-01-01",
                    "distance": "Middle",
                    "time": "10:00",
                },
                {
                    "name": "Race 2",
                    "date": "2024-01-02",
                    "distance": "Long",
                    # No time
                },
            ],
        }

        with open(os.path.join(event_dir, "event.yaml"), "w") as f:
            yaml.dump(event_data, f)

        # Create dummy PDF
        with open(os.path.join(event_dir, "bulletin.pdf"), "w") as f:
            f.write("dummy content")

        yield tmpdirname


def test_load_manual_events(manual_events_dir: str) -> None:
    source = ManualSource(manual_events_dir)
    events = source.load_events()

    assert len(events) == 1
    event = events[0]
    assert event.id == "TEST-EVENT-1"
    assert event.name == "Test Manual Event"
    # Event dates should be PLAIN YYYY-MM-DD
    assert event.start_time == "2024-01-01"

    assert len(event.races) == 2
    assert event.races[0].name == "Race 1"
    # Race dates should be ISO with offset
    assert event.races[0].datetimez == "2024-01-01T10:00:00+01:00"

    assert event.races[1].name == "Race 2"
    assert event.races[1].datetimez == "2024-01-02T00:00:00+01:00"


def test_missing_directory() -> None:
    source = ManualSource("non_existent_dir")
    events = source.load_events()
    assert len(events) == 0
