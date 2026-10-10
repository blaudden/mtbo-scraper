"""Tests for scripts/startlist_bibs.py startlist lookup tool."""

import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from scripts.startlist_bibs import (
    _parse_date_bounds,
    main,
    search_bibs,
)


def test_parse_date_bounds_single_date():
    """Test parsing exact date string."""
    d1, d2 = _parse_date_bounds("2026-08-26")
    assert d1 == date(2026, 8, 26)
    assert d2 == date(2026, 8, 26)


def test_parse_date_bounds_range():
    """Test parsing date ranges with '..' and ':'."""
    d1, d2 = _parse_date_bounds("2026-08-25..2026-08-30")
    assert d1 == date(2026, 8, 25)
    assert d2 == date(2026, 8, 30)

    d1, d2 = _parse_date_bounds("2026-08-30:2026-08-25")
    assert d1 == date(2026, 8, 25)
    assert d2 == date(2026, 8, 30)


def test_parse_date_bounds_month():
    """Test parsing YYYY-MM bounds."""
    d1, d2 = _parse_date_bounds("2026-08")
    assert d1 == date(2026, 8, 1)
    assert d2 == date(2026, 8, 31)

    d1, d2 = _parse_date_bounds("2026-02")
    assert d1 == date(2026, 2, 1)
    assert d2 == date(2026, 2, 28)


def test_parse_date_bounds_year():
    """Test parsing YYYY bounds."""
    d1, d2 = _parse_date_bounds("2026")
    assert d1 == date(2026, 1, 1)
    assert d2 == date(2026, 12, 31)


def test_parse_date_bounds_invalid():
    """Test invalid date string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid date format"):
        _parse_date_bounds("2026-99-99")


def test_search_bibs_with_mock_data(tmp_path: Path):
    """Test search_bibs against temporary partitioned data files."""
    data_dir = tmp_path / "data" / "events"
    year_dir = data_dir / "2026"
    year_dir.mkdir(parents=True)

    # Mock events.json
    events_json = {
        "events": [
            {
                "id": "SWE_9999",
                "name": "Test Cup 2026",
                "start_time": "2026-05-10T10:00:00+02:00",
                "races": [
                    {
                        "race_number": 1,
                        "name": "Sprint",
                        "discipline": "Sprint",
                        "datetimez": "2026-05-10T10:00:00+02:00",
                    }
                ],
            }
        ]
    }
    with (year_dir / "events.json").open("w", encoding="utf-8") as f:
        json.dump(events_json, f)

    # Mock startlist YAML
    startlist_yaml = {
        "participants": [
            {
                "name": "Test Athlete",
                "bib": 105,
                "club": "Test OK",
                "class": "M21",
                "start_time": "10:30:00",
            },
            {
                "name": "Other Rider",
                "start_no": 200,
                "club": "Club B",
                "class": "W21",
            },
        ]
    }
    with (year_dir / "SWE_9999_startlist_1.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(startlist_yaml, f)

    # Match existing bib
    matches = search_bibs(data_dir, date(2026, 5, 10), date(2026, 5, 10), 105)
    assert len(matches) == 1
    assert matches[0].event_id == "SWE_9999"
    assert matches[0].competition_name == "Test Cup 2026"
    assert matches[0].name == "Test Athlete"
    assert matches[0].club == "Test OK"
    assert matches[0].class_name == "M21"
    assert matches[0].start_number == 105
    assert matches[0].distance == "Sprint"

    # Match alternative start_no key
    matches_other = search_bibs(data_dir, date(2026, 5, 10), date(2026, 5, 10), "200")
    assert len(matches_other) == 1
    assert matches_other[0].name == "Other Rider"

    # Search non-matching bib
    no_matches = search_bibs(data_dir, date(2026, 5, 10), date(2026, 5, 10), 999)
    assert len(no_matches) == 0

    # Search outside date range
    outside_range = search_bibs(data_dir, date(2026, 6, 1), date(2026, 6, 30), 105)
    assert len(outside_range) == 0


def test_search_bibs_real_events_smoke():
    """Smoke test against active workspace event files if present."""
    data_dir = Path("data/events")
    if not (data_dir / "2026" / "events.json").exists():
        pytest.skip("Active 2026 event data not found in test environment.")

    # Bib 280 was Rasmus Nordgren on 2026-08-26 (WMTBOC Middle)
    matches = search_bibs(data_dir, date(2026, 8, 26), date(2026, 8, 26), 280)
    assert len(matches) >= 1
    assert any("Rasmus Nordgren" in m.name for m in matches)


def test_cli_contract_single_date_stdout_json(capsys, monkeypatch):
    """Verify CLI contract for single date: <date> <number> -> JSON on stdout."""
    data_dir = Path("data/events")
    if not (data_dir / "2026" / "events.json").exists():
        pytest.skip("Active 2026 event data not found.")

    monkeypatch.setattr(sys, "argv", ["startlist_bibs.py", "2026-08-26", "280"])
    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert len(payload) >= 1

    entry = payload[0]
    expected_contract_keys = {
        "event_id",
        "competition_name",
        "race_number",
        "race_name",
        "distance",
        "date",
        "start_time",
        "start_number",
        "name",
        "club",
        "class_name",
    }
    assert expected_contract_keys.issubset(entry.keys())
    assert entry["start_number"] == 280
    assert entry["date"] == "2026-08-26"
    assert "Rasmus Nordgren" in entry["name"]


def test_cli_contract_range_stdout_json(capsys, monkeypatch):
    """Verify CLI interface contract for date range: <start>..<end> <number>."""
    data_dir = Path("data/events")
    if not (data_dir / "2026" / "events.json").exists():
        pytest.skip("Active 2026 event data not found.")

    monkeypatch.setattr(
        sys,
        "argv",
        ["startlist_bibs.py", "2026-08-25..2026-08-30", "330"],
    )
    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert len(payload) >= 1
    assert any("Signe Feil" in r["name"] for r in payload)


def test_cli_contract_no_matches_returns_empty_json_list(capsys, monkeypatch):
    """Verify CLI interface returns empty JSON list when no matches are found."""
    monkeypatch.setattr(sys, "argv", ["startlist_bibs.py", "2026-08-26", "999999"])
    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == []
