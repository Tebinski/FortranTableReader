"""
flatparse/parsers/whitespace.py

Splits rows on any run of whitespace. Cannot represent empty cells or
values with internal spaces - use FixedWidthParser or a delimited parser
for those.
"""

from typing import List, Union

from flatparse.core.engine import BaseParser
from flatparse.core.models import Table
from flatparse.core.registry import register


@register("whitespace")
class WhitespaceParser(BaseParser):

    def __init__(self, header_rows: int = 1):
        self.header_rows = header_rows

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False
        token_counts = [len(line.split()) for line in lines]
        if not token_counts or max(token_counts) < 2:
            return False
        most_common = max(set(token_counts), key=token_counts.count)
        consistent = sum(c == most_common for c in token_counts)
        return consistent >= 0.8 * len(token_counts)

    def parse(self, block) -> Table:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return Table(header=[], rows=[])
        header = self._extract_header(lines[:self.header_rows])
        rows = self._extract_rows(lines[self.header_rows:])
        return Table(header=header, rows=rows)

    def _extract_header(self, header_lines: List[str]) -> List[str]:
        if len(header_lines) == 1:
            return header_lines[0].split()
        per_line = [hl.split() for hl in header_lines]
        n = max(len(parts) for parts in per_line)
        result = []
        for col in range(n):
            parts = [pl[col] if col < len(pl) else '' for pl in per_line]
            result.append(' '.join(p for p in parts if p))
        return result

    def _extract_rows(self, data_lines: List[str]) -> List[List[str]]:
        return [line.split() for line in data_lines]

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip() and not WhitespaceParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)
