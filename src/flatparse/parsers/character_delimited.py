"""
flatparse/parsers/character_delimited.py

Splits rows on a single explicit delimiter character. Preserves empty
cells; strips surrounding whitespace. Convenience subclasses cover the
common delimiters.
"""

from typing import List, Union

from flatparse.core.engine import BaseParser
from flatparse.core.models import Table
from flatparse.core.registry import register


@register("character_delimited")
class CharacterDelimitedParser(BaseParser):

    def __init__(self, delimiter: str = ",", header_rows: int = 1,
                 strip_cells: bool = True):
        if len(delimiter) != 1:
            raise ValueError(
                f"delimiter must be a single character, got {delimiter!r}")
        self.delimiter = delimiter
        self.header_rows = header_rows
        self.strip_cells = strip_cells

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False
        with_delim = [l for l in lines if self.delimiter in l]
        if len(with_delim) < 0.8 * len(lines):
            return False
        counts = [l.count(self.delimiter) for l in with_delim]
        return len(set(counts)) <= 2

    def parse(self, block) -> Table:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return Table(header=[], rows=[])
        header = self._extract_header(lines[:self.header_rows])
        rows = self._extract_rows(lines[self.header_rows:])
        return Table(header=header, rows=rows)

    def _extract_header(self, header_lines: List[str]) -> List[str]:
        if len(header_lines) == 1:
            return self._split(header_lines[0])
        per_line = [self._split(hl) for hl in header_lines]
        n = max(len(parts) for parts in per_line)
        result = []
        for col in range(n):
            parts = [pl[col] if col < len(pl) else '' for pl in per_line]
            result.append(' '.join(p for p in parts if p))
        return result

    def _extract_rows(self, data_lines: List[str]) -> List[List[str]]:
        return [self._split(line) for line in data_lines]

    def _split(self, line: str) -> List[str]:
        cells = line.split(self.delimiter)
        return [c.strip() for c in cells] if self.strip_cells else cells

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip()
            and not CharacterDelimitedParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)


@register("comma_separated")
class CommaSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__(',', header_rows, strip_cells)


@register("tab_separated")
class TabSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__('\t', header_rows, strip_cells)


@register("pipe_delimited")
class PipeDelimitedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__('|', header_rows, strip_cells)


@register("semicolon_separated")
class SemicolonSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__(';', header_rows, strip_cells)
