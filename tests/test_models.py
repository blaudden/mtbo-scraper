from src.models import (
    Area,
    Document,
    EntryDeadline,
    Event,
    Official,
    Organiser,
    Position,
    Race,
    Url,
)


def test_event_roundtrip_full() -> None:
    """Test that Event.from_dict returns an equivalent object with all fields."""
    original = Event(
        id="SWE_123",
        name="Test Event",
        start_time="2023-01-01",
        end_time="2023-01-02",
        status="Applied",
        original_status="Applied",
        types=["National", "Championship"],
        tags=["MTBO", "Long"],
        form="Individual",
        organisers=[
            Organiser(name="Club A", country_code="SWE"),
            Organiser(name="Club B", country_code=None),
        ],
        officials=[
            Official(role="EventDirector", name="Director X"),
        ],
        classes=["H21", "D21"],
        urls=[
            Url(
                type="Website",
                url="http://example.com",
                title="Home",
                last_updated_at="2023-01-01T10:00:00",
            ),
        ],
        documents=[
            Document(
                type="Bulletin",
                title="Bull 1",
                url="http://doc.pdf",
                published_time="2022-12-01",
            ),
        ],
        information="Info text",
        region="Region X",
        punching_system="SI",
        entry_deadlines=[
            EntryDeadline(type="normal", datetimez="2022-12-20T23:59:00+01:00"),
        ],
        races=[
            Race(
                race_number=1,
                name="Race 1",
                datetimez="2023-01-01T10:00:00+01:00",
                discipline="Long",
                night_or_day="day",
                position=Position(lat=59.0, lng=18.0),
                areas=[
                    Area(lat=59.1, lng=18.1, polygon=[[59.1, 18.1], [59.2, 18.2]]),
                ],
                urls=[
                    Url(type="StartList", url="http://starts.xml"),
                ],
                documents=[],
                entry_counts={"H21": 10},
                start_counts={"H21": 9},
                result_counts={"H21": 8},
                fingerprints=["hash1", "hash2"],
            )
        ],
    )

    as_dict = original.to_dict()
    reconstructed = Event.from_dict(as_dict)

    assert reconstructed == original
    # explicit checks for nested objects to be sure
    assert len(reconstructed.races) == 1
    assert reconstructed.races[0].name == "Race 1"
    assert reconstructed.races[0].position is not None
    assert reconstructed.races[0].position.lat == 59.0
    assert reconstructed.races[0].areas[0].polygon == [[59.1, 18.1], [59.2, 18.2]]
    assert reconstructed.organisers[0].name == "Club A"


def test_event_roundtrip_minimal() -> None:
    """Test roundtrip with minimal fields (many defaults/Nones)."""
    original = Event(
        id="SWE_MIN",
        name="Min",
        start_time="2023-01-01",
        end_time="2023-01-01",
        status="Planned",
        original_status="Planned",
        races=[],
    )
    # Validate defaults are set correctly
    assert original.types == []
    assert original.tags == []

    as_dict = original.to_dict()
    reconstructed = Event.from_dict(as_dict)

    assert reconstructed == original
    assert reconstructed.id == "SWE_MIN"
    assert reconstructed.races == []
