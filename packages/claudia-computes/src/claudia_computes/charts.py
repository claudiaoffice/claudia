"""Chart definitions: what a diagram draws, in computes' own terms (E6.6).

A :class:`ChartSpec` is computes' :class:`~claudia_core.DiagramDefinition` — the data a chart is drawn from, kept
apart from where it is shown. A chart may be shown as its own tab (``model.Chart``) or as a floating object on a
sheet (``ObjectBody.diagram``), and the two may show the very same ``ChartSpec``, exactly as two image objects may
share one :class:`~claudia_core.ImageAsset`. The kernel never looks inside a ``ChartSpec``; it is read back only
through :meth:`~claudia_computes.WorkbookModel.diagram_from_data`, the one door this module's data enters through.

Deliberately minimal for the first chart kind, the bar chart (E6.6's starting scope): ``kind`` is a plain string
and every other field is generic, so a line, pie or scatter chart can join ``CHART_KINDS`` later without changing
anything already stored.

A chart may instead read a **named result or table** (E6.5): ``source`` names it, ``source_scope`` says which sheet's
own name is meant (``None`` for a workbook-wide one), and the chart follows the name live — a ``SQL()`` result that
grows or moves is still the chart's data, which a frozen range could never be. A chart has exactly one of ``range``
and ``source``.

A chart's range is frozen at the cells it was given, the same policy ``model.py`` already states for a floating
object's anchor: nothing here makes it follow a row or column insert or delete. Unlike an object's position, which
is a visual choice the model deliberately leaves alone, a chart's range is a *data reference* — closer in kind to
a formula's — so a future iteration may want it to follow structural edits the way ``RangeRef.adjusted`` already
lets a formula follow them. That is an open decision, not an oversight; it is called out again where
``Structure.apply`` touches cell references, and belongs in the decision log once one exists for it.

:func:`figure_of` turns a definition plus already-read category and series data into the chart's Plotly figure
(data+layout); :meth:`~claudia_computes.WorkbookModel.chart_figure` is what actually reads the sheet, since this
module cannot import the model that owns the cells without a cycle (``model.py`` imports from here, not the
other way around).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .limits import MAX_COLS, MAX_ROWS
from .refs import RangeRef, SheetId

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
_KEYS = {
    "format",
    "id",
    "kind",
    "range",
    "source",
    "source_scope",
    "series_in",
    "header_row",
    "title",
    "x_title",
    "y_title",
    "legend",
    "gridlines",
}
_REQUIRED = ("format", "id", "kind")


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


def _check_source(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise ChartError("source: must be the name of a named range or table")
    return value


def _check_source_scope(value: object) -> SheetId | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ChartError("source_scope: a sheet id, or null for a name of the whole workbook")
    return SheetId(value)


@dataclass(frozen=True)
class ChartSpec:
    """What one chart draws: a range of cells and how to read it, plus its titles and whether it carries a
    legend or gridlines. computes' :class:`~claudia_core.DiagramDefinition` (E6.6).

    Build one from stored or wire data with :meth:`from_data`, which refuses anything the format does not
    allow; :meth:`~claudia_computes.WorkbookModel.diagram_from_data` additionally checks that ``range`` fits a
    sheet this document actually has, which this class alone cannot know."""

    def __post_init__(self) -> None:
        if (self.range is None) == (not self.source):
            raise ChartError("a chart reads either a range or a named source, one of the two")
        if self.source_scope is not None and not self.source:
            raise ChartError("source_scope: only a named source has a scope")

    id: str
    kind: str
    range: RangeRef | None = None
    #: The name of a named range or table (or a ``SQL()`` result) to read instead of ``range``; empty when the
    #: chart reads a range. A named source always has a header row — a name is a table, and a table has headers.
    source: str = ""
    #: The sheet a sheet-scoped ``source`` belongs to; ``None`` for a name of the whole workbook.
    source_scope: SheetId | None = None
    series_in: str = "columns"
    #: Whether the range's first row is a header — the series' names when ``series_in`` is "columns", the
    #: category labels when it is "rows" — rather than a row of data like every other (E6.6, header-row bug).
    #: Defaults to ``True``, the "select your data including its headers" a spreadsheet chart usually assumes;
    #: a range with no room for a header on this axis (one row) ignores it, same as before this field existed
    #: (:meth:`~claudia_computes.WorkbookModel.chart_figure`). The first *column* has no equivalent toggle yet —
    #: only the row convention turned out to need one in practice, read by shape alone as it always has.
    header_row: bool = True
    title: str = ""
    x_title: str = ""
    y_title: str = ""
    legend: bool = True
    gridlines: bool = True

    def to_data(self) -> dict:
        """The plain-data form: what the log stores and clients are sent."""
        where: dict = {"range": self.range.to_dict()} if self.range is not None else {}
        if self.source:
            where = {"source": self.source, "source_scope": self.source_scope}
        return {
            "format": FORMAT,
            "id": self.id,
            "kind": self.kind,
            **where,
            "series_in": self.series_in,
            "header_row": self.header_row,
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
            range=_check_range(data["range"]) if data.get("range") is not None else None,
            source=_check_source(data["source"]) if data.get("source") is not None else "",
            source_scope=_check_source_scope(data.get("source_scope")),
            series_in=_check_series_in(data.get("series_in", "columns")),
            header_row=_check_bool(data.get("header_row", True), "header_row"),
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


#: A fixed, validated categorical order for a chart's series (E6.6) — teal, iris, rose, then a darkened
#: "chart-safe" apricot. The suite's own four app/brand hues (D-prefixed design-system.md), reordered for
#: adjacency and with apricot darkened from the brand `#F2A057` to `#C97A33`: the brand tone is too light to
#: clear the categorical lightness band and sits too close to rose for a deuteranope at this order's other
#: end. Checked with the dataviz skill's `validate_palette.js --mode light`: lightness band, chroma floor, CVD
#: adjacent-pair separation, the normal-vision floor and contrast against the paper surface all pass in this
#: exact order — reordering or cycling these four breaks the CVD check again, so a chart never cycles them; a
#: fifth series folds into "Other" rather than inventing a fifth hue (E6.6 is bar charts only, so this has not
#: come up yet). Not yet re-validated against a dark surface (the suite has no dark mode wired up either,
#: UX-05) — worth a look together, not blocking this round.
BAR_COLORS: tuple[str, ...] = ("#13917F", "#5B4BC4", "#D6477A", "#C97A33")


@dataclass(frozen=True)
class ChartSeries:
    """One series' name and values, already read off a sheet in the order the chart will draw them — the shape
    :meth:`~claudia_computes.WorkbookModel.chart_figure` passes to :func:`figure_of`."""

    name: str
    values: tuple[float, ...]


def figure_of(spec: ChartSpec, categories: Sequence[str], series: Sequence[ChartSeries]) -> dict:
    """A chart's Plotly figure — ``{"data": [...], "layout": {...}}`` — from its definition plus the category
    labels and per-series values a sheet's live cells gave (:meth:`~claudia_computes.WorkbookModel.chart_figure`
    reads those; this function only shapes them, so it needs no model and is plain to test). The **server**
    builds this, not either client, so the web and desktop shells draw byte-identical charts from the same JSON
    (`e0-3-web-surface-notes.md`'s "Figure JSON... is provided by the doc server").

    The one door a second chart kind's own trace shape would enter through — with only ``"bar"`` in
    :data:`CHART_KINDS` so far, a dispatch table would have exactly one entry, so this stays a plain function
    until a line or scatter kind actually shows up (mirrors why ``CHART_KINDS`` itself is a tuple, not a
    dispatch-worthy type yet)."""
    if spec.kind != "bar":  # pragma: no cover - unreachable while CHART_KINDS == ("bar",); guards the day it grows
        raise ChartError(f"kind: no figure builder for {spec.kind!r} yet")
    single = len(series) <= 1
    data = [
        {
            "type": "bar",
            "name": one.name,
            "x": list(categories),
            "y": list(one.values),
            "marker": {"color": BAR_COLORS[i % len(BAR_COLORS)]},
        }
        for i, one in enumerate(series)
    ]
    return {
        "data": data,
        "layout": {
            "title": {"text": spec.title},
            "xaxis": {"title": {"text": spec.x_title}, "showgrid": False},
            "yaxis": {"title": {"text": spec.y_title}, "showgrid": spec.gridlines},
            "showlegend": spec.legend and not single,  # a single series needs no legend box (dataviz skill)
            "barmode": "group",
            "bargap": 0.2,
            "bargroupgap": 0.1,
        },
    }
