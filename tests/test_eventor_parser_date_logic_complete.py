import pytest

from src.models import Event, Race
from src.sources.eventor_parser import EventorParser


class TestDateDerivationLogic:
    """Tests the _derive_event_dates method in EventorParser covering all 4 cases."""

    @pytest.fixture
    def parser(self) -> EventorParser:
        return EventorParser()

    @pytest.fixture
    def base_event(self) -> Event:
        return Event(
            id="TEST_Event",
            name="Test Logic Event",
            start_time="2025-01-01",
            end_time="2025-01-01",
            status="Applied",
            original_status="Applied",
            races=[],
        )

    def test_case_1_date_attribute_takes_precedence(
        self, parser: EventorParser, base_event: Event
    ) -> None:
        """Case 1: Both races and Date attribute present. Date attribute wins."""
        # Setup races with specific dates (e.g. June)
        races = [
            Race(
                race_number=1,
                name="R1",
                datetimez="2026-06-01T10:00:00",
                discipline="Middle",
            ),
            Race(
                race_number=2,
                name="R2",
                datetimez="2026-06-03T10:00:00",
                discipline="Long",
            ),
        ]
        base_event.races = races

        # Attribute says January (e.g. training camp + races later?)
        # User wants Attribute to win.
        attributes = {"Date": "Sunday 1 January 2026"}

        parser._derive_event_dates(base_event, attributes)

        assert base_event.start_time == "2026-01-01"
        assert base_event.end_time == "2026-01-01"

    def test_case_2_no_races_date_range(
        self, parser: EventorParser, base_event: Event
    ) -> None:
        """Case 2: No races. Date attribute has a range."""
        base_event.races = []
        attributes = {"Date": "Monday 21 July 2025 - Saturday 26 July 2025"}

        parser._derive_event_dates(base_event, attributes)

        assert base_event.start_time == "2025-07-21"
        assert base_event.end_time == "2025-07-26"

    def test_case_3_no_races_single_date(
        self, parser: EventorParser, base_event: Event
    ) -> None:
        """Case 3: No races. Date attribute has a single date."""
        base_event.races = []
        attributes = {"Date": "Sunday 10 May 2026"}

        parser._derive_event_dates(base_event, attributes)

        assert base_event.start_time == "2026-05-10"
        assert base_event.end_time == "2026-05-10"

    def test_case_4_no_races_no_date_attribute(
        self, parser: EventorParser, base_event: Event
    ) -> None:
        """Case 4: No races. No Date attribute. Should keep original/default."""
        base_event.races = []
        attributes = {"Other": "Info"}  # No "Date" key

        # Set original to something distinctive
        base_event.start_time = "ORIGINAL_START"
        base_event.end_time = "ORIGINAL_END"

        parser._derive_event_dates(base_event, attributes)

        assert base_event.start_time == "ORIGINAL_START"
        assert base_event.end_time == "ORIGINAL_END"

    def test_case_mixed_races_ignored_if_no_datetimez(
        self, parser: EventorParser, base_event: Event
    ) -> None:
        """Edge Case: Races exist but have no datetimez. Fallback to Date attribute."""
        races = [
            Race(race_number=1, name="R1", datetimez="", discipline="Middle"),
        ]
        base_event.races = races
        attributes = {"Date": "Wednesday 12 August 2026"}

        parser._derive_event_dates(base_event, attributes)

        # Races were empty of valid dates, so fallback logic applies
        assert base_event.start_time == "2026-08-12"
        assert base_event.end_time == "2026-08-12"
