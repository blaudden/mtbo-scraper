from src.sources.eventor_parser import EventorParser
from tests.test_parser import create_base_event, load_test_file


def test_document_date_extraction() -> None:
    """Test that document published time is correctly extracted."""
    parser = EventorParser()
    html = load_test_file("IOF_8558_single.html")
    event = create_base_event("IOF_8558", "Test IOF", "2026-05-22", "IOF")

    parsed_event = parser.parse_event_details(html, event)

    # Check "Embargoed areas" document
    # HTML: <span class="documentSizeAndDate">(3 446 kB, 14/05/2025)</span>
    embargo_doc = next(
        (d for d in parsed_event.documents if "Embargoed areas" in d.title), None
    )
    assert embargo_doc is not None
    assert embargo_doc.published_time == "2025-05-14", (
        f"Expected 2025-05-14, got {embargo_doc.published_time}"
    )

    # Check "Bulletin 2" document
    # HTML: <span class="documentSizeAndDate">(3 403 kB, 14/05/2025)</span>
    bulletin_doc = next(
        (d for d in parsed_event.documents if "Bulletin 2" in d.title), None
    )
    assert bulletin_doc is not None
    assert bulletin_doc.published_time == "2025-05-14", (
        f"Expected 2025-05-14, got {bulletin_doc.published_time}"
    )


def test_swe_document_date_extraction() -> None:
    """Test document date extraction for a Swedish event with multiple documents."""
    parser = EventorParser()
    html = load_test_file("SWE_51338_main.html")
    event = create_base_event("SWE_51338", "Test SWE", "2025-08-30", "SWE")

    parsed_event = parser.parse_event_details(html, event)

    # Check "Inbjudan" (21/05/2025)
    inbjudan = next((d for d in parsed_event.documents if "Inbjudan" in d.title), None)
    assert inbjudan is not None
    assert inbjudan.published_time == "2025-05-21"

    # Check "PM" (28/08/2025)
    pm = next((d for d in parsed_event.documents if "PM" in d.title), None)
    assert pm is not None
    assert pm.published_time == "2025-08-28"

    # Check "Karta Arena" (28/08/2025) - same date as PM
    karta = next((d for d in parsed_event.documents if "Karta Arena" in d.title), None)
    assert karta is not None
    assert karta.published_time == "2025-08-28"
