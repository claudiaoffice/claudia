"""A scripted stand-in for the AI model, for demos and tests (the real model is E3.6).

It understands a few phrases about cells and says so honestly when it does not understand: it is not an intelligence
and does not pretend to be one. It works on the sheet the asker is looking at (their presence), else on the first one.
Sums and the like are computed here and written as plain numbers: formulas come with the formula engine.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from claudia_computes import (
    CellRef,
    CellRegion,
    RangeRef,
    RefParseError,
    SheetId,
    WorkbookModel,
    column_name,
    parse_range_ref,
)

from .assistant import Call, Say, Step, Task

MAX_CELLS = 2_000  # cells one instruction may touch
_CELL = r"[A-Za-z]{1,3}[0-9]{1,7}"
_RANGE = rf"{_CELL}(?::{_CELL})?"
_FILL = re.compile(rf"(?:fill|put)\s+({_RANGE})\s+with\s+(.+)", re.I)
_SET_TO = re.compile(rf"set\s+({_RANGE})\s+to\s+(.+)", re.I)
_WRITE = re.compile(rf"(?:write|put|type|enter)\s+(.+?)\s+(?:in|into|at)\s+({_RANGE})", re.I)
_CLEAR = re.compile(rf"(?:clear|empty|erase)\s+({_RANGE})", re.I)
_SUMMARY = re.compile(
    rf"(sum|total|average|mean|min|max|count)\s+(?:of\s+)?({_RANGE})\s+(?:in|into|to|at)\s+({_CELL})", re.I
)
_SHEET = re.compile(r"add\s+(?:a\s+)?(?:new\s+)?sheet\s+(?:called\s+|named\s+)?(.+)", re.I)
_EXAMPLE = re.compile(r"\b(?:example|sample|demo|budget)\b", re.I)
_HELP = re.compile(r"^\W*(?:hi|hello|hey|help|what can you do)\b", re.I)

HELP = (
    "I am a stand-in for the real model and understand only a few phrases: "
    "fill B2:B6 with 10 · set A1 to hello · write 42 in C3 · clear A1:B2 · sum B2:B6 into B7 "
    "(also average, min, max, count) · add sheet Forecast · build an example budget."
)
NOT_UNDERSTOOD = "I did not understand that: I am only a stand-in for the real model. Say help to see what I can do."
NO_SHEET = "There is no sheet yet. Add one first (say: add sheet Budget)."
BUDGET = (("Item", "Amount"), ("Rent", 1200), ("Food", 450), ("Transport", 120), ("Savings", 300))


def _clean(value: str) -> str:
    """A value as typed in a sentence: without quotes around it."""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    return text


def _label(area: RangeRef) -> str:
    first = f"{column_name(area.first.col)}{area.first.row + 1}"
    last = f"{column_name(area.last.col)}{area.last.row + 1}"
    return first if first == last else f"{first}:{last}"


def _shown(number: float) -> str:
    """A number as one types it, without noise such as 2.0 or 0.30000000000000004."""
    return str(int(number)) if float(number).is_integer() else format(number, ".12g")


def _cells(area: RangeRef, text: str) -> list[dict]:
    return [{"row": r, "col": c, "input": text} for r, c in area.cells()]


def _focus(sheet: SheetId, area: RangeRef) -> tuple[dict, ...]:
    return (CellRegion.of(sheet, area.first.row, area.first.col, area.last.row, area.last.col).to_data(),)


def _area(row: int, first_col: int, last_col: int) -> RangeRef:
    return RangeRef.between(CellRef(row, first_col), CellRef(row, last_col))


class ScriptedEngine:
    """Reads one instruction and turns it into steps."""

    def plan(self, task: Task) -> list[Step]:
        """The steps for what the asker wrote."""
        text = task.text.strip()
        if _HELP.match(text):
            return [Say(HELP)]
        sentence = text.rstrip(".!? ")
        if match := _SHEET.fullmatch(sentence):
            name = _clean(match.group(1))
            return [Call("add_sheet", {"name": name}), Say(f"I added the sheet {name}.")]
        model = task.document.model
        assert isinstance(model, WorkbookModel)
        rules: tuple[tuple[re.Pattern[str], Callable[..., list[Step]]], ...] = (
            (_FILL, self._fill),
            (_SET_TO, self._fill),
            (_WRITE, self._write),
            (_CLEAR, self._clear),
            (_SUMMARY, self._summary),
            (_EXAMPLE, self._example),
        )
        for pattern, handler in rules:
            match = pattern.search(sentence)
            if match is None:
                continue
            sheet = self._sheet_of(task, model)
            if sheet is None:
                return [Say(NO_SHEET)]
            try:
                return handler(model, sheet, *match.groups())
            except RefParseError:
                break
        return [Say(NOT_UNDERSTOOD)]

    @staticmethod
    def _sheet_of(task: Task, model: WorkbookModel) -> SheetId | None:
        hold = task.document.presence.of(task.sender)
        for region in hold.regions if hold else ():
            if isinstance(region, CellRegion) and region.sheet in model.sheets:
                return region.sheet
        return next(iter(model.sheets), None)

    @staticmethod
    def _put(sheet: SheetId, area: RangeRef, text: str, said: str) -> list[Step]:
        count = (area.last.row - area.first.row + 1) * (area.last.col - area.first.col + 1)
        if count > MAX_CELLS:
            return [Say(f"That is {count} cells; I touch at most {MAX_CELLS} at a time.")]
        return [Call("set_cells", {"sheet": sheet, "cells": _cells(area, text)}, _focus(sheet, area)), Say(said)]

    def _fill(self, model: WorkbookModel, sheet: SheetId, where: str, value: str) -> list[Step]:
        area, text = parse_range_ref(where), _clean(value)
        return self._put(sheet, area, text, f"{_label(area)} now says {text}.")

    def _write(self, model: WorkbookModel, sheet: SheetId, value: str, where: str) -> list[Step]:
        return self._fill(model, sheet, where, value)

    def _clear(self, model: WorkbookModel, sheet: SheetId, where: str) -> list[Step]:
        area = parse_range_ref(where)
        return self._put(sheet, area, "", f"I cleared {_label(area)}.")

    def _summary(self, model: WorkbookModel, sheet: SheetId, how: str, source: str, target: str) -> list[Step]:
        area, into = parse_range_ref(source), parse_range_ref(target)
        cells = model.sheet(sheet).cells
        numbers = [cells[p]["v"] for p in area.cells() if p in cells and cells[p]["t"] in ("int", "float")]
        if not numbers:
            return [Say(f"There are no numbers in {_label(area)} to work with.")]
        how = how.casefold()
        result = {
            "sum": sum(numbers),
            "total": sum(numbers),
            "average": sum(numbers) / len(numbers),
            "mean": sum(numbers) / len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "count": len(numbers),
        }[how]
        said = (
            f"The {how} of {_label(area)} is {_shown(result)}, written into {_label(into)} "
            "as a plain number for now: formulas come later."
        )
        return self._put(sheet, into, _shown(result), said)

    def _example(self, model: WorkbookModel, sheet: SheetId) -> list[Step]:
        steps: list[Step] = [Say("I will type a small monthly budget into A1:B6.")]
        for row, (item, amount) in enumerate((*BUDGET, ("Total", sum(a for _, a in BUDGET[1:])))):
            cells = [{"row": row, "col": 0, "input": item}, {"row": row, "col": 1, "input": str(amount)}]
            steps.append(Call("set_cells", {"sheet": sheet, "cells": cells}, _focus(sheet, _area(row, 0, 1))))
        steps.append(Say("Done. Try changing a number, or ask me to sum B2:B5 into B7."))
        return steps
