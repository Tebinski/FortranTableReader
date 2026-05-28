"""
flatparse/contrib/fuel_consumption.py

Example plugin. A FORTRAN "fuel consumption" block looks like:

    === FUEL CONSUMPTION REPORT ===
    Units: kg/s | Date: 2024-01
    ENGINE_ID   FLOW_RATE   TEMP
                [kg/s]      [K]
    ENG-001     123.45      450.00
    ENG-002      98.12      431.00

The title and metadata lines are irregular, so this parser handles them
itself. The table underneath is a normal two-line-header fixed-width
table, so it delegates that to FixedWidthParser via `row_strategy` instead
of reimplementing column detection. The registry records the dependency
on `fixed_width` automatically.
"""

from flatparse.core.engine import BaseParser
from flatparse.core.models import Table
from flatparse.core.registry import register
from flatparse.parsers.fixed_width import FixedWidthParser


@register("fuel_consumption")
class FuelConsumptionParser(BaseParser):

    row_strategy = FixedWidthParser(header_rows=2)

    def detect(self, block: str) -> bool:
        lines = block.splitlines()
        return bool(lines) and "FUEL CONSUMPTION" in lines[0].upper()

    def parse(self, block: str) -> Table:
        lines = block.splitlines()
        title = lines[0].strip("= ").strip()
        metadata = self._parse_metadata(lines[1]) if len(lines) > 1 else {}

        # Delegate the table itself to the existing fixed-width parser.
        table = self.row_strategy.parse(lines[2:])
        table.title = title
        table.metadata = metadata
        return table

    @staticmethod
    def _parse_metadata(line: str) -> dict:
        """Parse 'Key: value | Key2: value2' into a dict."""
        meta = {}
        for part in line.split("|"):
            if ":" in part:
                k, v = part.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta
