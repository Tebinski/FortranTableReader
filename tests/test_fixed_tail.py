"""
Tests for FixedTailParser - the right-anchored parser for messy-left,
clean-numeric-right tables (FORTRAN/CFD reports).
"""

import pytest
from flatparse.parsers.fixed_tail import FixedTailParser


HEADER = ("Surface-Part          Name              "
          "CM_x_v          CM_y_v          CM_z_v          Area[%]")


def tau_block():
    return HEADER + "\n" + "\n".join([
        "        Overall Sum              5.017027756e-05   0.003367838416   -0.019856425184          100",
        "bdry-part   0    Fuselage_Front   1.034774793e-05  -0.000123201849   -0.001395066122   4.749649",
        "bdry-part   8    Belly           -3.448091422e-05  -0.000002201812   -0.000642715768   9.127563",
        "bdry-part  16    IB_Engine_Ventilation_Outlet_Duct   -2.099411240e-06   4.388504e-05  -0.000192821   0.596223",
    ])


class TestCoreChallenges:

    def test_overall_sum_row_with_no_name(self):
        """The summary row has a label but no index/name - just values."""
        table = FixedTailParser(n_tail=4).parse(tau_block())
        first = table.rows[0]
        assert first[0] == "Overall Sum"
        assert first[1:] == [
            "5.017027756e-05", "0.003367838416", "-0.019856425184", "100",
        ]

    def test_long_name_does_not_shift_value_columns(self):
        """A name long enough to overflow its column must not corrupt the
        value columns - this is what kills fixed-width here."""
        table = FixedTailParser(n_tail=4).parse(tau_block())
        last = table.rows[-1]
        assert last[0] == "bdry-part 16 IB_Engine_Ventilation_Outlet_Duct"
        assert last[1:] == [
            "-2.099411240e-06", "4.388504e-05", "-0.000192821", "0.596223",
        ]

    def test_normal_row(self):
        table = FixedTailParser(n_tail=4).parse(tau_block())
        row = table.rows[1]
        assert row[0] == "bdry-part 0 Fuselage_Front"
        assert row[1:] == [
            "1.034774793e-05", "-0.000123201849",
            "-0.001395066122", "4.749649",
        ]

    def test_header_split(self):
        table = FixedTailParser(n_tail=4).parse(tau_block())
        assert table.header == [
            "Surface-Part Name", "CM_x_v", "CM_y_v", "CM_z_v", "Area[%]",
        ]


class TestAutoDetect:

    def test_auto_detects_four_value_columns(self):
        table = FixedTailParser().parse(tau_block())  # no n_tail given
        assert len(table.header) == 5  # label + 4 values
        assert table.rows[0][0] == "Overall Sum"
        assert len(table.rows[0]) == 5


class TestNumberRecognition:

    def test_fortran_d_exponent(self):
        block = (
            "name   value\n"
            "alpha  1.5D-05\n"
            "beta  -2.3d+02"
        )
        table = FixedTailParser(n_tail=1).parse(block)
        assert table.rows[0] == ["alpha", "1.5D-05"]
        assert table.rows[1] == ["beta", "-2.3d+02"]

    def test_integer_value(self):
        block = "label  count\nrows   100\ncols   42"
        table = FixedTailParser(n_tail=1).parse(block)
        assert table.rows[0] == ["rows", "100"]

    def test_numeric_token_inside_label_stays_in_label(self):
        """An index like '0' before the name must not be mistaken for a
        value column - fixed-count from the right protects against this."""
        block = (
            "part   Name           v1       v2\n"
            "bdry   0  Wing_Tip    1.0e-3   2.0e-3\n"
            "bdry   7  Belly       3.0e-3   4.0e-3"
        )
        table = FixedTailParser(n_tail=2).parse(block)
        assert table.rows[0] == ["bdry 0 Wing_Tip", "1.0e-3", "2.0e-3"]
        assert table.rows[1] == ["bdry 7 Belly", "3.0e-3", "4.0e-3"]


class TestDetect:

    def test_detect_true_on_tau_table(self):
        assert FixedTailParser(n_tail=4).detect(tau_block()) is True

    def test_detect_true_with_autodetect(self):
        assert FixedTailParser().detect(tau_block()) is True

    def test_detect_false_on_prose(self):
        block = "this is prose\nwith no numeric tail at all\njust words here"
        assert FixedTailParser().detect(block) is False


class TestSeparatorFiltering:

    def test_dashed_rule_lines_ignored(self):
        block = (
            "Surface-Part   Name   v1      v2\n"
            "------------------------------------\n"
            "bdry  0  Wing   1.0e-3  2.0e-3\n"
            "bdry  7  Belly  3.0e-3  4.0e-3"
        )
        table = FixedTailParser(n_tail=2).parse(block)
        assert len(table.rows) == 2
        assert table.rows[0] == ["bdry 0 Wing", "1.0e-3", "2.0e-3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])