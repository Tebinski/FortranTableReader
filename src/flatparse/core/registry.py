"""
flatparse/core/registry.py

A registry that tracks every reader and parser registered with @register,
and - crucially - the dependencies between them. When a parser declares a
`row_strategy`, the registry records that it depends on that strategy's
parser. This makes reuse visible: if you change a base parser you can see
exactly which plugins depend on it, instead of discovering that five
plugins quietly reimplemented it.
"""

from typing import Dict, Set, Type


class Registry:

    def __init__(self):
        self._readers: Dict[str, Type] = {}
        self._parsers: Dict[str, Type] = {}
        self._deps: Dict[str, Set[str]] = {}  # name -> names it depends on

    def register(self, name: str):
        """Class decorator. Classifies the class as a reader or parser and
        captures any row_strategy dependency."""
        def decorator(cls):
            # Imported here to avoid a circular import at module load.
            from .engine import BaseParser, BaseReader

            if issubclass(cls, BaseReader):
                self._check_unique(name)
                self._readers[name] = cls
            elif issubclass(cls, BaseParser):
                self._check_unique(name)
                self._parsers[name] = cls
                self._capture_row_strategy(name, cls)
            else:
                raise TypeError(
                    f"@register: {cls.__name__} must subclass "
                    f"BaseReader or BaseParser"
                )
            cls._registry_name = name
            return cls
        return decorator

    # --- dependency capture ---

    def _capture_row_strategy(self, name: str, cls: Type) -> None:
        strategy = getattr(cls, "row_strategy", None)
        if strategy is None:
            return
        dep_name = getattr(type(strategy), "_registry_name", None)
        if dep_name:
            self._deps.setdefault(name, set()).add(dep_name)

    def _check_unique(self, name: str) -> None:
        if name in self._readers or name in self._parsers:
            raise ValueError(f"@register: name {name!r} is already registered")

    # --- queries ---

    def get_parser(self, name: str) -> Type:
        return self._parsers[name]

    def get_reader(self, name: str) -> Type:
        return self._readers[name]

    def parsers(self) -> Dict[str, Type]:
        return dict(self._parsers)

    def readers(self) -> Dict[str, Type]:
        return dict(self._readers)

    def dependencies_of(self, name: str) -> Set[str]:
        """What does `name` depend on?"""
        return set(self._deps.get(name, set()))

    def dependents_of(self, name: str) -> Set[str]:
        """Who depends on `name`? Check this before changing a base parser."""
        return {n for n, deps in self._deps.items() if name in deps}

    def summary(self) -> str:
        lines = [
            f"Registry: {len(self._readers)} reader(s), "
            f"{len(self._parsers)} parser(s)",
        ]
        for name in sorted(self._parsers):
            deps = self.dependencies_of(name)
            used_by = self.dependents_of(name)
            tag = []
            if deps:
                tag.append(f"uses: {', '.join(sorted(deps))}")
            if used_by:
                tag.append(f"used by: {', '.join(sorted(used_by))}")
            suffix = f"  ({'; '.join(tag)})" if tag else ""
            lines.append(f"  parser  {name}{suffix}")
        for name in sorted(self._readers):
            lines.append(f"  reader  {name}")
        return "\n".join(lines)


# The default global registry. `from flatparse.core.registry import register`
default_registry = Registry()
register = default_registry.register
