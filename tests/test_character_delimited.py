"""
Tests for CharacterDelimitedParser and its convenience subclasses.
"""

import pytest
from flatparse.character_delimited import (
    CharacterDelimitedParser,
    CommaSeparatedParser,
    TabSeparatedParser,
    PipeDelimitedParser,
    SemicolonSeparatedParser,
)


# ---------------------------------------------------------------------------
# Basic comma-separated
# ---------------------------------------------------------------------------

class TestCommaSeparated:

    def test_basic_csv(self):
        block = (
            "name,density,youngs_modulus,poisson\n"
            "aluminium,2700,70000,0.33\n"
            "steel,7800,210000,0.30"
        )
        table = CommaSeparatedParser().parse(block)
        assert table.header == ["name", "density", "youngs_modulus", "poisson"]
        assert table.rows[0] == ["aluminium", "2700", "70000", "0.33"]
        assert table.rows[1] == ["steel", "7800", "210000", "0.30"]

    def test_whitespace_around_values_stripped(self):
        block = (
            "name, density, youngs\n"
            "aluminium , 2700 , 70000"
        )
        table = CommaSeparatedParser().parse(block)
        assert table.header == ["name", "density", "youngs"]
        assert table.rows[0] == ["aluminium", "2700", "70000"]

    def test_empty_cells_preserved(self):
        block = (
            "a,b,c,d\n"
            "1,,3,\n"
            ",,3,4"
        )
        table = CommaSeparatedParser().parse(block)
        assert table.rows[0] == ["1", "", "3", ""]
        assert table.rows[1] == ["", "", "3", "4"]


# ---------------------------------------------------------------------------
# Other delimiters
# ---------------------------------------------------------------------------

class TestPipeDelimited:

    def test_markdown_style_table(self):
        block = (
            "ID     | Nombre         | Edad | Ciudad\n"
            "-------|----------------|------|---------\n"
            "001    | Ana Gómez      | 28   | Madrid\n"
            "002    | Luis Martínez  | 34   | Bogotá\n"
            "003    | María Silva    | 22   | Lima"
        )
        table = PipeDelimitedParser().parse(block)
        assert table.header == ["ID", "Nombre", "Edad", "Ciudad"]
        assert table.rows[0] == ["001", "Ana Gómez", "28", "Madrid"]
        assert table.rows[1] == ["002", "Luis Martínez", "34", "Bogotá"]
        assert table.rows[2] == ["003", "María Silva", "22", "Lima"]


class TestTabSeparated:

    def test_basic_tsv(self):
        block = "name\tvalue\tunit\nflow\t123.45\tkg/s\ntemp\t450.0\tK"
        table = TabSeparatedParser().parse(block)
        assert table.header == ["name", "value", "unit"]
        assert table.rows[0] == ["flow", "123.45", "kg/s"]


class TestSemicolonSeparated:

    def test_regional_csv_variant(self):
        block = (
            "name;value\n"
            "flow;123,45\n"  # German-style decimal comma inside cells
            "temp;450,00"
        )
        table = SemicolonSeparatedParser().parse(block)
        assert table.rows[0] == ["flow", "123,45"]
        assert table.rows[1] == ["temp", "450,00"]


# ---------------------------------------------------------------------------
# Multi-line headers
# ---------------------------------------------------------------------------

class TestMultiLineHeaders:

    def test_name_plus_units(self):
        block = (
            "id,flow,temp\n"
            ",kg/s,K\n"
            "ENG-001,123.45,450.0\n"
            "ENG-002,98.12,431.0"
        )
        table = CommaSeparatedParser(header_rows=2).parse(block)
        assert table.header == ["id", "flow kg/s", "temp K"]
        assert table.rows[0] == ["ENG-001", "123.45", "450.0"]


# ---------------------------------------------------------------------------
# Separator-line filtering
# ---------------------------------------------------------------------------

class TestSeparatorLines:

    def test_dash_separator_under_csv_header(self):
        block = (
            "name,value\n"
            "----,-----\n"
            "flow,123.45\n"
            "temp,450"
        )
        table = CommaSeparatedParser().parse(block)
        assert table.header == ["name", "value"]
        assert table.rows == [["flow", "123.45"], ["temp", "450"]]

    def test_pipe_dash_separator_in_markdown_table(self):
        """The '-------|----' line under a markdown table header."""
        block = (
            "a | b | c\n"
            "--|---|--\n"
            "1 | 2 | 3"
        )
        table = PipeDelimitedParser().parse(block)
        assert table.header == ["a", "b", "c"]
        assert table.rows == [["1", "2", "3"]]


# ---------------------------------------------------------------------------
# detect() behaviour
# ---------------------------------------------------------------------------

class TestDetect:

    def test_detect_valid_csv(self):
        block = "a,b,c\n1,2,3\n4,5,6"
        assert CommaSeparatedParser().detect(block) is True

    def test_detect_rejects_non_csv(self):
        block = "this is just prose without commas\nanother line of prose"
        assert CommaSeparatedParser().detect(block) is False

    def test_detect_rejects_inconsistent_column_count(self):
        block = "a,b,c\n1,2,3,4,5,6\nx,y"  # wildly varying counts
        assert CommaSeparatedParser().detect(block) is False

    def test_detect_correct_delimiter_wins(self):
        block = "a|b|c\n1|2|3\n4|5|6"
        assert PipeDelimitedParser().detect(block) is True
        assert CommaSeparatedParser().detect(block) is False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfiguration:

    def test_strip_cells_can_be_disabled(self):
        block = "a, b , c\n 1 , 2 , 3 "
        table = CommaSeparatedParser(strip_cells=False).parse(block)
        assert table.header == ["a", " b ", " c"]
        assert table.rows[0] == [" 1 ", " 2 ", " 3 "]

    def test_custom_delimiter_via_base_class(self):
        block = "a:b:c\n1:2:3"
        table = CharacterDelimitedParser(delimiter=":").parse(block)
        assert table.header == ["a", "b", "c"]
        assert table.rows == [["1", "2", "3"]]

    def test_rejects_multi_char_delimiter(self):
        with pytest.raises(ValueError):
            CharacterDelimitedParser(delimiter="||")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
