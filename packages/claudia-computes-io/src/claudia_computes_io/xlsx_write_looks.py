"""The looks of a workbook's cells in a new xlsx file, through openpyxl (E6.14, D379).

Body text is the file's *Normal*: its font is the workbook's default font. A style with a name a person gave it
becomes a named cell style of the file, so Excel shows it under *Cell Styles* with that name. A cell's look is that
named style (or Normal) with the cell's own look on top, as direct formats -- which is how a provisional style goes
out: the direct formats it came from. The style ranges of rows and columns become row and column formats; those of
cells are written into each cell (:func:`~claudia_computes_io.cell_looks.sheet_styling`).
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side
from openpyxl.utils import get_column_letter

from claudia_computes import Sheet, WorkbookModel
from claudia_computes.cellstyles import DEFAULT_CELL_STYLE

from .cell_looks import GENERAL, CellLook, LookExport, first_family, points, sheet_styling, solid

_SIDES = {
    ("1", "solid"): "thin",
    ("2", "solid"): "medium",
    ("3", "solid"): "thick",
    ("1", "dashed"): "dashed",
    ("2", "dashed"): "mediumDashed",
    ("3", "dashed"): "mediumDashed",
    ("1", "dotted"): "dotted",
    ("2", "dotted"): "dotted",
    ("3", "dotted"): "dotted",
    ("1", "double"): "double",
    ("2", "double"): "double",
    ("3", "double"): "double",
}
_ALIGN = {"left": "left", "start": "left", "center": "center", "right": "right", "end": "right", "justify": "justify"}
_VALIGN = {"top": "top", "middle": "center", "bottom": "bottom"}
_INDENT_POINTS = 9
#: The most rows of one run of rows written as row formats: beyond, a run is cut there (a loss).
MAX_STYLED_ROWS = 100_000


class _Parts:
    """openpyxl's pieces of one look, made once."""

    def __init__(self, look: CellLook) -> None:
        css = look.style
        self.font = _font(css)
        self.fill = _fill(css)
        self.border = _border(css)
        self.alignment = _alignment(css)
        self.code = look.code


def _font(css: Mapping[str, str]) -> Font:
    size = points(css.get("font-size", ""))
    colour = solid(css.get("color", ""))
    decoration = css.get("text-decoration", "")
    weight = css.get("font-weight", "normal")
    return Font(
        name=first_family(css["font-family"]) if "font-family" in css else None,
        sz=round(size * 2) / 2 if size else None,  # Excel sizes go in half points
        b=weight in {"bold", "bolder"} or (weight.isdigit() and int(weight) >= 600),  # noqa: PLR2004
        i=css.get("font-style") in ("italic", "oblique"),
        u="single" if "underline" in decoration else None,
        strike="line-through" in decoration or None,
        color=None if colour is None else "FF" + colour,
    )


def _fill(css: Mapping[str, str]) -> PatternFill:
    colour = solid(css.get("background-color", "transparent"))
    return PatternFill() if colour is None else PatternFill("solid", fgColor="FF" + colour)


def _border(css: Mapping[str, str]) -> Border:
    sides = {}
    for side in ("top", "right", "bottom", "left"):
        value = css.get(f"border-{side}", "none")
        if value == "none":
            sides[side] = Side()
            continue
        width, line, colour = value.split(" ", 2)
        size = points(width)
        thickness = str(min(3, max(1, round(size / 0.75)))) if size else "1"
        rgb = solid(colour)
        style: Any = _SIDES.get((thickness, line), "thin")
        sides[side] = Side(style=style, color=None if rgb is None else "FF" + rgb)
    return Border(left=sides["left"], right=sides["right"], top=sides["top"], bottom=sides["bottom"])


def _alignment(css: Mapping[str, str]) -> Alignment:
    indent = points(css.get("padding-left", "0pt")) or 0
    return Alignment(
        horizontal=_ALIGN.get(css.get("text-align", "")),
        vertical=_VALIGN.get(css.get("vertical-align", "bottom"), "bottom"),
        wrap_text=css.get("white-space") in ("normal", "pre-wrap") or None,
        indent=round(indent / _INDENT_POINTS) if indent else 0,
    )


class XlsxLookWriter:
    """Writes the looks of one workbook into one openpyxl workbook."""

    def __init__(self, model: WorkbookModel, wb: openpyxl.Workbook) -> None:
        self.model = model
        self.wb = wb
        self.looks = LookExport(model)
        self._parts: dict[CellLook, _Parts] = {}
        self._named: dict[str, str] = {}
        self.dropped = 0
        normal = _Parts(self.looks.named_look(DEFAULT_CELL_STYLE))
        book: Any = wb  # (openpyxl keeps Normal and the default font where its types do not say)
        book._named_styles["Normal"].font = normal.font  # noqa: SLF001
        book._fonts[0] = normal.font  # noqa: SLF001

    def parts(self, look: CellLook) -> _Parts:
        if look not in self._parts:
            self._parts[look] = _Parts(look)
        return self._parts[look]

    def named(self, style_id: str) -> str | None:
        """The name of the file's named style for ``style_id``, added the first time (``None`` for Normal)."""
        if style_id == DEFAULT_CELL_STYLE:
            return None
        if style_id not in self._named:
            name = self.model.styles.get(style_id).name
            if name.casefold() == "normal":
                name = f"{name} (claudia)"
            parts = self.parts(self.looks.named_look(style_id))
            made = NamedStyle(name=name, font=parts.font, fill=parts.fill, border=parts.border)
            made.alignment = parts.alignment
            if parts.code != GENERAL:
                made.number_format = parts.code
            self.wb.add_named_style(made)
            self._named[style_id] = name
        return self._named[style_id]

    def dress(self, target, look: CellLook) -> None:  # noqa: ANN001 (an openpyxl cell, row or column)
        """Give a cell, a row or a column ``look``: its named style, then its own look on top."""
        name = self.named(look.parent)
        if name is not None:  # (openpyxl's own setter refuses rows and columns: the style's tuple is what it sets)
            book: Any = self.wb
            target._style = copy(book._named_styles[name].as_tuple())  # noqa: SLF001
        parts = self.parts(look)
        target.font = parts.font
        target.fill = parts.fill
        target.border = parts.border
        target.alignment = parts.alignment
        target.number_format = parts.code

    def sheet(self, sheet: Sheet, ws) -> None:  # noqa: ANN001 (openpyxl's worksheet)
        """Write the looks of ``sheet`` into ``ws``."""
        styling = sheet_styling(sheet)
        self.dropped += styling.dropped
        for first, last, (box, words) in styling.columns:
            letter = get_column_letter(first + 1)
            dimension = ws.column_dimensions[letter]
            dimension.min, dimension.max = first + 1, last + 1
            self.dress(dimension, self.looks.look(box, words))
        for first, last, (box, words) in styling.rows:
            end = min(last, first + MAX_STYLED_ROWS - 1)
            self.dropped += last - end
            look = self.looks.look(box, words)
            for row in range(first, end + 1):
                self.dress(ws.row_dimensions[row + 1], look)
        for (row, col), (box, words) in styling.cells.items():
            self.dress(ws.cell(row=row + 1, column=col + 1), self.looks.look(box, words))
