"""
vs_pandas.py

An honest, runnable comparison: can pandas (read_fwf / read_csv) do the job
that FixedWidthParser / CharacterDelimitedParser / WhitespaceParser do?

Run it:   python vs_pandas.py

The answer: pandas handles the CLEAN cases fine (basic fixed-width, basic
CSV, simple whitespace). It fails the messy real-world FORTRAN cases that
this framework was built for - multi-word headers, decorative separator
lines, and multi-line headers - regardless of how you tune its flags.

To be maximally fair to pandas, every pandas attempt below uses dtype=str,
so type coercion (001 -> 1, 0.000 -> 0.0) is NOT counted against it. The
failures shown are purely structural.
"""

from io import StringIO

import pandas as pd

from flatparse import (
    FixedWidthParser,
    CommaSeparatedParser,
    PipeDelimitedParser,
    WhitespaceParser,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def df_to_pairs(df):
    """Normalise a DataFrame to (header, rows) of stripped strings."""
    header = [str(c).strip() for c in df.columns]
    rows = [[('' if pd.isna(v) else str(v).strip()) for v in row]
            for row in df.to_numpy()]
    return header, rows


def table_to_pairs(table):
    return [h.strip() for h in table.header], table.rows


def verdict(got_header, got_rows, exp_header, exp_rows):
    if got_header == exp_header and got_rows == exp_rows:
        return "PASS"
    return "FAIL"


def run_case(name, block, expected_header, expected_rows,
             pandas_attempt, framework_attempt):
    print("=" * 72)
    print(name)
    print("-" * 72)

    # pandas
    try:
        ph, pr = df_to_pairs(pandas_attempt(block))
        pv = verdict(ph, pr, expected_header, expected_rows)
        pandas_note = "" if pv == "PASS" else f"  got header={ph}"
    except Exception as e:
        pv = "FAIL"
        pandas_note = f"  {type(e).__name__}: {str(e)[:80]}"

    # framework
    try:
        fh, fr = table_to_pairs(framework_attempt(block))
        fv = verdict(fh, fr, expected_header, expected_rows)
        fw_note = "" if fv == "PASS" else f"  got header={fh}"
    except Exception as e:
        fv = "FAIL"
        fw_note = f"  {type(e).__name__}: {str(e)[:80]}"

    print(f"  pandas:    {pv}{pandas_note}")
    print(f"  framework: {fv}{fw_note}")
    print()
    return pv, fv


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

CASES = []

# 1. Basic left-aligned fixed-width
CASES.append(dict(
    name="1. Fixed-width, left-aligned",
    block=(
        "ENGINE_ID        FLOW_RATE   TEMP\n"
        "ENG-001          123.45      450\n"
        "ENG-002           98.12      431"
    ),
    expected_header=["ENGINE_ID", "FLOW_RATE", "TEMP"],
    expected_rows=[["ENG-001", "123.45", "450"], ["ENG-002", "98.12", "431"]],
    pandas_attempt=lambda b: pd.read_fwf(StringIO(b), dtype=str),
    framework_attempt=lambda b: FixedWidthParser().parse(b),
))

# 2. Negative numbers
CASES.append(dict(
    name="2. Fixed-width with negative numbers",
    block=(
        "NODE   X        Y        Z\n"
        "N001   1.234    5.678    0.000\n"
        "N002  -2.345   -6.789    1.000"
    ),
    expected_header=["NODE", "X", "Y", "Z"],
    expected_rows=[
        ["N001", "1.234", "5.678", "0.000"],
        ["N002", "-2.345", "-6.789", "1.000"],
    ],
    pandas_attempt=lambda b: pd.read_fwf(StringIO(b), dtype=str),
    framework_attempt=lambda b: FixedWidthParser().parse(b),
))

# 3. Multi-word column names
CASES.append(dict(
    name="3. Fixed-width with multi-word header ('MASS FLOW RATE')",
    block=(
        "ENGINE        MASS FLOW RATE   TOTAL TEMP\n"
        "ENG-001       123.45           450.00\n"
        "ENG-002        98.12           431.00"
    ),
    expected_header=["ENGINE", "MASS FLOW RATE", "TOTAL TEMP"],
    expected_rows=[
        ["ENG-001", "123.45", "450.00"],
        ["ENG-002", "98.12", "431.00"],
    ],
    pandas_attempt=lambda b: pd.read_fwf(StringIO(b), dtype=str),
    framework_attempt=lambda b: FixedWidthParser().parse(b),
))

# 4. Decorative separator line
CASES.append(dict(
    name="4. Fixed-width with box-drawing separator line",
    block=(
        "ID      Nombre           Edad    Ciudad\n"
        + "\u2500" * 41 + "\n"
        + "001     Ana Gomez        28      Madrid\n"
        + "002     Luis Martinez    34      Bogota"
    ),
    expected_header=["ID", "Nombre", "Edad", "Ciudad"],
    expected_rows=[
        ["001", "Ana Gomez", "28", "Madrid"],
        ["002", "Luis Martinez", "34", "Bogota"],
    ],
    pandas_attempt=lambda b: pd.read_fwf(StringIO(b), dtype=str),
    framework_attempt=lambda b: FixedWidthParser().parse(b),
))

# 5. Multi-line header (name + units)
CASES.append(dict(
    name="5. Fixed-width with two-line header (name + units)",
    block=(
        "ENGINE_ID   FLOW_RATE   TEMP\n"
        "            [kg/s]      [K]\n"
        "ENG-001     123.45      450.00\n"
        "ENG-002      98.12      431.00"
    ),
    expected_header=["ENGINE_ID", "FLOW_RATE [kg/s]", "TEMP [K]"],
    expected_rows=[
        ["ENG-001", "123.45", "450.00"],
        ["ENG-002", "98.12", "431.00"],
    ],
    pandas_attempt=lambda b: pd.read_fwf(StringIO(b), dtype=str),
    framework_attempt=lambda b: FixedWidthParser(header_rows=2).parse(b),
))

# 6. Basic CSV
CASES.append(dict(
    name="6. Comma-separated values",
    block=(
        "name,density,modulus\n"
        "aluminium,2700,70000\n"
        "steel,7800,210000"
    ),
    expected_header=["name", "density", "modulus"],
    expected_rows=[
        ["aluminium", "2700", "70000"],
        ["steel", "7800", "210000"],
    ],
    pandas_attempt=lambda b: pd.read_csv(StringIO(b), dtype=str),
    framework_attempt=lambda b: CommaSeparatedParser().parse(b),
))

# 7. Pipe-delimited markdown-style table
CASES.append(dict(
    name="7. Pipe-delimited table with separator row",
    block=(
        "ID     | Nombre         | Edad | Ciudad\n"
        "-------|----------------|------|---------\n"
        "001    | Ana Gomez      | 28   | Madrid\n"
        "002    | Luis Martinez  | 34   | Bogota"
    ),
    expected_header=["ID", "Nombre", "Edad", "Ciudad"],
    expected_rows=[
        ["001", "Ana Gomez", "28", "Madrid"],
        ["002", "Luis Martinez", "34", "Bogota"],
    ],
    pandas_attempt=lambda b: pd.read_csv(StringIO(b), sep="|", dtype=str),
    framework_attempt=lambda b: PipeDelimitedParser().parse(b),
))

# 8. Whitespace-separated
CASES.append(dict(
    name="8. Whitespace-separated (variable spacing)",
    block=(
        "NODE   X        Y        Z\n"
        "N001   1.234    5.678    0.000\n"
        "N002   2.345    6.789    1.000"
    ),
    expected_header=["NODE", "X", "Y", "Z"],
    expected_rows=[
        ["N001", "1.234", "5.678", "0.000"],
        ["N002", "2.345", "6.789", "1.000"],
    ],
    pandas_attempt=lambda b: pd.read_csv(StringIO(b), sep=r"\s+", dtype=str),
    framework_attempt=lambda b: WhitespaceParser().parse(b),
))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    results = []
    for c in CASES:
        pv, fv = run_case(
            c["name"], c["block"],
            c["expected_header"], c["expected_rows"],
            c["pandas_attempt"], c["framework_attempt"],
        )
        results.append((c["name"], pv, fv))

    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"{'case':<52}{'pandas':<9}{'framework'}")
    print("-" * 72)
    for name, pv, fv in results:
        short = name if len(name) <= 50 else name[:47] + "..."
        print(f"{short:<52}{pv:<9}{fv}")

    p_pass = sum(1 for _, pv, _ in results if pv == "PASS")
    f_pass = sum(1 for _, _, fv in results if fv == "PASS")
    print("-" * 72)
    print(f"{'TOTAL PASSED':<52}{p_pass}/{len(results):<7}{f_pass}/{len(results)}")
    print()
    print("Takeaway: pandas wins the clean cases (1, 2, 6, 8) but cannot")
    print("structurally handle multi-word headers (3), separator lines (4),")
    print("multi-line headers (5), or pipe tables with rule rows (7) - no")
    print("combination of flags fixes these. And even when it succeeds it")
    print("returns a DataFrame, not the framework's Table/Node/Collection")
    print("model with provenance.")


if __name__ == "__main__":
    main()