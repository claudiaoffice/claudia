"""Commands of the computes model: sheets, slides, cell contents, structural edits, row and column sizes.

Everything about floating objects — images, shapes, text boxes, diagrams: define, forget, add, remove, move,
resize, rotate, retext, snap — is shared with composes and creates and lives in :mod:`claudia_core.objects`
(E10.16); a chart's definition (a :class:`~claudia_computes.ChartSpec`) is managed by the shared
``DefineAsset``/``UpdateAsset``/``ForgetAsset`` (E6.6, D1431), and what a step with a chart takes along is decided in
:mod:`claudia_computes.chart_steps` (E6.31).

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the
kernel without any computes-specific code in it. ``shifted_by`` is what lets one author undo an old step after
colleagues have inserted or deleted rows, or have written to the same cells, in between (E1.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import N_, SLOTS, AddObject, Batch, Command, Context, PageSetup, Refusal, fits
from claudia_core.slides import Slide

from .cellstyles import CELL_SLOTS, LAYERS, Area, Piece, check_area, layer_of
from .events import (
    CellsChanged,
    CellStylesChanged,
    LinesResized,
    NamesChanged,
    PrintSetupChanged,
    RandomChanged,
    StructureChanged,
    TabsChanged,
)
from .formula import parse_formula
from .formula.rewrite import adjusted
from .model import (
    MAX_COL_WIDTH,
    MAX_COLS,
    MAX_ROW_HEIGHT,
    MAX_ROWS,
    MIN_COL_WIDTH,
    MIN_ROW_HEIGHT,
    Content,
    Sheet,
    WorkbookModel,
    content_of,
    value_of,
)
from .printing import DEFAULT_SHEET_PRINT, SheetPrintSetup
from .refs import (
    DeleteCols,
    DeleteRows,
    InsertCols,
    InsertRows,
    SheetId,
    StructuralEdit,
    column_name,
)
from .region import CellRegion
from .values import ErrorValue, Value

register = WorkbookModel.registry.register


@WorkbookModel.registry.upcaster("computes.AddSheet", 1)
@WorkbookModel.registry.upcaster("computes.AddSheet", 2)
def _names_not_yet_shared(data: dict) -> dict:
    """Schema 1 wrote sheets before names were one namespace, schema 2 before named ranges joined it
    (D552): replay them under the old rule."""
    return {**data, "legacy_names": True}


MAX_LISTED = 3  # cells a history sentence names one by one
MAX_LISTED_TEXT = 70  # characters of such a sentence; longer ones name the area instead
MAX_LISTED_ALT = 40  # characters of an image's alt text that a history sentence quotes


def _quote(text: str) -> str:
    """A short, one-line piece of an image's alt text for a sentence in the history."""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= MAX_LISTED_ALT else flat[: MAX_LISTED_ALT - 1] + "…"


def _show(content: dict) -> str:
    """A cell's content as one short piece of text (for sentences in the history)."""
    value = content["v"]
    text = ("TRUE" if value else "FALSE") if content["t"] == "bool" else str(value)  # (a formula: its text)
    return text if len(text) <= 30 else text[:29] + "…"


def _one(row: int, col: int, content: dict | None) -> str:
    """``B3 = 40`` or ``B3 cleared``."""
    where = f"{column_name(col)}{row + 1}"
    return f"{where} cleared" if content is None else f"{where} = {_show(content)}"


def _line(axis: str, index: int, size: float | None) -> str:
    """``row 4 = 40px`` or ``column C reset`` (back to the sheet's default)."""
    where = f"row {index + 1}" if axis == "row" else f"column {column_name(index)}"
    return f"{where} reset" if size is None else f"{where} = {size:g}px"


def _followed(content: Content, edit: StructuralEdit, home: SheetId) -> Content:
    """A formula that is put back after ``edit`` happened: what it points at has moved, so it follows.

    Only formulas without sheet names are followed: a command knows the ids of sheets, not their names, and a formula
    names them. Those keep their text (what they point at on other sheets is, as a rule, where it was)."""
    if content is None or content["t"] != "formula" or "!" in content["v"]:
        return content
    formula = parse_formula(content["v"])
    followed = adjusted(formula, edit, home)
    return content if followed is formula else {"t": "formula", "v": followed.source}


def _check_position(row: int, col: int) -> None:
    if not (0 <= row < MAX_ROWS and 0 <= col < MAX_COLS):
        raise IndexError(f"cell ({row}, {col}) is outside the sheet")


# ------------------------------------------------------------------------------ sheets
@register
@dataclass(frozen=True)
class AddSheet(Command):
    """Add a sheet. Its name must be free in the whole document, not only among the sheets (D550). ``legacy_names`` is
    set for what a log wrote before names were shared: it keeps the old rule (no second sheet of that name), so an old
    document replays, even one that has a sheet and a chart tab of one name."""

    kind: ClassVar[str] = "computes.AddSheet"
    schema: ClassVar[int] = 3  # 2: names are shared with chart tabs and objects (D550); 3: and named ranges (D552)
    id: SheetId
    name: str
    index: int | None = None  # where in the tab order; None: at the end
    legacy_names: bool = False

    @property
    def label(self) -> str:
        return "Add sheet"

    @property
    def summary(self) -> str:
        return f"add sheet {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        model.check_new_tab(self.id, self.index)
        if any(s.name.casefold() == self.name.casefold() for s in model.sheets.values()):
            raise Refusal("There is already a sheet called “{name}”", name=self.name)
        if not self.legacy_names:
            model.check_name_free(self.id, self.name)
        model.add_sheet(Sheet(self.id, self.name), self.index)
        ctx.emit(TabsChanged())
        return RemoveSheet(self.id)

    def to_data(self) -> dict:
        data = {"id": self.id, "name": self.name, "index": self.index}
        if self.legacy_names:
            data["legacy_names"] = True
        return data

    @classmethod
    def from_data(cls, data, registry) -> AddSheet:
        return cls(SheetId(data["id"]), data["name"], data.get("index"), data.get("legacy_names", False))

    def stub(self) -> dict:
        return {"sheet": self.id}

    def redacted(self) -> Command:
        # still there for later commands, with a neutral name
        return AddSheet(self.id, self.id, self.index, legacy_names=True)


@register
@dataclass(frozen=True)
class RemoveSheet(Command):
    kind: ClassVar[str] = "computes.RemoveSheet"
    id: SheetId

    @property
    def label(self) -> str:
        return "Remove sheet"

    @property
    def summary(self) -> str:
        return "remove a sheet"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        sheet = model.sheet(self.id)
        blocking = model.charts_reading(self.id)
        if blocking:
            # A diagram's range is frozen at the cells it names (E6.6, same policy as an object's anchor) — it
            # does not follow the sheet elsewhere the way a formula reference would, so removing the sheet
            # would leave it pointing nowhere. Refusing is the same answer ``forget_shape``/``forget_image``
            # give while something still uses them.
            raise Refusal(
                "the sheet “{name}” still has the data of the chart “{chart}” on it", name=sheet.name, chart=blocking[0]
            )
        index = model.tab_index(self.id)
        cells = tuple((r, c, content) for (r, c), content in sorted(sheet.cells.items()))
        row_heights = tuple(sorted(sheet.row_heights.items()))
        col_widths = tuple(sorted(sheet.col_widths.items()))
        objects = tuple(model.objects_on(self.id))  # bottom first; a removed sheet takes its objects with it
        for obj in objects:
            model.delete_object(obj.id)
        model.close_holder(str(self.id))
        restores, name_restores = model.drop_sheet(
            self.id
        )  # formulas elsewhere that pointed here, and names, as they were
        ctx.emit(TabsChanged())
        if name_restores:
            ctx.emit(NamesChanged())
        # a name that clashed even then (an old document) is put back as it was; any other is checked again
        undo: list[Command] = [
            AddSheet(sheet.id, sheet.name, index, legacy_names=model.name_holder(sheet.id, sheet.name) is not None)
        ]
        if cells:
            undo.append(SetCells(sheet.id, cells))
        if row_heights:
            undo.append(ResizeLines(sheet.id, "row", row_heights))
        if col_widths:
            undo.append(ResizeLines(sheet.id, "col", col_widths))
        undo.extend(
            SetCellStyle(sheet.id, slot, layer, (r0, c0, r1, c1), (((r0, c0, r1, c1), style),))
            for slot, layer, r0, c0, r1, c1, style in sheet.cell_styles.to_data()
        )
        undo.extend(AddObject(obj.body, obj.anchor.to_data(), place) for place, obj in enumerate(objects))
        undo.extend(SetCells(other, tuple(sorted(items))) for other, items in restores.items())
        if name_restores:  # (after the sheet is back: a name needs its sheet)
            from .name_commands import RestoreNames

            undo.append(RestoreNames(tuple(reversed(name_restores))))
        return undo[0] if len(undo) == 1 else Batch(tuple(undo))

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveSheet:
        return cls(SheetId(data["id"]))

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ cells


@register
@dataclass(frozen=True)
class AddSlide(Command):
    """Add a slide to the tabs (E6.31, D1471): a page of objects in the core's 16:9 frame, at ``index`` in the tab
    order (``None``: at the end). Its name must be free in the whole document, as a sheet's is (D550); what is written
    about it comes back with it when the removal of a slide is undone. Creates' slides are its own command: they carry
    speaker notes and planned times, a workbook's carry their place among the sheets (D1470)."""

    kind: ClassVar[str] = "computes.AddSlide"
    id: str
    name: str
    index: int | None = None
    description: str = ""

    @property
    def label(self) -> str:
        return "Add slide"

    @property
    def summary(self) -> str:
        return f"add slide {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        model.slides.check_new(self.id)
        if not self.name:
            raise Refusal("a slide needs a name")
        model.check_thing_name(self.id, self.name)
        model.add_slide(Slide(self.id, self.name, self.description), self.index)
        ctx.emit(TabsChanged())
        return RemoveSlide(self.id, if_empty=True)

    def to_data(self) -> dict:
        data: dict = {"id": self.id, "name": self.name, "index": self.index}
        if self.description:
            data["description"] = self.description
        return data

    @classmethod
    def from_data(cls, data, registry) -> AddSlide:
        return cls(data["id"], data["name"], data.get("index"), data.get("description", ""))

    def stub(self) -> dict:
        return {"slide": self.id}

    def redacted(self) -> Command:
        # still there for the objects on it, with a neutral name and nothing written about it
        return AddSlide(self.id, self.id, self.index)


@register
@dataclass(frozen=True)
class RemoveSlide(Command):
    """Remove a slide that has no objects (the core's rule for every holder); undo puts it back in its place, with
    its name and what was written about it. With ``if_empty`` a slide that has objects stays and nothing happens: the
    undo of a slide made for a chart takes the slide away only while it is empty, since a slide goes with its last
    object (E6.31, Q4 and Q20 of the review of 2026-11-22)."""

    kind: ClassVar[str] = "computes.RemoveSlide"
    id: str
    if_empty: bool = False

    @property
    def label(self) -> str:
        return "Remove slide"

    @property
    def summary(self) -> str:
        return "remove a slide"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        if self.if_empty and ctx.model.stack_of(self.id):
            return Batch(())  # it stays, and so there is nothing to put back
        slide, index = ctx.model.remove_slide(self.id)
        ctx.emit(TabsChanged())
        return AddSlide(slide.id, slide.name, index, slide.description)

    def to_data(self) -> dict:
        return {"id": self.id, "if_empty": True} if self.if_empty else {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveSlide:
        return cls(data["id"], bool(data.get("if_empty", False)))

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class SetCells(Command):
    """Set (or clear, with ``None``) cells of one sheet."""

    kind: ClassVar[str] = "computes.SetCells"
    sheet: SheetId
    cells: tuple[tuple[int, int, Content], ...]

    @property
    def label(self) -> str:
        return "Edit cell" if len(self.cells) == 1 else "Edit cells"

    @property
    def summary(self) -> str:
        if not self.cells:
            return "no cells"
        (r0, c0, first) = self.cells[0]
        if len(self.cells) == 1:
            return _one(r0, c0, first)
        if len(self.cells) <= MAX_LISTED and not all(content is None for _, _, content in self.cells):
            listed = ", ".join(_one(r, c, content) for r, c, content in self.cells)
            if len(listed) <= MAX_LISTED_TEXT:
                return listed
        rows, cols = [r for r, _, _ in self.cells], [c for _, c, _ in self.cells]
        area = f"{column_name(min(cols))}{min(rows) + 1}:{column_name(max(cols))}{max(rows) + 1}"
        if all(content is None for _, _, content in self.cells):
            return f"cleared {len(self.cells)} cells in {area}"
        return f"{len(self.cells)} cells in {area}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        sheet = ctx.model.sheet(self.sheet)
        for row, col, _ in self.cells:
            _check_position(row, col)
        previous = tuple((r, c, sheet.cells.get((r, c))) for r, c, _ in self.cells)
        model = ctx.model
        model.check_writable(sheet, [(r, c) for r, c, _ in self.cells])
        final = {(r, c): model.store(sheet, r, c, content) for r, c, content in self.cells}  # later duplicates win
        model.header_edited(self.sheet, list(final))  # (formulas that name a table's columns read the new headers)
        grown = model.grow_names(self.sheet, [position for position, v in final.items() if v is not None])
        # Formulas are told by ``settle``, with the value they give; the event here carries what needs no calculating.
        shown = tuple((r, c, v) for (r, c), v in final.items() if v is None or v["t"] != "formula")
        ctx.emit(CellsChanged(self.sheet, frozenset(final), shown))
        undo = SetCells(self.sheet, tuple(reversed(previous)))  # reversed: later duplicates restore first
        if not grown:
            return undo
        from .name_commands import RestoreNames  # (a table that took in the new rows lets them go again)

        ctx.emit(NamesChanged())
        return Batch((undo, RestoreNames(tuple(grown))))

    def to_data(self) -> dict:
        return {"sheet": self.sheet, "cells": [[r, c, content] for r, c, content in self.cells]}

    @classmethod
    def from_data(cls, data, registry) -> SetCells:
        return cls(SheetId(data["sheet"]), tuple((r, c, content) for r, c, content in data["cells"]))

    def regions(self, model) -> tuple[CellRegion, ...]:
        if not self.cells:
            return ()
        rows = [r for r, _, _ in self.cells]
        cols = [c for _, c, _ in self.cells]
        return (CellRegion.of(self.sheet, min(rows), min(cols), max(rows), max(cols)),)

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, Structure) and other.edit.sheet == self.sheet:
            moved = []
            for row, col, content in self.cells:
                target = other.edit.map_index(row if other.edit.axis == "row" else col)
                if target is not None:  # cells whose line was deleted no longer exist: nothing to restore
                    followed = _followed(content, other.edit, self.sheet)
                    moved.append((target, col, followed) if other.edit.axis == "row" else (row, target, followed))
            return SetCells(self.sheet, tuple(moved)) if moved else None
        if isinstance(other, SetCells) and other.sheet == self.sheet:
            mine = {(r, c) for r, c, _ in self.cells}
            if any((r, c) in mine for r, c, _ in other.cells):
                return None  # a colleague wrote these cells after us: undoing would overwrite their work
        if isinstance(other, RemoveSheet) and other.id == self.sheet:
            return None
        return self

    def stub(self) -> dict:
        return {"sheet": self.sheet, "positions": [[r, c] for r, c, _ in self.cells]}

    def redacted(self) -> Command:
        return SetCells(self.sheet, tuple((r, c, None) for r, c, _ in self.cells))  # same cells, emptied


# ------------------------------------------------------------------------------ heavy calls
@register
@dataclass(frozen=True)
class ApplyCalculated(Command):
    """A worker's result for one heavy formula call (``UserFunction.heavy``), landing on the cell that deferred
    it exactly like any other change -- recalculated readers, an event, a log entry -- except undo: this is the
    server's own continuation of a formula the person already typed, not a new edit of theirs, so nobody undoes
    it (PERF review 2026-11-08, D37, D1314).

    Applying is a no-op if the cell is not (or is no longer) waiting for this call -- edited away, its sheet
    removed, or already answered -- so a result computed from a stale snapshot can never land (``Calculator
    .resolve_heavy``); the dispatcher deciding whether the snapshot is still fresh enough to try is
    ``claudia-server``'s job, not this command's."""

    kind: ClassVar[str] = "computes.ApplyCalculated"
    undoable = False
    sheet: SheetId
    row: int
    col: int
    value: Value

    @property
    def label(self) -> str:
        return "Calculated"

    @property
    def summary(self) -> str:
        return _one(self.row, self.col, content_of(self.value))

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        ctx.model.calc.resolve_heavy((self.sheet, self.row, self.col), self.value)
        return self  # nobody undoes this (undoable = False); the inverse is never asked for

    def to_data(self) -> dict:
        return {"sheet": self.sheet, "row": self.row, "col": self.col, "value": content_of(self.value)}

    @classmethod
    def from_data(cls, data, registry) -> ApplyCalculated:
        content = data["value"]
        if content is not None and content["t"] == "error":
            value: Value = ErrorValue(content["v"], content.get("d", ""))
        else:
            value = value_of(content)
        return cls(SheetId(data["sheet"]), data["row"], data["col"], value)

    def redacted(self) -> Command:
        return ApplyCalculated(self.sheet, self.row, self.col, None)


# ------------------------------------------------------------------------------ structure
_OPPOSITE = {InsertRows: DeleteRows, DeleteRows: InsertRows, InsertCols: DeleteCols, DeleteCols: InsertCols}


@register
@dataclass(frozen=True)
class Structure(Command):
    """Insert or delete rows/columns of one sheet. Cells move; deleted cells come back with the inverse."""

    kind: ClassVar[str] = "computes.Structure"
    edit: StructuralEdit

    @property
    def label(self) -> str:
        what = "row" if self.edit.axis == "row" else "column"
        return f"{'Insert' if self.edit.insert else 'Delete'} {what}{'s' if self.edit.count > 1 else ''}"

    @property
    def summary(self) -> str:
        e = self.edit
        if e.axis == "row":
            noun = f"{e.count} row{'s' if e.count > 1 else ''}"
            return (
                f"insert {noun} before row {e.at + 1}"
                if e.insert
                else (f"delete row {e.at + 1}" if e.count == 1 else f"delete rows {e.at + 1}:{e.at + e.count}")
            )
        first, last = column_name(e.at), column_name(e.at + e.count - 1)
        noun = f"{e.count} column{'s' if e.count > 1 else ''}"
        if e.insert:
            return f"insert {noun} before column {first}"
        return f"delete column {first}" if e.count == 1 else f"delete columns {first}:{last}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        edit = self.edit
        destroyed, restores, destroyed_sizes, cut_styles, name_restores = ctx.model.restructure(edit)
        ctx.emit(StructureChanged(edit))
        undo = Structure(_OPPOSITE[type(edit)](edit.sheet, edit.at, edit.count))
        # Deleted cells come back, and so do the formulas that pointed at them, as they were typed.
        restores[edit.sheet] = [*restores.get(edit.sheet, []), *destroyed]
        sets: list[Command] = [
            SetCells(sheet, tuple(sorted(items, key=lambda t: t[:2]))) for sheet, items in restores.items() if items
        ]
        if destroyed_sizes:  # the deleted lines' own sizes, which a reference can't bring back
            sets.append(ResizeLines(edit.sheet, edit.axis, destroyed_sizes))
        # The style ranges that lay on the deleted lines, put back where the lines come back (E6.13, D307).
        sets.extend(
            SetCellStyle(edit.sheet, slot, layer, area, ((area, style),)) for slot, layer, (area, style) in cut_styles
        )
        if cut_styles:
            ctx.emit(CellStylesChanged(edit.sheet, (0, 0, MAX_ROWS - 1, MAX_COLS - 1)))
        if name_restores:  # names that moved or went, as they were (last: they are about the cells put back above)
            from .name_commands import RestoreNames

            ctx.emit(NamesChanged())
            sets.append(RestoreNames(tuple(reversed(name_restores))))
        return Batch((undo, *sets)) if sets else undo

    def to_data(self) -> dict:
        e = self.edit
        return {"sheet": e.sheet, "axis": e.axis, "insert": e.insert, "at": e.at, "count": e.count}

    @classmethod
    def from_data(cls, data, registry) -> Structure:
        kinds = {
            ("row", True): InsertRows,
            ("row", False): DeleteRows,
            ("col", True): InsertCols,
            ("col", False): DeleteCols,
        }
        return cls(kinds[(data["axis"], data["insert"])](SheetId(data["sheet"]), data["at"], data["count"]))

    def regions(self, model) -> tuple[CellRegion, ...]:
        e = self.edit  # everything from the edit onwards moves (or goes)
        if e.axis == "row":
            return (CellRegion.of(e.sheet, e.at, 0, MAX_ROWS - 1, MAX_COLS - 1),)
        return (CellRegion.of(e.sheet, 0, e.at, MAX_ROWS - 1, MAX_COLS - 1),)

    def shifted_by(self, other: Command) -> Command | None:
        e = self.edit
        if isinstance(other, Structure) and other.edit.sheet == e.sheet and other.edit.axis == e.axis:
            if e.insert:  # putting lines back: a gap, it only moves
                at = other.edit.map_index(e.at)
                return self if at == e.at else Structure(replace(e, at=e.at if at is None else at))
            span = other.edit.map_span(e.at, e.at + e.count - 1)  # removing lines: they must still exist whole
            if span is None or span[1] - span[0] + 1 != e.count:
                return None
            return self if span[0] == e.at else Structure(replace(e, at=span[0]))
        if isinstance(other, SetCells) and other.sheet == e.sheet and not e.insert:
            index = 0 if e.axis == "row" else 1
            lines = range(e.at, e.at + e.count)
            if any((r, c)[index] in lines and content is not None for r, c, content in other.cells):
                return None  # a colleague typed into the lines we would delete
        if isinstance(other, RemoveSheet) and other.id == e.sheet:
            return None
        return self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ cell styles
def _area_name(area: Area) -> str:
    r0, c0, r1, c1 = area
    layer = layer_of(area)
    if layer == "sheet":
        return "the whole sheet"
    if layer == "column":
        first, last = column_name(c0), column_name(c1)
        return f"column {first}" if c0 == c1 else f"columns {first}:{last}"
    if layer == "row":
        return f"row {r0 + 1}" if r0 == r1 else f"rows {r0 + 1}:{r1 + 1}"
    start = f"{column_name(c0)}{r0 + 1}"
    return start if (r0, c0) == (r1, c1) else f"{start}:{column_name(c1)}{r1 + 1}"


@register
@dataclass(frozen=True)
class SetCellStyle(Command):
    """Make ``area`` of one slot and layer of a sheet's style ranges hold exactly ``pieces`` (E6.13, D307, D311).

    The ordinary case is one piece, the area itself, and a style: "these cells are Header" in the ``box`` or the
    ``words`` slot (:meth:`put`). No piece clears the area, so the layers below show through. The inverse is the
    same command with the pieces the area held before, which is also how a row delete's undo puts styles back.
    Every style must exist and fit the slot of a cell (D304, D316)."""

    kind: ClassVar[str] = "computes.SetCellStyle"
    sheet: SheetId
    slot: str
    layer: str
    area: Area
    pieces: tuple[Piece, ...]

    @classmethod
    def put(cls, sheet: SheetId, slot: str, area: Area, style: str | None) -> SetCellStyle:
        """Put ``style`` into the layer of ``area``'s shape only (``None``: no style of this layer there). What a
        person does is :meth:`applying`, where the last action wins."""
        return cls(sheet, slot, layer_of(area), area, () if style is None else ((area, style),))

    @classmethod
    def applying(cls, model: WorkbookModel, sheet: SheetId, slot: str, area: Area, style: str | None) -> Command:
        """What styling ``area`` in ``slot`` means to a person: every cell of it takes ``style``, whatever was there
        before — the last action wins (D317). One step, undone as one. ``None`` clears ``area`` so that what lies
        beneath shows through (“Clear cell style”)."""
        plan = model.sheet(sheet).cell_styles.plan(slot, check_area(area), style)
        steps = [cls(sheet, slot, layer, where, pieces) for layer, where, pieces in plan]
        return steps[0] if len(steps) == 1 else Batch(tuple(steps), "Cell style")

    @property
    def label(self) -> str:
        return "Cell style"

    @property
    def summary(self) -> str:
        styles = sorted({style for _, style in self.pieces})
        what = ", ".join(styles) if styles else "no style"
        return f"{_area_name(self.area)} {self.slot}: {what}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        sheet = model.sheet(self.sheet)
        area = check_area(self.area)
        if self.slot not in CELL_SLOTS:
            raise ValueError(f"a cell has no slot “{self.slot}”; it has {', '.join(CELL_SLOTS)}")
        if self.layer not in LAYERS:
            raise ValueError(f"there is no layer {self.layer!r}; there are {', '.join(LAYERS)}")
        slot = SLOTS.slot("cell", self.slot)
        for _, style_id in self.pieces:
            if style_id not in model.styles:
                raise ValueError(f"no style {style_id!r}")
            style = model.styles.get(style_id)
            if not fits(style.kind, slot):
                wrong = (
                    N_("“{name}” is a style of another kind and cannot be put into the box of a cell")
                    if self.slot == "box"
                    else N_("“{name}” is a style of another kind and cannot be put into the words of a cell")
                )
                raise Refusal(wrong, name=style.name)
        before = sheet.cell_styles.pieces(self.slot, self.layer, area)
        sheet.cell_styles.replace(self.slot, self.layer, area, self.pieces)
        ctx.emit(CellStylesChanged(self.sheet, area))
        return SetCellStyle(self.sheet, self.slot, self.layer, area, before)

    def to_data(self) -> dict:
        return {
            "sheet": self.sheet,
            "slot": self.slot,
            "layer": self.layer,
            "area": list(self.area),
            "pieces": [[*area, style] for area, style in self.pieces],
        }

    @classmethod
    def from_data(cls, data, registry) -> SetCellStyle:
        pieces = tuple(((r0, c0, r1, c1), style) for r0, c0, r1, c1, style in data["pieces"])
        return cls(SheetId(data["sheet"]), data["slot"], data["layer"], tuple(data["area"]), pieces)

    def regions(self, model) -> tuple[CellRegion, ...]:
        r0, c0, r1, c1 = self.area
        return (CellRegion.of(self.sheet, r0, c0, r1, c1),)

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, Structure) and other.edit.sheet == self.sheet:
            return None  # the cells moved under the style: undoing by position would style the wrong cells
        if isinstance(other, SetCellStyle) and (other.sheet, other.slot) == (self.sheet, self.slot):
            a, b = self.area, other.area
            if other.layer == self.layer and a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                return None  # a colleague styled some of the same cells after us
        if isinstance(other, RemoveSheet) and other.id == self.sheet:
            return None
        return self

    def redacted(self) -> Command:
        return self  # a style name is a name the document's own style book carries anyway


# ------------------------------------------------------------------------------ layout
_SIZE_LIMITS = {"row": (MIN_ROW_HEIGHT, MAX_ROW_HEIGHT), "col": (MIN_COL_WIDTH, MAX_COL_WIDTH)}


@register
@dataclass(frozen=True)
class ResizeLines(Command):
    """Set (or clear, with ``None``) the height of rows or the width of columns of one sheet. Clearing returns a
    line to the sheet's default size (D135: a size is sheet layout, not a cell style — E6.13's not-yet-built style
    system is a separate, later concern)."""

    kind: ClassVar[str] = "computes.ResizeLines"
    sheet: SheetId
    axis: str  # "row" or "col"
    sizes: tuple[tuple[int, float | None], ...]  # (index, new size; None: back to the sheet's default)

    @property
    def label(self) -> str:
        noun = "row" if self.axis == "row" else "column"
        return f"Resize {noun}" if len(self.sizes) == 1 else f"Resize {noun}s"

    @property
    def summary(self) -> str:
        if not self.sizes:
            return "no lines"
        if len(self.sizes) == 1:
            (index, size) = self.sizes[0]
            return _line(self.axis, index, size)
        if len(self.sizes) <= MAX_LISTED:
            listed = ", ".join(_line(self.axis, i, s) for i, s in self.sizes)
            if len(listed) <= MAX_LISTED_TEXT:
                return listed
        indexes = [i for i, _ in self.sizes]
        noun = "row" if self.axis == "row" else "column"
        where = (
            f"rows {min(indexes) + 1}:{max(indexes) + 1}"
            if self.axis == "row"
            else f"columns {column_name(min(indexes))}:{column_name(max(indexes))}"
        )
        return f"{len(self.sizes)} {noun}s in {where}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        sheet = ctx.model.sheet(self.sheet)
        limit = MAX_ROWS if self.axis == "row" else MAX_COLS
        lo, hi = _SIZE_LIMITS[self.axis]
        for index, size in self.sizes:
            if not 0 <= index < limit:
                raise IndexError(f"{self.axis} {index} is outside the sheet")
            if size is not None and not lo <= size <= hi:
                out = (
                    N_("a row is {lo} to {hi} high, not {size}")
                    if self.axis == "row"
                    else N_("a column is {lo} to {hi} wide, not {size}")
                )
                raise Refusal(out, lo=lo, hi=hi, size=size)
        store = sheet.sizes(self.axis)
        previous = tuple((i, store.get(i)) for i, _ in self.sizes)
        for index, size in self.sizes:
            if size is None:
                store.pop(index, None)
            else:
                store[index] = size
        ctx.emit(LinesResized(self.sheet, self.axis, self.sizes))
        return ResizeLines(self.sheet, self.axis, tuple(reversed(previous)))

    def to_data(self) -> dict:
        return {"sheet": self.sheet, "axis": self.axis, "sizes": [[i, s] for i, s in self.sizes]}

    @classmethod
    def from_data(cls, data, registry) -> ResizeLines:
        return cls(SheetId(data["sheet"]), data["axis"], tuple((i, s) for i, s in data["sizes"]))

    # No ``regions()`` override: a size is layout, not cell content, so a colleague's cell lock never blocks a
    # resize and a resize never needs to hold anything either (the default — nothing lockable — is exactly right).

    def shifted_by(self, other: Command) -> Command | None:
        if isinstance(other, Structure) and other.edit.sheet == self.sheet and other.edit.axis == self.axis:
            moved = []
            for index, size in self.sizes:
                target = other.edit.map_index(index)
                if target is not None:  # a line whose index moved: the resize still applies, at its new index
                    moved.append((target, size))
            return ResizeLines(self.sheet, self.axis, tuple(moved)) if moved else None
        if isinstance(other, ResizeLines) and other.sheet == self.sheet and other.axis == self.axis:
            mine = {i for i, _ in self.sizes}
            if any(i in mine for i, _ in other.sizes):
                return None  # a colleague resized these lines after us: undoing would overwrite their work
        if isinstance(other, RemoveSheet) and other.id == self.sheet:
            return None
        return self

    def redacted(self) -> Command:
        return self  # a size is layout, not content with anything to hide (same reasoning as Structure)


@register
@dataclass(frozen=True)
class Resample(Command):
    """Draw fresh random numbers (Tools > Resample, F9): the document's draw number goes up by ``steps``.

    Relative on purpose: two people resampling at once count both, and the inverse is the same command with the
    opposite sign, so one author can undo it after colleagues did other things (E1.4)."""

    kind: ClassVar[str] = "computes.Resample"
    steps: int = 1

    @property
    def label(self) -> str:
        return "Resample random numbers"

    @property
    def summary(self) -> str:
        return "resample the random numbers"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        if model.random_draw + self.steps < 0:
            raise Refusal("the draw number cannot go below 0")
        model.random_draw += self.steps
        model.calc.redraw()
        ctx.emit(RandomChanged(model.random_seed, model.random_draw))
        return Resample(-self.steps)

    def to_data(self) -> dict:
        return {"steps": self.steps}

    @classmethod
    def from_data(cls, data, registry) -> Resample:
        return cls(data["steps"])


@register
@dataclass(frozen=True)
class SetRandomSeed(Command):
    """Give the document's random numbers a new seed (a fixed seed makes a model reproducible)."""

    kind: ClassVar[str] = "computes.SetRandomSeed"
    seed: int

    @property
    def label(self) -> str:
        return "Set the random seed"

    @property
    def summary(self) -> str:
        return f"set the random seed to {self.seed}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        previous = model.random_seed
        model.random_seed = self.seed
        model.calc.redraw()
        ctx.emit(RandomChanged(model.random_seed, model.random_draw))
        return SetRandomSeed(previous)

    def to_data(self) -> dict:
        return {"seed": self.seed}

    @classmethod
    def from_data(cls, data, registry) -> SetRandomSeed:
        return cls(data["seed"])


# ------------------------------------------------------------------------------ printing (E6.19)
@register
@dataclass(frozen=True)
class SetPrintPage(Command):
    """Say which page the workbook is printed on (D1004): paper, orientation of the paper, margins, page numbers. One
    step for everybody; the page is the same for all sheets."""

    kind: ClassVar[str] = "computes.SetPrintPage"
    page: PageSetup

    @property
    def label(self) -> str:
        return "Page setup"

    @property
    def summary(self) -> str:
        return f"set the page to {self.page.describe()}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        old = ctx.model.print_page
        ctx.model.print_page = self.page
        ctx.emit(PrintSetupChanged(page=self.page.to_data()))
        return SetPrintPage(old)

    def to_data(self) -> dict:
        return {"page": self.page.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> SetPrintPage:
        return cls(PageSetup.from_data(data["page"]))


@register
@dataclass(frozen=True)
class SetSheetPrint(Command):
    """Say how one sheet is printed (D1004): orientation, scale, page order, repeated rows and
    columns, gridlines and the rest. The sheet stores nothing while its setup is the default, so setting it back to
    the default takes the entry away again."""

    kind: ClassVar[str] = "computes.SetSheetPrint"
    sheet: str
    setup: SheetPrintSetup

    @property
    def label(self) -> str:
        return "Print setup"

    @property
    def summary(self) -> str:
        return f"set printing of a sheet to {self.setup.describe()}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        if SheetId(self.sheet) not in model.sheets:
            raise KeyError(f"no sheet {self.sheet!r}")
        old = model.sheet_print_of(self.sheet)
        if self.setup == DEFAULT_SHEET_PRINT:
            model.sheet_print.pop(self.sheet, None)
        else:
            model.sheet_print[self.sheet] = self.setup
        ctx.emit(PrintSetupChanged(sheet=self.sheet, setup=self.setup.to_data()))
        return SetSheetPrint(self.sheet, old)

    def to_data(self) -> dict:
        return {"sheet": self.sheet, "setup": self.setup.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> SetSheetPrint:
        return cls(data["sheet"], SheetPrintSetup.from_data(data["setup"]))
