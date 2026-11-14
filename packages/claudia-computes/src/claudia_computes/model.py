"""The computes document model: sheets of cells that hold values or formulas.

A cell *holds* ``Content`` (what was typed: a constant, or a formula as text) and *shows* a value. The first is the
document: it is what commands write, what is serialized and what history keeps. The second is derived from it by
the calculator (``calc``) after every command, so it is never stored and always follows from the contents.

    sheet.cells   stored contents, sparse            {"t": "int"|"float"|"text"|"bool"|"formula", "v": ...}
    sheet.grid    the values the cells show, sparse  int, float, str, bool or ErrorValue (never None)
    sheet.view()  the content a client displays      a constant as stored; a formula as its value plus "f", the formula

Everything that changes a cell goes through ``WorkbookModel`` (``store``, ``restructure``, ``drop_sheet``), which
tells the calculator what happened; commands never touch ``cells`` themselves.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from typing import ClassVar, Self, TypeIs, cast

from claudia_core import (
    Command,
    CommandRegistry,
    DocumentModel,
    ObjectBody,
    ObjectModel,
    Palette,
    Region,
    StyleBook,
    VisualObject,
    builtin_palette,
    new_registry,
)

from .calc import Calculator
from .cellstyles import CellStyles, Piece
from .charts import ChartError, ChartSeries, ChartSpec, figure_of, in_bounds
from .formula.rewrite import adjusted, renamed_name, without_sheet
from .functions.registry import FunctionRegistry
from .limits import MAX_COLS, MAX_ROWS  # noqa: F401  (the names have lived here: other packages import them from here)
from .names import NamedRange, NameKey, Names, Rect, key_of, name_problem
from .outcomes import InputCell, OutcomeTable, Summary
from .refs import CellRef, Position, RangeRef, SheetId, StructuralEdit, column_name
from .spill import Table
from .sql import column_names, column_type, run_query
from .styles import builtin_styles
from .trace import Trace, Window
from .trace import follow as follow_computation
from .values import ErrorValue, Value, format_value

Content = dict | None  # None (empty) or {"t": "int"|"float"|"text"|"bool"|"formula", "v": ...}
Cells = list[tuple[int, int, Content]]
NameRestores = list[tuple[NameKey, NamedRange | None]]  # (key, the name as it was, None: there was none)

# Row height and column width (D135): sheet layout, not a cell style — a line not in ``Sheet.row_heights`` or
# ``col_widths`` shows at the default. Pixels, matching the grid's own units; the bounds keep a line shrinkable
# a long way without a drag ever hiding it outright (there is no separate hide-row/column feature yet).
DEFAULT_ROW_HEIGHT = 26
DEFAULT_COL_WIDTH = 96
MIN_ROW_HEIGHT = 8
MAX_ROW_HEIGHT = 1_000
MIN_COL_WIDTH = 16
MAX_COL_WIDTH = 2_000

# Floating objects anchored to a cell (E6.17, E10.16): a shared ``ObjectBody`` plus a ``CellAnchor``. The
# body — kind, size, style, text, shape, image, rotation, snap — is ``claudia_core``'s and the same in all three
# apps; the anchor is the only part that is a sheet's own.
#
# An object's anchor and size never change because of a structural edit (row/column insert, delete, or a
# row/column resize) — only ``MoveObject`` (the person dragging it) changes where it sits. That is a deliberate
# policy, not an oversight: a picture should not leap across the sheet because somebody inserted a row above it.
# It is why ``CellAnchor`` is not a ``RangeRef`` and takes no part in ``refs.adjusted``.
OBJECT_KINDS = ("text", "shape", "image", "diagram")
MIN_OBJECT_SIZE = 20  # pixels; an object is at least this wide and this tall
MAX_OBJECTS_PER_SHEET = 500


def _is_whole(value: object) -> TypeIs[int]:
    """``True`` for a plain ``int`` (not a ``bool``), narrowing the type for the caller."""
    return type(value) is int


@dataclass(frozen=True)
class CellAnchor:
    """Where an object sits on a sheet: its top-left corner pinned to a cell.

    This is the only thing about a computes object that creates and composes do not share. ``row``/``col`` are
    the anchor cell; the object's pixel size lives in its body. Nothing in the model ever moves or resizes it on
    its own (see the note above)."""

    kind: ClassVar[str] = "cell"
    sheet: SheetId
    row: int
    col: int

    @property
    def container(self) -> str:
        """The sheet this object belongs to."""
        return str(self.sheet)

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"kind": self.kind, "container": str(self.sheet), "row": self.row, "col": self.col}

    @classmethod
    def from_data(cls, data: dict) -> CellAnchor:
        """Read an anchor sent by a client or stored in the log; ``ValueError`` if it is not one."""
        if data.get("kind") != cls.kind:
            raise ValueError(f"computes knows only cell anchors, not {data.get('kind')!r}")
        sheet, row, col = data.get("container"), data.get("row"), data.get("col")
        if not isinstance(sheet, str) or not _is_whole(row) or not _is_whole(col):
            raise ValueError("a cell anchor names a sheet and whole row and col")
        return cls(SheetId(sheet), row, col)


#: One floating thing on a sheet: an image, and (as the shared layer grows into computes) a shape or text box.
type SheetObject = VisualObject[CellAnchor]


@dataclass(frozen=True)
class Chart:
    """One chart tab (E6.6): a name in the tab strip, and the id of the :class:`~claudia_computes.ChartSpec` it
    shows — the same definition a floating diagram object elsewhere in the workbook may show too (see
    ``ObjectBody.diagram``). A tab adds nothing of its own to what is drawn; it only gives a definition a place
    in the tab strip, the same way a floating object gives one a place on a sheet. Two charts (or a chart and a
    floating object) may point at the same ``spec_id``, exactly as two image objects may share one
    :class:`~claudia_core.ImageAsset`."""

    id: str
    name: str
    spec_id: str

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {"id": self.id, "name": self.name, "spec_id": self.spec_id}

    @classmethod
    def from_data(cls, data: dict) -> Chart:
        """Inverse of :meth:`to_data`."""
        return cls(data["id"], data["name"], data["spec_id"])


_default_functions: FunctionRegistry | None = None


def default_functions() -> FunctionRegistry:
    """The built-in functions, one registry for all workbooks of the process."""
    global _default_functions  # noqa: PLW0603
    if _default_functions is None:
        from .functions.builtin import builtin_registry

        _default_functions = builtin_registry()
    return _default_functions


def content_of(value) -> Content:
    """Typed content for a Python value (``None`` is an empty cell). An ``ErrorValue`` becomes an ``error`` content,
    which is how a client is told about a formula that ended in an error."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "int", "v": value}
    if isinstance(value, float):
        return {"t": "float", "v": value}
    if isinstance(value, ErrorValue):
        return {"t": "error", "v": value.code, **({"d": value.detail} if value.detail else {})}
    return {"t": "text", "v": str(value)}


def value_of(content: Content) -> Value:
    """The value a constant content shows (formulas show what they calculate: this gives ``None`` for them)."""
    if content is not None and content["t"] in ("int", "float", "text", "bool"):
        return content["v"]
    return None


class _LiveMax:
    """The largest of a set of non-negative ints that gains and loses members, without rescanning on removal.

    A max-heap of values that have ever been live, lazily cleaned: a value no longer live is dropped only once it
    would be the answer, not when it stops being live. Cost is amortized over how often a value newly becomes live,
    never over how many values are currently live — the same trade a hash index makes against a sorted one."""

    __slots__ = ("_heap", "_live")

    def __init__(self) -> None:
        self._heap: list[int] = []
        self._live: dict[int, int] = {}  # value -> how many times it is currently live

    def add(self, value: int) -> None:
        count = self._live.get(value, 0)
        self._live[value] = count + 1
        if count == 0:
            heappush(self._heap, -value)

    def discard(self, value: int) -> None:
        count = self._live.get(value, 0)
        if count <= 1:
            self._live.pop(value, None)
        else:
            self._live[value] = count - 1

    def max(self) -> int:
        """The largest live value, or -1 if nothing is live."""
        while self._heap and self._live.get(-self._heap[0], 0) == 0:
            heappop(self._heap)
        return -self._heap[0] if self._heap else -1


class Sheet:
    """One sheet of a workbook: its cells (sparse), the values they show, and its row heights and column widths."""

    def __init__(self, sheet_id: SheetId, name: str):
        self.id = sheet_id
        self.name = name
        self.cells: dict[Position, dict] = {}  # sparse: only cells that hold something
        self.grid: dict[Position, Value] = {}  # sparse: the values they show
        self.rows_used = 0  # rows and columns beyond these hold nothing
        self.cols_used = 0
        self.cell_styles = CellStyles()  # the style ranges of the cells' two slots (E6.13, D307)
        self.row_heights: dict[int, float] = {}  # sparse: only rows resized away from DEFAULT_ROW_HEIGHT
        self.col_widths: dict[int, float] = {}  # sparse: only columns resized away from DEFAULT_COL_WIDTH
        #: Cells that show a part of the result of a ``SQL()`` formula (``position -> the formula's key``): they are
        #: not stored (they are not in ``cells``), they cannot be written and the formula owns them (E6.5).
        self.spilled: dict[Position, tuple[SheetId, int, int]] = {}
        #: Derived, not stored (kept by ``claudia_computes.outcomes`` after every calculation): the cells that hold
        #: alternatives (``{800, 1000, 1300}``) and, for the cells that depend on them, where their outcomes lie.
        self.alternatives: dict[Position, InputCell] = {}
        self.outcomes: dict[Position, Summary] = {}
        self._tick = 0
        self._epoch = 0  # the tick of the last change to every column at once (rows moved)
        self._columns: dict[int, int] = {}  # column -> tick of its last change
        # The row/column index behind `cells_in` and `extent` (QA review 2026-11-06, PERF-01, PERF-05): kept
        # incrementally on every single-cell set/clear (`_note_filled`/`_note_emptied`, called from
        # `WorkbookModel.store`), so a window query or the extent cost what they return, not the size of the sheet.
        # A structural edit moves or destroys cells wholesale, so `refit` rebuilds this the same way it already
        # rebuilds `rows_used`/`cols_used` — that path was already O(sheet size) and stays so.
        self._row_cols: dict[int, list[int]] = {}  # row -> sorted columns that hold something, for `cells_in`
        self._rows_live = _LiveMax()  # rows that hold something, for `extent`
        self._cols_live = _LiveMax()  # columns that hold something, for `extent`

    def to_data(self) -> dict:
        """The sheet as plain data for a snapshot: id, name, cell contents and the resized rows and columns."""
        return {
            "id": self.id,
            "name": self.name,
            "cells": [[r, c, content] for (r, c), content in sorted(self.cells.items())],
            "row_heights": [[r, h] for r, h in sorted(self.row_heights.items())],
            "col_widths": [[c, w] for c, w in sorted(self.col_widths.items())],
            "cell_styles": self.cell_styles.to_data(),
        }

    def sizes(self, axis: str) -> dict[int, float]:
        """The sparse size overrides for ``axis`` ("row" heights or "col" widths); a line missing from it is at the
        default. The returned dict is the sheet's own: mutate it to resize, same as ``cells``."""
        return self.row_heights if axis == "row" else self.col_widths

    # -- values
    def set_value(self, position: Position, value: Value) -> bool:
        """Show ``value`` at ``position`` (``None``: nothing). Returns whether that was a change."""
        old = self.grid.get(position)
        if value is None:
            if old is None:
                return False
            del self.grid[position]
        else:
            if old is not None and old.__class__ is value.__class__ and old == value:
                return False
            self.grid[position] = value
            row, col = position
            if row >= self.rows_used:
                self.rows_used = row + 1
            if col >= self.cols_used:
                self.cols_used = col + 1
        self._tick += 1
        self._columns[position[1]] = self._tick
        return True

    def column_version(self, col: int) -> int:
        """Changes whenever a value in the column does (lookup indexes of the column stay good until it does)."""
        return max(self._epoch, self._columns.get(col, 0))

    def version(self) -> int:
        """Changes whenever any value on the sheet does."""
        return self._tick

    def bump_all(self) -> None:
        """Everything may have moved: every column has changed."""
        self._tick += 1
        self._epoch = self._tick

    def refit(self) -> None:
        """Recount how far the sheet reaches and rebuild the row/column index (after cells moved or went: a
        structural edit, or loading from storage). Single-cell edits stay incremental instead — see `_note_filled`
        and `_note_emptied`, called from `WorkbookModel.store`."""
        self.rows_used = max((r for r, _ in self.grid), default=-1) + 1
        self.cols_used = max((c for _, c in self.grid), default=-1) + 1
        grouped: dict[int, list[int]] = {}
        for row, col in (*self.cells, *self.spilled):
            grouped.setdefault(row, []).append(col)
        self._row_cols = {row: sorted(cols) for row, cols in grouped.items()}
        self._rows_live = _LiveMax()
        self._cols_live = _LiveMax()
        for row, cols in self._row_cols.items():
            self._rows_live.add(row)
            for col in cols:
                self._cols_live.add(col)

    # -- the row/column index: `cells_in` and `extent` cost what they return, not the size of the sheet
    def _note_filled(self, position: Position) -> None:
        """A cell that was empty now holds something."""
        row, col = position
        insort(self._row_cols.setdefault(row, []), col)
        self._rows_live.add(row)
        self._cols_live.add(col)

    def _note_emptied(self, position: Position) -> None:
        """A cell that held something is now empty; shrinks the index the same way `_note_filled` grew it."""
        row, col = position
        cols = self._row_cols.get(row)
        if cols is not None:
            at = bisect_left(cols, col)
            if at < len(cols) and cols[at] == col:
                del cols[at]
            if not cols:
                del self._row_cols[row]
        self._rows_live.discard(row)
        self._cols_live.discard(col)

    # -- cells a SQL() result fills
    def spill_value(self, position: Position, value: Value, owner: tuple[SheetId, int, int]) -> bool:
        """Show ``value`` at ``position`` as part of the result ``owner`` gave. Returns whether anything changed."""
        new = position not in self.spilled
        if new:
            self.spilled[position] = owner
            self._note_filled(position)
        return self.set_value(position, value) or new

    def spill_clear(self, position: Position) -> bool:
        """The cell is no longer part of a result: it is empty. Returns whether it was."""
        if self.spilled.pop(position, None) is None:
            return False
        self._note_emptied(position)
        self.set_value(position, None)
        return True

    def blocker(self, first: Position, last: Position, owner: tuple[SheetId, int, int]) -> Position | None:
        """The first cell (row by row) of the rectangle, other than the cell of ``owner`` itself, that holds
        something of its own or is part of another result, or ``None`` when the rectangle is free for ``owner``."""
        (row0, col0), (row1, col1) = first, last
        own = (owner[1], owner[2])

        def in_the_way(position: Position) -> bool:
            return position != own and (position in self.cells or self.spilled.get(position, owner) != owner)

        if (row1 - row0 + 1) * (col1 - col0 + 1) <= len(self.cells) + len(self.spilled):
            return next(
                (
                    (row, col)
                    for row in range(row0, row1 + 1)
                    for col in range(col0, col1 + 1)
                    if in_the_way((row, col))
                ),
                None,
            )
        found = [p for p in (*self.cells, *self.spilled) if row0 <= p[0] <= row1 and col0 <= p[1] <= col1]
        return min((p for p in found if in_the_way(p)), default=None)

    def cells_in(self, row0: int, row1: int, col0: int, col1: int) -> list[Position]:
        """Positions that hold something inside a window (both ends included), sorted by row then column. Costs the
        number of rows in the window plus the number of cells returned — never the size of the sheet."""
        found: list[Position] = []
        for row in range(row0, row1 + 1):
            cols = self._row_cols.get(row)
            if not cols:
                continue
            lo, hi = bisect_left(cols, col0), bisect_right(cols, col1)
            found.extend((row, col) for col in cols[lo:hi])
        return found

    def extent(self) -> tuple[int, int]:
        """Rows and columns that hold something (the same extent `_sheets`/`_extent` report), amortized O(1) —
        never a scan of the sheet."""
        return self._rows_live.max() + 1, self._cols_live.max() + 1

    # -- what a client displays
    def view(self, position: Position) -> dict | None:
        """The content of a cell as a client shows it: a constant as stored, a formula as the value it gave (in the
        form of a constant, ``error`` for an error) with the formula itself under ``"f"``. A cell that shows a
        part of a query result carries ``"spill": true`` and, under ``"from"``, the ``[row, col]`` of the formula that
        fills it."""
        content = self.cells.get(position)
        if content is None and position in self.spilled:  # (a part of a query result: shown, not stored)
            part = content_of(self.grid.get(position)) or {"t": "text", "v": ""}
            _, row, col = self.spilled[position]  # (the cell of the formula that fills it, on this same sheet)
            return {**part, "spill": True, "from": [row, col]}
        if content is None or content["t"] != "formula":
            return content
        value = self.grid.get(position)
        shown = content_of(0 if value is None else value)
        view = {**shown, "f": content["v"]}  # type: ignore[dict-item]
        alternatives = self.alternatives.get(position)
        if alternatives is not None:  # (an input: the formula bar shows what was typed, the client the alternatives)
            view["f"] = alternatives.text
            view["alts"] = [alt.to_data() for alt in alternatives.alts]
        outcomes = self.outcomes.get(position)
        if outcomes is not None:
            view["out"] = outcomes.to_data()
        return view


class WorkbookModel(DocumentModel, ObjectModel[CellAnchor]):
    """The state of a computes document: its sheets, chart tabs, diagrams, objects, style book and palette."""

    app: ClassVar[str] = "computes"
    # 3: the workbook also carries images and objects anchored to cells (E6.17)
    # 4: objects are a shared body plus a CellAnchor, and the workbook carries a style book (E10.16)
    # 5: the workbook carries its own colour palette (D200)
    # 6: the workbook carries diagram definitions and chart tabs, either of which may show one (E6.6)
    # 7: the workbook carries names: named ranges, tables and query results (E6.5, D600)
    # 8: the workbook carries the seed and draw number of its random numbers (E6.22, D291)
    state_schema: ClassVar[int] = 9  # 8: object bodies without a description
    registry: ClassVar[CommandRegistry] = new_registry()

    object_kinds: ClassVar[tuple[str, ...]] = OBJECT_KINDS
    min_object_size: ClassVar[int] = MIN_OBJECT_SIZE
    max_objects_per_container: ClassVar[int] = MAX_OBJECTS_PER_SHEET

    def __init__(
        self,
        functions: FunctionRegistry | None = None,
        styles: StyleBook | None = None,
        palette: Palette | None = None,
    ):
        super().__init__()
        self.sheets: dict[SheetId, Sheet] = {}
        self.calc = Calculator(self, functions or default_functions())
        self._ids: dict[str, SheetId] | None = None
        self.styles: StyleBook = styles if styles is not None else builtin_styles()
        #: The colours of this workbook, by what they mean. Part of the document, so it looks the same on
        #: whichever server it is opened (D200); the built-in styles are written entirely in terms of it.
        self.palette: Palette = palette if palette is not None else builtin_palette()
        #: The chart tabs in tab order (E6.6), each a name plus the id of the diagram definition
        #: (``self.diagrams``, from :class:`~claudia_core.ObjectModel`) it shows. A floating diagram object may
        #: show the very same definition — see ``Chart``'s own docstring.
        self.charts: dict[str, Chart] = {}
        #: Named ranges, tables and the results of ``SQL()`` formulas (E6.5): see :class:`~claudia_computes.Names`.
        self.names = Names()
        #: The seed and the draw number every random number is a function of (D291). Both are part of the document, so
        #: everybody sees the same numbers; ``Resample`` raises the draw number, ``SetRandomSeed`` changes the seed.
        self.random_seed = 0
        self.random_draw = 0

    @classmethod
    def empty(cls) -> Self:
        return cls()

    @classmethod
    def setup_commands(cls, language: str | None) -> tuple[Command, ...]:
        """A new workbook starts with its first sheet, ``s1`` called "Sheet1" (UX-33: before, the client added it as
        the person's own first step, which her first Ctrl+Z took away again)."""
        from .commands import AddSheet

        return (AddSheet(SheetId("s1"), "Sheet1"),)

    def serialize(self) -> dict:
        return {
            "sheets": [sheet.to_data() for sheet in self.sheets.values()],
            "styles": self.styles.to_data(),
            "palette": self.palette.to_data(),
            "shapes": self.shapes_to_data(),
            "images": self.images_to_data(),
            "diagrams": self.diagrams_to_data(),
            "objects": self.objects_to_data(),
            "charts": [chart.to_data() for chart in self.charts.values()],
            "names": self.names.to_data(),
            "random": {"seed": self.random_seed, "draw": self.random_draw},
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls(styles=StyleBook.from_data(state["styles"]), palette=Palette.from_data(state["palette"]))
        for item in state["sheets"]:
            sheet = Sheet(SheetId(item["id"]), item["name"])
            sheet.cells = {(r, c): content for r, c, content in item["cells"]}
            sheet.row_heights = dict(item["row_heights"])
            sheet.col_widths = dict(item["col_widths"])
            sheet.cell_styles = CellStyles.from_data(item["cell_styles"])  # no upcast before the first release (D308)
            model.sheets[sheet.id] = sheet
            model.open_container(str(sheet.id))
        model.restore_objects(state["objects"], state["images"], state["shapes"], state["diagrams"])
        model.charts = {item["id"]: Chart.from_data(item) for item in state["charts"]}
        model.names = Names.from_data(state["names"])
        model.random_seed, model.random_draw = state["random"]["seed"], state["random"]["draw"]
        model._calculate_loaded()
        return model

    # -- the object seam -------------------------------------------------------
    def style_in_use(self, style_id: str) -> bool:
        """Does an object, its words, or a style range of any sheet name this style? (Asked by the core style
        commands before they take a style back.)"""
        in_cells = any(sheet.cell_styles.names(style_id) for sheet in self.sheets.values())
        return in_cells or ObjectModel.style_in_use(self, style_id)

    def containers(self) -> list[str]:
        """The sheets objects may sit on, in order."""
        return [str(sheet) for sheet in self.sheets]

    def anchor_from_data(self, data: dict) -> CellAnchor:
        """Read a cell anchor; ``ValueError`` if the data is not one."""
        return CellAnchor.from_data(data)

    def check_anchor(self, anchor: CellAnchor, body: ObjectBody) -> None:
        """An object's anchor must be a cell of the sheet. Its size is not bounded by the sheet: a sheet has no
        edge to fall off, unlike a slide."""
        if not _is_whole(anchor.row) or not _is_whole(anchor.col):
            raise ValueError("row and col must be whole numbers")
        if anchor.row < 0 or anchor.col < 0 or anchor.row >= MAX_ROWS or anchor.col >= MAX_COLS:
            raise ValueError("the object's anchor must be a cell of the sheet")

    def diagram_from_data(self, data: dict) -> ChartSpec:
        """Read a chart definition; ``ValueError`` if the data is not one, or its range does not fit a sheet
        this workbook actually has (:class:`~claudia_computes.ChartSpec` alone cannot know that)."""
        try:
            spec = ChartSpec.from_data(data)
        except ChartError as error:
            raise ValueError(str(error)) from None
        if spec.source:
            if spec.source_scope is not None and spec.source_scope not in self.sheets:
                raise ValueError(f"this document does not know the sheet {spec.source_scope!r}")
            if self.names.get(key_of(spec.source_scope, spec.source)) is None:
                raise ValueError(f"this document has no name {spec.source!r} to draw a chart from")
            return spec
        assert spec.range is not None  # (a spec reads a range or a source)
        if spec.range.sheet not in self.sheets:
            raise ValueError(f"this document does not know the sheet {spec.range.sheet!r}")
        if not in_bounds(spec.range):
            raise ValueError("a chart's range must be inside the sheet")
        return spec

    def users_of_diagram(self, diagram_id: str) -> list[str]:
        """As the shared check (floating objects), plus any chart tab showing this diagram (E6.6): a tab is a
        user of a diagram definition exactly as an object anchored to one is, so ``forget_diagram`` refuses
        while either kind of user remains."""
        return [*super().users_of_diagram(diagram_id), *(c.id for c in self.charts.values() if c.spec_id == diagram_id)]

    def charts_reading(self, sheet_id: SheetId) -> list[str]:
        """Ids of the diagram definitions whose range names ``sheet_id`` (E6.6): what ``RemoveSheet`` refuses
        to orphan, the same way it refuses to orphan a formula elsewhere were there no ``#REF!`` for that.

        ``self.diagrams`` is typed by the shared :class:`~claudia_core.ObjectModel` as holding the
        app-agnostic :class:`~claudia_core.DiagramDefinition`; every value in it is in fact a ``ChartSpec``,
        since :meth:`diagram_from_data` is the only thing that ever puts one there."""
        return sorted(
            spec.id
            for spec in map(_chart_spec, self.diagrams.values())
            if spec.range is not None and spec.range.sheet == sheet_id
        )

    # -- chart tabs --------------------------------------------------------------
    def chart(self, chart_id: str) -> Chart:
        """The chart tab ``chart_id``; raises :class:`ValueError` if there is none."""
        try:
            return self.charts[chart_id]
        except KeyError:
            raise ValueError(f"unknown chart {chart_id!r}") from None

    def add_chart(self, chart: Chart, index: int | None) -> None:
        """Put a chart tab at ``index`` in the tab order, or last when ``index`` is ``None``."""
        ordered = list(self.charts.values())
        ordered.insert(len(ordered) if index is None else index, chart)
        self.charts = {c.id: c for c in ordered}

    def remove_chart(self, chart_id: str) -> None:
        """Take the chart tab ``chart_id`` out; raises :class:`ValueError` if there is none."""
        self.chart(chart_id)
        self.charts = {c.id: c for c in self.charts.values() if c.id != chart_id}

    def chart_figure(self, diagram_id: str) -> dict:
        """The Plotly figure (``{"data": [...], "layout": {...}}``) a diagram draws right now, read live off its
        sheet (E6.6); ``ValueError`` if ``diagram_id`` names no diagram this workbook knows.

        **The header convention:** the range's first column always names each category when ``series_in`` is
        "columns" (the other way around for "rows") — read by the range's own shape, same as it always has been.
        The first *row* is the same, except that ``spec.header_row`` can turn it off: a range with headers
        already baked in (the usual "select your data including its headers") keeps ``header_row`` at its
        default of ``True``, and a range that is data only, top to bottom, sets it to ``False`` so every row
        feeds the chart rather than the first one being read as a header and dropped (the header-row bug this
        field exists to fix: a 2-column, 3-row range of category/value pairs with no header line of its own used
        to silently lose its first row to exactly this). Either way, a row or column that has only one line to
        give has no room to be both the header and the data, so it is read as data only regardless of the
        setting, with generated names ("Series 1", "1", "2", …) — this keeps a 1-row or 1-column range usable
        rather than adding a minimum-size rule charts.py's range check does not have today. A text cell inside
        the numeric data block plots as 0 rather than failing the whole chart; :meth:`diagram_from_data` already
        guarantees the range fits a sheet this document has."""
        spec = _chart_spec(self.diagrams[diagram_id])
        window = self._chart_window(spec)
        if window is None:  # the named result is gone (or has no table right now): an empty chart, not an error
            return figure_of(spec, [], [])
        sheet, first, last, header_row = window
        has_header_row = header_row and last.row > first.row
        has_header_col = last.col > first.col
        data_row0 = first.row + (1 if has_header_row else 0)
        data_col0 = first.col + (1 if has_header_col else 0)

        def text_at(row: int, col: int) -> str | None:
            content = sheet.view((row, col))
            if content is None:
                return None
            value = content["v"]
            return ("TRUE" if value else "FALSE") if isinstance(value, bool) else str(value)

        def number_at(row: int, col: int) -> float:
            content = sheet.view((row, col))
            value = None if content is None else content["v"]
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return float(value) if isinstance(value, (int, float)) else 0.0

        def labels(count: int, header: int | None, along: Callable[[int, int], tuple[int, int]]) -> list[str]:
            if header is None:
                return [str(i) for i in range(1, count + 1)]
            return [text_at(*along(header, i)) or str(i + 1) for i in range(count)]

        if spec.series_in == "columns":
            rows, cols = range(data_row0, last.row + 1), range(data_col0, last.col + 1)
            categories = labels(len(rows), first.col if has_header_col else None, lambda h, i: (data_row0 + i, h))
            series = [
                ChartSeries(
                    (text_at(first.row, c) or f"Series {i + 1}") if has_header_row else f"Series {i + 1}",
                    tuple(number_at(r, c) for r in rows),
                )
                for i, c in enumerate(cols)
            ]
        else:
            rows, cols = range(data_row0, last.row + 1), range(data_col0, last.col + 1)
            categories = labels(len(cols), first.row if has_header_row else None, lambda h, i: (h, data_col0 + i))
            series = [
                ChartSeries(
                    (text_at(r, first.col) or f"Series {i + 1}") if has_header_col else f"Series {i + 1}",
                    tuple(number_at(r, c) for c in cols),
                )
                for i, r in enumerate(rows)
            ]
        return figure_of(spec, categories, series)

    def _chart_window(self, spec: ChartSpec) -> tuple[Sheet, CellRef, CellRef, bool] | None:
        """The cells a chart reads right now: ``(sheet, first, last, header_row)``, or ``None`` when its named
        source has no cells (the name is gone, or a ``SQL()`` result is not a table at the moment). A named source
        is a table, so it always has its header row; a range has it when the definition says so."""
        if not spec.source:
            assert spec.range is not None
            sheet_id = cast(SheetId, spec.range.sheet)  # a chart's range always names its sheet (charts.py)
            return self.sheet(sheet_id), spec.range.first, spec.range.last, spec.header_row
        named = self.names.get(key_of(spec.source_scope, spec.source))
        region = None if named is None else self.region_of(named)
        if named is None or region is None:
            return None
        sheet_id, row0, col0, row1, col1 = region
        return self.sheets[sheet_id], CellRef(row0, col0), CellRef(row1, col1), named.header or named.anchor is not None

    def _calculate_loaded(self) -> None:
        """Fill the values from the contents: constants as they are, formulas calculated."""
        self.calc.reset()
        self._ids = None
        for sheet in self.sheets.values():
            sheet.grid = {
                position: value_of(content) for position, content in sheet.cells.items() if content["t"] != "formula"
            }
        for sheet in self.sheets.values():  # (constants first: a table's header is read while its formulas compile)
            for position, content in sheet.cells.items():
                if content["t"] == "formula":
                    key = (sheet.id, *position)
                    self.calc.define(key, self.calc.compile(sheet.id, content["v"], position), forced=False)
            sheet.refit()
            sheet.bump_all()
        self.calc.recalculate_all()

    def settle(self, ctx) -> None:
        self.calc.settle(ctx)

    def trace(
        self, sheet_id: SheetId, row: int, col: int, *, reach: str = "group", window: Window | None = None
    ) -> Trace:
        """The cells that take part in a calculation with this cell, each with its part (input, calc or output): see
        ``claudia_computes.trace``. ``reach`` is ``"group"`` or ``"chain"``; ``window`` cuts the cells listed to what
        a client shows (first row, first column, last row, last column)."""
        return follow_computation(self, sheet_id, row, col, reach=reach, window=window)

    def outcome_table(self, sheet_id: SheetId, row: int, col: int, *, combine: str = "all") -> OutcomeTable | None:
        """Every outcome of a cell that depends on alternatives, with the alternatives that make them (``combine``:
        ``"all"`` combinations, or ``"pair"``: the first alternatives together, the second ones, ...); ``None`` for a
        cell that depends on none. A ``ValueError`` when pairing inputs that have different numbers of alternatives."""
        self.sheet(sheet_id)
        return self.calc.outcomes.table((sheet_id, row, col), combine)

    # -- names (formulas name sheets, the model knows them by id)
    def sheet_id_of(self, name: str) -> SheetId | None:
        """The id of the sheet called ``name`` (case-insensitive), or ``None`` if no sheet has that name."""
        if self._ids is None:
            self._ids = {sheet.name.casefold(): sheet.id for sheet in self.sheets.values()}
        return self._ids.get(name.casefold())

    def sheet_name_of(self, sheet_id: SheetId) -> str | None:
        """The name of sheet ``sheet_id``, or ``None`` if there is no such sheet."""
        sheet = self.sheets.get(sheet_id)
        return None if sheet is None else sheet.name

    # -- names (E6.5) ------------------------------------------------------------
    def header_texts(self, region: Rect) -> list[str]:
        """The text of the header cell of each column of ``region`` (its first row), as typed: a formula in a header
        shows what it showed when last calculated."""
        sheet_id, row0, col0, _, col1 = region
        sheet = self.sheets.get(sheet_id)
        if sheet is None:
            return []
        texts = []
        for col in range(col0, col1 + 1):
            content = sheet.cells.get((row0, col))
            if content is None:
                texts.append("")
            else:
                texts.append(format_value(sheet.grid.get((row0, col)) if content["t"] == "formula" else content["v"]))
        return texts

    def check_name(self, named: NamedRange) -> None:
        """``ValueError`` unless ``named`` is a name this workbook can hold: a good word, on sheets it has."""
        problem = name_problem(named.name)
        if problem is not None:
            raise ValueError(problem)
        if named.scope is not None and named.scope not in self.sheets:
            raise ValueError(f"this document does not know the sheet {named.scope!r}")
        if named.sheet not in self.sheets:
            raise ValueError(f"this document does not know the sheet {named.sheet!r}")
        area = named.range
        if area is not None and (
            min(area.first.row, area.first.col) < 0
            or area.last.row >= MAX_ROWS
            or area.last.col >= MAX_COLS
            or area.last.row < area.first.row
            or area.last.col < area.first.col
        ):
            raise ValueError("the cells of a name must be inside the sheet")
        if area is not None and named.header and area.last.row == area.first.row and area.last.col < area.first.col:
            raise ValueError("a table needs a header row")

    def region_of(self, named: NamedRange) -> Rect | None:
        """The cells a name is on right now (its header row included), or ``None`` for a result that has none: the
        formula that fills it gave no table (it failed, or is gone)."""
        if named.anchor is not None:
            return self.calc.spills.get(named.anchor)
        area = named.range
        assert area is not None and area.sheet is not None
        return area.sheet, area.first.row, area.first.col, area.last.row, area.last.col

    def columns_of(self, named: NamedRange, sample: int = 2_000) -> list[tuple[str, str]]:
        """The columns of a table as ``(name, type)``, the names as a query sees them (``Column<n>`` for a blank
        header, letters for a range without a header) and the type (``int``, ``real``, ``text`` or ``mixed``) read
        off the first ``sample`` rows."""
        region = self.region_of(named)
        if region is None:
            return []
        sheet_id, row0, col0, row1, col1 = region
        sheet = self.sheets[sheet_id]
        header = named.header or named.anchor is not None
        if header:
            names = column_names([format_value(sheet.grid.get((row0, c))) for c in range(col0, col1 + 1)])
        else:
            names = [column_name(c) for c in range(col0, col1 + 1)]
        top = row0 + 1 if header else row0
        last = min(row1, top + sample - 1)
        return [
            (text, column_type([sheet.grid.get((r, col0 + offset)) for r in range(top, last + 1)]))
            for offset, text in enumerate(names)
        ]

    def query(self, text: str, home: SheetId, parameters: Sequence[object] = ()) -> Table:
        """The result of the query ``text`` as a ``SQL()`` formula on ``home`` would give it, without putting it in a
        cell: what an editor previews. Raises ``FormulaError`` (``#SQL!``) for a query that is refused or fails."""
        scope = self.calc.scope_for(home)
        return run_query(text, parameters, scope.table_data)

    def put_names(self, entries: Sequence[tuple[NameKey, NamedRange | None]]) -> NameRestores:
        """Set (or, with ``None``, take out) names; returns what each key held before, to put back. Formulas that use
        any of them are compiled again."""
        before: NameRestores = []
        texts: set[str] = set()
        for key, named in entries:
            before.append((key, self.names.get(key)))
            self.names.put(named, key)
            texts.add(key[1])
        self.calc.rebind(texts)
        return before

    def grow_names(self, sheet_id: SheetId, positions: list[Position]) -> NameRestores:
        """Tables that grow with their last row take in the rows typed right below them (``positions`` are cells that
        now hold something). Returns the tables as they were, for those that grew."""
        grown: NameRestores = []
        for named in list(self.names):
            area = named.range
            if not named.grows or area is None or area.sheet != sheet_id:
                continue
            last = area.last.row
            for row in sorted({r for r, c in positions if area.first.col <= c <= area.last.col and r > last}):
                if row != last + 1 or row >= MAX_ROWS:
                    break
                last = row
            if last != area.last.row:
                grown.append((named.key, named))
                self.names.put(named.with_range(RangeRef(area.first, area.last.with_row(last))))
        if grown:
            self.calc.rebind({key[1] for key, _ in grown})
        return grown

    def header_edited(self, sheet_id: SheetId, positions: list[Position]) -> None:
        """Header cells of tables were written: the formulas that name their columns are compiled again."""
        texts: set[str] = set()
        for named in self.names:
            area = named.range
            if not named.header or area is None or area.sheet != sheet_id:
                continue
            row = area.first.row
            if any(r == row and area.first.col <= c <= area.last.col for r, c in positions):
                texts.add(named.key[1])
        if texts:
            self.calc.rebind(texts)

    def rename_name(self, scope: SheetId | None, old: str, new: str) -> dict[SheetId, Cells]:
        """Call the name ``old`` by ``new``; the formulas that use it are rewritten (``ValueError`` when there is no
        such name or ``new`` is not a good one). Returns those formulas as they were typed, by sheet, for an undo."""
        named = self.names.get(key_of(scope, old))
        if named is None:
            raise ValueError(f"there is no name {old!r}")
        problem = name_problem(new)
        if problem is not None:
            raise ValueError(problem)
        target = key_of(scope, new)
        if target != named.key and self.names.get(target) is not None:
            raise ValueError(f"{new} is already a name")
        calc = self.calc
        plan = []
        for key in calc.users_of(old):
            compiled = calc.formulas[key]
            resolved = self.names.resolve(key[0], old)
            if resolved is None or resolved.key != named.key:
                continue  # (it means another name of the same text: a sheet's own, or the workbook's)
            formula = renamed_name(compiled.formula, old, new, self.sheet_name_of)
            if formula is not compiled.formula:
                plan.append((key, formula, compiled))
        self.names.put(None, named.key)
        self.names.put(replace(named, name=new))
        restores: dict[SheetId, Cells] = defaultdict(list)
        for key, formula, compiled in plan:
            home, row, col = key
            self.sheets[home].cells[(row, col)] = {"t": "formula", "v": formula.source}
            restores[home].append((row, col, {"t": "formula", "v": compiled.source}))
            calc.define(key, calc.compile_formula(home, formula, (row, col)))
        calc.rebind({old, new})
        return restores

    def _adjust_names(self, edit: StructuralEdit, remap) -> NameRestores:
        """Move the names with a structural edit: ranges as references do, results with the cell of their formula.
        A name whose cells are all gone goes. Returns the names as they were, for those that changed."""
        changed: NameRestores = []
        for named in list(self.names):
            if named.anchor is not None:
                sheet_id, row, col = named.anchor
                if sheet_id != edit.sheet:
                    continue
                target = remap((row, col))
                moved = None if target is None else replace(named, anchor=(sheet_id, *target))
            else:
                assert named.range is not None
                moved = self._moved_range(named, edit)
                if moved is named:
                    continue
            changed.append((named.key, named))
            self.names.put(moved, named.key)
        if changed:
            self.calc.rebind({key[1] for key, _ in changed})
        return changed

    @staticmethod
    def _moved_range(named: NamedRange, edit: StructuralEdit) -> NamedRange | None:
        area = named.range
        assert area is not None and area.sheet is not None
        new = area.adjusted(edit, area.sheet)
        if new is None or new.first.row >= MAX_ROWS or new.first.col >= MAX_COLS:
            return None
        if new == area:
            return named
        last = new.last
        if last.row >= MAX_ROWS or last.col >= MAX_COLS:
            last = CellRef(min(last.row, MAX_ROWS - 1), min(last.col, MAX_COLS - 1), last.sheet)
        return named.with_range(RangeRef(new.first, last))

    # -- reading ---------------------------------------------------------------
    def sheet(self, sheet_id: SheetId) -> Sheet:
        """The sheet ``sheet_id``; raises :class:`ValueError` if there is none."""
        try:
            return self.sheets[sheet_id]
        except KeyError:
            raise ValueError(f"unknown sheet {sheet_id!r}") from None

    def get(self, sheet_id: SheetId, row: int, col: int) -> Content:
        """What a cell holds (its content as typed, ``None`` for an empty one); see :meth:`value` for what it shows."""
        return self.sheet(sheet_id).cells.get((row, col))

    def value(self, sheet_id: SheetId, row: int, col: int) -> Value:
        """The value a cell shows (``None`` for an empty one)."""
        return self.sheet(sheet_id).grid.get((row, col))

    def region_from_data(self, data: dict) -> Region:
        from .region import CellRegion, ObjectSet

        if data.get("kind") == ObjectSet.kind:
            return ObjectSet.from_data(data)
        return CellRegion.from_data(data)

    # -- changing --------------------------------------------------------------
    def store(self, sheet: Sheet, row: int, col: int, content: Content) -> Content:
        """Put ``content`` into a cell (``None``: empty it). Returns what is stored: a formula is stored in its
        canonical text, so that a document means the same however it is rebuilt."""
        position = (row, col)
        key = (sheet.id, row, col)
        calc = self.calc
        was_filled = position in sheet.cells
        if content is not None and content["t"] == "formula":
            compiled = calc.compile(sheet.id, content["v"], position)
            stored = content if compiled.source == content["v"] else {"t": "formula", "v": compiled.source}
            sheet.cells[position] = stored
            calc.define(key, compiled)
            if not was_filled:
                sheet._note_filled(position)  # noqa: SLF001 (the index is Sheet's own; store() is its one writer)
            return stored
        if key in calc.formulas:
            calc.remove(key)
        if content is None:
            sheet.cells.pop(position, None)
            if was_filled:
                sheet._note_emptied(position)  # noqa: SLF001
        else:
            sheet.cells[position] = content
            if not was_filled:
                sheet._note_filled(position)  # noqa: SLF001
        if sheet.set_value(position, value_of(content)):
            calc.touch(key)
        return content

    def check_writable(self, sheet: Sheet, positions) -> None:
        """``ValueError`` if one of the cells shows a part of a query result: it is not to be written, the query is."""
        for row, col in positions:
            owner = sheet.spilled.get((row, col))
            if owner is not None:
                raise ValueError(
                    f"{column_name(col)}{row + 1} shows the result of SQL() in {column_name(owner[2])}{owner[1] + 1}: "
                    "change the query, not its result"
                )

    def add_sheet(self, sheet: Sheet, index: int | None) -> None:
        """Put a sheet at ``index`` in the tab order, or last when ``index`` is ``None``."""
        ordered = list(self.sheets.values())
        ordered.insert(len(ordered) if index is None else index, sheet)
        self.sheets = {s.id: s for s in ordered}
        self._ids = None
        self.open_container(str(sheet.id))

    def restructure(
        self, edit: StructuralEdit
    ) -> tuple[Cells, dict[SheetId, Cells], tuple[tuple[int, float], ...], list[tuple[str, str, Piece]], NameRestores]:
        """Insert or delete rows or columns: cells move, formulas follow them and keep pointing at what they pointed
        at, and the edited axis' sizes (``Sheet.row_heights`` or ``col_widths``) and the sheet's style ranges move
        with their lines.

        Names move too, and one whose cells are all gone goes. Returns the cells that were deleted, for every sheet
        the formulas whose text had to change (as they were), the sizes of the lines that were deleted (on ``edit``'s
        own axis only), the pieces of style ranges that lay on deleted lines, and the names that changed (as they
        were) — all five are what an undo needs to put back exactly (deleting what a formula pointed at, a line's
        size or its style cannot be undone by a reference)."""
        sheet = self.sheet(edit.sheet)
        limit = MAX_ROWS if edit.axis == "row" else MAX_COLS
        if edit.at >= limit or (not edit.insert and edit.at + edit.count > limit):
            raise ValueError("structural edit is outside the sheet")
        index = 0 if edit.axis == "row" else 1

        def remap(position: Position) -> Position | None:
            new = edit.map_index(position[index])
            if new is None:
                return None
            return (new, position[1]) if index == 0 else (position[0], new)

        moved: dict[Position, dict] = {}
        destroyed: Cells = []
        for position, content in sheet.cells.items():
            target = remap(position)
            if target is None:
                destroyed.append((position[0], position[1], content))
            else:
                moved[target] = content
        if any(r >= MAX_ROWS or c >= MAX_COLS for r, c in moved):
            raise ValueError("structural edit would push cells off the sheet")

        plan = self._plan_restructure(edit, remap)
        # nothing can fail from here on: change the state
        calc = self.calc
        calc.clear_spills(edit.sheet)  # (results are put back where they now belong when everything is calculated)
        for key in [k for k in calc.by_sheet.get(edit.sheet, ()) if remap((k[1], k[2])) is None]:
            calc.remove(key)
        for old_key, _, _, _ in plan:
            calc.remove(old_key)
        sheet.cells = moved
        sheet.grid = {
            target: value for position, value in sheet.grid.items() if (target := remap(position)) is not None
        }
        old_sizes = sheet.sizes(edit.axis)
        destroyed_sizes = tuple(sorted((i, s) for i, s in old_sizes.items() if edit.map_index(i) is None))
        remapped_sizes = {new: s for i, s in old_sizes.items() if (new := edit.map_index(i)) is not None}
        if edit.axis == "row":
            sheet.row_heights = remapped_sizes
        else:
            sheet.col_widths = remapped_sizes
        cut_styles = sheet.cell_styles.restructure(edit)
        sheet.refit()
        sheet.bump_all()
        restores = self._redefine(edit, plan)
        renames = self._adjust_names(edit, remap)
        calc.everything = True
        return destroyed, restores, destroyed_sizes, cut_styles, renames

    def _plan_restructure(self, edit: StructuralEdit, remap) -> list:
        """The formulas a structural edit touches: (old key, new key, formula after the edit, compiled before)."""
        calc = self.calc
        plan = []
        for key in set(calc.by_sheet.get(edit.sheet, ())) | calc.referring.get(edit.sheet, set()):
            home, row, col = key
            old = calc.formulas[key]
            formula = adjusted(old.formula, edit, home, self.sheet_name_of)
            target_key = key
            if home == edit.sheet:
                target = remap((row, col))
                if target is None:
                    continue  # (the formula goes with its cell)
                target_key = (home, *target)
            plan.append((key, target_key, formula, old))
        return plan

    def _redefine(self, edit: StructuralEdit, plan: list) -> dict[SheetId, Cells]:
        """Put the formulas of a plan back in the calculator at their new places; returns the texts an undo restores."""
        calc = self.calc
        restores: dict[SheetId, Cells] = defaultdict(list)
        for old_key, new_key, formula, old in plan:
            rewritten = formula is not old.formula
            if rewritten:
                compiled = calc.compile_formula(old_key[0], formula, (new_key[1], new_key[2]))
                content = {"t": "formula", "v": formula.source}
                self.sheets[new_key[0]].cells[(new_key[1], new_key[2])] = content
                if not edit.insert or ("#REF!" in formula.source and "#REF!" not in old.source):
                    restores[old_key[0]].append((old_key[1], old_key[2], {"t": "formula", "v": old.source}))
            else:
                compiled = old
            calc.define(new_key, compiled, forced=rewritten)
        return restores

    def drop_sheet(self, sheet_id: SheetId) -> tuple[dict[SheetId, Cells], NameRestores]:
        """Remove a sheet. Formulas elsewhere that pointed into it break (``#REF!``) and the names on it go; returns,
        for every sheet, those formulas as they were, and the names as they were, which an undo puts back."""
        self.sheet(sheet_id)
        calc = self.calc
        plan = []
        for key in calc.referring.get(sheet_id, ()):
            if key[0] == sheet_id:
                continue
            old = calc.formulas[key]
            formula = without_sheet(old.formula, sheet_id, self.sheet_name_of)
            if formula is not old.formula:
                plan.append((key, formula, old))
        for key in list(calc.by_sheet.get(sheet_id, ())):
            calc.remove(key)
        self.sheets = {s.id: s for s in self.sheets.values() if s.id != sheet_id}
        self._ids = None
        restores: dict[SheetId, Cells] = defaultdict(list)
        for key, formula, old in plan:
            content = {"t": "formula", "v": formula.source}
            self.sheets[key[0]].cells[(key[1], key[2])] = content
            restores[key[0]].append((key[1], key[2], {"t": "formula", "v": old.source}))
            calc.define(key, calc.compile_formula(key[0], formula, (key[1], key[2])))
        gone = [(named.key, None) for named in self.names if sheet_id in (named.scope, named.sheet)]
        names = self.put_names(gone)
        calc.everything = True
        return restores, names


def _chart_spec(definition: object) -> ChartSpec:
    """A stored diagram definition as the :class:`~claudia_computes.ChartSpec` it always is here: the shared
    object model types ``diagrams`` as the app-agnostic definition, and :meth:`~WorkbookModel.diagram_from_data`
    is the only thing that puts one there."""
    return cast(ChartSpec, definition)
