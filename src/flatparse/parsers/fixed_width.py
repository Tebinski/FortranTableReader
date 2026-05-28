"""
flatparse/parsers/fixed_width.py

Fixed-width parser with consensus-gap column detection. See the project
README for the full description of cases handled.
"""

from typing import List, Optional, Tuple, Union

from flatparse.core.engine import BaseParser
from flatparse.core.models import Table
from flatparse.core.registry import register


@register("fixed_width")
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

    # --- Phase hooks (override in subclasses) ---

    def _compute_boundaries(self, data_lines: List[str]) -> List[Tuple[int, int]]:
        if self.col_widths:
            return self._widths_to_boundaries(self.col_widths)
        return self._detect_data_boundaries(data_lines)

    def _extract_header(
        self, header_lines: List[str], boundaries: List[Tuple[int, int]],
    ) -> List[str]:
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
        self, data_lines: List[str], boundaries: List[Tuple[int, int]],
    ) -> List[List[str]]:
        return [
            [line[s:e].strip() if s < len(line) else ''
             for s, e in boundaries]
            for line in data_lines
        ]

    # --- helpers ---

    @staticmethod
    def _as_lines(block: Union[str, List[str]]) -> List[str]:
        raw = block.splitlines() if isinstance(block, str) else list(block)
        return [
            l for l in raw
            if l.strip() and not FixedWidthParser._is_separator_line(l)
        ]

    @staticmethod
    def _is_separator_line(line: str) -> bool:
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
        if not lines:
            return []
        max_len = max(len(line) for line in lines)
        if max_len == 0:
            return []
        is_gap = [
            all(pos >= len(line) or line[pos] == ' ' for line in lines)
            for pos in range(max_len)
        ]
        boundaries, in_col, start = [], False, 0
        for pos in range(max_len):
            if not is_gap[pos] and not in_col:
                start, in_col = pos, True
            elif is_gap[pos] and in_col:
                boundaries.append((start, pos))
                in_col = False
        if in_col:
            boundaries.append((start, max_len))
        return boundaries

    def _split_header(
        self, header_line: str, data_boundaries: List[Tuple[int, int]],
    ) -> List[str]:
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
        groups, i, n = [], 0, len(line)
        while i < n:
            while i < n and line[i] == ' ':
                i += 1
            if i >= n:
                break
            start = last_non_space = i
            while i < n:
                if line[i] != ' ':
                    last_non_space, i = i, i + 1
                else:
                    space_start = i
                    while i < n and line[i] == ' ':
                        i += 1
                    if i >= n or i - space_start >= min_gap:
                        break
            groups.append((start, last_non_space + 1, line[start:last_non_space + 1]))
        return groups

    @staticmethod
    def _assign_groups_to_columns(
        groups: List[Tuple[int, int, str]],
        data_boundaries: List[Tuple[int, int]],
    ) -> List[str]:
        column_groups = [[] for _ in data_boundaries]
        col_centers = [(s + e) / 2 for s, e in data_boundaries]
        for g_start, g_end, g_text in groups:
            g_center = (g_start + g_end) / 2
            best = min(range(len(data_boundaries)),
                       key=lambda j: abs(g_center - col_centers[j]))
            column_groups[best].append(g_text)
        return [' '.join(parts) for parts in column_groups]
