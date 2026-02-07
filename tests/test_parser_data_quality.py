from pathlib import Path

from src.sources.eventor_parser import EventorParser


def test_start_number_extraction_iof_7490() -> None:
    """Verify start_number extraction and type conversion for IOF championships."""
    parser = EventorParser()

    # Path to the sample start list
    html_file = Path(__file__).parent / "data" / "IOF_7490_race1_start_list.html"

    if not html_file.exists():
        # Fallback for different test run environments
        html_file = Path("tests/data/IOF_7490_race1_start_list.html")

    html_content = html_file.read_text(encoding="utf-8")

    participants = parser.parse_participant_list(html_content)

    assert len(participants) > 0

    # Check first few participants (Men class)
    # 101: Ildar Mihnev
    # 102: Tobias Breitschaedel

    p1 = next(p for p in participants if p["name"] == "Ildar Mihnev")
    assert int(str(p1["start_number"])) == 101
    assert isinstance(p1["start_number"], int)

    p2 = next(p for p in participants if p["name"] == "Tobias Breitschaedel")
    assert int(str(p2["start_number"])) == 102
    assert isinstance(p2["start_number"], int)


def test_start_number_handling_various_formats() -> None:
    """Test handling of different start_number formats manually."""
    parser = EventorParser()

    # Mock HTML with various start number scenarios
    html = """
    <div class="eventClassHeader"><h3>Test Class</h3></div>
    <table>
        <tbody>
            <tr><td class="n">Numeric</td><td class="o">Club</td>
                <td class="b"> 123 </td></tr>
            <tr><td class="n">Alpha</td><td class="o">Club</td>
                <td class="b">123A</td></tr>
            <tr><td class="n">Empty</td><td class="o">Club</td>
                <td class="b">   </td></tr>
            <tr><td class="n">None</td><td class="o">Club</td></tr>
        </tbody>
    </table>
    """

    participants = parser.parse_participant_list(html)

    numeric = next(p for p in participants if p["name"] == "Numeric")
    assert int(str(numeric["start_number"])) == 123
    assert isinstance(numeric["start_number"], int)

    # Test with hidden characters (non-breaking space)
    html_hidden = """
    <div class="eventClassHeader"><h3>Hidden Class</h3></div>
    <table>
        <tbody>
                <tr>
                    <td class="n">Hidden</td>
                    <td class="o">Club</td>
                    <td class="b"> 202&nbsp;</td>
                </tr>
        </tbody>
    </table>
    """
    participants_hidden = parser.parse_participant_list(html_hidden)
    hidden = next(p for p in participants_hidden if p["name"] == "Hidden")
    assert int(str(hidden["start_number"])) == 202
    assert isinstance(hidden["start_number"], int)

    alpha = next(p for p in participants if p["name"] == "Alpha")
    assert alpha["start_number"] == "123A"
    assert isinstance(alpha["start_number"], str)

    empty = next(p for p in participants if p["name"] == "Empty")
    assert empty["start_number"] is None

    none = next(p for p in participants if p["name"] == "None")
    assert none["start_number"] is None
