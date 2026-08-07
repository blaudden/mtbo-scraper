from src.models import CupStandings


def test_parse_series_standings_1539(cup_2026: CupStandings) -> None:
    """Test parsing Svenska cupen MTBO 2026 (series 1539)."""
    assert cup_2026.id == "1539"
    assert cup_2026.year == 2026
    assert "Svenska" in cup_2026.name

    # Verify exact class keys without extra page-chrome headings
    expected_classes = {"H21", "D21", "H17-20", "D17-20"}
    assert set(cup_2026.classes.keys()) == expected_classes

    # Check top entry in H21
    h21_entries = cup_2026.classes["H21"]
    # Three rows have an empty place cell and are excluded
    assert len(h21_entries) == 8
    first = h21_entries[0]
    assert first.rank == 1
    assert first.name == "Rasmus Nordgren"
    assert first.club == "OK Kåre"
    assert first.points == 110.0


def test_parse_series_standings_1418(cup_2025: CupStandings) -> None:
    """Test parsing Svenska Cupen MTBO 2025 (series 1418)."""
    assert cup_2025.id == "1418"
    assert cup_2025.year == 2025

    expected_classes = {"H21", "D21", "H17-20", "D17-20"}
    assert set(cup_2025.classes.keys()) == expected_classes

    h21_entries = cup_2025.classes["H21"]
    assert h21_entries[0].name == "Rasmus Nordgren"
    assert h21_entries[0].points == 550.0
