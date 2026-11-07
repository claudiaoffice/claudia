"""Commands of the mini computes model: sheets, cell contents, structural edits.

Every command carries final values and returns its exact inverse, so undo, replay and checkpoints work on the
kernel without any computes-specific code in it. ``shifted_by`` is what lets one author undo an old step after
colleagues have inserted or deleted rows, or have written to the same cells, in between (E1.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

from claudia_core import Batch, Command, Context, ImageAsset

from .events import CellsChanged, ImagesChanged, LinesResized, SheetsChanged, StructureChanged
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
    SheetObject,
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
from .region import CellRegion, ObjectSet

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
        index = list(model.sheets).index(self.id)
        cells = tuple((r, c, content) for (r, c), content in sorted(sheet.cells.items()))
        row_heights = tuple(sorted(sheet.row_heights.items()))
        col_widths = tuple(sorted(sheet.col_widths.items()))
        objects = tuple(model.objects_on(self.id))  # bottom first; a removed sheet takes its objects with it
        for obj in objects:
            model.delete_object(obj.id)
        del model._stack[self.id]  # noqa: SLF001 (the stack is WorkbookModel's own; this command is its one clearer)
        restores = model.drop_sheet(self.id)  # formulas elsewhere that pointed here, as they were
        ctx.emit(SheetsChanged())
        undo: list[Command] = [AddSheet(sheet.id, sheet.name, index)]
        if cells:
            undo.append(SetCells(sheet.id, cells))
        if row_heights:
            undo.append(ResizeLines(sheet.id, "row", row_heights))
        if col_widths:
            undo.append(ResizeLines(sheet.id, "col", col_widths))
        undo.extend(AddObject(obj, place) for place, obj in enumerate(objects))
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
        destroyed, restores, destroyed_sizes = ctx.model.restructure(edit)
        ctx.emit(StructureChanged(edit))
        undo = Structure(_OPPOSITE[type(edit)](edit.sheet, edit.at, edit.count))
        # Deleted cells come back, and so do the formulas that pointed at them, as they were typed.
        restores[edit.sheet] = [*restores.get(edit.sheet, []), *destroyed]
        sets: list[Command] = [
            SetCells(sheet, tuple(sorted(items, key=lambda t: t[:2]))) for sheet, items in restores.items() if items
        ]
        if destroyed_sizes:  # the deleted lines' own sizes, which a reference can't bring back
            sets.append(ResizeLines(edit.sheet, edit.axis, destroyed_sizes))
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


# ------------------------------------------------------------------------------ images
@register
@dataclass(frozen=True)
class DefineImage(Command):
    """Take a decoded image into the document, so that it opens the same anywhere (mirrors creates' own)."""

    kind: ClassVar[str] = "computes.DefineImage"
    image: ImageAsset

    @property
    def label(self) -> str:
        return "Define image"

    @property
    def summary(self) -> str:
        return f"the document takes an image ({self.image.width} × {self.image.height})"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        ctx.model.define_image(self.image)
        ctx.emit(ImagesChanged(self.image.id, self.image))
        return ForgetImage(self.image.id)

    def to_data(self) -> dict:
        return {"image": self.image.to_data()}

    @classmethod
    def from_data(cls, data, registry) -> DefineImage:
        return cls(ImageAsset.from_data(data["image"]))

    def shifted_by(self, other: Command) -> Command | None:
        return None if isinstance(other, DefineImage) and other.image.id == self.image.id else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class ForgetImage(Command):
    """Let go of an image that no object uses (the undo of :class:`DefineImage`)."""

    kind: ClassVar[str] = "computes.ForgetImage"
    id: str

    @property
    def label(self) -> str:
        return "Forget image"

    @property
    def summary(self) -> str:
        return f"the document lets go of the image {self.id}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        image = ctx.model.forget_image(self.id)
        ctx.emit(ImagesChanged(self.id, None))
        return DefineImage(image)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> ForgetImage:
        return cls(data["id"])

    def shifted_by(self, other: Command) -> Command | None:
        """Refuse when a colleague now uses the image, or defined it anew."""
        if isinstance(other, AddObject) and other.obj.image == self.id:
            return None
        return None if isinstance(other, DefineImage) and other.image.id == self.id else self

    def redacted(self) -> Command:
        return self


# ------------------------------------------------------------------------------ objects
@register
@dataclass(frozen=True)
class AddObject(Command):
    """Put an image on a sheet, anchored to a cell: on top of the others, or at stacking place ``at``.

    The object's anchor (``row``/``col``) and its pixel size (``w``/``h``) never change because of a structural
    edit (a row/column insert, delete, or resize) — see the module docstring. Only :class:`MoveObject` (the
    person dragging it to another cell) changes where it sits, and nothing changes its size."""

    kind: ClassVar[str] = "computes.AddObject"
    obj: SheetObject
    at: int | None = None

    @property
    def label(self) -> str:
        return "Add image"

    @property
    def summary(self) -> str:
        alt = self.obj.imported.alt if self.obj.imported else ""
        return f"added an image: {_quote(alt)}" if alt.strip() else "added an image"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        ctx.model.insert_object(self.obj, self.at)
        ctx.emit(ctx.model.changed(self.obj.sheet, changed=(self.obj,)))
        return RemoveObject(self.obj.id)

    def to_data(self) -> dict:
        return {"object": self.obj.to_data(), "at": self.at}

    @classmethod
    def from_data(cls, data, registry) -> AddObject:
        return cls(SheetObject.from_data(data["object"]), data.get("at"))

    def regions(self, model: WorkbookModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return (ObjectSet(self.obj.sheet, frozenset({self.obj.id})),)

    def shifted_by(self, other: Command) -> Command | None:
        """Bringing an object back is refused when somebody made another one with its id, took its image away, or
        removed the sheet it anchors to."""
        if isinstance(other, AddObject) and other.obj.id == self.obj.id:
            return None
        if isinstance(other, RemoveSheet) and other.id == self.obj.sheet:
            return None
        return None if isinstance(other, ForgetImage) and other.id == self.obj.image else self

    def redacted(self) -> Command:
        return self  # an image object carries no text of its own to redact (unlike creates' text boxes)


@register
@dataclass(frozen=True)
class RemoveObject(Command):
    """Take an object off its sheet."""

    kind: ClassVar[str] = "computes.RemoveObject"
    id: str

    @property
    def label(self) -> str:
        return "Remove object"

    @property
    def summary(self) -> str:
        return "removed an image"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        obj, place = ctx.model.delete_object(self.id)
        ctx.emit(ctx.model.changed(obj.sheet, removed=(obj.id,)))
        return AddObject(obj, place)

    def to_data(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_data(cls, data, registry) -> RemoveObject:
        return cls(data["id"])

    def regions(self, model: WorkbookModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _object_selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        """Never destroy what a colleague has done to the object since (this is the undo of adding it)."""
        return None if _touches_object(other, self.id) else self

    def redacted(self) -> Command:
        return self


@register
@dataclass(frozen=True)
class MoveObject(Command):
    """Put an object at a new anchor cell; its pixel size stays. The only way an object's position ever changes —
    see the module docstring for why a structural edit never does."""

    kind: ClassVar[str] = "computes.MoveObject"
    id: str
    row: int
    col: int

    @property
    def label(self) -> str:
        return "Move object"

    @property
    def summary(self) -> str:
        return f"moved an image to {column_name(self.col)}{self.row + 1}"

    def apply(self, ctx: Context[WorkbookModel]) -> Command:
        old = ctx.model.get_object(self.id)
        new = replace(old, row=self.row, col=self.col)
        ctx.model.replace_object(new)
        ctx.emit(ctx.model.changed(new.sheet, changed=(new,)))
        return MoveObject(self.id, old.row, old.col)

    def to_data(self) -> dict:
        return {"id": self.id, "row": self.row, "col": self.col}

    @classmethod
    def from_data(cls, data, registry) -> MoveObject:
        return cls(data["id"], data["row"], data["col"])

    def regions(self, model: WorkbookModel) -> tuple[ObjectSet, ...]:  # type: ignore[override]
        return _object_selection(model, self.id)

    def shifted_by(self, other: Command) -> Command | None:
        return None if _changes_object_frame(other, self.id) else self

    def redacted(self) -> Command:
        return self


def _object_selection(model: WorkbookModel, object_id: str) -> tuple[ObjectSet, ...]:
    obj = model.objects.get(object_id)
    return () if obj is None else (ObjectSet(obj.sheet, frozenset({object_id})),)


def _object_target(command: Command) -> str | None:
    """The id of the object a command is about, if it is about one."""
    if isinstance(command, AddObject):
        return command.obj.id
    if isinstance(command, MoveObject | RemoveObject):
        return command.id
    return None


def _touches_object(other: Command, object_id: str) -> bool:
    return _object_target(other) == object_id


def _changes_object_frame(other: Command, object_id: str) -> bool:
    """Did ``other`` place, remove or re-create the object? (There is no resize of an object yet.)"""
    return isinstance(other, MoveObject | RemoveObject | AddObject) and _object_target(other) == object_id
