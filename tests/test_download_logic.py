from pathlib import Path

from src.models import Event, Url
from src.sources.eventor_source import EventorSource


class TestDownloadLogic:
    def test_should_download_correct_series_swe(
        self, temp_event_data_dir: Path
    ) -> None:
        """Test that start list is downloaded for Swedish Cup events."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],  # Raw value from Eventor
            races=[],
            urls=[
                Url(
                    type="Series",
                    url="/series/1",
                    title="Svenska VeteranCupen MTBO 2025",
                )
            ],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        # Ensure _should_download_start_list is accessible (python convention allows it)
        assert source._should_download_start_list(event) is True

    def test_should_download_correct_series_swe_case_insensitive(
        self, temp_event_data_dir: Path
    ) -> None:
        """Test case insensitivity."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[Url(type="Series", url="/series/1", title="svenska cupen")],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is True

    def test_should_not_download_other_series_swe(
        self, temp_event_data_dir: Path
    ) -> None:
        """Test that local series are ignored."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[Url(type="Series", url="/series/1", title="Närkeserien MTBO")],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is False

    def test_should_not_download_missing_series_link(
        self, temp_event_data_dir: Path
    ) -> None:
        """Test that missing series link returns False."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is False

    def test_should_not_download_missing_title(self, temp_event_data_dir: Path) -> None:
        """Test that missing series title returns False."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[Url(type="Series", url="/series/1", title=None)],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is False

    def test_should_not_download_non_swe(self, temp_event_data_dir: Path) -> None:
        """Test that non-SWE countries don't download even if title matches."""
        event = Event(
            id="NOR_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[Url(type="Series", url="/series/1", title="Svenska Cupen")],
        )
        source = EventorSource(
            "NOR", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is False

    def test_should_download_iof_international(self, temp_event_data_dir: Path) -> None:
        """Test that IOF International events download startlists."""
        event = Event(
            id="IOF_7490",
            name="World Championships",
            start_time="2025-08-11",
            end_time="2025-08-17",
            status="Sanctioned",
            original_status="Active",
            types=["World Championships"],  # Raw value from IOF Eventor
            races=[],
            urls=[],
        )
        source = EventorSource(
            "IOF", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is True

    def test_should_not_download_iof_regional(self, temp_event_data_dir: Path) -> None:
        """Test that IOF Regional events don't download startlists."""
        event = Event(
            id="IOF_8558",
            name="Regional Event",
            start_time="2025-08-11",
            end_time="2025-08-17",
            status="Sanctioned",
            original_status="Active",
            types=["Regional Championships"],  # Raw value from IOF Eventor
            races=[],
            urls=[],
        )
        source = EventorSource(
            "IOF", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_download_start_list(event) is False

    def test_should_not_fetch_counts_iof_international(
        self, temp_event_data_dir: Path
    ) -> None:
        """Test that IOF International events don't fetch counts."""
        event = Event(
            id="IOF_7490",
            name="World Championships",
            start_time="2025-08-11",
            end_time="2025-08-17",
            status="Sanctioned",
            original_status="Active",
            types=["World Championships"],
            races=[],
            urls=[],
        )
        source = EventorSource(
            "IOF", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_fetch_counts(event) is False

    def test_should_fetch_counts_other_events(self, temp_event_data_dir: Path) -> None:
        """Test that non-IOF-International events do fetch counts."""
        event = Event(
            id="SWE_123",
            name="Test Event",
            start_time="2025-07-01",
            end_time="2025-07-01",
            status="Planned",
            original_status="Planned",
            types=["National event"],
            races=[],
            urls=[],
        )
        source = EventorSource(
            "SWE", "http://mock", output_dir=str(temp_event_data_dir)
        )
        assert source._should_fetch_counts(event) is True
