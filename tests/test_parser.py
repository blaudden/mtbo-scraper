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

    # Classification - "National event" -> "National"
    assert parsed_event.classification == "National"


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

    # start_time (2026-08-25) should remain a plain date
    assert updated_event.start_time == "2026-08-25"

    # Race date (2026-08-26 10:00) -> 2026-08-26T10:00:00+02:00 (extracted from UTC+2)
    assert updated_event.races[0].datetimez == "2026-08-26T10:00:00+02:00"
