"""
Tests for FixedWidthParser - covers the FORTRAN report variants discussed:
  - left/right/center alignment
  - negative numbers in data
  - multi-word column names ("MASS FLOW RATE")
  - tight single-space headers above wide-spaced data
  - explicit col_widths override
"""

import pytest
from flatparse import FixedWidthParser


# ---------------------------------------------------------------------------
# Basic alignment variants
# ---------------------------------------------------------------------------

class TestAlignmentVariants:

    def test_left_aligned_three_columns(self):
        block = (
            "ENGINE_ID        FLOW_RATE   TEMP\n"
            "ENG-001          123.45      450\n"
            "ENG-002           98.12      431"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ENGINE_ID", "FLOW_RATE", "TEMP"]
        assert table.rows == [
            ["ENG-001", "123.45", "450"],
            ["ENG-002", "98.12", "431"],
        ]

    def test_right_aligned_numbers(self):
        block = (
            "    ID   FLOW_RATE\n"
            "  A001      123.45\n"
            "  B002       98.12"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "FLOW_RATE"]
        assert table.rows == [["A001", "123.45"], ["B002", "98.12"]]

    def test_mixed_alignment_id_left_numbers_right(self):
        block = (
            "ID        FLOW\n"
            "A001    123.45\n"
            "B002     98.12"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "FLOW"]
        assert table.rows == [["A001", "123.45"], ["B002", "98.12"]]


# ---------------------------------------------------------------------------
# Negative numbers - the '-' must not fool boundary detection
# ---------------------------------------------------------------------------

class TestNegativeNumbers:

    def test_negative_numbers_scattered(self):
        block = (
            "NODE   X        Y        Z\n"
            "N001   1.234    5.678    0.000\n"
            "N002  -2.345   -6.789    1.000\n"
            "N003   0.500   10.123   -2.500"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["NODE", "X", "Y", "Z"]
        assert table.rows[0] == ["N001", "1.234", "5.678", "0.000"]
        assert table.rows[1] == ["N002", "-2.345", "-6.789", "1.000"]
        assert table.rows[2] == ["N003", "0.500", "10.123", "-2.500"]

    def test_all_negative_in_a_column(self):
        block = (
            "ID    DELTA\n"
            "A    -100.0\n"
            "B    -200.5\n"
            "C    -350.7"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "DELTA"]
        assert [r[1] for r in table.rows] == ["-100.0", "-200.5", "-350.7"]


# ---------------------------------------------------------------------------
# Multi-word column names
# ---------------------------------------------------------------------------

class TestHeaderWithSpaces:

    def test_multi_word_header(self):
        block = (
            "ENGINE        MASS FLOW RATE   TOTAL TEMP\n"
            "ENG-001       123.45           450.00\n"
            "ENG-002        98.12           431.00"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ENGINE", "MASS FLOW RATE", "TOTAL TEMP"]
        assert table.rows[0] == ["ENG-001", "123.45", "450.00"]
        assert table.rows[1] == ["ENG-002", "98.12", "431.00"]

    def test_tight_header_wide_data(self):
        """Header uses single-space separators; data is wide-spaced."""
        block = (
            "ID FLOW_RATE TEMP\n"
            "A001 123.45 450\n"
            "B002  98.12 431"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "FLOW_RATE", "TEMP"]
        assert table.rows[0] == ["A001", "123.45", "450"]


# ---------------------------------------------------------------------------
# Explicit col_widths override
# ---------------------------------------------------------------------------

class TestExplicitWidths:

    def test_col_widths_overrides_detection(self):
        block = (
            "ENGINE_ID       FLOW_RATE   TEMP\n"
            "ENG-001         123.45      450 \n"
            "ENG-002          98.12      431 "
        )
        table = FixedWidthParser(col_widths=[16, 12, 4]).parse(block)
        assert len(table.header) == 3
        assert len(table.rows) == 2
        assert all(len(r) == 3 for r in table.rows)


# ---------------------------------------------------------------------------
# detect() behaviour
# ---------------------------------------------------------------------------

class TestDetect:

    def test_detect_valid_block(self):
        block = "ID    VALUE\nA001  100\nA002  200"
        assert FixedWidthParser().detect(block) is True

    def test_detect_single_line_returns_false(self):
        assert FixedWidthParser().detect("ID    VALUE") is False

    def test_detect_empty_returns_false(self):
        assert FixedWidthParser().detect("") is False


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

class TestInputHandling:

    def test_accepts_list_of_lines(self):
        lines = [
            "ID    VALUE",
            "A001  100",
            "A002  200",
        ]
        table = FixedWidthParser().parse(lines)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["A002", "200"]]

    def test_ignores_blank_lines(self):
        block = (
            "ID    VALUE\n"
            "A001  100\n"
            "\n"
            "A002  200\n"
            "\n"
        )
        table = FixedWidthParser().parse(block)
        assert len(table.rows) == 2


# ---------------------------------------------------------------------------
# Separator lines (box-drawing, dashes, etc.) must be filtered
# ---------------------------------------------------------------------------

class TestSeparatorLines:

    def test_unicode_box_drawing_separator(self):
        block = (
            "ID      Nombre           Edad    Ciudad\n"
            "─────────────────────────────────────────\n"
            "001     Ana Gómez        28      Madrid\n"
            "002     Luis Martínez    34      Bogotá\n"
            "003     María Silva      22      Lima"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "Nombre", "Edad", "Ciudad"]
        assert len(table.rows) == 3
        assert table.rows[0] == ["001", "Ana Gómez", "28", "Madrid"]
        assert table.rows[1] == ["002", "Luis Martínez", "34", "Bogotá"]
        assert table.rows[2] == ["003", "María Silva", "22", "Lima"]

    def test_ascii_dash_separator(self):
        block = (
            "ID    VALUE\n"
            "----  -----\n"
            "A001  100\n"
            "A002  200"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["A002", "200"]]

    def test_equals_separator(self):
        block = (
            "ID    VALUE\n"
            "============\n"
            "A001  100\n"
            "A002  200"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["A002", "200"]]

    def test_pipe_and_dash_separator(self):
        block = (
            "ID    VALUE\n"
            "+----+-----+\n"
            "A001  100\n"
            "A002  200"
        )
        table = FixedWidthParser().parse(block)
        assert table.header == ["ID", "VALUE"]
        assert table.rows == [["A001", "100"], ["A002", "200"]]


# ---------------------------------------------------------------------------
# Multi-line headers (header_rows=N)
# ---------------------------------------------------------------------------

class TestMultiLineHeaders:

    def test_two_line_header_stacked_names(self):
        """Case A: column names split across two lines for compactness."""
        block = (
            "ENGINE   MASS    TOTAL\n"
            "   ID    FLOW    TEMP\n"
            "ENG-001  123.45  450.00\n"
            "ENG-002   98.12  431.00"
        )
        table = FixedWidthParser(header_rows=2).parse(block)
        assert table.header == ["ENGINE ID", "MASS FLOW", "TOTAL TEMP"]
        assert table.rows[0] == ["ENG-001", "123.45", "450.00"]
        assert table.rows[1] == ["ENG-002", "98.12", "431.00"]

    def test_two_line_header_name_plus_units(self):
        """Case B: second header line carries units."""
        block = (
            "ENGINE_ID   FLOW_RATE   TEMP\n"
            "            [kg/s]      [K]\n"
            "ENG-001     123.45      450.00\n"
            "ENG-002      98.12      431.00"
        )
        table = FixedWidthParser(header_rows=2).parse(block)
        assert table.header == ["ENGINE_ID", "FLOW_RATE [kg/s]", "TEMP [K]"]
        assert table.rows[0] == ["ENG-001", "123.45", "450.00"]

    def test_three_line_header(self):
        """Three header rows where some columns have empty cells in some rows."""
        block = (
            "ENGINE   MASS    TOTAL\n"
            "   ID    FLOW    TEMP\n"
            "                 RATE\n"
            "ENG-001  123.45  450.00\n"
            "ENG-002   98.12  431.00"
        )
        table = FixedWidthParser(header_rows=3).parse(block)
        assert table.header == ["ENGINE ID", "MASS FLOW", "TOTAL TEMP RATE"]
        assert len(table.rows) == 2

    def test_multi_line_header_with_separator(self):
        """Separator line between multi-line header and data should be ignored."""
        block = (
            "ENGINE   MASS    TOTAL\n"
            "   ID    FLOW    TEMP\n"
            "-------- ------  ------\n"
            "ENG-001  123.45  450.00\n"
            "ENG-002   98.12  431.00"
        )
        table = FixedWidthParser(header_rows=2).parse(block)
        assert table.header == ["ENGINE ID", "MASS FLOW", "TOTAL TEMP"]
        assert table.rows[0] == ["ENG-001", "123.45", "450.00"]

    def test_detect_respects_header_rows(self):
        block = (
            "ENGINE   MASS\n"
            "   ID    FLOW\n"
            "ENG-001  123.45"
        )
        assert FixedWidthParser(header_rows=2).detect(block) is True
        # Only one data line + 2 header lines = 3 lines total, just barely valid
        block_too_short = (
            "ENGINE   MASS\n"
            "   ID    FLOW"
        )
        assert FixedWidthParser(header_rows=2).detect(block_too_short) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
