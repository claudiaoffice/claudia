"""Follow the computation: the cells that take part in a calculation with one cell, and their parts (E6.23, D297).

Clicking a cell that is part of a calculation lights up its inputs, the cells in between and its outputs, in the
colours of those parts, and dims the rest. This module finds the cells and their parts; what is drawn is the client's
business (and no arrows are drawn: the cells only light up).

* **Reach.** ``"group"`` is every cell connected to the clicked one, however the connection runs (two outputs that
  read the same input are in one group); ``"chain"`` is the cells it reads, directly or not, and the cells that read
  it, which keeps a big model readable.
* **Parts.** Relative to the connected cells: an *input* reads none of them, an *output* is read by none, anything
  else is a *calc*. A cell that is read from outside the window of cells being looked at keeps its part: the parts are
  worked out on all the connected cells, only the list that is returned is cut to the window.
* **Reading.** A cell that a formula names but that holds nothing does not light up. A range lights the cells in it that
  hold something.
* **Size.** No more than ``MAX_CELLS`` connected cells are followed; ``truncated`` says when that was not enough.

Other sheets are counted, not listed: a client marks their tabs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .refs import Position, SheetId

if TYPE_CHECKING:
    from .model import WorkbookModel

Key = tuple[SheetId, int, int]
Window = tuple[int, int, int, int]  # first row, first column, last row, last column (both included)

MAX_CELLS = 20_000  # connected cells that are followed
REACHES = ("group", "chain")


@dataclass(frozen=True, slots=True)
class Trace:
    """The cells connected to ``focus`` that lie in the window: ``cells`` maps their positions on the focus' sheet to
    ``"input"``, ``"calc"`` or ``"output"``. ``other_sheets`` counts the connected cells on other sheets, ``total`` all
    the connected cells (the focus included), ``connected`` says whether the focus is connected to anything at all."""

    focus: Key
    reach: str
    cells: dict[Position, str]
    other_sheets: dict[SheetId, int]
    total: int
    truncated: bool

    @property
    def connected(self) -> bool:
        """Whether the focus is connected to any other cell."""
        return self.total > 1

    def to_data(self) -> dict:
        """The trace as a client gets it."""
        sheet, row, col = self.focus
        return {
            "sheet": sheet,
            "row": row,
            "col": col,
            "reach": self.reach,
            "cells": [[r, c, role] for (r, c), role in sorted(self.cells.items())],
            "other": dict(sorted(self.other_sheets.items())),
            "total": self.total,
            "connected": self.connected,
            "truncated": self.truncated,
        }


def follow(
    model: WorkbookModel, sheet_id: SheetId, row: int, col: int, *, reach: str = "group", window: Window | None = None
) -> Trace:
    """The cells connected to the cell at (``row``, ``col``) of ``sheet_id``, as far as ``reach`` says (see the module
    documentation), and those of them in ``window`` (``None``: all on the sheet)."""
    if reach not in REACHES:
        raise ValueError(f"reach is one of {', '.join(REACHES)}, not {reach!r}")
    sheet = model.sheet(sheet_id)
    start: Key = (sheet_id, row, col)
    if (row, col) not in sheet.cells and (row, col) not in sheet.spilled:
        return Trace(start, reach, {}, {}, 0, False)
    walk = _Walk(model, start)
    if reach == "group":
        walk.spread([start], up=True, down=True)
    else:
        walk.spread([start], up=True, down=False)
        walk.spread([start], up=False, down=True)
    roles = walk.roles()
    if len(roles) == 1:  # (connected to nothing: nothing lights up)
        return Trace(start, reach, {}, {}, 1, False)
    cells = {
        (r, c): role
        for (s, r, c), role in roles.items()
        if s == sheet_id and (window is None or (window[0] <= r <= window[2] and window[1] <= c <= window[3]))
    }
    others: dict[SheetId, int] = {}
    for other, _, _ in roles:
        if other != sheet_id:
            others[other] = others.get(other, 0) + 1
    return Trace(start, reach, cells, others, len(roles), walk.truncated)


class _Walk:
    """The cells found so far from one start, and what each formula among them reads."""

    def __init__(self, model: WorkbookModel, start: Key):
        self.model = model
        self.found: dict[Key, None] = {start: None}
        self.truncated = False
        self._reads: dict[Key, list[Key]] = {}
        self._extents: dict[SheetId, tuple[int, int]] = {}

    def spread(self, frontier: list[Key], *, up: bool, down: bool) -> None:
        """Add, level by level, what the frontier reads (``up``) and what reads it (``down``)."""
        while frontier and not self.truncated:
            new: list[Key] = []
            if up:
                for key in frontier:
                    for precedent in self.reads(key):
                        self._add(precedent, new)
            if down:
                for reader in sorted(self.model.calc.readers_of(frontier)):
                    self._add(reader, new)
            frontier = new

    def _add(self, key: Key, new: list[Key]) -> None:
        if key in self.found or self.truncated:
            return
        if len(self.found) >= MAX_CELLS:
            self.truncated = True
            return
        self.found[key] = None
        new.append(key)

    def reads(self, key: Key) -> list[Key]:
        """The cells that hold something and that the formula at ``key`` reads (none for a constant)."""
        cached = self._reads.get(key)
        if cached is not None:
            return cached
        compiled = self.model.calc.formulas.get(key)
        found: list[Key] = []
        if compiled is not None:
            sheets = self.model.sheets
            for sheet_id, row, col in compiled.cells:
                sheet = sheets.get(sheet_id)
                if sheet is not None and ((row, col) in sheet.cells or (row, col) in sheet.spilled):
                    found.append((sheet_id, row, col))
            for sheet_id, row0, col0, row1, col1 in (*compiled.ranges, *compiled.reads):
                sheet = sheets.get(sheet_id)
                if sheet is None:
                    continue
                rows = self._extents.setdefault(sheet_id, sheet.extent())[0]
                found.extend((sheet_id, r, c) for r, c in sheet.cells_in(row0, min(row1, rows - 1), col0, col1))
        self._reads[key] = reads = [k for k in dict.fromkeys(found) if k != key]
        return reads

    def roles(self) -> dict[Key, str]:
        """The part of every cell found, from what the found formulas read among the found cells."""
        reading: set[Key] = set()  # reads one of the found cells
        read: set[Key] = set()  # is read by one of the found cells
        for key in self.found:
            for precedent in self.reads(key):
                if precedent in self.found:
                    reading.add(key)
                    read.add(precedent)
        return {key: "input" if key not in reading else ("calc" if key in read else "output") for key in self.found}
