"""What-if outcomes: every alternative of an input run through the cells that depend on it (E6.21, D294-D296).

A cell that holds alternatives (``{800, 1000, 1300}``) is an *input*. Everything that reads an input, however
indirectly, has one outcome per alternative; a cell that reads two inputs has one per combination. This module finds
those cells, runs them for the alternatives and summarises what came out, so a client can show the cell's median and
the distribution beside it.

How
---
* **Components.** Inputs whose dependent cells overlap belong together (they are combined); the others are independent
  and are *not* multiplied. A component is calculated once per combination of its inputs' alternatives with the
  calculator's own ``Round`` over exactly its cells (the inputs and what depends on them), so every formula,
  function and random number behaves as in the sheet. A random number is a function of its cell and the document's draw
  (``draws``), not of the alternative, so all alternatives see the same draw ("common random numbers").
* **Projection.** A cell is summarised over the inputs it actually reads, the others held at their first
  alternative: revenue that does not read the variable cost has three outcomes, not nine.
* **Limits.** More than ``MAX_COMBINATIONS`` combinations, or more than ``MAX_WORK`` cell calculations, are *sampled*:
  ``SAMPLES`` combinations chosen by the document's seed (so every machine takes the same ones). A summary says
  whether it was sampled.
* **When.** After every change that reaches a component's cells; a change elsewhere costs nothing. A workbook without
  alternatives never gets here.

Evaluating changes the sheet's values for a moment and then puts the first alternatives back (the calculation of a
command, and ``Calculator.outcome_table``, are synchronous: nobody sees the between).
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import product
from typing import TYPE_CHECKING

from .draws import uniform
from .formula.forms.alternatives import brace_text, items_of
from .refs import Position, SheetId
from .values import ErrorValue, Value

if TYPE_CHECKING:
    from .calc import Calculator

Key = tuple[SheetId, int, int]

MAX_COMBINATIONS = 10_000  # more combinations than this are sampled
SAMPLES = 2_000  # how many combinations a sampled component runs
MIN_SAMPLES = 100  # a component whose cells are many still runs at least this many
MAX_WORK = 2_000_000  # combinations x cells that one component may calculate
MAX_POINTS = 200  # how many outcomes a summary carries for a client to draw (evenly spread over the sorted ones)


# ------------------------------------------------------------------------------------------------ what is reported
@dataclass(frozen=True, slots=True)
class Alt:
    """One alternative of an input as the sheet shows it: its name (if it has one) and what it calculates to."""

    label: str | None
    value: Value

    def to_data(self) -> dict:
        """The alternative as a client gets it: typed content (``t``, ``v``) and ``l`` when it has a name."""
        from .model import content_of

        content = content_of(self.value) or {"t": "int", "v": 0}
        return {**content, "l": self.label} if self.label is not None else content


@dataclass(frozen=True, slots=True)
class InputCell:
    """What a client shows of an input cell: the text for the formula bar and the alternatives' values."""

    text: str
    alts: tuple[Alt, ...]


@dataclass(frozen=True, slots=True)
class Summary:
    """Where the outcomes of one cell lie: how many there are, how many of them are errors, and for the numbers their
    least, greatest, median and mean, and ``points`` (sorted, at most ``MAX_POINTS``) to draw a distribution from."""

    n: int
    errors: int
    sampled: bool
    minimum: float | None
    maximum: float | None
    median: float | None
    mean: float | None
    points: tuple[float, ...]

    def to_data(self) -> dict:
        """The summary as a client gets it."""
        return {
            "n": self.n,
            "errors": self.errors,
            "sampled": self.sampled,
            "min": self.minimum,
            "max": self.maximum,
            "median": self.median,
            "mean": self.mean,
            "points": list(self.points),
        }


@dataclass(frozen=True, slots=True)
class AltInput:
    """An input of a table: its cell, how many alternatives it has, their names and the text next to the cell."""

    key: Key
    count: int
    labels: tuple[str | None, ...]
    label: str | None

    def to_data(self) -> dict:
        """The input as a client gets it."""
        sheet, row, col = self.key
        return {
            "sheet": sheet,
            "row": row,
            "col": col,
            "count": self.count,
            "labels": list(self.labels),
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    """One outcome: which alternative of each input of the table (by position) it was run with, and what came out."""

    choice: tuple[int, ...]
    value: Value

    def to_data(self) -> dict:
        """The outcome as a client gets it: the choices and the value as typed content (``None``: nothing)."""
        from .model import content_of

        return {"choice": list(self.choice), "value": content_of(self.value)}


@dataclass(frozen=True, slots=True)
class Swing:
    """How far the outcomes move when only one input does: the mean outcome over the other inputs' alternatives for
    each alternative of ``input`` (a position in the table's inputs), the least and the greatest of those."""

    input: int
    low: float
    high: float
    low_choice: int
    high_choice: int

    def to_data(self) -> dict:
        """The swing as a client gets it."""
        return {
            "input": self.input,
            "low": self.low,
            "high": self.high,
            "low_choice": self.low_choice,
            "high_choice": self.high_choice,
        }


@dataclass(frozen=True, slots=True)
class OutcomeTable:
    """Every outcome of one cell with the inputs that make them, and which inputs matter most (widest swing first)."""

    inputs: tuple[AltInput, ...]
    rows: tuple[OutcomeRow, ...]
    sampled: bool
    sensitivity: tuple[Swing, ...] = field(default=())

    def to_data(self) -> dict:
        """The table as a client gets it."""
        return {
            "inputs": [i.to_data() for i in self.inputs],
            "rows": [r.to_data() for r in self.rows],
            "sampled": self.sampled,
            "sensitivity": [s.to_data() for s in self.sensitivity],
        }


# ------------------------------------------------------------------------------------------------ the arithmetic
def _numbers(values: list[Value]) -> list[float]:
    """The numbers among ``values`` (a TRUE is not one)."""
    return [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]


def summarize(values: list[Value], sampled: bool) -> Summary:
    """The summary of outcomes (numbers, errors, anything else: only numbers are placed)."""
    numbers = sorted(_numbers(values))
    errors = sum(1 for v in values if isinstance(v, ErrorValue))
    if not numbers:
        return Summary(len(values), errors, sampled, None, None, None, None, ())
    return Summary(
        len(values),
        errors,
        sampled,
        numbers[0],
        numbers[-1],
        statistics.median(numbers),
        math.fsum(numbers) / len(numbers),
        _thinned(numbers),
    )


def _thinned(numbers: list[float]) -> tuple[float, ...]:
    if len(numbers) <= MAX_POINTS:
        return tuple(numbers)
    last = len(numbers) - 1
    return tuple(numbers[round(i * last / (MAX_POINTS - 1))] for i in range(MAX_POINTS))


def _swings(rows: list[OutcomeRow], counts: list[int]) -> tuple[Swing, ...]:
    found = []
    for position, count in enumerate(counts):
        means: list[tuple[float, int]] = []
        for alternative in range(count):
            numbers = _numbers([r.value for r in rows if r.choice[position] == alternative])
            if numbers:
                means.append((math.fsum(numbers) / len(numbers), alternative))
        if means:
            low, high = min(means), max(means)
            found.append(Swing(position, low[0], high[0], low[1], high[1]))
    return tuple(sorted(found, key=lambda s: (s.low - s.high, s.input)))


# ------------------------------------------------------------------------------------------------ components
@dataclass(frozen=True, slots=True)
class Component:
    """Inputs that belong together and the cells that depend on them.

    ``down`` is, for each input, what depends on it; ``outputs`` the cells that get outcomes (everything that depends
    on an input, except inputs); ``needs`` for an output the positions in ``inputs`` of those it depends on."""

    inputs: tuple[Key, ...]
    down: dict[Key, frozenset[Key]]
    outputs: tuple[Key, ...]
    needs: dict[Key, tuple[int, ...]]
    cells: frozenset[Key]  # the inputs and everything that depends on them: what a combination calculates

    def signature(self) -> tuple:
        """What identifies the component: when it is the same, its summaries are good until one of its cells changes."""
        return self.inputs, self.cells


def build_components(calc: Calculator) -> list[Component]:
    """The components of the workbook's inputs (see the module documentation)."""
    inputs = sorted(calc.alternatives)
    if not inputs:
        return []
    down = {key: frozenset(calc._readers_closure({key})) for key in inputs}  # noqa: SLF001
    parent = {key: key for key in inputs}

    def find(key: Key) -> Key:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    claimed: dict[Key, Key] = {}
    for key in inputs:
        for cell in (*down[key], key):
            other = claimed.setdefault(cell, key)
            if other != key:
                parent[find(key)] = find(other)
    groups: dict[Key, list[Key]] = defaultdict(list)
    for key in inputs:
        groups[find(key)].append(key)
    components = []
    for members in groups.values():
        members.sort()
        reached = frozenset().union(*(down[m] for m in members))
        outputs = tuple(sorted(reached - set(members)))
        needs = {o: tuple(i for i, m in enumerate(members) if o in down[m]) for o in outputs}
        components.append(
            Component(tuple(members), {m: down[m] for m in members}, outputs, needs, reached | set(members))
        )
    return sorted(components, key=lambda c: c.inputs)


# ------------------------------------------------------------------------------------------------ the engine
class Outcomes:
    """The inputs and outcomes of one workbook, kept up to date by the calculator (``Calculator.settle``).

    The results are written to the sheets (``Sheet.alternatives`` and ``Sheet.outcomes``, which ``Sheet.view``
    shows)."""

    def __init__(self, calc: Calculator):
        self.calc = calc
        self.cells: dict[Key, InputCell] = {}
        self.summaries: dict[Key, Summary] = {}
        self._components: list[Component] = []
        self._graph = -1  # the calculator's graph version the components were built for
        self._state: dict[
            tuple[Key, ...], tuple[frozenset[Key], int | None]
        ] = {}  # per component: cells, seed if sampled

    def reset(self) -> None:
        """Forget everything (the model is being rebuilt)."""
        self.cells.clear()
        self.summaries.clear()
        self._components = []
        self._graph = -1
        self._state.clear()

    # -- keeping up
    def refresh(self, todo: set[Key] | None) -> dict[SheetId, set[Position]]:
        """Bring the inputs and outcomes up to date after ``todo`` was calculated (``None``: everything was). Returns
        the cells whose alternatives or outcomes are not what they were, for the people watching."""
        calc = self.calc
        if not (calc.alternatives or self.cells or self.summaries):
            return {}
        self._ensure_components()
        cells = {
            key: (self.cells[key] if key in self.cells and todo is not None and key not in todo else self._read(key))
            for key in sorted(calc.alternatives)
        }
        seed = calc.model.random_seed
        summaries: dict[Key, Summary] = {}
        state: dict[tuple[Key, ...], tuple[frozenset[Key], int | None]] = {}
        for component in self._components:
            sampled = self._sampled(component)
            state[component.inputs] = (component.cells, seed if sampled else None)
            fresh = (
                todo is None
                or self._state.get(component.inputs) != state[component.inputs]
                or not todo.isdisjoint(component.cells)
            )
            if fresh:
                summaries.update(self._summaries(component))
            else:
                summaries.update({o: self.summaries[o] for o in component.outputs if o in self.summaries})
        changed = self._apply(cells, summaries)
        self.cells, self.summaries, self._state = cells, summaries, state
        return changed

    def _ensure_components(self) -> None:
        if self._graph != self.calc.graph_version:
            self._components = build_components(self.calc)
            self._graph = self.calc.graph_version

    def _apply(self, cells: dict[Key, InputCell], summaries: dict[Key, Summary]) -> dict[SheetId, set[Position]]:
        sheets = self.calc.model.sheets
        changed: dict[SheetId, set[Position]] = defaultdict(set)
        for old, new, field_name in ((self.cells, cells, "alternatives"), (self.summaries, summaries, "outcomes")):
            for key in old.keys() - new.keys():
                sheet = sheets.get(key[0])
                if sheet is not None:
                    getattr(sheet, field_name).pop((key[1], key[2]), None)
                    changed[key[0]].add((key[1], key[2]))
            for key, value in new.items():
                if old.get(key) != value:
                    sheet = sheets.get(key[0])
                    if sheet is not None:
                        getattr(sheet, field_name)[(key[1], key[2])] = value
                        changed[key[0]].add((key[1], key[2]))
        return changed

    def _read(self, key: Key) -> InputCell:
        """An input as the sheet shows it: its alternatives' values (as the sheet is, with the first alternatives)."""
        calc = self.calc
        compiled = calc.formulas[key]
        items = items_of(compiled.formula.ast) or ()
        scope = calc.scope_for(key[0])
        scope.enter(*key)
        alts = []
        try:
            for position, (label, _) in enumerate(items):
                calc.choice[key] = position
                alts.append(Alt(label, calc._evaluate(compiled, scope)))  # noqa: SLF001
        finally:
            calc.choice.clear()
        return InputCell(brace_text(compiled.formula.ast, calc.model.sheet_name_of) or "", tuple(alts))

    # -- running combinations
    def _sample_size(self, component: Component) -> int | None:
        """How many combinations of ``component`` are run when they are too many to run all (``None``: all are run)."""
        total = math.prod(len(self.calc.alternatives[key]) for key in component.inputs)
        work = max(1, len(component.cells))
        if total <= MAX_COMBINATIONS and total * work <= MAX_WORK:
            return None
        count = min(SAMPLES, max(MIN_SAMPLES, MAX_WORK // work))
        return None if count >= total else count

    def _sampled(self, component: Component) -> bool:
        return self._sample_size(component) is not None

    def _plan(self, component: Component) -> tuple[list[tuple[int, ...]], bool]:
        """The combinations to run for ``component`` (one choice per input, first input changing slowest) and
        whether they are a sample of all of them (chosen by the document's seed: the same on every machine)."""
        counts = [len(self.calc.alternatives[key]) for key in component.inputs]
        count = self._sample_size(component)
        if count is None:
            return list(product(*(range(c) for c in counts))), False
        sheet, row, col = component.inputs[0]
        seed = self.calc.model.random_seed
        return [
            tuple(int(uniform(seed, sheet, row, col, -1, s * len(counts) + j) * c) for j, c in enumerate(counts))
            for s in range(count)
        ], True

    def _run(
        self, inputs: tuple[Key, ...], cells: frozenset[Key], choices: list[tuple[int, ...]], watch: list[Key]
    ) -> list[list[Value]]:
        """Calculate ``cells`` for each of ``choices`` (an alternative per input) and read ``watch`` each time; the
        first alternatives are put back afterwards."""
        calc = self.calc
        sheets = calc.model.sheets
        found: list[list[Value]] = []
        try:
            for choice in choices:
                calc.choice.clear()
                calc.choice.update(zip(inputs, choice, strict=True))
                calc._calculate(set(cells))  # noqa: SLF001
                found.append([sheets[sheet].grid.get((row, col)) for sheet, row, col in watch])
        finally:
            calc.choice.clear()
            calc._calculate(set(cells))  # noqa: SLF001
        return found

    def _summaries(self, component: Component) -> dict[Key, Summary]:
        choices, sampled = self._plan(component)
        values = self._run(component.inputs, component.cells, choices, list(component.outputs))
        found = {}
        for at, output in enumerate(component.outputs):
            needs = component.needs[output]
            keep = (
                range(len(choices))
                if sampled
                else [i for i, c in enumerate(choices) if all(c[p] == 0 for p in range(len(c)) if p not in needs)]
            )
            found[output] = summarize([values[i][at] for i in keep], sampled)
        return found

    # -- on demand
    def table(self, key: Key, combine: str = "all") -> OutcomeTable | None:
        """Every outcome of the cell ``key`` with the inputs that make them, or ``None`` when it has none.

        ``combine`` is ``"all"`` (every combination of the cell's inputs) or ``"pair"`` (the first alternative of each
        input with the first of the others, the second with the second, and so on: the inputs must have as many
        alternatives)."""
        if combine not in ("all", "pair"):
            raise ValueError(f"combine is 'all' or 'pair', not {combine!r}")
        self._ensure_components()
        found = self._component_of(key)
        if found is None:
            return None
        component, needs = found
        counts = [len(self.calc.alternatives[component.inputs[p]]) for p in needs]
        sampled = False
        if combine == "pair":
            if len(set(counts)) > 1:
                raise ValueError(f"to pair them the inputs must have the same number of alternatives, not {counts}")
            projected = [tuple([a] * len(needs)) for a in range(counts[0])]
            full = [self._widen(component, needs, choice) for choice in projected]
        else:
            planned, sampled = self._plan(component)
            if sampled:
                full = planned
                projected = [tuple(c[p] for p in needs) for c in planned]
            else:
                projected = list(product(*(range(c) for c in counts)))
                full = [self._widen(component, needs, choice) for choice in projected]
        cells = frozenset().union(*(component.down[component.inputs[p]] for p in needs)) | {
            component.inputs[p] for p in needs
        }
        values = self._run(component.inputs, cells | set(component.inputs), full, [key])
        rows = tuple(OutcomeRow(choice, value[0]) for choice, value in zip(projected, values, strict=True))
        inputs = tuple(self._input(component.inputs[p]) for p in needs)
        return OutcomeTable(inputs, rows, sampled, _swings(list(rows), counts))

    @staticmethod
    def _widen(component: Component, needs: tuple[int, ...], choice: tuple[int, ...]) -> tuple[int, ...]:
        """One choice per input of the component, from the choices of the ``needs`` inputs (the others: the first)."""
        wide = [0] * len(component.inputs)
        for position, alternative in zip(needs, choice, strict=True):
            wide[position] = alternative
        return tuple(wide)

    def _component_of(self, key: Key) -> tuple[Component, tuple[int, ...]] | None:
        for component in self._components:
            needs = component.needs.get(key)
            if needs:
                return component, needs
        return None

    def _input(self, key: Key) -> AltInput:
        labels = self.calc.alternatives[key]
        left = self.calc.model.sheets[key[0]].cells.get((key[1], key[2] - 1)) if key[2] > 0 else None
        text = left["v"] if left is not None and left["t"] == "text" else None
        return AltInput(key, len(labels), labels, text)
