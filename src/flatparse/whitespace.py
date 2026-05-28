"""
parsers/whitespace.py

WhitespaceParser - splits rows on ANY run of whitespace. Multiple
consecutive spaces, tabs, or mixed whitespace all collapse to a single
separator.

Use this for: FORTRAN data tables where columns are separated by variable
amounts of whitespace and no value contains internal spaces. The simplest,
fastest tool for the simplest case.

Trade-offs vs the other parsers:
  - vs CharacterDelimitedParser: WhitespaceParser cannot represent empty
    cells (an empty cell looks like extra whitespace, which collapses).
  - vs FixedWidthParser: WhitespaceParser is much simpler but cannot
    handle values with internal spaces (e.g. "Ana Gomez" would become two
    tokens). It also cannot handle multi-line headers where some lines
    have empty positions, because tokens carry no positional information.

Rule of thumb: try WhitespaceParser first for whitespace-separated data.
Fall back to FixedWidthParser if any value contains internal spaces or
columns need positional alignment.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union


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


class WhitespaceParser(BaseParser):

    def __init__(self, header_rows: int = 1):
        self.header_rows = header_rows

    # --- BaseParser interface ---

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False

        token_counts = [len(line.split()) for line in lines]
        if not token_counts or max(token_counts) < 2:
            return False

        # Majority of lines should share the same token count.
        most_common = max(set(token_counts), key=token_counts.count)
        consistent = sum(c == most_common for c in token_counts)
        return consistent >= 0.8 * len(token_counts)

    def parse(self, block) -> Table:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return Table(header=[], rows=[])

        header_lines = lines[:self.header_rows]
        data_lines = lines[self.header_rows:]

        header = self._extract_header(header_lines)
        rows = self._extract_rows(data_lines)
        return Table(header=header, rows=rows)

    # --- Phase hooks (override in subclasses) ---

    def _extract_header(self, header_lines: List[str]) -> List[str]:
        """Single line: split on whitespace.

        Multi-line: stack tokens by position. Requires all header lines
        to have the same token count - that's the limitation. For stacked
        headers with positional gaps, use FixedWidthParser.
        """
        if len(header_lines) == 1:
            return header_lines[0].split()
        per_line = [hl.split() for hl in header_lines]
        n = max(len(parts) for parts in per_line)
        result = []
        for col in range(n):
            parts = [pl[col] if col < len(pl) else '' for pl in per_line]
            parts = [p for p in parts if p]
            result.append(' '.join(parts))
        return result

    def _extract_rows(self, data_lines: List[str]) -> List[List[str]]:
        return [line.split() for line in data_lines]

    # --- Helpers ---

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip()
            and not WhitespaceParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
        """Decorative dividers (─, =, -, +, |) with no alphanumeric content."""
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)
