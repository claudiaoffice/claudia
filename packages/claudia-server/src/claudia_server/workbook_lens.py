"""The AI's lens on a workbook (E7.5 a): cells are named like people name them (``B7``) and every change is reported
with the cells that were recalculated because of it, errors first."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from claudia_computes import WorkbookModel, column_name
from claudia_computes.events import CellsChanged, SheetsChanged, StructureChanged
from claudia_computes.refs import StructuralEdit
from claudia_core import Document

from .lens import fence, shorten

MAX_LISTED_SHEETS = 50  # sheets named to the model; a small model has little room
MAX_SHEET_NAME = 30
PREVIEW_SHEETS = 3  # sheets whose top left corner is shown
PREVIEW_ROWS, PREVIEW_COLS, PREVIEW_CELLS = 6, 8, 30
MAX_TEXT = 60  # characters of one text value shown
MAX_SHOWN_CELLS = 200  # cells of one read answer shown
MAX_REPORTED_CELLS = 25  # cells of one effect report listed

ORIENTATION = (
    "Rows and columns in requests are counted from 0: A1 is row 0, column 0; B1 is row 0, column 1; A2 is row 1, "
    "column 0. What you are shown is written as A1, B7 and so on.{example}"
)
EXAMPLE = (
    ' A request looks like {{"method": "set_cells", "params": {{"sheet": "s1", "cells": '
    '[{{"row": 0, "col": 0, "input": "42"}}]}}}}.'
)  # left out when the asker's mode or role lets the AI change nothing: it would only invite a refused request


def address(row: int, col: int) -> str:
    """``(1, 1)`` -> ``B2``."""
    return f"{column_name(col)}{row + 1}"


def window(row0: int, row1: int, col0: int, col1: int) -> str:
    """``(0, 9, 0, 3)`` -> ``A1:D10``."""
    return f"{address(row0, col0)}:{address(row1, col1)}"


def _held(rows: int, cols: int) -> str:
    return window(0, rows - 1, 0, cols - 1) if rows and cols else "empty"


def describe_cell(row: int, col: int, content: dict | None) -> str:
    """One cell for the model: ``B2: 24 (=B1*2)``, ``A1: "Item"``, ``C3: ERROR #DIV/0! (=A1/0)``."""
    where = address(row, col)
    if content is None:
        return f"{where}: (empty)"
    value, formula = content.get("v"), content.get("f")
    if content.get("t") == "error":
        shown = f"ERROR {value}"
    elif content.get("t") == "text" or isinstance(value, str):
        shown = '"' + shorten(str(value), MAX_TEXT) + '"'
    elif isinstance(value, float):
        shown = f"{value:.10g}"
    else:
        shown = str(value)
    return f"{where}: {shown}" + (f" ({shorten(formula, MAX_TEXT)})" if formula else "")


class WorkbookLens:
    """The lens for computes."""

    look_methods: tuple[str, ...] = ("sheets", "cells", "functions", "function_help")

    # -- where the model starts
    def orient(self, document: Document, *, can_write: bool) -> str:
        """How cells are counted, the sheets with what they hold, and the top left corner of the first few."""
        model = document.model
        assert isinstance(model, WorkbookModel)
        sheets = list(model.sheets.values())
        text = ORIENTATION.format(example=EXAMPLE if can_write else "")
        if not sheets:
            return text + "\nThere are no sheets yet: add one with add_sheet."
        lines = []
        for sheet in sheets[:MAX_LISTED_SHEETS]:
            rows, cols = sheet.extent()
            lines.append(f"{sheet.id}: {shorten(' '.join(sheet.name.split()), MAX_SHEET_NAME)} ({_held(rows, cols)})")
        if len(sheets) > MAX_LISTED_SHEETS:
            lines.append(f"... and {len(sheets) - MAX_LISTED_SHEETS} more")
        text += "\nSheets in this document (id: name (cells in use)):\n" + "\n".join(lines)
        previews = [self._preview(sheet) for sheet in sheets[:PREVIEW_SHEETS]]
        previews = [p for p in previews if p]
        if previews:
            text += "\nTop left of the first sheets:\n" + fence("\n".join(previews))
        return text

    @staticmethod
    def _preview(sheet: Any) -> str:
        found = sheet.cells_in(0, PREVIEW_ROWS - 1, 0, PREVIEW_COLS - 1)[:PREVIEW_CELLS]
        if not found:
            return ""
        return f"{sheet.id}:\n" + "\n".join(describe_cell(r, c, sheet.view((r, c))) for r, c in found)

    # -- what the read requests show
    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of a read request, fenced as data."""
        if method == "cells":
            return fence(self._cells(params, result["cells"]))
        if method == "sheets":
            lines = [f"{s['id']}: {s['name']} ({_held(s['rows'], s['cols'])})" for s in result]
            return fence("\n".join(lines) or "There are no sheets.")
        return fence(json.dumps(result, separators=(",", ":"), ensure_ascii=False))

    @staticmethod
    def _cells(params: dict, cells: list) -> str:
        where = window(params["row0"], params["row1"], params["col0"], params["col1"])
        if not cells:
            return f"Nothing in {where} of {params['sheet']}."
        lines = [describe_cell(r, c, content) for r, c, content in cells[:MAX_SHOWN_CELLS]]
        if len(cells) > MAX_SHOWN_CELLS:
            lines.append(f"... {len(cells) - MAX_SHOWN_CELLS} more cells in this window; ask for a smaller one.")
        return f"{params['sheet']} {where}:\n" + "\n".join(lines)

    # -- what a change did
    def recorder(self, document: Document) -> WorkbookRecorder:
        """Hold round one write request."""
        return WorkbookRecorder(document)


class WorkbookRecorder:
    """Listens to the document's events while one request runs: the cells that changed (the typed ones first, then the
    ones recalculated because of them), structural edits and sheet changes."""

    def __init__(self, document: Document):
        self._document = document
        self._cells: dict[tuple[str, int, int], dict | None] = {}
        self._notes: list[str] = []
        self._stop: Callable[[], None] | None = None

    def __enter__(self) -> WorkbookRecorder:
        self._stop = self._document.subscribe(self._hear)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stop is not None:
            self._stop()
            self._stop = None

    def _hear(self, event: object) -> None:
        if isinstance(event, CellsChanged):
            for row, col, content in event.cells:
                self._cells[(event.sheet, row, col)] = content
        elif isinstance(event, StructureChanged):
            self._notes.append(self._structure(event.edit))
        elif isinstance(event, SheetsChanged):
            self._notes.append("The sheets changed.")

    @staticmethod
    def _structure(edit: StructuralEdit) -> str:
        where = column_name(edit.at) if edit.axis == "col" else str(edit.at + 1)
        what = "inserted" if edit.insert else "deleted"
        return (
            f"{edit.count} {edit.axis}{'s' if edit.count != 1 else ''} {what} at {edit.axis} {where} of {edit.sheet}."
        )

    def report(self) -> str:
        """What changed, one cell a line, then which ones show an error; fenced as data."""
        lines = list(self._notes)
        sheets = {sheet for sheet, _, _ in self._cells}
        prefix = len(sheets) > 1
        listed = list(self._cells.items())
        for (sheet, row, col), content in listed[:MAX_REPORTED_CELLS]:
            lines.append((f"{sheet}!" if prefix else "") + describe_cell(row, col, content))
        if len(listed) > MAX_REPORTED_CELLS:
            lines.append(f"... and {len(listed) - MAX_REPORTED_CELLS} more cells changed.")
        if not listed and not self._notes:
            lines.append("No cell changed.")
        errors = [
            (f"{sheet}!" if prefix else "") + address(row, col)
            for (sheet, row, col), content in listed
            if content is not None and content.get("t") == "error"
        ]
        lines.append(f"Cells that now show an error: {', '.join(errors)}." if errors else "No cell shows an error.")
        return fence("\n".join(lines))


__all__ = ["WorkbookLens", "WorkbookRecorder", "address", "describe_cell", "window"]
