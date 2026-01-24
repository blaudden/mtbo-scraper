from src.sources.eventor_parser import EventorParser


class TestEventorParserUtils:
    def test_split_multi_value_field_basic(self) -> None:
        """Test basic newline splitting."""
        text = "Name 1\nName 2"
        expected = ["Name 1", "Name 2"]
        assert EventorParser.split_multi_value_field(text) == expected

    def test_split_multi_value_field_comma(self) -> None:
        """Test comma splitting."""
        text = "Name 1, Name 2"
        expected = ["Name 1", "Name 2"]
        assert EventorParser.split_multi_value_field(text) == expected

    def test_split_multi_value_field_concatenated_camel_case(self) -> None:
        """Test splitting concatenated names like NameLastname."""
        text = "HenrikJohnsson"
        expected = ["Henrik Johnsson"]
        assert EventorParser.split_multi_value_field(text) == expected

    def test_split_multi_value_field_concatenated_pairs(self) -> None:
        """Test splitting concatenated pairs e.g. Name LastnameName Lastname."""
        text = "Henrik JohnssonGustav Jonsson"
        expected = ["Henrik Johnsson", "Gustav Jonsson"]
        assert EventorParser.split_multi_value_field(text) == expected

    def test_split_multi_value_field_acronym(self) -> None:
        """Test that acronyms are skipped."""
        text = "MTBO"
        expected = ["MTBO"]
        assert EventorParser.split_multi_value_field(text) == expected

    def test_split_multi_value_field_swedish_chars(self) -> None:
        """Test that non-ascii avoids complex splitting to be safe."""
        text = "Åke Öberg"
        expected = ["Åke Öberg"]
        assert EventorParser.split_multi_value_field(text) == expected
