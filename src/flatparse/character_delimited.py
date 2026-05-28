"""
parsers/character_delimited.py

CharacterDelimitedParser - splits rows on a single explicit delimiter
character. Preserves empty cells. Strips whitespace around values.

Use this for: CSV, TSV, pipe-delimited markdown-style tables, semicolon-
separated regional CSV variants.

DO NOT use this when the separator is "any whitespace" (multiple consecutive
spaces collapse to one). That's a different problem - use WhitespaceParser
for those.

For full RFC 4180 CSV semantics (quoted fields containing the delimiter),
wrap Python's `csv.reader` instead. This parser does simple splits and is
fine for FORTRAN reports and most engineering exports.
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


class CharacterDelimitedParser(BaseParser):

    def __init__(
        self,
        delimiter: str = ",",
        header_rows: int = 1,
        strip_cells: bool = True,
    ):
        if len(delimiter) != 1:
            raise ValueError(
                f"delimiter must be a single character, got {delimiter!r}"
            )
        self.delimiter = delimiter
        self.header_rows = header_rows
        self.strip_cells = strip_cells

    # --- BaseParser interface ---

    def detect(self, block) -> bool:
        lines = self._as_lines(block)
        if len(lines) < self.header_rows + 1:
            return False
        # Delimiter must appear in at least 80% of lines and column count
        # must be consistent across most lines.
        with_delim = [l for l in lines if self.delimiter in l]
        if len(with_delim) < 0.8 * len(lines):
            return False
        counts = [l.count(self.delimiter) for l in with_delim]
        return len(set(counts)) <= 2  # allow one outlier

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
        """Single line: simple split. Multi line: stack per column."""
        if len(header_lines) == 1:
            return self._split(header_lines[0])
        per_line = [self._split(hl) for hl in header_lines]
        n = max(len(parts) for parts in per_line)
        result = []
        for col in range(n):
            parts = [pl[col] if col < len(pl) else '' for pl in per_line]
            parts = [p for p in parts if p]
            result.append(' '.join(parts))
        return result

    def _extract_rows(self, data_lines: List[str]) -> List[List[str]]:
        return [self._split(line) for line in data_lines]

    # --- Helpers ---

    def _split(self, line: str) -> List[str]:
        cells = line.split(self.delimiter)
        if self.strip_cells:
            cells = [c.strip() for c in cells]
        return cells

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
        """A line of decorative chars (─, =, -, +, |, etc.) with no alnum content."""
        stripped = line.strip()
        return bool(stripped) and not any(c.isalnum() for c in stripped)


# --- Convenience subclasses for common delimiters ---

class CommaSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__(',', header_rows, strip_cells)


class TabSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__('\t', header_rows, strip_cells)


class PipeDelimitedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__('|', header_rows, strip_cells)


class SemicolonSeparatedParser(CharacterDelimitedParser):
    def __init__(self, header_rows: int = 1, strip_cells: bool = True):
        super().__init__(';', header_rows, strip_cells)
