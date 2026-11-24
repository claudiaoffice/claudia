"""Charts in an xlsx file (D463).

A chart of an xlsx file is a ``graphicFrame`` in the drawing of a sheet (``xl/drawings/drawing1.xml``), pinned by an
anchor to a cell, and a part of its own (``xl/charts/chart1.xml``) that says what kind of chart it is, its titles,
legend and gridlines, and for each series the cells it reads (``Data!$B$2:$B$5``) and the cell that names it, with a
copy of the numbers (``numCache``) for a program that does not calculate.

What of the model's charts is written, and what of a file's is read, is what the ods does (:mod:`.ods_charts`, D462): a
bar chart over one range, one series per column (or row), read back as the same definition; every other chart of a
file stays in it, untouched, and is counted (``chart``). The differences are the file's own: a chart is told apart by
its **anchor** (a ``oneCellAnchor`` has the size the chart is, a ``twoCellAnchor`` two cells it reaches, from which
the size is worked out with the widths and heights the sheet has), and Excel has **no direction of series**: whether
the series of a chart are the columns or the rows of its range is told by the cells they read.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from io import BytesIO
from xml.sax.saxutils import escape

from lxml import etree

from claudia_computes import MAX_OBJECTS_PER_SHEET, CellAnchor, ChartSpec, SheetId, WorkbookModel
from claudia_computes.charts import BAR_COLORS
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.model import MIN_OBJECT_SIZE
from claudia_computes.refs import column_index, column_name
from claudia_core.assets import MAX_ALT_CHARS
from claudia_odf_io import xml_safe

from .chart_plan import Area, ReadChart, number_text, plan_from, plan_of, spec_of, with_id
from .xlsx_layout import PIXELS_PER_CHARACTER, POINTS_PER_PIXEL
from .xlsx_read import Package, parse_xml, related, relationships

NS = {
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}
#: The media types of a chart and of a drawing.
CHART_TYPE = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
DRAWING_TYPE = "application/vnd.openxmlformats-officedocument.drawing+xml"
#: English Metric Units in a pixel (at 96 dots to the inch).
EMU = 9525
_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_ROOT = 'xmlns:c="{c}" xmlns:a="{a}" xmlns:r="{r}"'.format(**NS)
_ANCHORS = ("oneCellAnchor", "twoCellAnchor")
_ADDRESS = re.compile(
    r"^(?:'(?P<quoted>(?:[^']|'')+)'|(?P<plain>[^'!()]+))!"
    r"\$?(?P<c1>[A-Za-z]{1,3})\$?(?P<r1>\d+)(?::\$?(?P<c2>[A-Za-z]{1,3})\$?(?P<r2>\d+))?$"
)


def _q(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


# ------------------------------------------------------------------------------------------------ addresses
def sheet_text(name: str) -> str:
    """A sheet's name as a formula writes it: bare when it can be, else in quotes."""
    plain = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and not re.fullmatch(r"[A-Za-z]{1,3}\d+|[Rr]\d*[Cc]\d*", name)
    return name if plain else "'" + name.replace("'", "''") + "'"


def _cell_text(cell: tuple[int, int]) -> str:
    return f"${column_name(cell[1])}${cell[0] + 1}"


def address(sheet: str, area: Area) -> str:
    """``Data!$B$2:$B$5``: the way a chart names cells (one cell as a single one)."""
    first, last = area
    cells = _cell_text(first) if first == last else f"{_cell_text(first)}:{_cell_text(last)}"
    return f"{sheet_text(sheet)}!{cells}"


def read_address(text: str | None, sheet_ids: Mapping[str, SheetId]) -> tuple[SheetId, Area] | None:
    """The sheet and the cells of an address of a chart, or ``None`` for what is not one range of a sheet of the file
    (a union, a name, a sheet that is not there, a cell off the grid). ``sheet_ids`` maps names, folded, to sheets."""
    found = _ADDRESS.match((text or "").strip())
    if found is None:
        return None
    name = found["quoted"].replace("''", "'") if found["quoted"] is not None else found["plain"]
    sheet = sheet_ids.get(name.casefold())
    first_column, first_row = column_index(found["c1"]), int(found["r1"]) - 1
    last_column = column_index(found["c2"]) if found["c2"] else first_column
    last_row = int(found["r2"]) - 1 if found["r2"] else first_row
    low, high = (
        (min(first_row, last_row), min(first_column, last_column)),
        (
            max(first_row, last_row),
            max(first_column, last_column),
        ),
    )
    if sheet is None or high[0] >= MAX_ROWS or high[1] >= MAX_COLS or low[0] < 0:
        return None
    return sheet, (low, high)


# ------------------------------------------------------------------------------------------------ writing
def _text(value: str) -> str:
    return escape(xml_safe(value))


def _title(text: str, *, vertical: bool = False) -> str:
    rotation = ' rot="-5400000" vert="horz"' if vertical else ""
    return (
        f"<c:title><c:tx><c:rich><a:bodyPr{rotation}/><a:lstStyle/><a:p><a:r><a:t>{_text(text)}</a:t></a:r></a:p>"
        '</c:rich></c:tx><c:overlay val="0"/></c:title>'
    )


def _strings(sheet: str, area: Area, values: Sequence[str]) -> str:
    points = "".join(f'<c:pt idx="{place}"><c:v>{_text(value)}</c:v></c:pt>' for place, value in enumerate(values))
    return (
        f'<c:strRef><c:f>{_text(address(sheet, area))}</c:f><c:strCache><c:ptCount val="{len(values)}"/>{points}'
        "</c:strCache></c:strRef>"
    )


def _numbers(sheet: str, area: Area, values: Sequence[float]) -> str:
    points = "".join(
        f'<c:pt idx="{place}"><c:v>{number_text(value)}</c:v></c:pt>' for place, value in enumerate(values)
    )
    return (
        f"<c:numRef><c:f>{_text(address(sheet, area))}</c:f><c:numCache><c:formatCode>General</c:formatCode>"
        f'<c:ptCount val="{len(values)}"/>{points}</c:numCache></c:numRef>'
    )


def chart_xml(model: WorkbookModel, spec: ChartSpec) -> bytes | None:
    """The ``chart1.xml`` of ``spec``, or ``None`` when the chart reads nothing (a named source that is gone)."""
    cells = model.chart_cells(spec.id)
    if cells is None:
        return None
    area, header_row = cells
    assert area.sheet is not None  # (a chart's range always names its sheet)
    sheet = model.sheets[area.sheet].name
    plan = plan_of(area.first, area.last, series_in=spec.series_in, header_row=header_row)
    figure = model.chart_figure(spec.id)
    series = ""
    for number, (one, drawn) in enumerate(zip(plan.series, figure["data"], strict=False)):
        name = "" if one.label is None else f"<c:tx>{_strings(sheet, (one.label, one.label), [drawn['name']])}</c:tx>"
        color = BAR_COLORS[number % len(BAR_COLORS)].removeprefix("#").upper()
        categories = (
            ""
            if plan.categories is None
            else f"<c:cat>{_strings(sheet, plan.categories, [str(x) for x in drawn['x']])}</c:cat>"
        )
        series += (
            f'<c:ser><c:idx val="{number}"/><c:order val="{number}"/>{name}'
            f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr><c:invertIfNegative val="0"/>'
            f"{categories}<c:val>{_numbers(sheet, one.values, drawn['y'])}</c:val></c:ser>"
        )
    grid = (
        '<c:majorGridlines><c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="D9D9D9"/></a:solidFill></a:ln>'
        "</c:spPr></c:majorGridlines>"
        if spec.gridlines
        else ""
    )
    legend = '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>' if spec.legend else ""
    body = (
        f'{_DECLARATION}<c:chartSpace {_ROOT}><c:roundedCorners val="0"/><c:chart>'
        f"{_title(spec.title) if spec.title else ''}"
        f'<c:autoTitleDeleted val="{0 if spec.title else 1}"/>'
        '<c:plotArea><c:layout/><c:barChart><c:barDir val="col"/><c:grouping val="clustered"/>'
        f'<c:varyColors val="0"/>{series}<c:gapWidth val="100"/><c:axId val="500000001"/><c:axId val="500000002"/>'
        "</c:barChart>"
        '<c:catAx><c:axId val="500000001"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/>'
        f'<c:axPos val="b"/>{_title(spec.x_title) if spec.x_title else ""}'
        '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
        '<c:tickLblPos val="nextTo"/><c:crossAx val="500000002"/><c:crosses val="autoZero"/><c:auto val="1"/>'
        '<c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
        '<c:valAx><c:axId val="500000002"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/>'
        f'<c:axPos val="l"/>{grid}{_title(spec.y_title, vertical=True) if spec.y_title else ""}'
        '<c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
        '<c:tickLblPos val="nextTo"/><c:crossAx val="500000001"/><c:crosses val="autoZero"/>'
        '<c:crossBetween val="between"/></c:valAx></c:plotArea>'
        f'{legend}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart></c:chartSpace>'
    )
    return body.encode()


# ------------------------------------------------------------------------------------------------ reading
def _title_text(element: etree._Element | None) -> str:
    if element is None:
        return ""
    paragraphs = ("".join(t.text or "" for t in p.iter(_q("a", "t"))) for p in element.iter(_q("a", "p")))
    return "\n".join(paragraphs).strip()


def _reference(element: etree._Element | None, kind: str) -> str | None:
    """The cells a ``c:tx``, ``c:cat`` or ``c:val`` names (``kind`` is the reference it must be, ``None`` for any
    of the two kinds of a category), or ``None`` for one that holds literal data or a reference of another kind."""
    if element is None:
        return None
    for tag in (kind,) if kind else ("strRef", "numRef"):
        found = element.find(f"c:{tag}/c:f", NS)
        if found is not None and found.text:
            return found.text
    return None


def _is_a_plain_bar_chart(chart: etree._Element) -> etree._Element | None:
    """The ``c:barChart`` of a chart that is nothing but a clustered bar chart upright with one pair of axes."""
    plot = chart.find("c:plotArea", NS)
    if plot is None:
        return None
    drawn = [child for child in plot if isinstance(child.tag, str) and etree.QName(child).localname.endswith("Chart")]
    axes = [etree.QName(child).localname for child in plot if etree.QName(child).localname.endswith("Ax")]
    bar = drawn[0] if len(drawn) == 1 and etree.QName(drawn[0]).localname == "barChart" else None
    if bar is None or sorted(axes) != ["catAx", "valAx"]:
        return None
    direction = bar.find("c:barDir", NS)
    grouping = bar.find("c:grouping", NS)
    if direction is None or direction.get("val") != "col":
        return None
    if grouping is not None and grouping.get("val") != "clustered":
        return None
    return bar


def read_chart(content: bytes, sheet_ids: Mapping[str, SheetId]) -> ReadChart | None:  # noqa: PLR0911, PLR0912 (each way a chart is not the model's)
    """The chart of a chart part (``xl/charts/chart1.xml``) as the model holds it, or ``None`` when it is not a bar
    chart drawn the way the model draws one over cells of one sheet of this file. ``sheet_ids`` maps the names of the
    sheets, folded, to them. The size is the anchor's, not the chart's."""
    try:
        root = etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        return None
    chart = root.find("c:chart", NS)
    bar = None if chart is None else _is_a_plain_bar_chart(chart)
    if chart is None or bar is None:
        return None
    sheets: set[SheetId] = set()
    categories: Area | None = None
    asked_for_categories = False
    series: list[tuple[Area, Area | None]] = []
    for one in bar.iterfind("c:ser", NS):
        values = read_address(_reference(one.find("c:val", NS), "numRef"), sheet_ids)
        if values is None:
            return None
        sheets.add(values[0])
        name = None
        if one.find("c:tx", NS) is not None:
            found = read_address(_reference(one.find("c:tx", NS), "strRef"), sheet_ids)
            if found is None or found[1][0] != found[1][1]:
                return None
            sheets.add(found[0])
            name = found[1]
        if one.find("c:cat", NS) is not None:
            found = read_address(_reference(one.find("c:cat", NS), ""), sheet_ids)
            if found is None or (asked_for_categories and found[1] != categories):
                return None
            sheets.add(found[0])
            categories, asked_for_categories = found[1], True
        elif asked_for_categories:
            return None
        series.append((values[1], name))
    if len(sheets) != 1 or not series:
        return None
    shaped_as_rows = series[0][0][0][0] == series[0][0][1][0] and series[0][0][0][1] != series[0][0][1][1]
    drawn = None
    for rows in (shaped_as_rows, not shaped_as_rows):
        drawn = plan_from(next(iter(sheets)), categories, series, rows)
        if drawn is not None:
            break
    if drawn is None:
        return None
    first, last, header_row, _ = drawn
    value_axis = chart.find("c:plotArea/c:valAx", NS)
    category_axis = chart.find("c:plotArea/c:catAx", NS)
    spec = spec_of(
        first,
        last,
        rows=rows,
        header_row=header_row,
        title=_title_text(chart.find("c:title", NS)),
        x_title=_title_text(None if category_axis is None else category_axis.find("c:title", NS)),
        y_title=_title_text(None if value_axis is None else value_axis.find("c:title", NS)),
        legend=chart.find("c:legend", NS) is not None,
        gridlines=value_axis is not None and value_axis.find("c:majorGridlines", NS) is not None,
    )
    return None if spec is None else ReadChart(spec, 0, 0, "")


# ------------------------------------------------------------------------------------------------ anchors
def pixels(emu: str | None) -> int:
    """A length in EMU as pixels."""
    try:
        return round(int(emu or 0) / EMU)
    except ValueError:
        return 0


def anchor_element(  # noqa: PLR0913 (an anchor is: which chart, where, how big, what it is called and says)
    rid: str, number: int, name: str, row: int, col: int, width: int, height: int, description: str = ""
) -> etree._Element:
    """The ``oneCellAnchor`` of a chart: pinned to the corner of cell ``row``, ``col`` and ``width`` by ``height``
    pixels, its chart the part ``rid`` points at."""
    xml = (
        f'<xdr:oneCellAnchor xmlns:xdr="{NS["xdr"]}" xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}" xmlns:c="{NS["c"]}">'
        f"<xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff>"
        f'</xdr:from><xdr:ext cx="{width * EMU}" cy="{height * EMU}"/>'
        f'<xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr/><xdr:cNvGraphicFramePr/>'
        '</xdr:nvGraphicFramePr><xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
        f'<a:graphic><a:graphicData uri="{NS["c"]}"><c:chart r:id="{rid}"/></a:graphicData></a:graphic>'
        "</xdr:graphicFrame><xdr:clientData/></xdr:oneCellAnchor>"
    )
    anchor = etree.fromstring(xml)
    properties = anchor.find("xdr:graphicFrame/xdr:nvGraphicFramePr/xdr:cNvPr", NS)
    assert properties is not None
    properties.set("id", str(number))
    properties.set("name", xml_safe(name))
    if description:
        properties.set("descr", xml_safe(description))
    return anchor


def new_drawing() -> etree._Element:
    """A drawing with nothing in it."""
    return etree.fromstring(f'<xdr:wsDr xmlns:xdr="{NS["xdr"]}" xmlns:a="{NS["a"]}"/>')


@dataclass
class FileChart:
    """One chart of a sheet's drawing."""

    sheet: SheetId
    #: The part of the drawing, its anchor and the frame in it, the part of the chart.
    drawing: str
    anchor: etree._Element
    frame: etree._Element
    part: str
    #: The cell it is pinned to.
    row: int
    col: int
    #: What the model makes of it, and the ids it has there; ``None`` for a chart the model does not hold.
    held: ReadChart | None = None
    width: int = 0
    height: int = 0
    description: str = ""
    object_id: str = ""
    spec_id: str = ""

    @property
    def spec(self) -> ChartSpec:
        """The definition the model has of this chart (only for one the model holds)."""
        assert self.held is not None
        return with_id(self.held.spec, self.spec_id)


def _cell_of(element: etree._Element | None) -> tuple[int, int, int, int] | None:
    """``(row, col, row offset, column offset)`` of a ``from`` or ``to``, the offsets in pixels."""
    if element is None:
        return None
    try:
        row, col = (int(element.findtext(_q("xdr", tag)) or "") for tag in ("row", "col"))
    except ValueError:
        return None
    return row, col, pixels(element.findtext(_q("xdr", "rowOff"))), pixels(element.findtext(_q("xdr", "colOff")))


def _span(sizes: Mapping[int, float], default: float, first: int, last: int) -> float:
    return sum(sizes.get(place, default) for place in range(first, last))


@dataclass
class Geometry:
    """The sizes the cells of a sheet have in the file, in pixels: what a two-cell anchor reaches over. Not the model's
    (the model has its own default size of a cell); the file's, as Excel and LibreOffice lay it out."""

    widths: dict[int, float]
    heights: dict[int, float]
    width: float = 64.0  # Excel's default column (8.43 characters)
    height: float = 20.0  # and its default row (15 points)


def geometry_of(data: bytes) -> Geometry:
    """The widths and heights of the columns and rows of a worksheet's XML, and its defaults."""
    out = Geometry({}, {})
    main = f"{{{NS['x']}}}"
    for _, element in etree.iterparse(
        BytesIO(data), events=("end",), tag=(main + "sheetFormatPr", main + "col", main + "row"), resolve_entities=False
    ):
        name = etree.QName(element).localname
        try:
            if name == "sheetFormatPr":
                out.width = (
                    float(element.get("defaultColWidth")) * PIXELS_PER_CHARACTER
                    if element.get("defaultColWidth")
                    else 64.0
                )
                out.height = float(element.get("defaultRowHeight") or 15) / POINTS_PER_PIXEL
            elif name == "col":
                size = (
                    0.0
                    if element.get("hidden") in ("1", "true")
                    else float(element.get("width", "0")) * PIXELS_PER_CHARACTER
                )
                first, last = int(element.get("min", "1")), min(int(element.get("max", "1")), MAX_COLS)
                out.widths.update(dict.fromkeys(range(first - 1, last), size))
            elif element.get("ht") or element.get("hidden") in ("1", "true"):
                hidden = element.get("hidden") in ("1", "true")
                out.heights[int(element.get("r", "0")) - 1] = (
                    0.0 if hidden else float(element.get("ht", "0")) / POINTS_PER_PIXEL
                )
        except (TypeError, ValueError):
            pass
        element.clear()
    return out


def _size_of(anchor: etree._Element, geometry: Callable[[], Geometry]) -> tuple[int, int] | None:
    """The size in pixels an anchor gives its frame (``geometry`` has the sizes of the cells of the sheet, for a
    ``twoCellAnchor`` to work out what it reaches over); ``None`` when it is neither anchor."""
    kind = etree.QName(anchor).localname
    start = _cell_of(anchor.find("xdr:from", NS))
    if start is None:
        return None
    if kind == "oneCellAnchor":
        extent = anchor.find("xdr:ext", NS)
        if extent is None:
            return None
        return pixels(extent.get("cx")), pixels(extent.get("cy"))
    end = _cell_of(anchor.find("xdr:to", NS))
    if end is None:
        return None
    extent = anchor.find("xdr:graphicFrame/xdr:xfrm/a:ext", NS)
    if extent is not None and pixels(extent.get("cx")) > 0 and pixels(extent.get("cy")) > 0:
        # LibreOffice states the size it laid the frame out at; Excel leaves it zero and the cells say it
        return pixels(extent.get("cx")), pixels(extent.get("cy"))
    layout = geometry()
    width = _span(layout.widths, layout.width, start[1], end[1]) - start[3] + end[3]
    height = _span(layout.heights, layout.height, start[0], end[0]) - start[2] + end[2]
    return round(width), round(height)


def file_charts(
    package: Package, drawings: Mapping[str, etree._Element] | None = None
) -> tuple[list[FileChart], dict[str, etree._Element]]:
    """Every chart of the sheets of a file, with the ones the model holds numbered in the order of the file: the
    ``n``-th is the object ``o{n}`` showing the definition ``c{n}``. A ``twoCellAnchor`` is as big as the cells it
    reaches, by the widths and heights the file gives them. The drawings are returned, parsed, for a patch to change;
    ``drawings`` can hand over ones that were parsed already."""
    sheet_ids = {sheet.name.casefold(): sheet.sheet_id for sheet in package.sheets}
    roots: dict[str, etree._Element] = dict(drawings or {})
    found: list[FileChart] = []
    held = 0
    for sheet in package.sheets:
        counted = 0
        geometry = cache(lambda sheet=sheet: geometry_of(package.parts[sheet.part]))
        for part in related(package.parts, sheet.part, "drawing"):
            if part not in package.parts:
                continue
            root = roots.get(part)
            if root is None:
                root = roots[part] = parse_xml(package.parts[part])
            targets = {
                rid: target for rid, kind, target in relationships(package.parts, part) if kind.endswith("/chart")
            }
            for anchor in root:
                if not isinstance(anchor.tag, str) or etree.QName(anchor).localname not in _ANCHORS:
                    continue
                frame = anchor.find("xdr:graphicFrame", NS)
                reference = None if frame is None else frame.find(".//c:chart", NS)
                target = None if reference is None else targets.get(reference.get(_q("r", "id"), ""))
                start = _cell_of(anchor.find("xdr:from", NS))
                if frame is None or target is None or start is None:
                    continue
                chart = FileChart(sheet.sheet_id, part, anchor, frame, target, start[0], start[1])
                data = package.parts.get(target)
                read = None if data is None else read_chart(data, sheet_ids)
                size = _size_of(anchor, geometry)
                properties = frame.find("xdr:nvGraphicFramePr/xdr:cNvPr", NS)
                description = (
                    "" if properties is None else (properties.get("descr") or properties.get("title") or "").strip()
                )
                if (
                    read is not None
                    and size is not None
                    and min(size) >= MIN_OBJECT_SIZE
                    and len(description) <= MAX_ALT_CHARS
                    and counted < MAX_OBJECTS_PER_SHEET
                ):
                    held += 1
                    counted += 1
                    chart.held, (chart.width, chart.height), chart.description = read, size, description
                    chart.object_id, chart.spec_id = f"o{held}", f"c{held}"
                found.append(chart)
    return found, roots


# ------------------------------------------------------------------------------------------------ what is written
@dataclass(frozen=True)
class WrittenChart:
    """A chart ready for a file: the sheet it is on (by name), its part, where it is pinned, its size, what it says."""

    sheet: str
    xml: bytes
    row: int
    col: int
    width: int
    height: int
    description: str
    layer: int = 0  # its place in the stack of its sheet, which the pictures on it share


def sheet_name(wanted: str, taken: set[str]) -> str:
    """A name for a sheet a slide becomes: ``wanted`` as a sheet may be called in Excel (at most 31 characters, none
    of ``[]*?:/\\``), and one no sheet in ``taken`` has; it is added to ``taken``."""
    name = re.sub(r"[\[\]*?:/\\]", "-", xml_safe(wanted)).strip("' ")[:31] or "Chart"
    candidate, number = name, 1
    while candidate.casefold() in taken:
        number += 1
        suffix = f" ({number})"
        candidate = name[: 31 - len(suffix)] + suffix
    taken.add(candidate.casefold())
    return candidate


def written_charts(model: WorkbookModel) -> list[WrittenChart]:
    """The charts of ``model`` for a file: the charts floating on its sheets, each pinned where it is (a slide is a
    sheet by then, ``slide_plan``)."""
    out: list[WrittenChart] = []
    for sheet_id, sheet in model.sheets.items():
        for layer, object_id in enumerate(model.stack_of(str(sheet_id))):
            obj = model.get_object(object_id)
            if obj.body.chart is None:
                continue
            spec = model.charts[obj.body.chart]
            assert isinstance(spec, ChartSpec)
            assert isinstance(obj.anchor, CellAnchor)  # (an object on a sheet hangs at a cell)
            xml = chart_xml(model, spec)
            if xml is not None:
                body = obj.body
                out.append(
                    WrittenChart(
                        sheet.name, xml, obj.anchor.row, obj.anchor.col, body.w, body.h, body.description, layer
                    )
                )
    return out
