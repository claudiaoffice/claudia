"""Charts in an ods file (D462).

A chart of an ods file is a frame on a sheet (``draw:frame`` with a ``draw:object``) and, beside the sheet's own
content, a part of its own, ``Object 1/content.xml``, which is a small OpenDocument chart document: the kind of chart,
the titles, the legend and gridlines, and for each series the cells it reads (``Data.B2:Data.B5``) and the cells that
name it. The numbers are in the sheet, the chart only says where; the part also carries a copy of them (``local-table``)
for a program that does not calculate.

**What a chart of the model is in a file.** A bar chart of the model is one range with a header row and column the way
:meth:`~claudia_computes.WorkbookModel.chart_figure` reads it, so what is written is one series per column (or row)
of that range, named by its header, over categories from its first column (row). A chart that follows a named range or
table is written as the cells the name is today: a file has no chart that follows a name (``chart``, ``source``).

**What of a file the model can hold.** A frame of a bar chart that is drawn the way the model draws one, over one
range of one sheet of the file, in which the series are what the model would make of that range, is read as a
floating chart object (D462). Everything else, a chart of another kind, a stacked or a horizontal one, a chart over
several ranges, of a sheet that is not there, one that has series the range does not explain, is left alone in the
file and counted (``chart``): it is not read and it is not touched.

A chart is told apart from the others by where its frame sits, by its place in the document (the ``n``-th held chart is
``o{n}`` and its definition ``c{n}``), so that the model read from a file and the file it came from can be matched
again when an edit is patched in.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from lxml import etree

from claudia_computes import ChartSpec, SheetId, WorkbookModel
from claudia_computes.charts import BAR_COLORS
from claudia_computes.model import MIN_OBJECT_SIZE
from claudia_computes.refs import column_name
from claudia_odf_io import NS, local_name, qname, transform_of, xml_safe

from ._placed import Placed
from .chart_plan import Area, ReadChart, number_text, plan_from, plan_of, spec_of
from .ods_layout import _CM_PER_PIXEL, pixels_of, text_of  # noqa: PLC2701 (one length, one conversion)
from .ods_names import range_of

#: The media type of an embedded chart (the folder ``Object 1/`` in the manifest).
CHART_MEDIA = "application/vnd.oasis.opendocument.chart"
_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
_DECLARED = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items() if prefix != "xml")
_STYLE_OF_OBJECT = "plain-image"  # (a chart carries its own colours, as an image does)
_LABELS = {(True, True): "both", (True, False): "row", (False, True): "column", (False, False): "none"}
#: What a chart style may say that the model's bar chart does not: another direction, stacking, a third dimension.
_NOT_THE_MODELS = ("vertical", "stacked", "percentage", "three-dimensional", "deep", "lines", "symbol-type")

SheetIds = Callable[[str], SheetId | None]


def _q(name: str) -> str:
    return qname(name)


# ------------------------------------------------------------------------------------------------ addresses
def _sheet_text(name: str) -> str:
    return name if re.fullmatch(r"\w+", name) else "'" + name.replace("'", "''") + "'"


def _cell_text(cell: tuple[int, int]) -> str:
    return f"{column_name(cell[1])}{cell[0] + 1}"


def address(sheet: str, area: tuple[tuple[int, int], tuple[int, int]]) -> str:
    """``Data.B2:Data.B5``: the way a chart names cells (a single cell twice, as LibreOffice writes it)."""
    name = _sheet_text(sheet)
    return f"{name}.{_cell_text(area[0])}:{name}.{_cell_text(area[1])}"


def _read_area(text: str | None, sheet_ids: SheetIds) -> tuple[SheetId, tuple[tuple[int, int], tuple[int, int]]] | None:
    """The sheet and the cells an address of a chart names, or ``None`` for what is not one range of one sheet."""
    found = None if not text else range_of(text, sheet_ids)
    if found is None or found.sheet is None:
        return None
    return found.sheet, ((found.first.row, found.first.col), (found.last.row, found.last.col))


# ------------------------------------------------------------------------------------------------ writing
def _style(name: str, family: str, *properties: tuple[str, Mapping[str, str]]) -> str:
    inner = "".join(
        f"<style:{kind} " + " ".join(f'{key}="{value}"' for key, value in attributes.items()) + "/>"
        for kind, attributes in properties
    )
    return f'<style:style style:name="{name}" style:family="{family}">{inner}</style:style>'


def _escape(text: str) -> str:
    return xml_safe(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _title(text: str) -> str:
    return f"<chart:title><text:p>{_escape(text)}</text:p></chart:title>"


def _local_table(figure: dict) -> str:
    """The copy of the numbers a chart carries (``local-table``): the series by column, the categories in the first."""
    data = figure["data"]
    categories = list(data[0]["x"]) if data else []
    columns = "".join("<table:table-column/>" for _ in data)
    header = "<table:table-cell><text:p/></table:table-cell>" + "".join(
        f'<table:table-cell office:value-type="string"><text:p>{_escape(one["name"])}</text:p></table:table-cell>'
        for one in data
    )
    rows = ""
    for place, category in enumerate(categories):
        cells = (
            f'<table:table-cell office:value-type="string"><text:p>{_escape(str(category))}</text:p></table:table-cell>'
        )
        for one in data:
            number = number_text(one["y"][place])
            cells += (
                f'<table:table-cell office:value-type="float" office:value="{number}"><text:p>{number}</text:p>'
                "</table:table-cell>"
            )
        rows += f"<table:table-row>{cells}</table:table-row>"
    return (
        '<table:table table:name="local-table">'
        "<table:table-header-columns><table:table-column/></table:table-header-columns>"
        f"<table:table-columns>{columns or '<table:table-column/>'}</table:table-columns>"
        f"<table:table-header-rows><table:table-row>{header}</table:table-row></table:table-header-rows>"
        f"<table:table-rows>{rows}</table:table-rows></table:table>"
    )


def chart_document(model: WorkbookModel, spec: ChartSpec, width: int, height: int) -> bytes | None:
    """The ``content.xml`` of the embedded chart for ``spec`` drawn at ``width`` by ``height`` pixels, or ``None`` when
    the chart reads nothing (a named source that is gone)."""
    cells = model.chart_cells(spec.id)
    if cells is None:
        return None
    area, header_row = cells
    assert area.sheet is not None  # (a chart's range always names its sheet)
    sheet = model.sheets[area.sheet].name
    plan = plan_of(area.first, area.last, series_in=spec.series_in, header_row=header_row)
    figure = model.chart_figure(spec.id)
    whole = ((area.first.row, area.first.col), (area.last.row, area.last.col))
    styles = [
        _style(
            "ch1",
            "chart",
            ("graphic-properties", {"draw:stroke": "none", "draw:fill": "solid", "draw:fill-color": "#ffffff"}),
        ),
        _style("ch2", "chart", ("chart-properties", {"chart:auto-position": "true"})),
        _style("ch3", "chart", ("chart-properties", {"chart:include-hidden-cells": "false"})),
        _style("ch4", "chart", ("chart-properties", {"chart:display-label": "true"})),
        _style(
            "ch5",
            "chart",
            ("chart-properties", {"chart:display-label": "true", "chart:gap-width": "20", "chart:overlap": "-10"}),
        ),
        _style("ch6", "chart", ("graphic-properties", {"svg:stroke-color": "#d9d9d9"})),
        _style("ch7", "chart", ("graphic-properties", {"draw:stroke": "none", "draw:fill": "none"})),
    ]
    series_xml = ""
    for number, one in enumerate(plan.series):
        color = BAR_COLORS[number % len(BAR_COLORS)]
        styles.append(
            _style(
                f"chs{number}",
                "chart",
                ("graphic-properties", {"draw:stroke": "none", "draw:fill": "solid", "draw:fill-color": color}),
            )
        )
        label = f' chart:label-cell-address="{address(sheet, (one.label, one.label))}"' if one.label else ""
        series_xml += (
            f'<chart:series chart:style-name="chs{number}"'
            f' chart:values-cell-range-address="{address(sheet, one.values)}"'
            f'{label} chart:class="chart:bar"/>'
        )
    categories = (
        f'<chart:categories table:cell-range-address="{address(sheet, plan.categories)}"/>' if plan.categories else ""
    )
    rows = ' chart:series-source="rows"' if spec.series_in == "rows" else ""
    labels = _LABELS[(plan.first_row_is_header, plan.first_column_is_header)]
    x_axis = (
        '<chart:axis chart:dimension="x" chart:name="primary-x" chart:style-name="ch4">'
        f"{_title(spec.x_title) if spec.x_title else ''}{categories}</chart:axis>"
    )
    grid = '<chart:grid chart:class="major" chart:style-name="ch6"/>' if spec.gridlines else ""
    y_axis = (
        '<chart:axis chart:dimension="y" chart:name="primary-y" chart:style-name="ch5">'
        f"{_title(spec.y_title) if spec.y_title else ''}{grid}</chart:axis>"
    )
    legend = (
        '<chart:legend chart:legend-position="end" style:legend-expansion="high" chart:style-name="ch2"/>'
        if spec.legend
        else ""
    )
    content = (
        f'{_DECLARATION}<office:document-content {_DECLARED} office:version="1.3">'
        f"<office:automatic-styles>{''.join(styles)}</office:automatic-styles>"
        "<office:body><office:chart>"
        f'<chart:chart svg:width="{text_of(width)}" svg:height="{text_of(height)}" xlink:href=".." xlink:type="simple" '
        'chart:class="chart:bar" chart:style-name="ch1">'
        f"{_title(spec.title) if spec.title else ''}{legend}"
        f'<chart:plot-area chart:style-name="ch3" table:cell-range-address="{address(sheet, whole)}" '
        f'chart:data-source-has-labels="{labels}"{rows}>{x_axis}{y_axis}{series_xml}'
        '<chart:wall chart:style-name="ch7"/></chart:plot-area>'
        f"{_local_table(figure)}</chart:chart></office:chart></office:body></office:document-content>"
    )
    return content.encode()


def place_of(placed: Placed, rotation: int = 0) -> dict[str, str]:
    """Where a frame is and how big, as the attributes of a ``draw:frame``: its distance from the corner of its tab
    (``svg:x``, ``svg:y``) or, turned by ``rotation`` degrees, the ``draw:transform`` that turns it about its centre
    and puts it there. Every drawing of a tab is placed this way, a chart and a picture alike (D1477)."""
    size = {"svg:width": text_of(placed.width), "svg:height": text_of(placed.height)}
    box = tuple(pixels * _CM_PER_PIXEL for pixels in (placed.x, placed.y, placed.width, placed.height))
    transform = transform_of(rotation, box)  # type: ignore[arg-type]
    if transform is None:
        return {**size, "svg:x": text_of(placed.x), "svg:y": text_of(placed.y)}
    return {**size, "draw:transform": transform}


def frame_element(folder: str, name: str, placed: Placed) -> etree._Element:
    """The ``draw:frame`` of a chart whose part is ``folder`` (``Object 1``), where ``placed`` says."""
    frame = etree.Element(_q("draw:frame"), nsmap={p: u for p, u in NS.items() if p != "xml"})
    for key, value in {"draw:z-index": str(placed.layer), "draw:name": name, **place_of(placed)}.items():
        frame.set(_q(key), value)
    chart = etree.SubElement(frame, _q("draw:object"))
    for key, value in {
        "xlink:href": f"./{folder}",
        "xlink:type": "simple",
        "xlink:show": "embed",
        "xlink:actuate": "onLoad",
    }.items():
        chart.set(_q(key), value)
    if placed.obj.body.description:
        etree.SubElement(frame, _q("svg:desc")).text = xml_safe(placed.obj.body.description)
    return frame


# ------------------------------------------------------------------------------------------------ reading
def _text_of(element: etree._Element | None) -> str:
    if element is None:
        return ""
    return "\n".join(
        "".join(str(part) for part in paragraph.itertext()) for paragraph in element.iterfind("text:p", NS)
    ).strip()


def _properties(root: etree._Element, name: str | None) -> dict[str, str]:
    """The ``chart:`` properties of the automatic style ``name`` of a chart part, by their local name."""
    for style in root.iterfind("office:automatic-styles/style:style", NS):
        if name and style.get(_q("style:name")) == name:
            found: dict[str, str] = {}
            for properties in style.iterfind("style:chart-properties", NS):
                for key, value in properties.attrib.items():
                    if str(key).startswith(f"{{{NS['chart']}}}"):
                        found[local_name(str(key))] = str(value)
            return found
    return {}


def _is_the_models(root: etree._Element, chart: etree._Element, plot: etree._Element) -> bool:
    """Whether the styles of a chart leave it a plain bar chart upright, side by side, in two dimensions."""
    styles = (chart.get(_q("chart:style-name")), plot.get(_q("chart:style-name")))
    for name in styles:
        found = _properties(root, name)
        if any(found.get(key) not in (None, "false") for key in _NOT_THE_MODELS):
            return False
    return True


def _named_areas(
    plot: etree._Element, sheet_ids: SheetIds
) -> tuple[SheetId, Area | None, list[tuple[Area, Area | None]]] | None:
    """The cells a chart names, all on one sheet: ``(sheet, categories, [(values, label), ...])``; ``None`` when it
    names cells of several sheets, of one that is not in the file, or something that is not a range."""
    axis = next((a for a in plot.iterfind("chart:axis", NS) if a.get(_q("chart:dimension")) == "x"), None)
    named = None if axis is None else axis.find("chart:categories", NS)
    sheets: set[SheetId] = set()
    categories: Area | None = None
    if named is not None and named.get(_q("table:cell-range-address")):
        found = _read_area(named.get(_q("table:cell-range-address")), sheet_ids)
        if found is None:
            return None
        sheets.add(found[0])
        categories = found[1]
    series: list[tuple[Area, Area | None]] = []
    for one in plot.iterfind("chart:series", NS):
        if one.get(_q("chart:class")) not in (None, "chart:bar"):
            return None
        values = _read_area(one.get(_q("chart:values-cell-range-address")), sheet_ids)
        if values is None:
            return None
        sheets.add(values[0])
        label = None
        if one.get(_q("chart:label-cell-address")):
            found = _read_area(one.get(_q("chart:label-cell-address")), sheet_ids)
            if found is None or found[1][0] != found[1][1]:
                return None
            sheets.add(found[0])
            label = found[1]
        series.append((values[1], label))
    if len(sheets) != 1 or not series:
        return None
    return next(iter(sheets)), categories, series


def read_chart(content: bytes, sheet_ids: SheetIds) -> ReadChart | None:  # noqa: PLR0911 (each way a chart is not the model's)
    """The chart of an embedded chart part (``Object 1/content.xml``) as the model holds it, or ``None`` when it is
    not a bar chart that is drawn the way the model draws one over cells of one sheet of this file. ``sheet_ids`` says
    which sheet a name is. The width and the height are those of the chart itself, a frame's own replace them."""
    try:
        root = etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        return None
    chart = root.find("office:body/office:chart/chart:chart", NS)
    plot = None if chart is None else chart.find("chart:plot-area", NS)
    if (
        chart is None
        or plot is None
        or chart.get(_q("chart:class")) != "chart:bar"
        or not _is_the_models(root, chart, plot)
    ):
        return None
    named = _named_areas(plot, sheet_ids)
    if named is None:
        return None
    sheet, categories, series = named
    (r0, c0), (r1, c1) = series[0][0]
    rows = plot.get(_q("chart:series-source")) == "rows" or (r0 == r1 and c0 != c1)
    drawn = plan_from(sheet, categories, series, rows)
    if drawn is None:
        return None
    first, last, header_row, _ = drawn
    x_axis = next((a for a in plot.iterfind("chart:axis", NS) if a.get(_q("chart:dimension")) == "x"), None)
    y_axis = next((a for a in plot.iterfind("chart:axis", NS) if a.get(_q("chart:dimension")) == "y"), None)
    spec = spec_of(
        first,
        last,
        rows=rows,
        header_row=header_row,
        title=_text_of(chart.find("chart:title", NS)),
        x_title=_text_of(None if x_axis is None else x_axis.find("chart:title", NS)),
        y_title=_text_of(None if y_axis is None else y_axis.find("chart:title", NS)),
        legend=chart.find("chart:legend", NS) is not None,
        gridlines=y_axis is not None and y_axis.find("chart:grid", NS) is not None,
    )
    if spec is None:
        return None
    width, height = (pixels_of(chart.get(_q(f"svg:{side}"))) for side in ("width", "height"))
    return ReadChart(spec, width or 0, height or 0, "")


def holds_a_chart(frame: etree._Element) -> str | None:
    """The folder a frame's embedded object is in (``Object 1``), or ``None`` for a frame that holds none."""
    held = frame.find("draw:object", NS)
    href = None if held is None else held.get(_q("xlink:href"))
    if not href:
        return None
    return href.removeprefix("./").rstrip("/") or None


def sizes_of(frame: etree._Element, chart: ReadChart) -> tuple[int, int] | None:
    """The size in pixels a frame gives its chart (the frame's own, then the chart's), or ``None`` when the model cannot
    hold an object so small."""
    width = pixels_of(frame.get(_q("svg:width"))) or chart.width
    height = pixels_of(frame.get(_q("svg:height"))) or chart.height
    return (width, height) if min(width, height) >= MIN_OBJECT_SIZE else None


def describe(frame: etree._Element) -> str:
    """What a frame says to someone who cannot see it: its description, or else its title."""
    for tag in ("svg:desc", "svg:title"):
        text = (frame.findtext(_q(tag)) or "").strip()
        if text:
            return text
    return ""


# ------------------------------------------------------------------------------------------------ a file's charts
Parts = dict[str, tuple[bytes | None, str]]


@dataclass
class ChartOut:
    """One chart ready for a file: its frame, and the parts it needs (the folder and its ``content.xml``)."""

    frame: etree._Element
    parts: Parts


def a_chart(model: WorkbookModel, spec: ChartSpec, number: int, placed: Placed) -> ChartOut | None:
    """The chart for ``spec`` as ``Object {number}``, where ``placed`` says; ``None`` when it reads no cells."""
    document = chart_document(model, spec, round(placed.width), round(placed.height))
    if document is None:
        return None
    folder = f"Object {number}"
    parts: Parts = {f"{folder}/": (None, CHART_MEDIA), f"{folder}/content.xml": (document, "text/xml")}
    return ChartOut(frame_element(folder, placed.obj.body.name or f"Chart {number}", placed), parts)


def new_shapes() -> etree._Element:
    """An empty ``table:shapes``."""
    return etree.Element(_q("table:shapes"), nsmap={p: u for p, u in NS.items() if p != "xml"})
