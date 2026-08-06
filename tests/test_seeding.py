from src.models import CupStandings
from src.utils.seeding import calculate_seeding_order


def test_calculate_seeding_order_2026(
    cup_2026: CupStandings, cup_2025: CupStandings
) -> None:
    """Test seeding calculation using 2025 and 2026 cup standings."""
    seeding = calculate_seeding_order(cup_2026, cup_2025, year=2026)

    assert seeding.year == 2026
    assert "H21" in seeding.classes
    assert "D21" in seeding.classes

    h21_seeding = seeding.classes["H21"]
    assert len(h21_seeding) >= 8

    # Rank 1 should be Rasmus Nordgren (1st in 2025 and 1st in 2026)
    assert h21_seeding[0].seed_rank == 1
    assert h21_seeding[0].name == "Rasmus Nordgren"
    assert h21_seeding[0].seed_val == 1
    assert h21_seeding[0].is_seeded is True

    # Check H21 top 8 seeded flag (field size > 24 so capped at 8)
    h21_seeded_count = sum(1 for e in h21_seeding if e.is_seeded)
    assert h21_seeded_count == 8
    assert h21_seeding[8].is_seeded is False

    # Check H17-20 small class case (13 riders -> top 8 are marked as seeded group)
    h17_seeding = seeding.classes["H17-20"]
    assert len(h17_seeding) == 13
    h17_seeded_count = sum(1 for e in h17_seeding if e.is_seeded)
    assert h17_seeded_count == 8
    assert h17_seeding[7].is_seeded is True
    assert h17_seeding[8].is_seeded is False


def test_calculate_seeding_order_fallback_previous_year(
    cup_2025: CupStandings,
) -> None:
    """Test fallback when current year cup has no standings yet."""
    # When current_cup is None (before 1st race of 2026)
    seeding = calculate_seeding_order(
        current_cup=None, previous_cup=cup_2025, year=2026
    )

    assert seeding.year == 2026
    h21_seeding = seeding.classes["H21"]
    assert h21_seeding[0].name == "Rasmus Nordgren"
    assert h21_seeding[0].seed_val == 1
    assert h21_seeding[0].current_rank is None
    assert h21_seeding[0].previous_rank == 1


def test_calculate_seeding_order_both_none() -> None:
    """Test behavior when both current_cup and previous_cup are None."""
    seeding = calculate_seeding_order(current_cup=None, previous_cup=None, year=2026)

    assert seeding.year == 2026
    for cls in ("H21", "D21", "H17-20", "D17-20"):
        assert seeding.classes[cls] == []


def test_seeding_order_provenance(
    cup_2026: CupStandings, cup_2025: CupStandings
) -> None:
    """Test that provenance metadata is populated."""
    seeding = calculate_seeding_order(cup_2026, cup_2025, year=2026)

    assert seeding.generated_at is not None
    assert len(seeding.generated_at) > 0
    assert seeding.current_cup_url == (
        "https://eventor.orientering.se/Standings/View/Series/1539"
    )
    assert seeding.previous_cup_url == (
        "https://eventor.orientering.se/Standings/View/Series/1418"
    )


def test_seeding_order_provenance_partial() -> None:
    """Test provenance when cups are None."""
    seeding = calculate_seeding_order(current_cup=None, previous_cup=None, year=2026)

    assert seeding.current_cup_url is None
    assert seeding.previous_cup_url is None
    assert seeding.generated_at is not None
