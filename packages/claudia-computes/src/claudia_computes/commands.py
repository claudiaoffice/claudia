"""Commands of the computes model: sheets, cell contents, structural edits, row and column sizes, chart tabs.

Everything about floating objects — images, shapes, text boxes, diagrams: define, forget, add, remove, move,
resize, rotate, retext, snap — is shared with composes and creates and lives in :mod:`claudia_core.objects`
(E10.16). ``AddChart``/``RemoveChart`` below are computes' own: a chart *tab* is a concept this app alone has
(creates has slides, composes has none of this), so it stays here even though the diagram *definition* it shows
(a :class:`~claudia_computes.ChartSpec`) is managed by the shared ``DefineDiagram``/``UpdateDiagram``/
``ForgetDiagram`` (E6.6).

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the
kernel without any computes-specific code in it. ``shifted_by`` is what lets one author undo an old step after
colleagues have inserted or deleted rows, or have written to the same cells, in between (E1.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import SLOTS, AddObject, Batch, Command, Context, ForgetDiagram, fits

from .cellstyles import CELL_SLOTS, LAYERS, Area, Piece, check_area, layer_of
from .events import CellsChanged, CellStylesChanged, ChartsChanged, LinesResized, SheetsChanged, StructureChanged
from .formula import parse_formula
from .formula.rewrite import adjusted
from .model import (
    MAX_COL_WIDTH,
    MAX_COLS,
    MAX_ROW_HEIGHT,
    MAX_ROWS,
    MIN_COL_WIDTH,
    MIN_ROW_HEIGHT,
    Chart,
    Content,
    Sheet,
    WorkbookModel,
)
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

register = WorkbookModel.registry.register

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
    kind: ClassVar[str] = "computes.AddSheet"
    id: SheetId
    name: str
    index: int | None = None  # where in the tab order; None: at the end

    @property
    def label(self) -> str:
        return "Add sheet"

    @property
    def summary(self) -> str:
        return f"add sheet {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        if self.id in model.sheets:
            raise ValueError(f"sheet id {self.id!r} exists")
        if any(s.name.casefold() == self.name.casefold() for s in model.sheets.values()):
            raise ValueError(f"a sheet called {self.name!r} exists")
        model.add_sheet(Sheet(self.id, self.name), self.index)
        ctx.emit(SheetsChanged())
        return RemoveSheet(self.id)

    def to_data(self) -> dict:
        return {"id": self.id, "name": self.name, "index": self.index}

    @classmethod
    def from_data(cls, data, registry) -> AddSheet:
        return cls(SheetId(data["id"]), data["name"], data.get("index"))

    def stub(self) -> dict:
        return {"sheet": self.id}

    def redacted(self) -> Command:
        return AddSheet(self.id, self.id, self.index)  # still there for later commands, with a neutral name


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
            raise ValueError(f"sheet {sheet.name!r} still has chart {blocking[0]!r}'s data on it")
        index = list(model.sheets).index(self.id)
        cells = tuple((r, c, content) for (r, c), content in sorted(sheet.cells.items()))
        row_heights = tuple(sorted(sheet.row_heights.items()))
        col_widths = tuple(sorted(sheet.col_widths.items()))
        objects = tuple(model.objects_on(self.id))  # bottom first; a removed sheet takes its objects with it
        for obj in objects:
            model.delete_object(obj.id)
        model.close_container(str(self.id))
        restores = model.drop_sheet(self.id)  # formulas elsewhere that pointed here, as they were
        ctx.emit(SheetsChanged())
        undo: list[Command] = [AddSheet(sheet.id, sheet.name, index)]
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
        final = {(r, c): model.store(sheet, r, c, content) for r, c, content in self.cells}  # later duplicates win
        # Formulas are told by ``settle``, with the value they give; the event here carries what needs no calculating.
        shown = tuple((r, c, v) for (r, c), v in final.items() if v is None or v["t"] != "formula")
        ctx.emit(CellsChanged(self.sheet, frozenset(final), shown))
        return SetCells(self.sheet, tuple(reversed(previous)))  # reversed: later duplicates restore first

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
        destroyed, restores, destroyed_sizes, cut_styles = ctx.model.restructure(edit)
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
                raise ValueError(
                    f"“{style.name}” is a {style.kind} style and cannot be put into the {self.slot} of a cell"
                )
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
                raise ValueError(f"a {self.axis} size must be between {lo} and {hi}, not {size}")
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


# ------------------------------------------------------------------------------ chart tabs
@register
@dataclass(frozen=True)
class AddChart(Command):
    """Add a chart tab (E6.6): a name in the tab strip, showing the diagram definition ``spec_id`` names.

    That definition must already be in the document — put there by :class:`~claudia_core.DefineDiagram` — and
    stays shared: a floating diagram object elsewhere may show the very same ``spec_id`` (``Chart``'s own
    docstring says why that mirrors an image asset). A tab is computes' own concept, so this command lives
    here rather than in :mod:`claudia_core.objects`, even though the definition it shows does not."""

    kind: ClassVar[str] = "computes.AddChart"
    id: str
    name: str
    spec_id: str
    index: int | None = None  # where in the tab order; None: at the end

    @property
    def label(self) -> str:
        return "Add chart"

    @property
    def summary(self) -> str:
        return f"add chart {self.name}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        if self.id in model.charts:
            raise ValueError(f"chart id {self.id!r} exists")
        if any(c.name.casefold() == self.name.casefold() for c in model.charts.values()):
            raise ValueError(f"a chart called {self.name!r} exists")
        if self.spec_id not in model.diagrams:
            raise ValueError(f"this document does not know the diagram {self.spec_id!r}")
        model.add_chart(Chart(self.id, self.name, self.spec_id), self.index)
        ctx.emit(ChartsChanged())
        return RemoveChart(self.id)

    def to_data(self) -> dict:
        return {"id": self.id, "name": self.name, "spec_id": self.spec_id, "index": self.index}

    @classmethod
    def from_data(cls, data, registry) -> AddChart:
        return cls(data["id"], data["name"], data["spec_id"], data.get("index"))

    def shifted_by(self, other: Command) -> Command | None:
        """Refused once the diagram it would show is gone (the same guard ``AddObject`` keeps for its shape,
        image or diagram, applied here to a tab instead of a floating object)."""
        return None if isinstance(other, ForgetDiagram) and other.id == self.spec_id else self

    def stub(self) -> dict:
        return {"chart": self.id}

    def redacted(self) -> Command:
        return AddChart(self.id, self.id, self.spec_id, self.index)  # still there for later commands, neutral name


@register
@dataclass(frozen=True)
class RemoveChart(Command):
    """Remove a chart tab. The diagram definition it showed is untouched — it may still be shown elsewhere, the
    same way removing an object never forgets the image or shape it used (:class:`~claudia_core.ForgetDiagram`
    is the separate, explicit step for letting the definition itself go)."""

    kind: ClassVar[str] = "computes.RemoveChart"
    id: str

    @property
    def label(self) -> str:
        return "Remove chart"

    @property
    def summary(self) -> str:
        return "remove a chart"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        model = ctx.model
        chart = model.chart(self.id)
        index = list(model.charts).index(self.id)
        model.remove_chart(self.id)
        ctx.emit(ChartsChanged())
        return AddChart(chart.id, chart.name, chart.spec_id, index)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveChart:
        return cls(data["id"])

    def redacted(self) -> Command:
        return self
