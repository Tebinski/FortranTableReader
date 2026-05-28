"""
parsers/fixed_width.py

FixedWidthParser - auto-detects column boundaries from data rows using
the "consensus gap" method: a column boundary exists wherever EVERY data
row has a space at the same position.

Usable as:
  1. A standalone BaseParser, called directly on a block of text.
  2. A row_strategy inside a higher-level parser that handles
     title/metadata extraction separately.

Handles FORTRAN-report quirks:
  - Headers with internal spaces ("MASS FLOW RATE")
  - Negative numbers in data (the '-' fills what would be a gap)
  - Mixed left/right alignment per column (irrelevant after strip())
  - Tight single-space headers above wide-spaced data

For pathological cases, pass explicit `col_widths`.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


# In Daniel's framework this lives in core/models/table.py
@dataclass
class Table:
    header: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    title: Optional[str] = None
    metadata: dict = field(default_factory=dict)


# In Daniel's framework this lives in core/engine/base.py
class BaseParser:
    def detect(self, block) -> bool:
        raise NotImplementedError

    def parse(self, block):
        raise NotImplementedError


class FixedWidthParser(BaseParser):

    def __init__(
        self,
        col_widths: Optional[List[int]] = None,
        header_rows: int = 1,
    ):
        self.col_widths = col_widths
        self.header_rows = header_rows

    # --- BaseParser interface ---

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False
        boundaries = self._compute_boundaries(lines[self.header_rows:])
        return len(boundaries) >= 2

    def parse(self, block) -> Table:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return Table(header=[], rows=[])

        header_lines = lines[:self.header_rows]
        data_lines = lines[self.header_rows:]

        boundaries = self._compute_boundaries(data_lines)
        header = self._extract_header(header_lines, boundaries)
        rows = self._extract_rows(data_lines, boundaries)

        return Table(header=header, rows=rows)

    # --- Phase hooks (override these in subclasses) ---

    def _compute_boundaries(
        self, data_lines: List[str],
    ) -> List[Tuple[int, int]]:
        """Phase 1: determine column boundaries."""
        if self.col_widths:
            return self._widths_to_boundaries(self.col_widths)
        return self._detect_data_boundaries(data_lines)

    def _extract_header(
        self,
        header_lines: List[str],
        boundaries: List[Tuple[int, int]],
    ) -> List[str]:
        """Phase 2: derive column names from header lines.

        Each header line is run through smart phrase-split independently
        (so multi-word names map correctly to columns regardless of how
        narrow the data column is). Then results are stacked per column.
        """
        if not boundaries:
            return []
        per_line = [self._split_header(hl, boundaries) for hl in header_lines]
        result = []
        for col_idx in range(len(boundaries)):
            parts = [per_line[i][col_idx] for i in range(len(header_lines))]
            parts = [p for p in parts if p]
            result.append(' '.join(parts))
        return result

    def _extract_rows(
        self,
        data_lines: List[str],
        boundaries: List[Tuple[int, int]],
    ) -> List[List[str]]:
        """Phase 3: extract data cells from data lines."""
        return [
            [line[s:e].strip() if s < len(line) else ''
             for s, e in boundaries]
            for line in data_lines
        ]

    # --- Helpers ---

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip() and not FixedWidthParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
        """A line of decorative chars (─, =, -, +, |, etc.) with no alnum content.

        Catches box-drawing separators from tabulate/rich/prettytable and
        plain ASCII rules like '---' or '+-----+'.
        """
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)

    @staticmethod
    def _widths_to_boundaries(widths: List[int]) -> List[Tuple[int, int]]:
        out, pos = [], 0
        for w in widths:
            out.append((pos, pos + w))
            pos += w
        return out

    @staticmethod
    def _detect_data_boundaries(lines: List[str]) -> List[Tuple[int, int]]:
        """Find column boundaries via consensus gap detection.

        A position is a 'gap' iff it is a space in EVERY data line.
        Columns are runs of non-gap positions.
        """
        if not lines:
            return []

        max_len = max(len(line) for line in lines)
        if max_len == 0:
            return []

        is_gap = [
            all(pos >= len(line) or line[pos] == ' ' for line in lines)
            for pos in range(max_len)
        ]

        boundaries = []
        in_col = False
        start = 0
        for pos in range(max_len):
            if not is_gap[pos] and not in_col:
                start = pos
                in_col = True
            elif is_gap[pos] and in_col:
                boundaries.append((start, pos))
                in_col = False
        if in_col:
            boundaries.append((start, max_len))

        return boundaries

    def _split_header(
        self,
        header_line: str,
        data_boundaries: List[Tuple[int, int]],
    ) -> List[str]:
        """Split header text into column names.

        Strategy:
          1. Try phrases (groups separated by 2+ spaces).
             If # phrases == # data cols, use that.
          2. Else fall back to words (1+ space separators).
             If # words == # data cols, use that.
          3. Else slice header at data boundaries.
        """
        if not data_boundaries:
            return []
        n = len(data_boundaries)

        phrases = self._extract_groups(header_line, min_gap=2)
        if len(phrases) == n:
            return self._assign_groups_to_columns(phrases, data_boundaries)

        words = self._extract_groups(header_line, min_gap=1)
        if len(words) == n:
            return self._assign_groups_to_columns(words, data_boundaries)

        return [header_line[s:e].strip() for s, e in data_boundaries]

    @staticmethod
    def _extract_groups(line: str, min_gap: int) -> List[Tuple[int, int, str]]:
        """Find groups of non-space chars where internal gaps are < min_gap.

        With min_gap=2: 'MASS FLOW RATE   TOTAL TEMP' -> 2 groups.
        With min_gap=1: same -> 5 groups (every word).
        """
        groups = []
        i, n = 0, len(line)
        while i < n:
            while i < n and line[i] == ' ':
                i += 1
            if i >= n:
                break
            start = i
            last_non_space = i
            while i < n:
                if line[i] != ' ':
                    last_non_space = i
                    i += 1
                else:
                    space_start = i
                    while i < n and line[i] == ' ':
                        i += 1
                    if i >= n or i - space_start >= min_gap:
                        break
            end = last_non_space + 1
            groups.append((start, end, line[start:end]))
        return groups

    @staticmethod
    def _assign_groups_to_columns(
        groups: List[Tuple[int, int, str]],
        data_boundaries: List[Tuple[int, int]],
    ) -> List[str]:
        """Assign each header group to its nearest data column by center."""
        column_groups = [[] for _ in data_boundaries]
        col_centers = [(s + e) / 2 for s, e in data_boundaries]

        for g_start, g_end, g_text in groups:
            g_center = (g_start + g_end) / 2
            best = min(
                range(len(data_boundaries)),
                key=lambda j: abs(g_center - col_centers[j]),
            )
            column_groups[best].append(g_text)

        return [' '.join(parts) for parts in column_groups]
