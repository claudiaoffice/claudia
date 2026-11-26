"""Small helpers for tests of the kernel and of the apps: a toy list model, fake clocks.

``ListModel`` is the "toy model" of E1.1: a list of integers with Insert, Remove and Replace, an ``Interval`` region
that moves with the edits, and enough structure (redaction, undo, regions) to exercise every kernel feature
without any spreadsheet, text or slide code.
"""

from __future__ import annotations

import gc
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar, Self

from .commands import Command, CommandRegistry, new_registry
from .context import Context
from .model import DocumentModel
from .region import Region


def pointing_as_ref(fields: dict) -> dict:
    """Flat test fields that name the pointer by its kind (``image=…``) with the one ``ref`` a body has."""
    pointers = ("shape", "image", "chart", "container", "table")
    return {("ref" if name in pointers else name): value for name, value in fields.items()}


def body_before_ref(data: dict, *without: str) -> dict:
    """An object body's plain data as it was written with one pointer field per kind (``shape``, ``image``,
    ``diagram``, ``rendered``, ``table``) instead of ``ref``, and without the fields named: for the tests of documents
    that were written long ago."""
    old = {name: value for name, value in data.items() if name != "ref"}
    for pointer in ("shape", "image", "diagram", "rendered", "table"):
        old[pointer] = data["ref"] if pointer == data["kind"] else None
    return {name: value for name, value in old.items() if name not in without}


def work_of(fn: Callable[[], object]) -> int:
    """How much Python ``fn`` runs: the lines it starts and the turns of its loops, a one-line comprehension's too.

    The same on every machine and on every run, however busy the machine is or how big its caches are: what a
    performance guard compares when the cost is spent in Python (PROC-61, D1661). It does not see work done inside C
    (``x in a_list``, a list shifted by ``del``, ``max`` of a dict): a guard against that measures time
    (:func:`best_of`)."""
    monitoring = sys.monitoring
    tool = next(tool for tool in range(6) if monitoring.get_tool(tool) is None)  # (coverage may hold one)
    monitoring.use_tool_id(tool, "work_of")
    count = 0

    def counted(*_event: object) -> None:
        nonlocal count
        count += 1

    try:
        monitoring.register_callback(tool, monitoring.events.LINE, counted)
        monitoring.register_callback(tool, monitoring.events.JUMP, counted)
        monitoring.set_events(tool, monitoring.events.LINE | monitoring.events.JUMP)
        fn()
    finally:
        monitoring.set_events(tool, 0)
        monitoring.free_tool_id(tool)
    return count


BATCH_SECONDS = 0.2
"""How much processor time one measurement of :func:`best_of` gathers at least: a fast ``fn`` is run that many times,
so that the coarse processor clock of Windows (15.6 ms) is a small part of it."""


def best_of(repeat: int, fn: Callable[[], object]) -> float:
    """What one run of ``fn`` costs, in seconds of *processor* time, the least of ``repeat`` measurements, with the
    cyclic garbage collector held off: for a guard whose cost is spent in C, which :func:`work_of` cannot see.

    Processor time, not the wall clock: what other programs do with the machine meanwhile is not counted, so a busy
    runner does not make a linear cost look quadratic (it did: 61x to 71x for a 10x linear step under load, PERF-14).
    A collection is triggered by how much has been allocated, not by the work being measured, so it lands in the large
    case far more often than in the small one and reads as super-linear cost (reopening 8,000 formulas measured 20-25x
    the time of 800 with it on, 11x with it off). ``timeit`` turns it off for the same reason."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        best = float("inf")
        for _ in range(repeat):
            runs, started = 0, time.process_time()
            while (spent := time.process_time() - started) < BATCH_SECONDS or runs == 0:
                fn()
                runs += 1
            best = min(best, spent / runs)
        return best
    finally:
        if was_enabled:
            gc.enable()


class FakeClock:
    """Deterministic ISO times, one second apart, and a float clock for lock timeouts."""

    def __init__(self):
        self._start = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
        self.ticks = 0
        self.seconds = 0.0

    def time(self) -> str:
        self.ticks += 1
        return (self._start + timedelta(seconds=self.ticks)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def lock_time(self) -> float:
        return self.seconds

    def advance(self, seconds: float) -> None:
        self.seconds += seconds


@dataclass(frozen=True)
class Interval:
    """Positions ``start <= i < end`` of the list."""

    kind: ClassVar[str] = "interval"
    start: int
    end: int

    def overlaps(self, other: Region) -> bool:
        return isinstance(other, Interval) and self.start < other.end and other.start < self.end

    def transformed(self, command: Command) -> Interval | None:
        if isinstance(command, Insert):
            i = command.index
            if i <= self.start:
                return Interval(self.start + 1, self.end + 1)
            if i < self.end:
                return Interval(self.start, self.end + 1)
            return self
        if isinstance(command, Remove):
            i = command.index
            if i < self.start:
                return Interval(self.start - 1, self.end - 1)
            if i < self.end:
                return None if self.end - self.start == 1 else Interval(self.start, self.end - 1)
            return self
        return self

    def to_data(self) -> dict:
        return {"kind": self.kind, "start": self.start, "end": self.end}


lists = new_registry()


def _shift(index: int, other: Command, *, target: bool) -> int | None:
    """Where position ``index`` is after ``other`` ran. ``target``: the command acts *on* the element there
    (so a colleague removing or replacing that element makes it meaningless -> None) rather than at a gap."""
    if isinstance(other, Insert):
        return index + 1 if other.index <= index else index
    if isinstance(other, Remove):
        if other.index < index:
            return index - 1
        return None if (target and other.index == index) else index
    if isinstance(other, Replace):
        return None if (target and other.index == index) else index
    return index


class ListModel(DocumentModel):
    app: ClassVar[str] = "test-list"
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry] = lists

    def __init__(self, items: list[int] | None = None):
        self.items: list[int] = items or []
        self.settled = 0  # how often settle ran (tests check it runs once per command)

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"items": list(self.items)}

    @classmethod
    def restore(cls, state: dict) -> Self:
        return cls(list(state["items"]))

    def settle(self, ctx: Context) -> None:
        self.settled += 1

    def blank(self, parts: frozenset[str] | None) -> None:
        """Every item (or the items at the positions in ``parts``, written as numbers) becomes 0."""
        self.items = [0 if parts is None or str(i) in parts else item for i, item in enumerate(self.items)]

    def region_from_data(self, data: dict) -> Region:
        return Interval(data["start"], data["end"])


@lists.register
@dataclass(frozen=True)
class Insert(Command):
    kind: ClassVar[str] = "list.Insert"
    index: int
    value: int

    @property
    def label(self) -> str:
        return f"Insert {self.value}"

    def apply(self, ctx: Context) -> Command:
        items = ctx.model.items
        if not 0 <= self.index <= len(items):
            raise IndexError(f"cannot insert at {self.index}")
        items.insert(self.index, self.value)
        return Remove(self.index)

    def to_data(self) -> dict:
        return {"index": self.index, "value": self.value}

    @classmethod
    def from_data(cls, data, registry) -> Insert:
        return cls(data["index"], data["value"])

    def regions(self, model) -> tuple[Region, ...]:
        return (Interval(self.index, self.index + 1),)

    def shifted_by(self, other: Command) -> Command | None:
        index = _shift(self.index, other, target=False)
        return None if index is None else Insert(index, self.value)

    def redacted(self) -> Command:
        return Insert(self.index, 0)  # the position is structure, the value is content


@lists.register
@dataclass(frozen=True)
class Remove(Command):
    kind: ClassVar[str] = "list.Remove"
    index: int

    @property
    def label(self) -> str:
        return "Remove"

    def apply(self, ctx: Context) -> Command:
        items = ctx.model.items
        if not 0 <= self.index < len(items):
            raise IndexError(f"cannot remove at {self.index}")
        return Insert(self.index, items.pop(self.index))

    def to_data(self) -> dict:
        return {"index": self.index}

    @classmethod
    def from_data(cls, data, registry) -> Remove:
        return cls(data["index"])

    def regions(self, model) -> tuple[Region, ...]:
        return (Interval(self.index, self.index + 1),)

    def shifted_by(self, other: Command) -> Command | None:
        index = _shift(self.index, other, target=True)
        return None if index is None else Remove(index)

    def redacted(self) -> Command:
        return self


@lists.register
@dataclass(frozen=True)
class Replace(Command):
    kind: ClassVar[str] = "list.Replace"
    index: int
    value: int

    @property
    def label(self) -> str:
        return f"Set {self.value}"

    def apply(self, ctx: Context) -> Command:
        items = ctx.model.items
        if not 0 <= self.index < len(items):
            raise IndexError(f"cannot replace at {self.index}")
        old, items[self.index] = items[self.index], self.value
        return Replace(self.index, old)

    def to_data(self) -> dict:
        return {"index": self.index, "value": self.value}

    @classmethod
    def from_data(cls, data, registry) -> Replace:
        return cls(data["index"], data["value"])

    def regions(self, model) -> tuple[Region, ...]:
        return (Interval(self.index, self.index + 1),)

    def shifted_by(self, other: Command) -> Command | None:
        index = _shift(self.index, other, target=True)
        return None if index is None else Replace(index, self.value)

    def redacted(self) -> Command:
        return Replace(self.index, 0)
