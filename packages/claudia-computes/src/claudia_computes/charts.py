"""Chart definitions: what a diagram draws, in computes' own terms (E6.6).

A :class:`ChartSpec` is computes' :class:`~claudia_core.DiagramDefinition` — the data a chart is drawn from, kept
apart from where it is shown. A chart may be shown as its own tab (``model.Chart``) or as a floating object on a
sheet (``ObjectBody.diagram``), and the two may show the very same ``ChartSpec``, exactly as two image objects may
share one :class:`~claudia_core.ImageAsset`. The kernel never looks inside a ``ChartSpec``; it is read back only
through :meth:`~claudia_computes.WorkbookModel.diagram_from_data`, the one door this module's data enters through.

Deliberately minimal for the first chart kind, the bar chart (E6.6's starting scope): ``kind`` is a plain string
and every other field is generic, so a line, pie or scatter chart can join ``CHART_KINDS`` later without changing
anything already stored.

A chart's range is frozen at the cells it was given, the same policy ``model.py`` already states for a floating
object's anchor: nothing here makes it follow a row or column insert or delete. Unlike an object's position, which
is a visual choice the model deliberately leaves alone, a chart's range is a *data reference* — closer in kind to
a formula's — so a future iteration may want it to follow structural edits the way ``RangeRef.adjusted`` already
lets a formula follow them. That is an open decision, not an oversight; it is called out again where
``Structure.apply`` touches cell references, and belongs in the decision log once one exists for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .limits import MAX_COLS, MAX_ROWS
from .refs import RangeRef

#: The version of this definition's own data format (mirrors ``shapes.FORMAT``).
FORMAT = 1
#: Chart kinds this version understands. Bar charts only, to begin with (E6.6) — more (line, pie, scatter) can
#: join this tuple later without touching anything already stored, which is the point of keeping it a tuple of
#: plain strings rather than, say, an enum baked into the wire format.
CHART_KINDS = ("bar",)
#: How the chart reads its range: each column is a series, or each row is.
SERIES_IN = ("columns", "rows")
MAX_TITLE_CHARS = 120

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_KEYS = {"format", "id", "kind", "range", "series_in", "title", "x_title", "y_title", "legend", "gridlines"}
_REQUIRED = ("format", "id", "kind", "range")


class ChartError(ValueError):
    """A chart definition that is not right; the message names the part and says what is wrong."""


def _check_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ChartError("id: lower-case letters, digits, '-' and '_', starting with a letter, at most 40 characters")
    return value


def _check_kind(value: object) -> str:
    if value not in CHART_KINDS:
        raise ChartError(f"kind: one of {', '.join(CHART_KINDS)}, not {value!r}")
    return value


def _check_series_in(value: object) -> str:
    if value not in SERIES_IN:
        raise ChartError(f"series_in: one of {', '.join(SERIES_IN)}, not {value!r}")
    return value


def _check_title(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.isprintable():
        raise ChartError(f"{name}: must be a line of text")
    if len(value) > MAX_TITLE_CHARS:
        raise ChartError(f"{name}: at most {MAX_TITLE_CHARS} characters")
    return value


def _check_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ChartError(f"{name}: must be true or false")
    return value


def _check_range(value: object) -> RangeRef:
    if not isinstance(value, dict):
        raise ChartError("range: must be a cell range")
    try:
        range_ = RangeRef.from_dict(value)
    except (KeyError, TypeError, ValueError) as error:
        raise ChartError(f"range: {error}") from None
    if range_.sheet is None:
        # Unlike a formula, a definition has no sheet of its own to default to: it may be shown from a different
        # sheet entirely (a floating object) or from none at all (a chart tab), so "the current sheet" is not a
        # meaningful answer here. The range must always say which sheet it reads.
        raise ChartError("range: a chart's range must name its sheet")
    return range_


@dataclass(frozen=True)
class ChartSpec:
    """What one chart draws: a range of cells and how to read it, plus its titles and whether it carries a
    legend or gridlines. computes' :class:`~claudia_core.DiagramDefinition` (E6.6).

    Build one from stored or wire data with :meth:`from_data`, which refuses anything the format does not
    allow; :meth:`~claudia_computes.WorkbookModel.diagram_from_data` additionally checks that ``range`` fits a
    sheet this document actually has, which this class alone cannot know."""

    id: str
    kind: str
    range: RangeRef
    series_in: str = "columns"
    title: str = ""
    x_title: str = ""
    y_title: str = ""
    legend: bool = True
    gridlines: bool = True

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        return {
            "format": FORMAT,
            "id": self.id,
            "kind": self.kind,
            "range": self.range.to_dict(),
            "series_in": self.series_in,
            "title": self.title,
            "x_title": self.x_title,
            "y_title": self.y_title,
            "legend": self.legend,
            "gridlines": self.gridlines,
        }

    @classmethod
    def from_data(cls, data: object) -> ChartSpec:
        """Read the plain-data form; raises :class:`ChartError` naming the first thing that is wrong. Does not
        know whether ``range`` names a sheet this document has — that is
        :meth:`~claudia_computes.WorkbookModel.diagram_from_data`'s business, the one door this data enters
        through."""
        if not isinstance(data, dict):
            raise ChartError("a chart definition is one JSON object")
        unknown = sorted(str(key) for key in set(data) - _KEYS)
        if unknown:
            raise ChartError(f"unknown key {unknown[0]!r}: a chart has {', '.join(sorted(_KEYS))}")
        for key in _REQUIRED:
            if key not in data:
                raise ChartError(f"missing {key!r}")
        if data["format"] != FORMAT or isinstance(data["format"], bool):
            raise ChartError(f"format: this version reads format {FORMAT}, the data says {data['format']!r}")
        return cls(
            id=_check_id(data["id"]),
            kind=_check_kind(data["kind"]),
            range=_check_range(data["range"]),
            series_in=_check_series_in(data.get("series_in", "columns")),
            title=_check_title(data.get("title", ""), "title"),
            x_title=_check_title(data.get("x_title", ""), "x_title"),
            y_title=_check_title(data.get("y_title", ""), "y_title"),
            legend=_check_bool(data.get("legend", True), "legend"),
            gridlines=_check_bool(data.get("gridlines", True), "gridlines"),
        )


def in_bounds(range_: RangeRef) -> bool:
    """Whether a range's far corner is still inside a sheet of the maximum size (the near corner always is:
    :class:`~claudia_computes.RangeRef` never holds a negative row or column)."""
    return range_.last.row < MAX_ROWS and range_.last.col < MAX_COLS
