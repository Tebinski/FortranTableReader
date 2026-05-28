"""
flatparse/core/models.py

The data model every parser populates: Table (tabular), Node (tree), and
Collection (the container a Reader returns). Each carries an optional
`source` for provenance tracking.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass
class Table:
    header: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    title: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    source: Optional[str] = None  # provenance: which parser/file produced this

    @property
    def shape(self) -> tuple:
        return (len(self.rows), len(self.header))


@dataclass
class Node:
    name: str
    value: Any = None
    children: List["Node"] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source: Optional[str] = None

    def add(self, child: "Node") -> "Node":
        self.children.append(child)
        return child


@dataclass
class Collection:
    """A container of items - Tables and/or Nodes - returned by a Reader."""
    items: List[Union[Table, Node]] = field(default_factory=list)
    title: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def tables(self) -> List[Table]:
        return [i for i in self.items if isinstance(i, Table)]

    def nodes(self) -> List[Node]:
        return [i for i in self.items if isinstance(i, Node)]

    def __len__(self) -> int:
        return len(self.items)
