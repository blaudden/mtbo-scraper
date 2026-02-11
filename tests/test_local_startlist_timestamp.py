from unittest.mock import MagicMock

from src.models import Race
from src.sources.eventor_source import EventorSource


def test_update_local_file_url_unchanged_content() -> None:
    """
    Verify that if content is unchanged, the new Url object has last_updated_at=None.
    This allows Storage to preserve the existing timestamp from the previous scrape.
    """
    # 1. Setup
    # We don't need a real Scraper or valid config for this method test
    source = EventorSource("SWE", "http://mock", MagicMock())

    race = Race(
        race_number=1,
        name="Test Race",
        datetimez="2025-01-01T10:00:00+00:00",
        discipline="MTBO",
    )
    # race.urls is empty initially

    # 2. Call _update_local_file_url with changed=False
    filepath = "data/events/2025/test_startlist.yaml"
    source._update_local_file_url(race, filepath, changed=False)

    # 3. Assert
    local_url = next(u for u in race.urls if u.type == "LocalStartList")

    assert local_url.last_updated_at is None, (
        f"Expected None when unchanged, got {local_url.last_updated_at}"
    )


def test_update_local_file_url_changed_content() -> None:
    """Verify that if content IS changed, we update the timestamp."""
    source = EventorSource("SWE", "http://mock", MagicMock())
    race = Race(race_number=1, name="Test", datetimez="2025-01-01", discipline="MTBO")

    source._update_local_file_url(race, "path/to/file", changed=True)

    local_url = next(u for u in race.urls if u.type == "LocalStartList")
    assert local_url.last_updated_at is not None
