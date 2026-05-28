# FixedWidthParser

A parser for fixed-width tabular blocks, designed for the messy reality of FORTRAN-style ASCII reports.

## Files

- **`fixed_width.py`** — the parser implementation.
- **`test_fixed_width.py`** — 22 tests covering every case variant below.

---

## The problem

FORTRAN reports, legacy scientific output, and many engineering tools produce tables that look "obviously" parseable to a human but break naive parsers. Real-world variants you'll meet in the wild:

```
ENGINE_ID        FLOW_RATE   TEMP        ← left-aligned text, right-aligned numbers
ENG-001          123.45      450
ENG-002           98.12      431
```

```
NODE   X        Y        Z               ← negative numbers in some rows
N001   1.234    5.678    0.000
N002  -2.345   -6.789    1.000
```

```
ENGINE        MASS FLOW RATE   TOTAL TEMP  ← column names with internal spaces
ENG-001       123.45           450.00
```

```
ENGINE_ID   FLOW_RATE   TEMP             ← second header line with units
            [kg/s]      [K]
ENG-001     123.45      450.00
```

```
ID      Nombre           Edad    Ciudad   ← decorative separator line
─────────────────────────────────────────
001     Ana Gómez        28      Madrid
```

No existing Python library (including `pandas.read_fwf`) handles all of these robustly. `FixedWidthParser` does.

---

## What it does

Given a block of text (header + data), produce a `Table(header, rows)`:

```python
from flatparse.parsers.fixed_width import FixedWidthParser

block = """ENGINE_ID   FLOW_RATE   TEMP
ENG-001     123.45      450
ENG-002      98.12      431"""

table = FixedWidthParser().parse(block)
# table.header == ["ENGINE_ID", "FLOW_RATE", "TEMP"]
# table.rows   == [["ENG-001", "123.45", "450"],
#                  ["ENG-002", "98.12",  "431"]]
```

It also implements `detect(block) -> bool` for use within the orchestrator's auto-detect dispatch.

---

## How it works

Three explicit phases inside `parse()`:

```python
boundaries = self._compute_boundaries(data_lines)      # Phase 1
header     = self._extract_header(header_lines, boundaries)  # Phase 2
rows       = self._extract_rows(data_lines, boundaries)       # Phase 3
```

### Phase 1 — `_compute_boundaries`

Uses the **consensus gap** method: a column boundary exists at position *P* if and only if *every* data row has a space at position *P*. Columns are runs of non-gap positions.

Why this works for the hard cases:

- **Negative numbers** — the `-` is a non-space character, so a row containing `-2.345` "fills" the position that would otherwise be a gap. Boundaries shift left to include the sign.
- **No false splits inside cell content** — internal spaces inside `"Ana Gómez"` don't align vertically with `"Luis Martínez"` or `"María Silva"`, so they don't become consensus gaps.
- **Alignment doesn't matter** — once boundaries are right, `strip()` resolves left, right, or center alignment indifferently.

If you already know the column widths, pass `col_widths=[...]` and Phase 1 is skipped.

### Phase 2 — `_extract_header`

For each header line, runs a **smart phrase split**:

1. Try splitting on 2+ space gaps. If the number of phrases matches the number of columns, assign each phrase to its nearest column by center distance.
2. Otherwise fall back to splitting on any whitespace.
3. As a last resort, slice the header at the data boundaries.

For multi-line headers (`header_rows=N`), this runs independently on each header line, then stacks the per-column results with spaces.

This is what lets `"MASS FLOW RATE"` survive as one column name, and `"FLOW_RATE"` + `"[kg/s]"` get joined correctly even when the data column is narrower than either header word.

### Phase 3 — `_extract_rows`

For each data row, slice at each boundary and `strip()`. That's it.

---

## Case variants handled

Every case below has a passing test in `test_fixed_width.py`. Group by what's tricky:

### Alignment

- **Left-aligned text columns** — `TestAlignmentVariants::test_left_aligned_three_columns`
- **Right-aligned numbers** — `test_right_aligned_numbers`
- **Mixed alignment** (ID left, numbers right in the same table) — `test_mixed_alignment_id_left_numbers_right`

### Negative numbers

- **Scattered negatives** in some rows but not others — `TestNegativeNumbers::test_negative_numbers_scattered`
- **All-negative column** — `test_all_negative_in_a_column`

### Multi-word headers

- **Single-line header with spaces in column names** (`"MASS FLOW RATE"`) — `TestHeaderWithSpaces::test_multi_word_header`
- **Tight single-space header above wide data** (`"ID FLOW_RATE TEMP"`) — `test_tight_header_wide_data`

### Decorative separator lines

Filtered automatically — any line with no alphanumeric content after `strip()` is treated as decoration.

- **Unicode box-drawing** (`─────`, accented data) — `TestSeparatorLines::test_unicode_box_drawing_separator`
- **ASCII dashes** (`----`) — `test_ascii_dash_separator`
- **Equals signs** (`====`) — `test_equals_separator`
- **Pipe-and-dash** (`+----+----+`) — `test_pipe_and_dash_separator`

### Multi-line headers

Pass `header_rows=N` for headers that span multiple lines:

- **Stacked names** (`ENGINE\nID`, `MASS\nFLOW`) — `TestMultiLineHeaders::test_two_line_header_stacked_names`
- **Name + units** (second row carries `[kg/s]`, `[K]`) — `test_two_line_header_name_plus_units`
- **Three-line header** with empty cells in some positions — `test_three_line_header`
- **Multi-line header followed by separator** — `test_multi_line_header_with_separator`

### Other

- **Explicit `col_widths`** as override when auto-detect would fail — `TestExplicitWidths`
- **`detect()`** returns false for blocks too short to be tables — `TestDetect`
- **Input as string or as list of lines** — `TestInputHandling`
- **Blank lines** are ignored — `test_ignores_blank_lines`

---

## Usage modes

### Standalone

```python
parser = FixedWidthParser()
if parser.detect(block):
    table = parser.parse(block)
```

### As a `row_strategy`

For blocks that mix title, metadata, and a table, write a custom parser that handles the irregular parts and delegates the table extraction:

```python
@register("fuel_consumption")
class FuelConsumptionParser(BaseParser):
    row_strategy = FixedWidthParser(header_rows=2)

    def detect(self, block):
        return block.startswith("=== FUEL CONSUMPTION")

    def parse(self, block):
        lines = block.splitlines()
        title = lines[0].strip("= ")
        metadata = self.parse_metadata(lines[1])
        table = self.row_strategy.parse(lines[2:])
        return Collection(title=title, metadata=metadata, items=[table])
```

The plugin author never reimplements column-detection logic — the registry sees the dependency on `FixedWidthParser` automatically.

---

## Extension points

The three-phase split is the extension contract. Subclass `FixedWidthParser` and override only the phase you need to change:

```python
class HierarchicalHeaderParser(FixedWidthParser):
    """For headers with grouping rows like:
       
           -----PRIMARY-----  -----SECONDARY-----
       ID  FLOW   TEMP        FLOW   TEMP
       ENG  123    450        98     431
    """

    def _extract_header(self, header_lines, boundaries):
        groups = self._parse_group_row(header_lines[0], boundaries)
        names  = super()._extract_header(header_lines[1:], boundaries)
        return [f"{g}.{n}" if g else n for g, n in zip(groups, names)]
```

`_compute_boundaries`, `_extract_header`, and `_extract_rows` are the three knobs. The orchestration in `parse()` stays constant.

---

## Out of scope

Cases that require a fully custom parser (not just a subclass):

- **Hierarchical headers** where parent groups span multiple sub-columns and the number of header phrases doesn't match the number of data columns. Use the `row_strategy` pattern with a custom `_extract_header`.
- **Multiple tables in the same block** separated by free-form prose. That's a job for the `BaseExtractor`, not the parser.
- **Tables with no header row at all.** Pass an empty first line, or use `header_rows=0` and rely on positional column names.
- **Variable-width records across rows** (different rows have different schemas). This isn't really fixed-width; treat each row type as its own block.

---
## Why not just use `pandas.read_fwf()`?

Short answer: pandas handles the clean cases and fails the messy ones — and the messy ones are exactly why this library exists.

We measured it. The `examples/pandas_vs_flatparse.py` script runs pandas and `flatparse` against eight representative cases and is runnable, so you can verify the results yourself:

```bash
uv run python examples/pandas_vs_flatparse.py
```

To be fair to pandas, every pandas attempt uses `dtype=str` (so value coercion like `001` → `1` or `0.000` → `0.0` is **not** counted against it) and the correct `sep`/reader for each case. The failures below are purely structural.

| Case | pandas | flatparse |
|---|:---:|:---:|
| Fixed-width, left-aligned | ✅ | ✅ |
| Fixed-width with negative numbers | ✅ | ✅ |
| Multi-word column header (`MASS FLOW RATE`) | ❌ | ✅ |
| Decorative separator line (`─────`) | ❌ | ✅ |
| Two-line header (name + units) | ❌ | ✅ |
| Comma-separated values | ✅ | ✅ |
| Pipe-delimited table with rule row | ❌ | ✅ |
| Whitespace-separated | ✅ | ✅ |
| **Total** | **4/8** | **8/8** |

### Where pandas breaks, and why no flag fixes it

- **Multi-word headers.** `read_fwf` splits `MASS FLOW RATE` into two columns (`MASS FLOW` and `RATE`), invents a phantom column, and fills it with `NaN`. The column-to-data mapping is wrong from that point on.
- **Decorative separator lines.** A rule like `─────────` or `----` is read as a data row. It corrupts column-width inference and merges adjacent columns.
- **Multi-line headers.** When the second header line carries units (`[kg/s]`, `[K]`), pandas treats that line as the first row of data, leaving the first real column as `NaN`.
- **Pipe tables with a rule row.** `read_csv(sep="|")` leaves whitespace padding inside every header and value, and ingests the `---|---|---` separator as a data row. Stripping it requires manual `skiprows` plus per-cell cleanup — and you have to know the quirk in advance.

These are not tuning problems. There is no combination of `read_fwf` / `read_csv` arguments that resolves them, because the issue is structural: pandas assumes one header line, no decorative rows, and column names without internal spaces.

### Two more reasons beyond correctness

- **It returns a `DataFrame`, not the framework's model.** Even on the cases pandas gets right, you still have to convert to `Table` / `Node` / `Collection` and you lose the `source` provenance the framework tracks.
- **It is a heavy dependency for a stdlib job.** `flatparse`'s core parsers import nothing outside the standard library. Pulling in pandas (and numpy) to parse a FORTRAN report is a large, slow dependency for a task that doesn't need it. pandas stays an optional extra here, used only by the comparison example.

pandas is the right tool for numerical analysis of clean tabular data. It is the wrong tool for faithfully extracting structure from messy FORTRAN-style reports — which is the job `flatparse` is built for.