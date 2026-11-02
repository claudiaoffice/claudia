"""The computes document model: sheets of typed cells. This is the mini-port that proves claudia-core (E1.1).

What is here: sheets, cells holding typed constants, structural edits (insert/delete rows and columns) and
the references machinery of the demo. What is not, yet: formulas, recalculation, names, SQL, layout, objects.
They arrive with E6.1 as more commands and a real ``settle``; the kernel does not change for them.
"""

from __future__ import annotations

from typing import ClassVar, Self

from claudia_core import CommandRegistry, DocumentModel, Region, new_registry

from .refs import Position, SheetId

MAX_ROWS = 1_048_576  # row 1048576, like Excel
MAX_COLS = 16_384  # column XFD

Content = dict | None  # None (empty) or {"t": "int"|"float"|"text"|"bool", "v": ...}


def content_of(value) -> Content:
    """Typed constant for a Python value (``None`` is an empty cell)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, float):
        return {"t": "float", "v": value}
    return {"t": "text", "v": str(value)}


class Sheet:
    def __init__(self, sheet_id: SheetId, name: str):
        self.id = sheet_id
        self.name = name
        self.cells: dict[Position, dict] = {}  # sparse: only cells that hold something

    def to_data(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cells": [[r, c, content] for (r, c), content in sorted(self.cells.items())],
        }


class WorkbookModel(DocumentModel):
    app: ClassVar[str] = "computes"
    state_schema: ClassVar[int] = 1
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.sheets: dict[SheetId, Sheet] = {}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"sheets": [sheet.to_data() for sheet in self.sheets.values()]}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        for item in state["sheets"]:
            sheet = Sheet(SheetId(item["id"]), item["name"])
            sheet.cells = {(r, c): content for r, c, content in item["cells"]}
            model.sheets[sheet.id] = sheet
        return model

    # -- reading ---------------------------------------------------------------
    def sheet(self, sheet_id: SheetId) -> Sheet:
        try:
            return self.sheets[sheet_id]
        except KeyError:
            raise ValueError(f"unknown sheet {sheet_id!r}") from None

    def get(self, sheet_id: SheetId, row: int, col: int) -> Content:
        return self.sheet(sheet_id).cells.get((row, col))

    def region_from_data(self, data: dict) -> Region:
        from .region import CellRegion

        return CellRegion.from_data(data)
