# CODEBASE.md

Working map of the `flatparse` codebase for contributors (human or LLM). Complements the README — the README explains *what the library does*; this file explains *where the code lives and why it's shaped this way*.

## Mental model

`flatparse` is a plugin framework, not a monolithic parser. The runtime flow is:

```
file text ──► BaseExtractor.extract() ──► [block, block, block]
                                               │
                                          for each block:
                                               │
                                          parsers[i].detect() ──► True ──► parsers[i].parse() ──► Table | Node
                                               │
                                               ▼
                                          Collection(items=[...])
```

Three abstractions, three responsibilities, three places to extend.

## Directory map

```
src/flatparse/
├── __init__.py                  Public API. Re-exports everything users need.
│                                Imports `contrib` LAST so registry deps capture.
├── core/
│   ├── models.py                Table, Node, Collection (dataclasses with `source`)
│   ├── engine.py                BaseParser, BaseExtractor, BaseReader (ABCs)
│   └── registry.py              Registry class + @register decorator + default_registry
├── parsers/
│   ├── fixed_width.py           Consensus-gap column detection. Phase-split parse().
│   ├── character_delimited.py   Single-char delimiter (CSV/TSV/pipe/semicolon)
│   ├── whitespace.py            Splits on any whitespace run
│   └── fixed_tail.py            Anchors N value columns from the RIGHT
├── extractors/
│   └── blank_line.py            Splits file into blocks on blank lines
└── contrib/
    └── fuel_consumption.py      Example plugin using row_strategy composition

tests/
├── test_fixed_width.py          22 tests across alignment / negatives / multi-line / separators
├── test_character_delimited.py  16 tests across delimiters + multi-line + detect
├── test_whitespace.py           14 tests including documented limitations
└── test_fixed_tail.py           12 tests for TAU-style right-anchored tables

examples/
├── registry_demo.py             End-to-end: reader + contrib plugin + registry summary
├── tau_demo.py                  fixed_width vs fixed_tail on the TAU-style table
└── pandas_vs_flatparse.py       Empirical comparison: 8 cases, 4/8 vs 8/8
```

## Core abstractions

### `BaseParser` (engine.py)

Contract for every parser:

```python
class BaseParser(ABC):
    row_strategy: Optional["BaseParser"] = None   # composition hook

    @abstractmethod
    def detect(self, block: str) -> bool: ...
    @abstractmethod
    def parse(self, block: str) -> Union[Table, Node]: ...
```

`detect()` must be conservative — false positives cause the orchestrator to consume blocks with the wrong parser. The convention is "return True only when the structural signal is strong" (e.g. CharacterDelimitedParser requires the delimiter in ≥80% of lines AND consistent column counts).

`row_strategy` is the reuse hook. Setting it to another parser instance lets the registry capture the dependency automatically (see Registry below).

### `BaseExtractor` (engine.py)

```python
class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> List[str]: ...
```

Splits raw file text into blocks. The only extractor right now is `BlankLineExtractor`. Future extractors might split on heading markers, section IDs, or fixed line counts.

### `BaseReader` (engine.py)

Not abstract — concrete orchestrator. Takes `parsers: Sequence[BaseParser]` and `extractor: BaseExtractor`. The `read(text, source=None)` method:

1. Calls `extractor.extract(text)` → list of blocks.
2. For each block, iterates `parsers` in order, first `detect() → True` wins.
3. Calls that parser's `parse(block)`, stamps `source` if unset, appends to `Collection.items`.

Parser order matters: most specific first, most general last.

## Data model (models.py)

All three models are dataclasses. All three carry `source: Optional[str]` for provenance.

- **`Table`** — `header: List[str]`, `rows: List[List[str]]`, `title`, `metadata`, `source`. The `.shape` property returns `(n_rows, n_cols)`. Cell values are always strings; type coercion is the consumer's job.
- **`Node`** — `name`, `value`, `children: List[Node]`, `metadata`, `source`. Use `.add(child)` to append a child (returns the child for chaining).
- **`Collection`** — `items: List[Table | Node]`, `title`, `metadata`. Helpers: `.tables()`, `.nodes()`, `len()`.

Cell values stay as strings on purpose. This library is about *structural extraction*; numeric parsing is a separate concern that should not corrupt provenance (e.g. `001` must not become `1`).

## Registry (registry.py)

`@register("name")` is a class decorator that:

1. Checks the class is a `BaseParser` or `BaseReader` subclass.
2. Stores it under `name` in the appropriate dict.
3. Stamps `cls._registry_name = name` on the class.
4. If the parser has a non-None `row_strategy`, looks up the strategy's class `_registry_name` and records the dependency.

Public queries on `default_registry`:

- `parsers()`, `readers()` — dicts of registered classes.
- `dependencies_of(name)` — set of parser names this parser depends on.
- `dependents_of(name)` — set of parser names that depend on this one. **This is the question you ask before changing a base parser.**
- `summary()` — human-readable text dump.

**Gotcha**: dependency capture happens at decoration time. For a row_strategy dependency to be captured, the strategy's parser must already be registered. This is why `flatparse/__init__.py` imports `parsers/` before `contrib/`.

## Parser conventions

### Three-phase pattern (fixed_width.py, fixed_tail.py)

`parse()` is split into three method calls that subclasses can override individually:

```python
def parse(self, block):
    lines = self._as_lines(block)
    boundaries = self._compute_boundaries(data_lines)   # Phase 1: where are columns?
    header     = self._extract_header(...)               # Phase 2: column names
    rows       = self._extract_rows(...)                 # Phase 3: cell values
    return Table(header=header, rows=rows)
```

When extending, override only the phase that changes. Don't replicate the orchestration in `parse()`.

### Separator-line filtering

Every parser's `_as_lines()` filters lines that are entirely non-alphanumeric (after `strip()`). This catches `─────`, `----`, `====`, `+----+----+` uniformly without needing case-specific logic. If you write a new parser, copy this idiom.

### `header_rows: int = 1`

Multi-line headers are a recurring case (units on a second line, stacked names). The convention is a constructor kwarg `header_rows=N`. Phase 2 stacks per-column non-empty cells with a space separator.

### Numeric tokens

`FixedTailParser._NUMBER` recognises Fortran exponents (`1.5e-05`, `1.5E-05`, `1.5d-05`, `1.5D-05`). If you parse numeric output from old Fortran codes, reuse that regex rather than rolling your own.

## How to add a new parser

1. Create `src/flatparse/parsers/<name>.py`.
2. Subclass `BaseParser`. Implement `detect()` (conservative) and `parse()` (returns `Table` or `Node`).
3. Decorate the class with `@register("<name>")`.
4. Export from `src/flatparse/parsers/__init__.py` and the top-level `__init__.py`.
5. Add `tests/test_<name>.py` with at least: a basic happy-path test, an edge case from real-world data, and a `detect()`-rejects-non-matching-blocks test.

## How to add a contrib plugin

Contrib parsers handle domain-specific block formats (e.g. a particular FORTRAN report). The pattern:

1. Subclass `BaseParser`.
2. Set `row_strategy = SomeBuiltinParser(...)` if a built-in parser can handle the tabular part.
3. Implement `detect()` against the title line or distinguishing markers.
4. In `parse()`, extract title/metadata yourself, then delegate the table:

```python
@register("fuel_consumption")
class FuelConsumptionParser(BaseParser):
    row_strategy = FixedWidthParser(header_rows=2)

    def detect(self, block):
        return "FUEL CONSUMPTION" in block.splitlines()[0].upper()

    def parse(self, block):
        lines = block.splitlines()
        title = lines[0].strip("= ").strip()
        metadata = self._parse_metadata(lines[1])
        table = self.row_strategy.parse(lines[2:])
        table.title = title
        table.metadata = metadata
        return table
```

The registry records the dependency on `fixed_width` automatically. Don't reimplement column detection.

## How to add a new extractor

1. Create `src/flatparse/extractors/<name>.py`.
2. Subclass `BaseExtractor`. Implement `extract(text) -> List[str]`.
3. Export from `extractors/__init__.py` and the top-level `__init__.py`.
4. Extractors are not currently registered with `@register` — they're passed directly to `BaseReader`. If you want extractor registry support, that's a registry extension, not a parser change.

## Test conventions

- One test file per parser, mirroring the source filename (`fixed_width.py` → `test_fixed_width.py`).
- Group related tests into classes named `TestSomeBehaviour` for readability.
- Include a `TestKnownLimitations` class for documented misbehaviour (see `test_whitespace.py`). This makes the parser's boundaries explicit and prevents users from misusing it.
- Run with `uv run pytest`. Tests must pass before merging.

## Conventions

- **All code, comments, docstrings, identifiers, and commit messages in English.** No Spanish in code, even though informal discussion may happen in Spanish.
- **Cell values are strings.** Don't introduce type coercion in parsers.
- **Stdlib only in core/ and parsers/.** External dependencies belong in `contrib/` or as optional extras in `pyproject.toml`. The library's identity is "stdlib parser for cases pandas can't handle"; a stdlib core is part of that promise.
- **Imports inside the package use the absolute form** (`from flatparse.core.models import Table`), not relative. The single exception is `__init__.py` files using `.module` for clarity.

## Known sharp edges

1. **Registry capture order.** Contrib parsers must import after the built-in parsers they depend on, or the dependency is missed. Handled in `flatparse/__init__.py`; preserve that order.
2. **`WhitespaceParser` cannot represent empty cells or values with internal spaces.** Documented as `TestKnownLimitations`. When in doubt, use `FixedWidthParser` or a delimited parser.
3. **`FixedTailParser` auto-detection picks the mode of trailing numeric token counts.** In production, pass `n_tail=N` explicitly to avoid surprises from outlier rows.
4. **`CharacterDelimitedParser.detect()` requires consistent column counts.** A block with a free-form title line above CSV data will fail detection — that's by design; handle title/metadata in a contrib parser using `row_strategy`.
5. **`__init__.py` re-exports are deliberate.** Users should write `from flatparse import FixedWidthParser`, not `from flatparse.parsers.fixed_width import FixedWidthParser`. Keep the surface area in the top-level `__init__.py` curated.

## Where to look first when…

| Task | Start here |
|---|---|
| Adding a new built-in parser | `parsers/fixed_width.py` as template |
| Adding a domain-specific plugin | `contrib/fuel_consumption.py` as template |
| Understanding how blocks flow through | `core/engine.py` `BaseReader.read()` |
| Understanding registry behaviour | `core/registry.py` + `examples/registry_demo.py` |
| Investigating a parsing bug | The matching `tests/test_*.py` file |
| Comparing to pandas | `examples/pandas_vs_flatparse.py` |