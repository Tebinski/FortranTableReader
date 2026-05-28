"""
flatparse/core/engine.py

The three abstractions plugin authors build on:
  - BaseParser    : detect(block) + parse(block); optional row_strategy
  - BaseExtractor : extract(text) -> list of blocks
  - BaseReader    : orchestrates extractor + parsers -> Collection
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence, Union

from .models import Collection, Node, Table


class BaseParser(ABC):
    """A parser knows how to recognise and parse one kind of block.

    `row_strategy` is the composition hook: set it to another parser
    instance to delegate tabular extraction instead of reimplementing it.
    The registry inspects this attribute to record the dependency.
    """

    row_strategy: Optional["BaseParser"] = None

    @abstractmethod
    def detect(self, block: str) -> bool:
        """Return True if this parser can handle the block."""

    @abstractmethod
    def parse(self, block: str) -> Union[Table, Node]:
        """Parse the block into a Table or Node."""


class BaseExtractor(ABC):
    """Splits a raw file into blocks for the parsers to consume."""

    @abstractmethod
    def extract(self, text: str) -> List[str]:
        """Return a list of block strings."""


class BaseReader:
    """Orchestrator. Extracts blocks, dispatches each to the first parser
    whose detect() returns True, and assembles the results into a Collection.
    """

    def __init__(
        self,
        parsers: Sequence[BaseParser],
        extractor: BaseExtractor,
    ):
        self.parsers = list(parsers)
        self.extractor = extractor

    def read(self, text: str, source: Optional[str] = None) -> Collection:
        items: List[Union[Table, Node]] = []
        for block in self.extractor.extract(text):
            for parser in self.parsers:
                if parser.detect(block):
                    item = parser.parse(block)
                    if item is not None:
                        if getattr(item, "source", None) is None:
                            item.source = source or type(parser).__name__
                        items.append(item)
                    break
        return Collection(items=items)
