"""How the cells of a file look, as the workbook's styles and number formats (E6.14, D348, D349).

xlsx and ods files say what a cell looks like in two ways: by a *named* style ("Heading 1", "Currency", "Note") and,
far more often, by *direct formats* that a person put on a cell -- bold here, a grey fill there, a number with
``"MWh"`` behind it. claudia has no direct formats (D306): every cell's look is a style, and every style can be named
for what it is for. So reading a file turns its looks into styles:

* the file's default look (Excel's *Normal*, LibreOffice's *Default*) is the workbook's **Body text**: its font, size
  and colour become Body text's, so an imported sheet looks as it did;
* each named style the cells use becomes a style of the same name, based on Body text;
* each different combination of direct formats becomes a **provisional style** (``to_name``), based on the named style
  it deviates from and named by what differs: ``Body text · bold, grey fill, MWh``. They wait in the *to name* list
  (E9.7) until somebody gives them a name for their purpose -- or merges them with a style that has one;
* a number format becomes one of the workbook's named formats (D348), its provisional name saying what it shows.

Then the sheet's cells, rows and columns get those styles as style ranges (E6.13): runs of equal cells are merged
into rectangles, so a formatted table costs a few ranges, not one per cell. Whatever a file's look has that a style
cannot hold (a rotated text, a pattern fill, shrinking to fit) is reported per cell as a ``look`` loss naming it.

The file formats each read their own XML into :class:`Look` objects (:mod:`.xlsx_looks`, :mod:`.ods_looks`); the
rest -- styles, names, ranges -- is this module's and the same for both (the parity rule).
"""

from __future__ import annotations

import colorsys
import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache

from claudia_computes import CellStyles, NumberFormat, Sheet, WorkbookModel
from claudia_computes.cellstyles import CELL_SLOTS, DEFAULT_CELL_STYLE, MAX_STYLE_RANGES, Piece
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.numformats import SHORT_DATE, check_code, describe, kind_of
from claudia_core import StyleDef
from claudia_core.css import CssError, validate_css
from claudia_core.facets import BOX_FACET, PARAGRAPH_FACET, TEXT_FACET
from claudia_core.styles import palette_colours

#: The code of a number format that shows a number as it comes (Excel's *General*, LibreOffice's *Standard*).
GENERAL = "General"
#: The font every program has a metric twin of on a free system (same widths, so a sheet keeps its line breaks).
_TWINS = {
    "calibri": "Carlito",
    "cambria": "Caladea",
    "arial": "'Liberation Sans'",
    "helvetica": "'Liberation Sans'",
    "times new roman": "'Liberation Serif'",
    "courier new": "'Liberation Mono'",
}
_SERIF = {"cambria", "times new roman", "georgia", "garamond", "liberation serif", "caladea", "book antiqua"}
_MONO = {"courier new", "consolas", "courier", "liberation mono", "dejavu sans mono", "lucida console"}
#: What a property of a cell's look is when the file does not set it: a deviation that takes a parent's property
#: away writes this (a cell that is *not* bold under a bold heading).
_PLAIN = {
    "font-weight": "normal",
    "font-style": "normal",
    "text-decoration": "none",
    "color": "@text",
    "background-color": "transparent",
    "border-top": "none",
    "border-right": "none",
    "border-bottom": "none",
    "border-left": "none",
    "text-align": "start",
    "vertical-align": "bottom",
    "white-space": "nowrap",
    "padding-left": "0pt",
}
_SIDES = ("top", "right", "bottom", "left")
_PURPOSE_NAMED = "cells the file gave this style"
_PURPOSE_DIRECT = "cells the file formatted directly: name it for what they are for"


@dataclass(frozen=True)
class Look:
    """What one look of a file's cells sets: CSS a style may hold (all of it, not only what differs from a parent),
    a number format code, and what the file sets that no style can (``rotation``, ``pattern``...)."""

    css: tuple[tuple[str, str], ...] = ()
    code: str = GENERAL
    unmapped: tuple[str, ...] = ()

    @classmethod
    def of(cls, css: Mapping[str, str], code: str = GENERAL, unmapped: Iterable[str] = ()) -> Look:
        """A look from a dictionary of CSS (in any order: a look is the same whatever order the file wrote it)."""
        return cls(tuple(sorted(css.items())), code, tuple(sorted(set(unmapped))))

    @property
    def style(self) -> dict[str, str]:
        """The CSS as a dictionary."""
        return dict(self.css)

    @property
    def shows_dates(self) -> bool:
        """Does the number format show a number as a date or a time?"""
        return _dated(self.code)


@cache
def _dated(code: str) -> bool:
    return code != GENERAL and kind_of(code) in ("date", "time")


# ------------------------------------------------------------------------------------------------ CSS from a file
def checked(prop: str, value: str) -> str | None:
    """``value`` as the clean CSS a style may hold for ``prop``, or ``None`` when no style may hold it."""
    try:
        return validate_css({prop: value})[prop]
    except CssError:
        return None


def font_family(name: str) -> str | None:
    """A font name as a family list with its free metric twin and a generic family: ``Calibri, Carlito,
    sans-serif``. ``None`` for a name no style may hold."""
    low = name.strip().lower()
    if not low:
        return None
    named = name.strip() if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", name.strip()) else f"'{name.strip()}'"
    generic = "serif" if low in _SERIF else "monospace" if low in _MONO else "sans-serif"
    parts = [named]
    if low in _TWINS:
        parts.append(_TWINS[low])
    parts.append(generic)
    return checked("font-family", ", ".join(parts))


def first_family(css_family: str) -> str:
    """The first font of a family list, without quotes: the one a file names."""
    return css_family.split(",")[0].strip().strip("'\"")


def size_text(points: float) -> str:
    """A size in points as CSS: ``11pt``, ``10.5pt``."""
    return f"{points:g}pt"


# ------------------------------------------------------------------------------------------------ naming a look
def colour_name(colour: str) -> str:
    """A word or two for a colour, for a person reading a provisional name: ``grey``, ``light blue``, ``dark red``.
    A palette role keeps its own name (``@accent`` -> ``accent``), except the text colour, which is the default."""
    if colour.split("/")[0] == "@text":
        return "default"
    if colour.startswith("@"):
        return colour[1:].split("/")[0]
    if colour == "transparent":
        return "no"
    rgb = solid(colour)
    if rgb is None:
        return colour
    red, green, blue = (int(rgb[i : i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, saturation = colorsys.rgb_to_hls(red, green, blue)
    if light > 0.94:  # noqa: PLR2004 (the edges of the colour words)
        return "white"
    if light < 0.1:  # noqa: PLR2004
        return "black"
    shade = "light " if light > 0.75 else "dark " if light < 0.3 else ""  # noqa: PLR2004
    if saturation < 0.15:  # noqa: PLR2004
        return f"{shade}grey"
    return shade + _hue_word(hue * 360)


def _hue_word(degrees: float) -> str:
    for edge, word in ((15, "red"), (48, "orange"), (70, "yellow"), (165, "green"), (195, "teal"), (255, "blue")):
        if degrees < edge:
            return word
    return "purple" if degrees < 290 else "pink" if degrees < 345 else "red"  # noqa: PLR2004


def _border_words(diff: Mapping[str, str]) -> list[str]:
    sides = [side for side in _SIDES if f"border-{side}" in diff]
    if not sides:
        return []
    drawn = [side for side in sides if diff[f"border-{side}"] != "none"]
    words = []
    if drawn:
        width, line, colour = diff[f"border-{drawn[0]}"].split(" ", 2)
        kind = ("thick " if float(re.sub(r"[a-z]+$", "", width) or 1) > 1 else "") + (
            "" if line == "solid" else f"{line} "
        )
        tint = "" if colour.startswith("@text") else f"{colour_name(colour)} "
        if len(drawn) == len(_SIDES):
            words.append(f"{kind}{tint}frame")
        else:
            where = {"top": "above", "bottom": "below", "left": "left", "right": "right"}
            words.append(f"{kind}{tint}line " + " and ".join(where[side] for side in drawn))
    if len(drawn) < len(sides):
        words.append("no border")
    return words


_ALIGN_WORDS = {"center": "centred", "right": "right-aligned", "left": "left-aligned", "justify": "justified"}
_VALIGN_WORDS = {"top": "at the top", "middle": "vertically centred", "bottom": "at the bottom"}


def difference_words(diff: Mapping[str, str]) -> list[str]:
    """What a deviation changes, in a few words each, in the order a person reads a cell: font, weight, colour,
    fill, lines, alignment."""
    words: list[str] = []
    if "font-family" in diff:
        words.append(first_family(diff["font-family"]))
    if "font-size" in diff:
        words.append(diff["font-size"])
    weight = diff.get("font-weight")
    if weight is not None:
        words.append("not bold" if weight in ("normal", "lighter", "100", "200", "300", "400") else "bold")
    if "font-style" in diff:
        words.append("upright" if diff["font-style"] == "normal" else "italic")
    decoration = diff.get("text-decoration")
    if decoration is not None:
        words.append(
            "no underline"
            if decoration == "none"
            else "struck through"
            if "line-through" in decoration
            else "underlined"
        )
    if "color" in diff:
        words.append(f"{colour_name(diff['color'])} text")
    if "background-color" in diff:
        words.append(f"{colour_name(diff['background-color'])} fill")
    words.extend(_border_words(diff))
    if "text-align" in diff:
        words.append(_ALIGN_WORDS.get(diff["text-align"], "aligned by content"))
    if "vertical-align" in diff:
        words.append(_VALIGN_WORDS[diff["vertical-align"]])
    if "white-space" in diff:
        words.append("not wrapped" if diff["white-space"] == "nowrap" else "wrapped")
    if "padding-left" in diff:
        words.append("not indented" if diff["padding-left"] in ("0pt", "0px", "0") else "indented")
    return words


def difference(parent: Mapping[str, str], child: Mapping[str, str]) -> dict[str, str]:
    """The CSS a style based on a style that looks like ``parent`` needs to look like ``child``: what ``child`` sets
    differently, and what ``parent`` sets that ``child`` does not, taken back to how a cell looks without it."""
    diff = {prop: value for prop, value in child.items() if parent.get(prop) != value}
    for prop in parent:
        if prop not in child and prop in _PLAIN and parent[prop] != _PLAIN[prop]:
            diff[prop] = _PLAIN[prop]
    return diff


# ------------------------------------------------------------------------------------------------ styles from looks
@dataclass
class LookImport:
    """Turns a file's looks into the styles and number formats of ``model`` -- each look once, however many cells
    have it. ``normal`` is the file's default look of a cell; it becomes Body text's."""

    model: WorkbookModel
    normal: Look
    _named: dict[Hashable, tuple[str, Look]] = field(default_factory=dict)
    _named_ids: dict[Hashable, str] = field(default_factory=dict)
    _direct: dict[tuple[str, Look], str] = field(default_factory=dict)
    _formats: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        body = self.model.styles.get(DEFAULT_CELL_STYLE)
        own = dict(body.css)
        own.update({prop: value for prop, value in self.normal.css if prop in ("font-family", "font-size", "color")})
        own["vertical-align"] = self.normal.style.get("vertical-align", "bottom")
        self.model.styles.set_css(DEFAULT_CELL_STYLE, own)
        if self.normal.code != GENERAL:
            self._set_format(DEFAULT_CELL_STYLE, self.format_id(self.normal.code))

    def name(self, key: Hashable, name: str, look: Look) -> None:
        """Say that the file has a named style ``name`` (known to the file as ``key``) that looks like ``look``. It
        becomes a style only when a cell uses it. The file's default style is not named: it is Body text."""
        self._named[key] = (name, look)

    def look_of(self, key: Hashable | None) -> Look:
        """The look of a named style by its key; the default look for ``None`` or a key the file does not name."""
        return self._named[key][1] if key in self._named else self.normal

    def style_for(self, look: Look, parent: Hashable | None = None) -> str:
        """The id of the style a cell with ``look`` gets, where the file says the cell has the named style
        ``parent``: that style itself when the cell looks just like it, else a provisional style based on it."""
        parent_id = self._named_style(parent)
        base = self.look_of(parent if parent_id != DEFAULT_CELL_STYLE else None)
        diff = difference(base.style, look.style)
        if not diff and look.code == base.code:
            return parent_id
        known = self._direct.get((parent_id, look))
        if known is not None:
            return known
        style_id = self._add(parent_id, diff, look.code if look.code != base.code else None)
        self._direct[(parent_id, look)] = style_id
        return style_id

    def format_id(self, code: str) -> str:
        """The id of the workbook's number format with ``code``, made with a provisional name the first time."""
        if code in self._formats:
            return self._formats[code]
        book = self.model.number_formats
        known = book.by_code(code)
        if known is None:
            check_code(code)
            number = len(book) + 1
            while f"format-{number}" in book:
                number += 1
            known = NumberFormat(f"format-{number}", book.free_name(describe(code)), code, to_name=True)
            book.add(known)
        self._formats[code] = known.id
        return known.id

    def _named_style(self, key: Hashable | None) -> str:
        if key is None or key not in self._named:
            return DEFAULT_CELL_STYLE
        if key in self._named_ids:
            return self._named_ids[key]
        name, look = self._named[key]
        styles = self.model.styles
        same = self._same_named(name, look)
        if same is not None:  # the workbook's own style, come back from a file claudia wrote
            self._named_ids[key] = same
            return same
        css = difference(self.normal.style, look.style)
        style_id = styles.unique_id(name)
        styles.add(StyleDef(style_id, self._free_name(name), _PURPOSE_NAMED, DEFAULT_CELL_STYLE, css))
        if look.code != self.normal.code:
            self._set_format(style_id, self.format_id(look.code))
        self._named_ids[key] = style_id
        return style_id

    def _same_named(self, name: str, look: Look) -> str | None:
        """The workbook's style called ``name``, if it changes Body text the way ``look`` changes the file's
        default look -- its palette roles taken as the colours a file writes for them."""
        styles = self.model.styles
        found = next((style for style in styles if style.name.casefold() == name.casefold()), None)
        if found is None or found.kind != "paragraph" or found.id == DEFAULT_CELL_STYLE:
            return None
        colours = palette_colours(self.model) or {}
        body = _comparable(styles.resolved(DEFAULT_CELL_STYLE, colours))
        own = {prop: value for prop, value in _comparable(styles.resolved(found.id, colours)).items()
               if body.get(prop) != value}  # fmt: skip
        wanted = _comparable(difference(self.normal.style, look.style))
        format_id = styles.number_format(found.id)
        book = self.model.number_formats
        code = book.get(format_id).code if format_id is not None and format_id in book else GENERAL
        return found.id if own == wanted and code == look.code else None

    def _add(self, parent_id: str, css: dict[str, str], code: str | None) -> str:
        styles = self.model.styles
        words = difference_words(css)
        if code is not None:
            words.append("short date" if code == SHORT_DATE else describe(code))
        name = self._free_name(_provisional(styles.get(parent_id).name, words))
        style_id = styles.unique_id(name)
        styles.add(StyleDef(style_id, name, _PURPOSE_DIRECT, parent_id, css, to_name=True))
        if code is not None:
            self._set_format(style_id, self.format_id(code))
        return style_id

    def _set_format(self, style_id: str, format_id: str) -> None:
        self.model.styles.set_number_format(style_id, format_id)

    def _free_name(self, name: str) -> str:
        styles = self.model.styles
        candidate, number = name, 1
        while styles.name_taken(candidate):
            number += 1
            suffix = f" {number}"
            candidate = name[: _NAME_ROOM - len(suffix)] + suffix
        return candidate


_NAME_ROOM = 60


def _comparable(css: Mapping[str, str]) -> dict[str, str]:
    """CSS as a file gives it back: colours as ``#RRGGBB``, a weight as bold or not."""
    out = {}
    for prop, value in css.items():
        if prop in ("color", "background-color"):
            rgb = solid(value)
            out[prop] = "none" if rgb is None else f"#{rgb}"
        elif prop.startswith("border-") and value != "none":
            width, line, colour = value.split(" ", 2)
            out[prop] = f"{width} {line} #{solid(colour)}"
        elif prop == "font-weight":
            out[prop] = "bold" if value == "bold" or (value.isdigit() and int(value) >= 600) else "normal"  # noqa: PLR2004
        else:
            out[prop] = value
    return out


def _provisional(parent: str, words: list[str]) -> str:
    """``Body text · bold, grey fill, MWh``: as many of the words as fit a style name, then ``…``."""
    name = f"{parent} ·"
    for i, word in enumerate(words):
        piece = (" " if i == 0 else ", ") + word
        if len(name) + len(piece) > _NAME_ROOM - 3:  # room for ", …"
            return name + ", …" if i else f"{parent} · …"[:_NAME_ROOM]
        name += piece
    return name if words else f"{parent} · changed"


# ------------------------------------------------------------------------------------------------ painting a sheet
@dataclass
class SheetLooks:
    """Which style the parts of one sheet have, as a file says it: runs of ``columns`` and ``rows`` (first, last,
    style), the ``cells`` whose style differs from their row's or column's, and ``blocks`` of such cells a file
    already gives as rectangles (a repeated run of an ods file)."""

    cells: dict[tuple[int, int], str] = field(default_factory=dict)
    rows: list[tuple[int, int, str]] = field(default_factory=list)
    columns: list[tuple[int, int, str]] = field(default_factory=list)
    blocks: list[Piece] = field(default_factory=list)


def paint(sheet: Sheet, looks: SheetLooks) -> int:
    """Give ``sheet`` the style ranges ``looks`` describes (both slots of a cell take the same style, D311) and
    return how many cells could not get theirs because the sheet would hold more than ``MAX_STYLE_RANGES`` ranges
    (the largest rectangles are kept). A run of plain rows is kept only where it crosses a styled column."""
    columns = [((0, c0, MAX_ROWS - 1, c1), style) for c0, c1, style in looks.columns if style != DEFAULT_CELL_STYLE]
    rows = [
        ((r0, 0, r1, MAX_COLS - 1), style)
        for r0, r1, style in _joined(looks.rows)
        if style != DEFAULT_CELL_STYLE or columns
    ]
    ranges = sorted([*_rectangles(looks.cells), *looks.blocks], key=lambda piece: -_size(piece[0]))
    room = max(MAX_STYLE_RANGES // len(CELL_SLOTS) - len(columns) - len(rows), 0)
    kept, dropped = ranges[:room], ranges[room:]
    data = [
        [slot, layer, *area, style]
        for layer, pieces in (("column", columns), ("row", rows), ("range", kept))
        for area, style in pieces
        for slot in CELL_SLOTS
    ]
    sheet.cell_styles = CellStyles.from_data(data)
    return sum(_size(area) for area, _ in dropped)


def runs_of(styles: Mapping[int, str]) -> list[tuple[int, int, str]]:
    """Lines (rows or columns) with a style each as runs of following lines with the same style."""
    return _joined((line, line, style) for line, style in sorted(styles.items()))


def _joined(runs: Iterable[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    joined: list[tuple[int, int, str]] = []
    for first, last, style in sorted(runs):
        if joined and joined[-1][2] == style and joined[-1][1] == first - 1:
            joined[-1] = (joined[-1][0], last, style)
        else:
            joined.append((first, last, style))
    return joined


class Lines[T]:
    """Runs of lines (rows or columns) with a style (or a pair of styles) each, to ask which a line has."""

    def __init__(self, runs: Iterable[tuple[int, int, T]]) -> None:
        self._runs = sorted(runs, key=lambda run: run[0])
        self._firsts = [first for first, _, _ in self._runs]

    def at(self, line: int) -> T | None:
        """The style a run gives ``line``, if one covers it."""
        index = bisect_right(self._firsts, line) - 1
        if index >= 0 and self._runs[index][1] >= line:
            return self._runs[index][2]
        return None


def _size(area: tuple[int, int, int, int]) -> int:
    return (area[2] - area[0] + 1) * (area[3] - area[1] + 1)


def _rectangles(cells: Mapping[tuple[int, int], str]) -> list[Piece]:
    """Cells with styles as few rectangles: runs along each row, and equal runs of following rows joined."""
    by_row: dict[int, list[tuple[int, str]]] = {}
    for (row, col), style in cells.items():
        by_row.setdefault(row, []).append((col, style))
    open_: dict[tuple[int, int, str], int] = {}  # (c0, c1, style) -> first row, for rectangles reaching the last row
    done: list[Piece] = []
    last_row = None
    for row in sorted(by_row):
        runs = _runs(sorted(by_row[row]))
        still: dict[tuple[int, int, str], int] = {}
        for run in runs:
            first = open_.pop(run, row) if last_row == row - 1 else row
            still[run] = first
        for (c0, c1, style), first in open_.items():
            done.append(((first, c0, last_row, c1), style))  # type: ignore[arg-type]
        open_ = still
        last_row = row
    for (c0, c1, style), first in open_.items():
        done.append(((first, c0, last_row, c1), style))  # type: ignore[arg-type]
    return done


def _runs(cells: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    runs: list[tuple[int, int, str]] = []
    for col, style in cells:
        if runs and runs[-1][2] == style and runs[-1][1] == col - 1:
            runs[-1] = (runs[-1][0], col, style)
        else:
            runs.append((col, col, style))
    return runs


class Dressing:
    """Gives the sheets of one file their looks: each look of the file becomes a style once, for the whole workbook
    (``looks`` tells the named style a look starts from and the look itself, by the file's own key for it); the
    ranges are made per sheet. ``lost`` counts, per thing no style holds, the cells whose look has it."""

    def __init__(
        self,
        model: WorkbookModel,
        normal: Look,
        named: Iterable[tuple[Hashable, tuple[str, Look]]],
        looks: Callable[[Hashable], tuple[Hashable | None, Look]],
    ) -> None:
        self.making = LookImport(model, normal)
        for key, (name, look) in named:
            self.making.name(key, name, look)
        self._looks = looks
        self._styles: dict[Hashable, str] = {}
        self.lost: Counter[str] = Counter()

    def style(self, key: Hashable) -> str:
        """The style of the file's look ``key``."""
        if key not in self._styles:
            parent, look = self._looks(key)
            self._styles[key] = self.making.style_for(look, parent)
        return self._styles[key]

    def count(self, key: Hashable, cells: int = 1) -> None:
        """Count what the look ``key`` has that no style holds, for ``cells`` cells."""
        for what in self._looks(key)[1].unmapped:
            self.lost[what] += cells

    def dress(self, sheet: Sheet, looks: SheetLooks) -> None:
        """Give ``sheet`` the style ranges ``looks`` describes; the cells that found no room are counted."""
        dropped = paint(sheet, looks)
        if dropped:
            self.lost["too-many-ranges"] += dropped


# ------------------------------------------------------------------------------------------------ looks for a file
#: How many cells of a sheet's style ranges a fresh file writes one by one (rows and columns are written whole).
MAX_EXPORTED_CELLS = 500_000
_BOX_PROPERTIES = frozenset(BOX_FACET.properties)
_WORDS_PROPERTIES = frozenset(TEXT_FACET.properties) | frozenset(PARAGRAPH_FACET.properties)
_NAMED_COLOURS = {"black": "000000", "white": "FFFFFF", "red": "FF0000", "green": "008000", "blue": "0000FF",
                  "yellow": "FFFF00", "gray": "808080", "grey": "808080", "orange": "FFA500"}  # fmt: skip
_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")


@dataclass(frozen=True)
class CellLook:
    """How a cell looks in a file: the named style it starts from (``DEFAULT_CELL_STYLE`` for the file's default),
    the CSS of its box and words together with palette roles made colours, and its number format code."""

    parent: str
    css: tuple[tuple[str, str], ...]
    code: str = GENERAL

    @property
    def style(self) -> dict[str, str]:
        """The CSS as a dictionary."""
        return dict(self.css)


def solid(colour: str) -> str | None:
    """A CSS colour as ``RRGGBB`` for a file, a see-through one laid over white; ``None`` for none or one not known."""
    colour = colour.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", colour):
        return colour[1:].upper()
    if re.fullmatch(r"#[0-9a-f]{3}", colour):
        return "".join(ch * 2 for ch in colour[1:]).upper()
    match = _RGB.fullmatch(colour)
    if match:
        alpha = float(match.group(4)) if match.group(4) else 1.0
        parts = [round(int(match.group(i)) * alpha + 255 * (1 - alpha)) for i in (1, 2, 3)]
        return "".join(f"{min(part, 255):02X}" for part in parts)
    return _NAMED_COLOURS.get(colour)


def points(length: str) -> float | None:
    """A CSS length in points (``13px`` -> ``9.75``); ``None`` for one relative to something else."""
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(pt|px)", length.strip())
    if match is None:
        return None
    return float(match.group(1)) * (0.75 if match.group(2) == "px" else 1.0)


class LookExport:
    """The looks of a workbook's cells for a file: each pair of box and words styles a cell has as one
    :class:`CellLook`, made once. A provisional style is written as direct formats on top of the nearest named
    style it is based on -- what it was before an import made it a style -- and a named style as a named style of
    the file (D349)."""

    def __init__(self, model: WorkbookModel) -> None:
        self.model = model
        self.colours = palette_colours(model) or {}
        self._looks: dict[tuple[str, str], CellLook] = {}

    def named_parent(self, style_id: str) -> str:
        """The style itself if it has a name a person gave it, else its nearest parent that has one."""
        styles = self.model.styles
        for style in styles.chain(style_id)[::-1]:
            if not style.to_name:
                return style.id
        return DEFAULT_CELL_STYLE

    def code(self, style_id: str) -> str:
        """The number format code a style shows numbers with."""
        format_id = self.model.styles.number_format(style_id)
        if format_id is None or format_id not in self.model.number_formats:
            return GENERAL
        return self.model.number_formats.get(format_id).code

    def css(self, style_id: str, wanted: frozenset[str] | None = None) -> dict[str, str]:
        """A style's CSS with its parents taken in and its roles made colours, only the ``wanted`` properties. The
        text colour itself stays ``@text``: a file writes it as its *automatic* colour, which every program shows as
        its text colour (and reads back as ``@text``)."""
        resolved = self.model.styles.resolved(style_id, self.colours)
        for prop, value in self.model.styles.computed(style_id).items():
            if value == "@text" or value.endswith(" @text"):
                resolved[prop] = value
        return {prop: value for prop, value in resolved.items() if wanted is None or prop in wanted}

    def look(self, box: str, words: str) -> CellLook:
        """The look of a cell whose box slot holds ``box`` and whose words slot holds ``words`` (D311)."""
        key = (box, words)
        if key not in self._looks:
            css = self.css(words, _WORDS_PROPERTIES) | self.css(box, _BOX_PROPERTIES)
            css.pop("text-align", None)
            align = self._alignment(words) or self._alignment(box)
            if align is not None:
                css["text-align"] = align
            self._looks[key] = CellLook(self.named_parent(words), tuple(sorted(css.items())), self.code(words))
        return self._looks[key]

    def _alignment(self, style_id: str) -> str | None:
        """The alignment a style or a parent short of Body text sets: Body text's own is a paragraph's, and a cell
        without one aligns by what it holds (D318)."""
        for style in self.model.styles.chain(style_id)[::-1]:
            if style.id == DEFAULT_CELL_STYLE:
                return None
            if "text-align" in style.css:
                return style.css["text-align"]
        return None

    def named_look(self, style_id: str) -> CellLook:
        """The look a named style has by itself (both slots of a cell)."""
        return self.look(style_id, style_id)


@dataclass
class SheetStyling:
    """Which pair of box and words styles the parts of a sheet have, for a file that has no layers: every cell that
    needs one of its own (a cell of a style range, or a cell with content in a styled row or column), runs of rows
    and runs of columns. ``dropped`` counts the cells of style ranges left out for ``MAX_EXPORTED_CELLS``."""

    cells: dict[tuple[int, int], tuple[str, str]] = field(default_factory=dict)
    rows: list[tuple[int, int, tuple[str, str]]] = field(default_factory=list)
    columns: list[tuple[int, int, tuple[str, str]]] = field(default_factory=list)
    dropped: int = 0


def sheet_styling(sheet: Sheet) -> SheetStyling:
    """How the style ranges of ``sheet`` are written to a file whose cells, rows and columns each have one look."""
    everything = (0, 0, MAX_ROWS - 1, MAX_COLS - 1)
    styles = sheet.cell_styles
    whole = {slot: next((s for _, s in styles.pieces(slot, "sheet", everything)), None) for slot in CELL_SLOTS}
    rows = {slot: _line_runs(styles.pieces(slot, "row", everything), 0) for slot in CELL_SLOTS}
    columns = {slot: _line_runs(styles.pieces(slot, "column", everything), 1) for slot in CELL_SLOTS}
    styling = SheetStyling()
    own: dict[str, dict[tuple[int, int], str]] = {slot: {} for slot in CELL_SLOTS}
    budget = MAX_EXPORTED_CELLS
    for slot in CELL_SLOTS:
        for (r0, c0, r1, c1), style in sorted(styles.pieces(slot, "range", everything), key=lambda p: _size(p[0])):
            size = _size((r0, c0, r1, c1))
            if size > budget:
                styling.dropped += size
                continue
            budget -= size
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    own[slot][(r, c)] = style
    lines = {slot: (Lines(rows[slot]), Lines(columns[slot])) for slot in CELL_SLOTS}

    def at(slot: str, row: int, col: int) -> str:
        by_row, by_column = lines[slot]
        return own[slot].get((row, col)) or by_row.at(row) or by_column.at(col) or whole[slot] or DEFAULT_CELL_STYLE

    for row, col in sorted({*sheet.cells, *own["box"], *own["words"]}):
        pair = (at("box", row, col), at("words", row, col))
        if pair != (DEFAULT_CELL_STYLE, DEFAULT_CELL_STYLE):
            styling.cells[(row, col)] = pair
    plain = dict.fromkeys(CELL_SLOTS)
    styling.rows = _segments(rows, plain, MAX_ROWS)
    styling.columns = _segments(columns, whole, MAX_COLS)
    return styling


def _line_runs(pieces: Iterable[Piece], axis: int) -> list[tuple[int, int, str]]:
    return sorted((area[axis], area[axis + 2], style) for area, style in pieces)


def _segments(
    runs: Mapping[str, list[tuple[int, int, str]]], beneath: Mapping[str, str | None], limit: int
) -> list[tuple[int, int, tuple[str, str]]]:
    """Runs of lines on which the pair of styles (box, words) stays the same, where either slot has a run or a
    style ``beneath`` them all (the sheet's)."""
    edges = {edge for slot_runs in runs.values() for first, last, _ in slot_runs for edge in (first, last + 1)}
    if any(beneath.values()):
        edges |= {0, limit}
    found = {slot: Lines(slot_runs) for slot, slot_runs in runs.items()}
    out: list[tuple[int, int, tuple[str, str]]] = []
    ordered = sorted(edge for edge in edges if edge <= limit)
    for first, after in zip(ordered, ordered[1:], strict=False):
        picked = {slot: found[slot].at(first) or beneath[slot] for slot in CELL_SLOTS}
        if not any(picked.values()):
            continue
        pair = (picked["box"] or DEFAULT_CELL_STYLE, picked["words"] or DEFAULT_CELL_STYLE)
        if out and out[-1][2] == pair and out[-1][1] == first - 1:
            out[-1] = (out[-1][0], after - 1, pair)
        else:
            out.append((first, after - 1, pair))
    return out


# ------------------------------------------------------------------------------------------------ restyled cells
@dataclass
class Restyling:
    """What looks changed on a sheet between two states of a workbook: each cell with its new look, and runs of rows
    and of columns with theirs (``None``: the row or column has no look of its own any more)."""

    cells: dict[tuple[int, int], CellLook] = field(default_factory=dict)
    rows: list[tuple[int, int, CellLook | None]] = field(default_factory=list)
    columns: list[tuple[int, int, CellLook | None]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.cells or self.rows or self.columns)


def changed_styles(old: LookExport, new: LookExport) -> frozenset[str]:
    """The styles whose look in a file is not the same in the two workbooks: their CSS (with their parents'), their
    number format or the named style they are written as changed, or one of the two lacks them."""

    def signature(looks: LookExport, style_id: str) -> tuple:
        styles = looks.model.styles
        if style_id not in styles:
            return ()
        parent = looks.named_parent(style_id)
        return (tuple(sorted(looks.css(style_id).items())), looks.code(style_id), parent, styles.get(parent).name)

    ids = set(old.model.styles.ids()) | set(new.model.styles.ids())
    return frozenset(i for i in ids if signature(old, i) != signature(new, i))


def restyling(
    before: tuple[LookExport, Sheet], after: tuple[LookExport, Sheet], changed: frozenset[str] | None = None
) -> Restyling:
    """The looks that changed from ``before`` to ``after`` (each a workbook's looks and one of its sheets): a cell's
    look changes when its styles do or when a style it has was changed itself (``changed``, from
    :func:`changed_styles`, worked out once for all sheets)."""
    (old_looks, old_sheet), (new_looks, new_sheet) = before, after
    if changed is None:
        changed = changed_styles(old_looks, new_looks)
    if old_sheet.cell_styles.to_data() == new_sheet.cell_styles.to_data() and not (
        set(new_sheet.cell_styles.uses()) & changed
    ):
        return Restyling()
    old, new = sheet_styling(old_sheet), sheet_styling(new_sheet)
    old_at, new_at = _PairAt(old), _PairAt(new)
    result = Restyling()
    for row, col in sorted(old.cells.keys() | new.cells.keys()):
        look = new_looks.look(*new_at.cell(row, col))
        if look != old_looks.look(*old_at.cell(row, col)):
            result.cells[(row, col)] = look
    result.rows = _changed_lines(old.rows, new.rows, old_looks, new_looks)
    result.columns = _changed_lines(old.columns, new.columns, old_looks, new_looks)
    return result


class _PairAt:
    def __init__(self, styling: SheetStyling) -> None:
        self.cells = styling.cells
        self.rows = Lines(styling.rows)
        self.columns = Lines(styling.columns)

    def cell(self, row: int, col: int) -> tuple[str, str]:
        found = self.cells.get((row, col)) or self.rows.at(row) or self.columns.at(col)
        return found or (DEFAULT_CELL_STYLE, DEFAULT_CELL_STYLE)


def _changed_lines(
    old: list[tuple[int, int, tuple[str, str]]],
    new: list[tuple[int, int, tuple[str, str]]],
    old_looks: LookExport,
    new_looks: LookExport,
) -> list[tuple[int, int, CellLook | None]]:
    edges = sorted({edge for runs in (old, new) for first, last, _ in runs for edge in (first, last + 1)})
    old_at, new_at = Lines(old), Lines(new)
    out: list[tuple[int, int, CellLook | None]] = []
    for first, after in zip(edges, edges[1:], strict=False):
        was, now = old_at.at(first), new_at.at(first)
        was_look = None if was is None else old_looks.look(*was)
        now_look = None if now is None else new_looks.look(*now)
        if was_look == now_look:
            continue
        if out and out[-1][2] == now_look and out[-1][1] == first - 1:
            out[-1] = (out[-1][0], after - 1, now_look)
        else:
            out.append((first, after - 1, now_look))
    return out
