import os

import pytest

from src.models import Event, Organiser, Race
from src.sources.eventor_parser import EventorParser
from src.utils.crypto import Crypto
from src.utils.date_and_time import format_iso_datetime


def load_test_file(filename: str) -> str:
    """Loads a test file."""
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def parser() -> EventorParser:
    return EventorParser()


def create_base_event(id: str, name: str, date: str, country: str = "SWE") -> Event:
    """Helper to create a base event object for testing details parsing."""
    # Event start/end should be PLAIN dates
    # Race date should be ISO with offset
    iso_race_dt = format_iso_datetime(date, None, country)
    e = Event(
        id=id,
        name=name,
        start_time=date,
        end_time=date,
        status="Sanctioned",
        original_status="Active",
        types=["Test event"],  # Placeholder, will be overwritten by parser
        races=[],
        organisers=[Organiser(name="Org", country_code=country)],
    )
    # Parser often expects at least one race to exist to update, or it creates one.
    e.races.append(
        Race(race_number=1, name=name, datetimez=iso_race_dt, discipline="Other")
    )
    return e


def test_parse_swe_single(parser: EventorParser) -> None:
    html = load_test_file("SWE_54361_single.html")
    event = create_base_event("SWE_54361", "Test", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    # Info text should be None (effectively empty for this event)
    assert parsed_event.information is None

    # Map positions -> race areas
    assert parsed_event.races, "Should have at least one race"
    areas = parsed_event.races[0].areas
    # Ensure areas or position exist
    assert areas or parsed_event.races[0].position
    if areas:
        assert areas[0].lat != 0
        assert areas[0].lng != 0

    # Discipline and Day/Night
    # The file has "Race distance": "Long" -> discipline="Long"
    assert parsed_event.races[0].discipline == "Long"
    assert parsed_event.races[0].night_or_day == "day"

    # Contact
    contact_names = [
        o.name
        for o in parsed_event.officials
        if "Contact" in o.role or "Kontakt" in o.role
    ]
    assert "Ilana Jode" in contact_names

    # Classes
    assert isinstance(parsed_event.classes, list)


def test_parse_swe_multi(parser: EventorParser) -> None:
    html = load_test_file("SWE_50597_multi.html")
    event = create_base_event("SWE_50597", "Test Multi", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    # Races
    assert len(parsed_event.races) == 5

    # Verify race 1
    # July 20th 2026 in Sweden is CEST (UTC+2)
    race1 = parsed_event.races[0]
    assert "Etapp 1" in race1.name
    assert race1.discipline == "Long"
    assert race1.datetimez == "2026-07-20T00:00:00+02:00"
    assert race1.night_or_day == "day"

    # Verify race 3
    race3 = parsed_event.races[2]
    assert "Etapp 3" in race3.name
    assert race3.discipline == "Sprint"
    assert race3.datetimez == "2026-07-23T00:00:00+02:00"

    # Types - ["National"] (cleaned from "National event")
    assert parsed_event.types == ["National"]


def test_parse_nor_single(parser: EventorParser) -> None:
    html = load_test_file("NOR_21169_single.html")
    event = create_base_event("NOR_21169", "Test NOR", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    # Contact
    contacts = [
        o.name
        for o in parsed_event.officials
        if "Contact" in o.role or "Kontakt" in o.role
    ]
    assert "Leif Eriksson" in contacts

    # Classes
    assert len(parsed_event.classes) == 3
    assert "Lang" in parsed_event.classes

    # Discipline
    # Parser correctly identified "Middle" (text was in English in test file)
    assert parsed_event.races[0].discipline == "Middle"

    # Check for decoded email (Encrypted)
    email_official = next(
        (o for o in parsed_event.officials if "email" in o.role and "enc:" in o.name),
        None,
    )
    assert email_official, "Should have decoded (and encrypted) email"
    decrypted_email = Crypto.decrypt(email_official.name)
    assert decrypted_email == "leif.gustav.eriksson@gmail.com"

    # Documents
    assert parsed_event.documents
    assert parsed_event.documents[0].title == "Innbydelse"
    assert parsed_event.documents[0].type == "Invitation"


def test_parse_iof_single(parser: EventorParser) -> None:
    html = load_test_file("IOF_8558_single.html")
    event = create_base_event("IOF_8558", "Test IOF", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    # Map positions
    assert parsed_event.races[0].areas or parsed_event.races[0].position

    # Documents
    doc_titles = [d.title for d in parsed_event.documents]
    assert "Embargoed areas" in doc_titles
    assert "Bulletin 2" in doc_titles


def test_parse_iof_multi(parser: EventorParser) -> None:
    html = load_test_file("IOF_8277_multi.html")
    event = create_base_event("IOF_8277", "Test IOF Multi", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    assert len(parsed_event.races) >= 4
    race_names = [r.name for r in parsed_event.races]
    assert any("Middle" in n for n in race_names)
    assert any("Long" in n for n in race_names)
    assert any("Sprint" in n for n in race_names)
    assert any("Relay" in n for n in race_names)

    # Documents
    assert len(parsed_event.documents) >= 2


def test_parse_skinkloppet(parser: EventorParser) -> None:
    html = load_test_file("SWE_56468_main.html")
    event = create_base_event("SWE_56468", "Skinkloppet", "2025-11-30")

    parsed_event = parser.parse_event_details(html, event)

    if parsed_event.information:
        assert "Klubbaktivitet för medlemmar" in parsed_event.information
        assert "Lars R" in parsed_event.information

    # Race
    assert len(parsed_event.races) == 1
    r = parsed_event.races[0]
    assert r.name == "Skinkloppet"
    assert r.discipline == "Other"


def test_parse_list_count(parser: EventorParser) -> None:
    html = load_test_file("SWE_51338_result_list.html")
    res = parser.parse_list_count(html)
    assert res["total_count"] > 50


def test_list_url_extraction(parser: EventorParser) -> None:
    html = load_test_file("SWE_51338_main.html")
    event = create_base_event("SWE_51338", "Test", "2025-08-30")

    parsed_event = parser.parse_event_details(html, event)

    # Check for List URLs in Race or Event
    has_list = False

    # Check races
    for r in parsed_event.races:
        for u in r.urls:
            if u.type in ["EntryList", "StartList", "ResultList"]:
                has_list = True

    # Check event
    for u in parsed_event.urls:
        if u.type in ["EntryList", "StartList", "ResultList"]:
            has_list = True

    assert has_list


def test_parse_livelox_links(parser: EventorParser) -> None:
    html = load_test_file("SWE_51338_main.html")
    event = create_base_event("SWE_51338", "Test", "2025-08-30")

    parsed_event = parser.parse_event_details(html, event)

    # Check Livelox
    has_livelox = False
    for r in parsed_event.races:
        for u in r.urls:
            if u.type == "Livelox":
                has_livelox = True
    assert has_livelox


def test_parse_swe_46200_livelox(parser: EventorParser) -> None:
    html = load_test_file("SWE_46200_main.html")
    # Event with 2 races/stages
    event = create_base_event("SWE_46200", "Livelox Test", "2025-08-30")
    event.races.append(
        Race(race_number=2, name="Etapp 2", datetimez="2025-08-31", discipline="Middle")
    )

    parsed_event = parser.parse_event_details(html, event)

    # Expect Livelox links on both races
    r1_livelox = [u for u in parsed_event.races[0].urls if u.type == "Livelox"]
    r2_livelox = [u for u in parsed_event.races[1].urls if u.type == "Livelox"]

    assert r1_livelox, "Race 1 should have Livelox link"
    assert r2_livelox, "Race 2 should have Livelox link"

    # Verify index mapping logic (link 1 -> race 1, link 2 -> race 2)
    # Based on user snippet:
    # Etapp 1 link -> .../161781
    # Etapp 2 link -> .../161782
    assert "161781" in r1_livelox[0].url
    assert "161782" in r2_livelox[0].url

    # No livelox links should be found in the main event.
    event_livelox = [u for u in parsed_event.urls if u.type == "Livelox"]
    assert not event_livelox, (
        f"Main event should not have generic Livelox links, found: {event_livelox}"
    )

    # Verify Website links: should only have the external one, not the
    # internal circular link
    websites = [u for u in parsed_event.urls if u.type == "Website"]
    assert len(websites) == 1, (
        f"Expected 1 Website link, found {len(websites)}: {websites}"
    )
    assert "oringen.se" in websites[0].url


def test_info_text_nullability(parser: EventorParser) -> None:
    # Minimal HTML with empty info text
    html = """
    <html>
    <body>
        <div class="showEventInfoContainer">
            <p class="info">   </p> <!-- Empty after strip -->
        </div>
    </body>
    </html>
    """
    event = create_base_event("TEST_NULL_INFO", "Null Info Test", "2025-01-01")
    parsed_event = parser.parse_event_details(html, event)

    # default is None, but we want to ensure parser doesn't set it to ""
    assert parsed_event.information is None, (
        f"Expected None, got '{parsed_event.information}'"
    )

    # Minimal HTML with actual text
    html_with_text = """
    <html>
    <body>
        <div class="showEventInfoContainer">
            <p class="info">Some info</p>
        </div>
    </body>
    </html>
    """
    parsed_event_text = parser.parse_event_details(html_with_text, event)
    assert parsed_event_text.information == "Some info"


def test_iof_venue_timezone(parser: EventorParser) -> None:
    # Mock IOF HTML with a specific country (e.g., Italy)
    html = """
    <table>
        <caption>General information</caption>
        <tr><th>Organising federation</th><td>Italy</td></tr>
        <tr><th>Date</th><td>25 August 2026 - 30 August 2026</td></tr>
    </table>
    <table class="eventInfo">
        <caption>Race 1</caption>
        <tr><th>Date</th><td>26 August 2026 at 10:00 local time (UTC+2)</td></tr>
        <tr><th>Competition format</th><td>Middle</td></tr>
    </table>
    """
    # Event ID must start with IOF_ to trigger extra logic
    event = create_base_event("IOF_123", "IOF Italy", "2026-08-25", country="IOF")

    # We need to make sure start_time is set to something that
    # format_iso_datetime can re-format
    # create_base_event sets it to ISO format already.
    # parse_event_details will re-format it using the extracted venue_country.

    updated_event = parser.parse_event_details(html, event)

    # start_time (2026-08-25) derived from "Date" attribute (Prioritized)
    assert updated_event.start_time == "2026-08-25"

    # Race date (2026-08-26 10:00) -> 2026-08-26T10:00:00+02:00 (extracted from UTC+2)
    assert updated_event.races[0].datetimez == "2026-08-26T10:00:00+02:00"


def test_iof_world_championship_type(parser: EventorParser) -> None:
    """Test that World Championships type is extracted correctly."""
    html = load_test_file("IOF_7490_main.html")
    event = create_base_event("IOF_7490", "World Championships", "2025-08-11", "IOF")

    parsed_event = parser.parse_event_details(html, event)

    # Should extract raw values from "Event types" as a list
    # HTML contains: "World Championships\nWorld Cup\nWorld Ranking Event"
    assert "World Championships" in parsed_event.types
    assert "World Cup" in parsed_event.types
    assert "World Ranking Event" in parsed_event.types


def test_iof_european_championship_type(parser: EventorParser) -> None:
    """Test that European Championships type is extracted correctly."""
    html = load_test_file("IOF_8558_single.html")
    event = create_base_event("IOF_8558", "European Championships", "2026-05-23", "IOF")

    parsed_event = parser.parse_event_details(html, event)

    # Should extract raw value from "Event type" attribute as a list
    assert parsed_event.types == ["Regional Championships"]


def test_iof_world_cup_type(parser: EventorParser) -> None:
    """Test that World Cup event type is extracted correctly."""
    html = load_test_file("IOF_8277_multi.html")
    event = create_base_event("IOF_8277", "World Championships", "2026-08-25", "IOF")

    parsed_event = parser.parse_event_details(html, event)

    # Should extract raw values from "Event types" as a list
    # HTML contains: "World Championships\nWorld Ranking Event"
    assert "World Championships" in parsed_event.types
    assert "World Ranking Event" in parsed_event.types


def test_discipline_tags(parser: EventorParser) -> None:
    """Test that discipline tags are parsed correctly (excluding MTBO)."""
    html = load_test_file("SWE_56468_main.html")
    event = create_base_event("SWE_56468", "Test", "2025-01-01")

    parsed_event = parser.parse_event_details(html, event)

    # SWE_56468 has: FootO, MTBO, SkiO, TrailO, Orienteringsskytte, Indoor
    # MTBO should be excluded
    assert "FootO" in parsed_event.tags
    assert "SkiO" in parsed_event.tags
    assert "TrailO" in parsed_event.tags
    assert "Indoor" in parsed_event.tags
    assert "MTBO" not in parsed_event.tags  # Should be filtered out


def test_iof_7490_race_links(parser: EventorParser) -> None:
    """Verifies that IOF_7490 (WMTBOC 2025) extracts links onto correct races."""
    html = load_test_file("IOF_7490_main.html")

    event = Event(
        id="IOF_7490",
        name="WMTBOC 2025",
        start_time="2025-08-10",
        end_time="2025-08-17",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )

    # Process the HTML
    event = parser.parse_event_details(html, event)

    # 5 races expected
    assert len(event.races) == 5

    # Race 1: Sprint
    r1 = event.races[0]
    assert r1.name == "Sprint"
    assert any(u.type == "StartList" and "eventId=8446" in u.url for u in r1.urls)
    assert any(u.type == "ResultList" and "/Events/Show/8446" in u.url for u in r1.urls)

    # Race 2: Middle
    r2 = event.races[1]
    assert r2.name == "Middle"
    assert any(u.type == "StartList" and "eventId=8447" in u.url for u in r2.urls)
    assert any(u.type == "ResultList" and "/Events/Show/8447" in u.url for u in r2.urls)

    # Race 5: Relay
    r5 = event.races[4]
    assert r5.name == "Relay"
    assert any(u.type == "StartList" and "eventId=8451" in u.url for u in r5.urls)
    # The Relay result link is NOT on the race (PDF/External Document)
    assert not any(u.type == "ResultList" for u in r5.urls)
    # But it SHOULD be in event.documents
    assert any(
        d.type == "ResultList" and "Relay results" in d.title for d in event.documents
    )


def test_iof_7490_no_event_links_leakage(parser: EventorParser) -> None:
    """Ensures StartList links are moved to races and not left at event level."""
    html = load_test_file("IOF_7490_main.html")

    event = Event(
        id="IOF_7490",
        name="WMTBOC 2025",
        start_time="2025-08-10",
        end_time="2025-08-17",
        status="Sanctioned",
        original_status="Active",
        races=[],
    )

    event = parser.parse_event_details(html, event)

    # There should be NO StartList links on the main event object anymore
    # as they were assigned to specific races
    event_start_lists = [u for u in event.urls if u.type == "StartList"]
    assert len(event_start_lists) == 0


def test_iof_7490_country_and_club(parser: EventorParser) -> None:
    """Verifies IOF_7490 extraction of country (Poland->POL) and club."""
    html = load_test_file("IOF_7490_main.html")
    event = create_base_event("IOF_7490", "WMTBOC 2025", "2025-08-11", "IOF")

    updated_event = parser.parse_event_details(html, event)

    organisers = updated_event.organisers

    # 1. Check for Federation "Poland" -> "POL"
    fed_org = next(
        (o for o in organisers if o.name == "Poland" and o.country_code == "POL"), None
    )
    assert fed_org is not None, "Federation organiser 'Poland' (POL) not found"

    # 2. Check for Club "Team 360..." -> "POL"
    club_org = next((o for o in organisers if "Team 360" in o.name), None)
    assert club_org is not None, "Club organiser 'Team 360...' not found"
    assert club_org.country_code == "POL", "Club organiser should inherit 'POL' code"
