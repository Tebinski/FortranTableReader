"""
flatparse/parsers/fixed_tail.py

FixedTailParser - for tables where the LEFT side is messy (variable-width
labels, names that overflow their column, missing fields) but the RIGHT
side is a fixed number of clean value columns.

Instead of detecting column positions (which fail when a long name shoves
everything rightward), it anchors N columns from the END of each row. The
last N whitespace tokens are the value columns; everything before them is
a single free-form label.

This solves two FORTRAN/CFD report problems that break fixed-width:
  - Rows with a different field count (e.g. an "Overall Sum" row that has
    no index and no name, just a label and the values).
  - Long names that overflow their column width and shift the numeric
    columns out of alignment with the other rows.

Recognises FORTRAN exponent styles (1.5e-05, 1.5E-05, 1.5d-05, 1.5D-05).
"""

import re
from typing import List, Optional, Union

from flatparse.core.engine import BaseParser
from flatparse.core.models import Table
from flatparse.core.registry import register

_NUMBER = re.compile(r'^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?$')


@register("fixed_tail")
class FixedTailParser(BaseParser):

    def __init__(self, n_tail: Optional[int] = None, header_rows: int = 1):
        """
        n_tail: number of value columns at the right end of each row.
                If None, auto-detected from the data as the most common
                count of trailing numeric tokens.
        """
        self.n_tail = n_tail
        self.header_rows = header_rows

    # --- BaseParser interface ---

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False
        data = lines[self.header_rows:]
        n = self.n_tail or self._auto_n_tail(data)
        if n < 1:
            return False
        ok = 0
        for line in data:
            toks = line.split()
            if len(toks) > n and all(self._is_number(t) for t in toks[-n:]):
                ok += 1
        return ok >= 0.8 * len(data)

    def parse(self, block) -> Table:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return Table(header=[], rows=[])

        header_lines = lines[:self.header_rows]
        data_lines = lines[self.header_rows:]

        n = self.n_tail or self._auto_n_tail(data_lines)
        header = self._extract_header(header_lines, n)
        rows = [self._split_row(line, n) for line in data_lines]
        return Table(header=header, rows=rows)

    # --- core logic ---

    def _split_row(self, line: str, n: int) -> List[str]:
        toks = line.split()
        if n <= 0:
            return [" ".join(toks)]
        if len(toks) <= n:
            # No label tokens; pad label as empty.
            return [""] + toks + [""] * (n - len(toks))
        label = " ".join(toks[:-n])
        values = toks[-n:]
        return [label] + values

    def _extract_header(self, header_lines: List[str], n: int) -> List[str]:
        # Use the last header line for value names; merge label names.
        line = header_lines[-1]
        parts = re.split(r'\s{2,}', line.strip())
        if len(parts) < n + 1:
            parts = line.split()
        if len(parts) < n + 1:
            # Can't separate label from values; fall back to generic names.
            value_headers = parts[-n:] if n <= len(parts) else parts
            return ["label"] + value_headers
        value_headers = parts[-n:]
        label_header = " ".join(parts[:-n]) or "label"
        return [label_header] + value_headers

    def _auto_n_tail(self, data_lines: List[str]) -> int:
        counts = []
        for line in data_lines:
            toks = line.split()
            c = 0
            for t in reversed(toks):
                if self._is_number(t):
                    c += 1
                else:
                    break
            if c:
                counts.append(c)
        if not counts:
            return 0
        return max(set(counts), key=counts.count)  # mode

    # --- helpers ---

    @staticmethod
    def _is_number(token: str) -> bool:
        return bool(_NUMBER.match(token))

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip() and not FixedTailParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)