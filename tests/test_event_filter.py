"""Tests for the event_filter module."""

from src.event_filter import (
    MTBO_KEYWORDS,
    SKIP_LIST,
    TAG_CLASSES_FILTERED,
    TAG_EVENT_SKIP,
    OringenFilter,
    detect_anomaly,
    has_mtbo_signal,
    is_excluded,
)
from src.models import Event, Race


def _make_event(
    event_id: str = "SWE_99999",
    name: str = "Test Event",
    tags: list[str] | None = None,
    classes: list[str] | None = None,
    races: list[Race] | None = None,
) -> Event:
    """Create a minimal Event for testing."""
    if races is None:
        races = [
            Race(
                race_number=1,
                name="Race 1",
                datetimez="2025-01-01T10:00:00+01:00",
                discipline="Middle",
            )
        ]
    return Event(
        id=event_id,
        name=name,
        start_time="2025-01-01",
        end_time="2025-01-01",
        status="Applied",
        original_status="Applied",
        races=races,
        tags=tags if tags is not None else [],
        classes=classes if classes is not None else [],
    )


# --- is_excluded ---


def test_skip_list_event_is_excluded() -> None:
    """Events in the skip list are excluded."""
    event = _make_event(event_id="SWE_55298")
    assert is_excluded(event) is True


def test_normal_event_not_excluded() -> None:
    """Normal events are not excluded."""
    event = _make_event(event_id="SWE_12345")
    assert is_excluded(event) is False


def test_oringen_umbrella_not_in_skip_list() -> None:
    """O-Ringen umbrellas are NOT in the skip list anymore."""
    event = _make_event(event_id="SWE_5115", name="O-Ringen Skåne 2014")
    assert is_excluded(event) is False


# --- has_mtbo_signal ---


def test_mtbo_in_name() -> None:
    """Event with MTBO in name has signal."""
    event = _make_event(name="Uppsala MTBO")
    assert has_mtbo_signal(event) is True


def test_mtb_o_in_name() -> None:
    """Event with MTB-O in name has signal."""
    event = _make_event(name="DM MTB-O medeldistans")
    assert has_mtbo_signal(event) is True


def test_mtb_o_case_insensitive() -> None:
    """Keyword matching is case-insensitive."""
    event = _make_event(name="MtbO Öviksserien #2")
    assert has_mtbo_signal(event) is True


def test_mtb_orientering_in_name() -> None:
    """Event with MTB-orientering in name has signal."""
    event = _make_event(name="Närkeserien i MTB-orientering")
    assert has_mtbo_signal(event) is True


def test_mtbo_in_classes() -> None:
    """Event with MTBO class has signal."""
    event = _make_event(
        name="7-Klubbs",
        classes=["Blå", "MTBO 6km", "Orange"],
    )
    assert has_mtbo_signal(event) is True


def test_mtb_o_in_classes() -> None:
    """Event with MTB-O class has signal."""
    event = _make_event(
        name="O-Ringen Boden",
        classes=["D21", "MTB-O D21", "MTB-O H21"],
    )
    assert has_mtbo_signal(event) is True


def test_no_signal_generic_name() -> None:
    """Event with no MTBO keywords has no signal."""
    event = _make_event(name="Stockholm Rogaining")
    assert has_mtbo_signal(event) is False


def test_mtb_alone_not_signal() -> None:
    """'MTB' alone in name is NOT an MTBO signal."""
    event = _make_event(name="Bahco MTB")
    assert has_mtbo_signal(event) is False


# --- detect_anomaly ---


def test_pure_mtbo_no_anomaly() -> None:
    """Events with empty tags have no anomaly."""
    event = _make_event(tags=[])
    assert detect_anomaly(event) is None


def test_tags_with_mtbo_name_no_anomaly() -> None:
    """Events with tags but MTBO in name are not anomalies."""
    event = _make_event(name="Uppsala MTBO", tags=["FootO"])
    assert detect_anomaly(event) is None


def test_tags_no_signal_is_anomaly() -> None:
    """Events with tags and no MTBO signal are suspect."""
    event = _make_event(name="Stockholm Rogaining", tags=["FootO"])
    assert detect_anomaly(event) == "suspect-no-signal"


# --- OringenFilter ---


def test_non_oringen_not_umbrella() -> None:
    """Non-O-Ringen events are not detected as umbrella."""
    event = _make_event(name="Uppsala MTBO", tags=["FootO"])
    of = OringenFilter(event)
    assert of.is_umbrella is False
    assert of.allowed_classes is None


def test_oringen_without_tags_not_umbrella() -> None:
    """O-Ringen events without discipline tags are not umbrella."""
    event = _make_event(name="O-Ringen Halland MTB-O", tags=[])
    of = OringenFilter(event)
    assert of.is_umbrella is False


def test_oringen_umbrella_detected() -> None:
    """O-Ringen with tags is detected as umbrella."""
    event = _make_event(
        name="O-Ringen Skåne 2014",
        tags=["TrailO", "FootO"],
        classes=["D21", "MTB-O D21"],
    )
    of = OringenFilter(event)
    assert of.is_umbrella is True


def test_filter_classes_keeps_mtbo() -> None:
    """filter_classes reduces event.classes to only MTBO ones."""
    event = _make_event(
        name="O-Ringen Skåne 2014",
        tags=["TrailO", "FootO"],
        classes=["D21", "H21", "MTB-O D21", "MTB-O H21", "MTB-O H40"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    assert event.classes == ["MTB-O D21", "MTB-O H21", "MTB-O H40"]
    assert of.allowed_classes == {"MTB-O D21", "MTB-O H21", "MTB-O H40"}


def test_filter_classes_no_mtbo() -> None:
    """filter_classes empties classes when no MTBO found."""
    event = _make_event(
        name="O-Ringen Hälsingland 2011",
        tags=["FootO", "TrailO"],
        classes=["D21", "H21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    assert event.classes == []
    assert of.allowed_classes == set()


def test_filter_classes_noop_for_non_umbrella() -> None:
    """filter_classes does not touch non-O-Ringen events."""
    event = _make_event(
        name="Uppsala MTBO",
        tags=["FootO"],
        classes=["D21", "H21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    assert event.classes == ["D21", "H21"]


def test_finalize_adds_classes_filtered_tag() -> None:
    """finalize adds CLASSES_FILTERED tag when MTBO classes exist."""
    event = _make_event(
        name="O-Ringen Skåne 2014",
        tags=["TrailO", "FootO"],
        classes=["D21", "MTB-O D21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert TAG_CLASSES_FILTERED in event.tags
    assert TAG_EVENT_SKIP not in event.tags


def test_finalize_adds_event_skip_tag() -> None:
    """finalize adds EVENT_SKIP tag when no MTBO classes."""
    event = _make_event(
        name="O-Ringen Hälsingland 2011",
        tags=["FootO", "TrailO"],
        classes=["D21", "H21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert TAG_EVENT_SKIP in event.tags
    assert TAG_CLASSES_FILTERED not in event.tags


def test_finalize_filters_counts() -> None:
    """finalize filters race counts to only MTBO class keys."""
    race = Race(
        race_number=1,
        name="Race 1",
        datetimez="2025-01-01T10:00:00+01:00",
        discipline="Middle",
        start_counts={"D21": 500, "H21": 600, "MTB-O D21": 25, "MTB-O H21": 30},
        result_counts={"D21": 490, "H21": 590, "MTB-O D21": 24, "MTB-O H21": 29},
    )
    event = _make_event(
        name="O-Ringen Boden",
        tags=["FootO", "TrailO"],
        classes=["D21", "H21", "MTB-O D21", "MTB-O H21"],
        races=[race],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert event.races[0].start_counts == {"MTB-O D21": 25, "MTB-O H21": 30}
    assert event.races[0].result_counts == {"MTB-O D21": 24, "MTB-O H21": 29}


def test_finalize_zeroes_counts_on_event_skip() -> None:
    """EVENT_SKIP events have all race counts cleared."""
    race = Race(
        race_number=1,
        name="Race 1",
        datetimez="2025-01-01T10:00:00+01:00",
        discipline="Middle",
        start_counts={"D21": 500, "H21": 600},
    )
    event = _make_event(
        name="O-Ringen Hälsingland 2011",
        tags=["FootO", "TrailO"],
        classes=["D21", "H21"],
        races=[race],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert event.races[0].start_counts is None


def test_finalize_clears_fingerprints_on_event_skip() -> None:
    """EVENT_SKIP events have fingerprints cleared."""
    race = Race(
        race_number=1,
        name="Race 1",
        datetimez="2025-01-01T10:00:00+01:00",
        discipline="Middle",
        fingerprints=["abc123", "def456"],
    )
    event = _make_event(
        name="O-Ringen Hälsingland 2011",
        tags=["FootO", "TrailO"],
        classes=["D21", "H21"],
        races=[race],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert event.races[0].fingerprints == []


def test_finalize_noop_for_non_umbrella() -> None:
    """finalize does not touch non-O-Ringen events."""
    event = _make_event(
        name="Uppsala MTBO",
        tags=["FootO"],
        classes=["D21", "H21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    assert TAG_CLASSES_FILTERED not in event.tags
    assert TAG_EVENT_SKIP not in event.tags


def test_filter_mutates_in_place() -> None:
    """OringenFilter mutates the event directly (no copy)."""
    event = _make_event(
        name="O-Ringen Skåne 2014",
        tags=["TrailO", "FootO"],
        classes=["D21", "MTB-O D21"],
    )
    of = OringenFilter(event)
    of.filter_classes()
    of.finalize()
    # Same object is modified
    assert event.classes == ["MTB-O D21"]
    assert TAG_CLASSES_FILTERED in event.tags


# --- Constants ---


def test_skip_list_only_non_events() -> None:
    """Skip list only contains truly uninteresting non-events."""
    assert "SWE_55298" in SKIP_LIST
    # O-Ringen IDs should NOT be in skip list
    assert "SWE_1351" not in SKIP_LIST
    assert "SWE_5115" not in SKIP_LIST
    assert "SWE_44022" not in SKIP_LIST


def test_keywords_list() -> None:
    """MTBO_KEYWORDS contains expected keywords."""
    assert "mtbo" in MTBO_KEYWORDS
    assert "mtb-o" in MTBO_KEYWORDS
    assert "mtb" not in MTBO_KEYWORDS


def test_tag_constants_uppercase() -> None:
    """Tag constants are uppercase to distinguish from discipline tags."""
    assert TAG_CLASSES_FILTERED == "CLASSES_FILTERED"
    assert TAG_EVENT_SKIP == "EVENT_SKIP"
