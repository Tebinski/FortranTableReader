"""
examples/registry_demo.py

End-to-end demonstration:
  1. A Reader parses a multi-section FORTRAN file into a Collection.
  2. The @register("fuel_consumption") plugin delegates its table to
     FixedWidthParser via row_strategy.
  3. The registry shows the dependency graph - including that
     fuel_consumption depends on fixed_width.

Run:  uv run python examples/registry_demo.py
"""

from flatparse.core import BaseReader ,default_registry
from flatparse.extractors import BlankLineExtractor
from flatparse import (
    CommaSeparatedParser,
    FixedWidthParser,
    WhitespaceParser,
)
from flatparse.contrib import FuelConsumptionParser


SAMPLE = """=== FUEL CONSUMPTION REPORT ===
Units: kg/s | Date: 2024-01
ENGINE_ID   FLOW_RATE   TEMP
            [kg/s]      [K]
ENG-001     123.45      450.00
ENG-002      98.12      431.00

name,density,modulus
aluminium,2700,70000
steel,7800,210000

NODE   X        Y        Z
N001   1.234    5.678    0.000
N002  -2.345   -6.789    1.000
"""


def main():
    reader = BaseReader(
        parsers=[
            FuelConsumptionParser(),   # most specific first
            CommaSeparatedParser(),
            FixedWidthParser(),
            WhitespaceParser(),
        ],
        extractor=BlankLineExtractor(),
    )

    collection = reader.read(SAMPLE, source="demo.txt")

    print(f"Parsed {len(collection)} table(s)\n")
    for t in collection.tables():
        print(f"  title:    {t.title}")
        print(f"  source:   {t.source}")
        print(f"  metadata: {t.metadata}")
        print(f"  header:   {t.header}")
        for row in t.rows:
            print(f"    {row}")
        print()

    print("=" * 60)
    print(default_registry.summary())
    print("=" * 60)
    print()
    print("If you change FixedWidthParser, these depend on it:",
          default_registry.dependents_of("fixed_width"))


if __name__ == "__main__":
    main()
