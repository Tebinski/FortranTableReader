"""
flatparse/extractors/blank_line.py

Splits a file into blocks on blank lines. The most common extractor for
FORTRAN reports, where logical sections are separated by empty lines.
"""

from typing import List

from flatparse.core.engine import BaseExtractor


class BlankLineExtractor(BaseExtractor):

    def extract(self, text: str) -> List[str]:
        blocks: List[str] = []
        current: List[str] = []
        for line in text.splitlines():
            if line.strip() == "":
                if current:
                    blocks.append("\n".join(current))
                    current = []
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))
        return blocks
