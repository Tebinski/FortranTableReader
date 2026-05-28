"""
Tests for WhitespaceParser - covers cases where whitespace splitting is
correct, and verifies detect() rejects cases that need FixedWidthParser
or CharacterDelimitedParser.
"""

import pytest
from flatparse import WhitespaceParser


# ---------------------------------------------------------------------------
# Cases WhitespaceParser handles well
# ---------------------------------------------------------------------------

class TestBasicCases:

    def test_simple_whitespace_table(self):
        block = (
            "NODE   X        Y        Z\n"
            "N001   1.234    5.678    0.000\n"
            "N002   2.345    6.789    1.000"
        )
        table = WhitespaceParser().parse(block)
        assert table.header == ["NODE", "X", "Y", "Z"]
        assert table.rows[0] == ["N001", "1.234", "5.678", "0.000"]
        assert table.rows[1] == ["N002", "2.345", "6.789", "1.000"]

    def test_variable_spacing_between_columns(self):
        """Inconsistent whitespace amounts should still work."""
        block = (
            "ID    VALUE  UNIT\n"
            "A001  100     kg\n"
            "B002    200       g"
        )
        table = WhitespaceParser().parse(block)
        assert table.header == ["ID", "VALUE", "UNIT"]
        assert table.rows == [["A001", "100", "kg"], ["B002", "200", "g"]]

    def test_tabs_treated_as_whitespace(self):
        block = "ID\tVALUE\nA001\t100\nB002\t200"
        table = WhitespaceParser().parse(block)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["B002", "200"]]

    def test_mixed_tabs_and_spaces(self):
        block = (
            "ID   VALUE\tUNIT\n"
            "A001\t100  kg\n"
            "B002  200\tg"
        )
        table = WhitespaceParser().parse(block)
        assert table.header == ["ID", "VALUE", "UNIT"]
        assert len(table.rows) == 2


# ---------------------------------------------------------------------------
# Negative numbers - works because '-' is non-whitespace
# ---------------------------------------------------------------------------

class TestNegativeNumbers:

    def test_negative_numbers_scattered(self):
        """Same FORTRAN data that FixedWidthParser handles - here it's
        simpler because no value contains internal spaces."""
        block = (
            "NODE   X        Y        Z\n"
            "N001   1.234    5.678    0.000\n"
            "N002  -2.345   -6.789    1.000\n"
            "N003   0.500   10.123   -2.500"
        )
        table = WhitespaceParser().parse(block)
        assert table.rows[1] == ["N002", "-2.345", "-6.789", "1.000"]
        assert table.rows[2] == ["N003", "0.500", "10.123", "-2.500"]


# ---------------------------------------------------------------------------
# Multi-line headers (only when each line has same token count)
# ---------------------------------------------------------------------------

class TestMultiLineHeaders:

    def test_name_plus_units(self):
        block = (
            "ID      FLOW    TEMP\n"
            "        kg/s    K\n"
            "ENG-001 123.45  450.0\n"
            "ENG-002 98.12   431.0"
        )
        # NB: header_rows=2 works here only because both header lines
        # happen to have 3 tokens. The "ID" column has empty unit, but
        # since the unit line has only 2 tokens, the alignment is by
        # position from the LEFT and the result mis-pairs columns.
        # This is the documented limitation.
        table = WhitespaceParser(header_rows=2).parse(block)
        # With only 2 tokens in line 2, they align with the first 2 cols:
        assert table.header == ["ID kg/s", "FLOW K", "TEMP"]


# ---------------------------------------------------------------------------
# Separator-line filtering
# ---------------------------------------------------------------------------

class TestSeparatorLines:

    def test_dash_separator_filtered(self):
        block = (
            "ID    VALUE\n"
            "----  -----\n"
            "A001  100\n"
            "A002  200"
        )
        table = WhitespaceParser().parse(block)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["A002", "200"]]

    def test_unicode_box_separator_filtered(self):
        block = (
            "ID    VALUE\n"
            "──────────\n"
            "A001  100\n"
            "A002  200"
        )
        table = WhitespaceParser().parse(block)
        assert table.header == ["ID", "VALUE"]


# ---------------------------------------------------------------------------
# detect() correctly rejects cases that need other parsers
# ---------------------------------------------------------------------------

class TestDetect:

    def test_detect_valid_whitespace_table(self):
        block = "a b c\n1 2 3\n4 5 6"
        assert WhitespaceParser().detect(block) is True

    def test_detect_rejects_inconsistent_token_counts(self):
        """A table where most rows have different column counts is
        probably prose, not data."""
        block = (
            "this is a sentence\n"
            "and another one with more words here\n"
            "short"
        )
        assert WhitespaceParser().detect(block) is False

    def test_detect_rejects_single_column(self):
        block = "value\n100\n200\n300"
        assert WhitespaceParser().detect(block) is False

    def test_detect_rejects_block_too_short(self):
        assert WhitespaceParser().detect("a b c") is False


# ---------------------------------------------------------------------------
# Limitations - cases where WhitespaceParser gives wrong result
# These tests document expected misbehaviour so users know when to switch
# ---------------------------------------------------------------------------

class TestKnownLimitations:

    def test_values_with_internal_spaces_get_split(self):
        """Values like 'Ana Gomez' become two tokens. Use FixedWidthParser
        or PipeDelimitedParser for this case."""
        block = (
            "ID    Nombre        Edad\n"
            "001   Ana Gomez     28\n"
            "002   Luis Martinez 34"
        )
        # detect() should refuse this because token counts disagree:
        # row 1 has 4 tokens, row 2 has 4 tokens, header has 3.
        # 2 out of 3 lines agree on 4, header is 3 -> not >= 80% consistent
        # depending on exact data; here detect rejects.
        assert WhitespaceParser().detect(block) is False

    def test_empty_cells_cannot_be_represented(self):
        """If you parse this, you lose the empty cell between A and 3."""
        block = (
            "a b c\n"
            "1 2 3\n"
            "4   6"  # b column is empty - but whitespace collapses
        )
        table = WhitespaceParser().parse(block)
        # The "empty b" row only has 2 tokens, not 3:
        assert table.rows[1] == ["4", "6"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
