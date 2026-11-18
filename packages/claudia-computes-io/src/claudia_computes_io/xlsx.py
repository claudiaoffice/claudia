"""Converting between a :class:`~claudia_computes.WorkbookModel` and xlsx, and adding a pivot table additively.

``workbook_to_xlsx`` is a minimal base export (values, formulas, one worksheet per sheet) built with openpyxl's own
object model: it is not the ODF-first, loss-reporting import/export story of E6.9 (D5, D70, D67, D69), only enough of
a real document for ``add_pivot_table`` to have something to attach to.

``add_pivot_table`` is the additive extension the spike validated: openpyxl cannot write a pivot table, so this
builds the three extra parts (cache definition, cache records, pivot table) and the relationships and content-type
overrides that reference them, by editing the already-written zip directly with ``lxml`` -- the same element/part
layer openpyxl itself writes to, not a fork of it. The result is read as a normal pivot table by Excel and
LibreOffice, and survives an openpyxl load-edit-save round trip (the library renumbers the relationship id but keeps
it internally consistent).

``xlsx_to_workbook`` reads a file as a model and ``xlsx_import_losses`` says what the model does not show of it
(:mod:`.xlsx_read`, D370); ``apply_edits_to_xlsx`` writes an edited import back by changing only the edited cells in
the original file's XML (:mod:`.xlsx_patch`, D371, after D220), so a chart, a picture, the look of a cell, a list in a
cell, an icon set or a spilled formula -- everything the model does not hold -- survives the edit. Formulas carry
Excel's ``_xlfn.`` marks in the file and lose them in the model (:mod:`.excel_names`).
"""

from __future__ import annotations

import posixpath
import zipfile
from collections.abc import Hashable
from dataclasses import replace
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

import openpyxl
from lxml import etree
from openpyxl.comments import Comment

from claudia_computes import CellAnchor, Content, ObjectBody, Sheet, VisualObject, WorkbookModel
from claudia_computes.cellstyles import DEFAULT_CELL_STYLE
from claudia_computes.values import ErrorValue, Value
from claudia_odf_io import DocumentInfo, Loss, LossLog, stamp_office_meta
from claudia_opc_io import write_parts

from ._unwritten import XLSX_WRITTEN, in_order, workbook_unwritten_changes
from .cell_looks import (
    Dressing,
    Lines,
    Look,
    LookExport,
    Restyling,
    SheetLooks,
    changed_styles,
    restyling,
    runs_of,
    sheet_styling,
)
from .chart_plan import chart_losses
from .excel_names import with_marks
from .extensions import to_excel, with_note
from .layout_sizes import changed_sizes
from .openformula import Untranslatable
from .pivot_exchange import adopt_pivots, pivot_positions, sheet_cells
from .xlsx_chart_patch import Drawings, patch_charts
from .xlsx_charts import WrittenChart, file_charts, written_charts
from .xlsx_layout import layout_losses
from .xlsx_looks import XlsxLooks, read_looks
from .xlsx_names import XlsxNamesPatch, header_losses, write_names
from .xlsx_patch import PackagePatch, SheetNotes, SheetPatch, UnsupportedEdit, written
from .xlsx_pivots import add_pivots, ask_refresh, read_pivots, written_pivots_of
from .xlsx_read import (
    Package,
    SheetRead,
    losses_in_order,
    names_and_tables,
    open_package,
    parse_xml,
    read_sheet,
    related,
    workbook_losses,
)
from .xlsx_restyle import StylesPatch, restyle_sheet
from .xlsx_write_looks import XlsxLookWriter

NS = {
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


def _qn(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def _tostring(element) -> bytes:
    return etree.tostring(element, xml_declaration=True, encoding="UTF-8", standalone=True)


def _attr(value) -> str:
    """``value`` (any cell content: a header name, a shared-item value, an amount) escaped for safe placement
    inside a double-quoted XML attribute value. The pivot cache/table XML below is hand-built with plain string
    interpolation rather than ``lxml`` elements (unlike ``_register_pivot_cache``), so every piece of data that
    reaches it this way has to be escaped explicitly -- without this, a cell value containing ``"``, ``<`` or
    ``&`` breaks out of its attribute and can inject arbitrary markup into the exported file."""
    return _xml_escape(str(value), {'"': "&quot;"})


_NOTE_AUTHOR = "claudia"


def _shown(value: Value) -> object:
    """What a formula that cannot be written shows, as a cell value: errors by their code."""
    return value.code if isinstance(value, ErrorValue) else value


def _written(content: Content, value: Value) -> tuple[object, str | None, Loss | None]:
    """What to put in a cell for ``content`` (a formula shows ``value``): its cell value, the note that says what its
    alternatives are (when it has any) and, when its formula cannot be said in Excel, why it is written as its value.

    ``RANDOM(...)`` becomes the Excel formula that draws the same distribution and a cell with alternatives its first
    alternative with a note (see :mod:`claudia_computes_io.extensions`)."""
    noted = with_note(content)
    shown = noted.content
    if shown is None:
        return None, noted.note, None
    if shown["t"] != "formula":
        return shown["v"], noted.note, None
    try:
        return with_marks(to_excel(shown["v"])), noted.note, None
    except Untranslatable as why:
        return _shown(value), noted.note, Loss("formula", why.reason)


def _put(cell, content: Content, value: Value) -> Loss | None:  # noqa: ANN001 (openpyxl's own cell class)
    """Write ``content`` into an openpyxl cell, with its note."""
    cell.value, note, lost = _written(content, value)
    cell.comment = Comment(note, _NOTE_AUTHOR) if note is not None else None
    return lost


def xlsx_export_losses(model: WorkbookModel) -> tuple[Loss, ...]:
    """What :func:`workbook_to_xlsx` cannot say in Excel for ``model``, each as a code with how many:
    ``"formula"`` (with the reason, ``random`` for a draw Excel has no single formula for: written as its value),
    ``"alternatives"`` (written as the first alternative with a note: only claudia reads the rest), ``"look"``
    (``too-many-cells``: cells of style ranges too large to write one by one) and ``"chart"`` (``tab``: a chart tab is
    a sheet with the chart in it; ``source``: a chart that follows a name has the cells the name is now; ``rotation``;
    ``empty``: a chart that reads nothing is not written), and what :func:`xlsx_unwritten_changes`
    says of a fresh file: ``"layout"``, ``"name"``, ``"chart"`` and ``"object"``."""
    losses = LossLog()
    dropped = sum(sheet_styling(sheet).dropped for sheet in model.sheets.values())
    if dropped:
        losses.add("look", "too-many-cells", dropped)
    for detail in chart_losses(model):
        losses.add("chart", detail)
    for sheet in model.sheets.values():
        for content, value in sheet_cells(model, sheet).values():
            _, note, lost = _written(content, value)
            if lost is not None:
                losses.add(lost.kind, lost.detail)
            if note is not None:
                losses.add("alternatives")
    for loss in written_pivots_of(model).losses:
        losses.add(loss.kind, loss.detail, loss.count)
    return (*losses.result(), *xlsx_unwritten_changes(model))


def xlsx_unwritten_changes(model: WorkbookModel, baseline: WorkbookModel | None = None) -> tuple[Loss, ...]:
    """What changed in ``model`` that the xlsx converters do not write, each as a code with how many entries differ from
    ``baseline`` -- the model the original file was read as, for an edit-and-reexport -- or from an empty workbook, for
    a fresh file (``None``): ``"layout"`` (``beyond-excel-limits``: a width or height Excel cannot hold, written at its
    limit), ``"name"`` (what a file
    cannot hold of a named range or table: ``result``, ``purpose``, ``table-scope``, ``table-header``), ``"chart"``
    and ``"object"`` (with the pictures and shapes they use)."""
    found = workbook_unwritten_changes(
        model, baseline, written=XLSX_WRITTEN | ({"pivots"} if baseline is None else set())
    )
    return in_order((*found, *header_losses(model, baseline).result(), *layout_losses(model, baseline).result()))


def workbook_to_xlsx(model: WorkbookModel, *, info: DocumentInfo | None = None) -> bytes:
    """A base xlsx of ``model``: one worksheet per sheet, each cell as its stored content (a formula as its text,
    with the leading ``=``; see ``_written`` for what is written differently), and the cells' looks: Body text as
    the file's Normal, named styles as named cell styles, the rest as direct formats with their number formats
    (``xlsx_write_looks``, D379), and the bar charts floating on its sheets, each pinned to its cell (a chart tab as a
    sheet of its own with the chart in it; ``xlsx_charts``, D463). The file says in its properties who made the workbook
    and when and who changed it last, from ``info``; what ``info`` does not know it leaves out (D466)."""
    wb = openpyxl.Workbook()
    assert wb.active is not None  # a freshly constructed Workbook always starts with one
    wb.remove(wb.active)
    looks = XlsxLookWriter(model, wb)
    for sheet in model.sheets.values():
        ws = wb.create_sheet(title=sheet.name)
        for (row, col), (content, value) in sheet_cells(model, sheet).items():
            _put(ws.cell(row=row + 1, column=col + 1), content, value)
        looks.sheet(sheet, ws)
    charts, tabs = written_charts(model)
    for name in tabs:
        wb.create_sheet(title=name)
    if not wb.sheetnames:
        wb.create_sheet(title="Sheet1")
    write_names(wb, model)
    out = BytesIO()
    wb.save(out)
    data = add_pivots(out.getvalue(), model, written_pivots_of(model).pivots)
    data = _with_charts(data, charts) if charts else data
    return stamp_office_meta(data, info)


def _with_charts(data: bytes, charts: list[WrittenChart]) -> bytes:
    """``data`` with ``charts`` on its sheets (each by the name of its sheet)."""
    package = open_package(data)
    patch = PackagePatch(package.parts)
    drawings = Drawings(patch)
    by_name = {sheet.name.casefold(): sheet.part for sheet in package.sheets}
    for chart in charts:
        drawings.add(
            by_name[chart.sheet.casefold()],
            chart.xml,
            chart.row,
            chart.col,
            chart.width,
            chart.height,
            chart.description,
        )
    drawings.finish()
    return write_parts(patch.finish())


def xlsx_to_workbook(xlsx_bytes: bytes) -> WorkbookModel:
    """``xlsx_bytes`` as a :class:`~claudia_computes.WorkbookModel`: one sheet per worksheet, in order, each
    non-empty cell becoming a constant or formula content, and the workbook's ranges and tables as names (D370). A
    formula the model cannot calculate as Excel does comes in as the value Excel last showed for it. The look of the
    cells comes in as styles and named number formats -- the file's named styles as they are, its direct formats as
    provisional styles that wait for a name (``cell_looks``, D379). What the model does not show at all (charts,
    pictures, a rotated text...) stays in the file for :func:`apply_edits_to_xlsx` and is listed by
    :func:`xlsx_import_losses`. Raises :class:`XlsxError` for bytes that are not an xlsx file."""
    return _model_of(open_package(xlsx_bytes))[0]


def _model_of(package: Package) -> tuple[WorkbookModel, tuple[Loss, ...]]:
    """The model of an opened file, and the losses of its pivot tables (those that are not live pivots in it)."""
    names, _ = names_and_tables(package)
    known = frozenset(named.name.casefold() for named in names)
    model = WorkbookModel()
    dressing = _dressing(model, read_looks(package.parts))
    for part in package.sheets:
        sheet = Sheet(part.sheet_id, part.name)
        read = read_sheet(package, part, known)
        sheet.cells.update(read.cells)
        _dress(dressing, sheet, read)
        model.sheets[sheet.id] = sheet
        model.open_container(str(sheet.id))
    for named in names:
        model.names.put(named)
    for chart in file_charts(package)[0]:
        if chart.held is not None:
            model.define_diagram(chart.spec)
            body = ObjectBody(chart.object_id, "diagram", chart.width, chart.height, "plain-image", ref=chart.spec_id)
            if chart.description:
                body = replace(body, description=chart.description)
            model.insert_object(VisualObject(body, CellAnchor(chart.sheet, chart.row, chart.col)))
    model._calculate_loaded()  # noqa: SLF001 (the restore()-mirroring construction idiom; see model.py's own)
    pivots = read_pivots(package, model)
    return model, (*pivots.losses.result(), *adopt_pivots(model, pivots.found).losses)


def xlsx_import_losses(xlsx_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`xlsx_to_workbook` does not show of the file, each as a code with how many: ``"formula"`` (with the
    reason it came in as its value: ``array``, ``function``, ``name``, ``syntax``), ``"date"``, ``"error-value"``,
    ``"look"``, ``"merge"``, ``"comment"``, ``"chart"``, ``"picture"``, ``"validation"``, ``"conditional-format"``,
    ``"named-range"``, ``"hidden-sheet"``... None of it is lost from the *file*: an edit written with
    :func:`apply_edits_to_xlsx` keeps all of it (D403, D371)."""
    package = open_package(xlsx_bytes)
    names, losses = names_and_tables(package)
    known = frozenset(named.name.casefold() for named in names)
    dressing = _dressing(WorkbookModel(), read_looks(package.parts))
    reads = []
    for part in package.sheets:
        read = read_sheet(package, part, known)
        _dress(dressing, Sheet(part.sheet_id, part.name), read)
        reads.append((part, read))
    held = [chart.sheet for chart in file_charts(package)[0] if chart.held is not None]
    for part, read in reads:
        for loss in read.lost.result():
            count = loss.count - held.count(part.sheet_id) if loss.kind == "chart" else loss.count
            if count:
                losses.add(loss.kind, loss.detail, count)
    for what, count in dressing.lost.items():
        losses.add("look", what, count)
    if any(related(package.parts, part.part, "pivotTable") for part in package.sheets):
        for loss in _model_of(package)[1]:
            losses.add(loss.kind, loss.detail, loss.count)
    workbook_losses(package, losses)
    return losses_in_order(losses.result(), _ORDER)


def _dressing(model: WorkbookModel, looks: XlsxLooks) -> Dressing:
    def look(index: Hashable) -> tuple[Hashable | None, Look]:
        assert isinstance(index, int)
        return looks.cells[index] if 0 <= index < len(looks.cells) else (0, looks.normal)

    return Dressing(model, looks.normal, looks.named.items(), look)


def _dress(dressing: Dressing, sheet: Sheet, read: SheetRead) -> None:
    """Give ``sheet`` the looks of its cells, rows and columns as ``read`` found them: a cell needs a range of its
    own only where its look is not its row's (or, in a row without one, its column's)."""
    columns = [(first, last, dressing.style(index)) for first, last, index in read.column_looks]
    rows = {row: dressing.style(index) for row, index in read.row_looks.items()}
    by_column = Lines(columns)
    sheet.col_widths.update(read.col_widths)
    sheet.row_heights.update(read.row_heights)
    cells = {}
    for (row, col), index in read.looks.items():
        dressing.count(index)
        style = dressing.style(index)
        inherited = rows.get(row) or by_column.at(col) or DEFAULT_CELL_STYLE
        if style != inherited:
            cells[(row, col)] = style
    dressing.dress(sheet, SheetLooks(cells, runs_of(rows), columns))


_ORDER = (
    "formula",
    "alternatives",
    "date",
    "error-value",
    "named-range",
    "table",
    "chart",
    "picture",
    "shape",
    "comment",
    "merge",
    "look",
    "layout",
    "conditional-format",
    "validation",
    "filter",
    "pivot-table",
    "protection",
    "hidden-sheet",
)


def apply_edits_to_xlsx(
    original_bytes: bytes, baseline: WorkbookModel, current: WorkbookModel, *, losses: LossLog | None = None
) -> bytes:
    """Re-export ``current`` to xlsx by writing the cells that changed since ``baseline`` (the model as it stood
    right after :func:`xlsx_to_workbook` imported ``original_bytes``) into those same bytes (D371, after D220).

    Only the edited cells of each worksheet change in its XML; every other cell, and everything else on the sheet
    and in the file -- the look of cells, lists, icon sets, spilled formulas, pictures, charts, comments -- stays as
    the file had it. An edited cell keeps its look. A cell, row or column whose look changed (another style, or a
    style that was changed) points at a new entry of ``styles.xml``, which is only ever added to
    (``xlsx_restyle``, D379). A note that holds alternatives is written into the sheet's comments; somebody else's
    comment on the same cell wins. When a formula changed, Excel's calculation chain is dropped (Excel builds it
    again), and the workbook asks to be calculated when it is opened.

    Charts: one that was added is a new part in the drawing of its sheet, one that was removed is taken out with its
    part, one that was moved or made another size has its anchor changed, one that was described its alt text, and
    one whose definition or numbers changed is drawn again; a chart another program drew keeps its drawing unless its
    definition changed (``losses`` gets ``chart`` / ``look`` then, and what a file cannot keep of the charts:
    :func:`xlsx_export_losses`; D463).

    Raises :class:`UnsupportedEdit` if a sheet or a chart tab was added, removed, renamed or reordered since
    ``baseline``, or a cell inside an array formula or a spilled range was changed. An unchanged model gives back
    ``original_bytes``."""
    baseline_sheets = [(sheet.id, sheet.name) for sheet in baseline.sheets.values()]
    current_sheets = [(sheet.id, sheet.name) for sheet in current.sheets.values()]
    if baseline_sheets != current_sheets:
        raise UnsupportedEdit(
            "adding, removing, renaming or reordering a sheet cannot be patched onto the original file yet"
        )
    current.calc.recalculate_all()  # (``store`` without the server's settle leaves dependents stale, as for ods)
    package = open_package(original_bytes)
    patch = PackagePatch(package.parts)
    names = XlsxNamesPatch(patch, package, baseline, current)
    styles = StylesPatch(patch.parts, current)
    old_looks = LookExport(baseline)
    restyled = changed_styles(old_looks, styles.looks)
    changed = formulas = refresh = False
    for part in package.sheets:
        before, after = baseline.sheets[part.sheet_id], current.sheets[part.sheet_id]
        looks = restyling((old_looks, before), (styles.looks, after), restyled)
        held = (sheet_cells(baseline, before), sheet_cells(current, after))
        edited = {
            position
            for position in held[0].keys() | held[1].keys()
            if _content(held[0], position) != _content(held[1], position)
        }
        if not edited and not looks and not _resized(before, after):
            continue  # nothing about this sheet changed: its part stays exactly as it is
        changed = True
        refresh |= bool(edited & pivot_positions(current, part.sheet_id))
        formulas |= _write_sheet(patch, part.part, (before, after), held, (styles, looks))
    if refresh:
        ask_refresh(patch, package)
    changed |= names.run()
    changed |= patch_charts(patch, package, baseline, current, (losses or LossLog()).add)
    if not changed:
        return original_bytes
    styles.finish()
    if formulas:
        patch.drop_calculation_chain()
    patch.ask_for_calculation()
    return write_parts(patch.finish())


def _resized(before: Sheet, after: Sheet) -> bool:
    return before.col_widths != after.col_widths or before.row_heights != after.row_heights


def _content(held: dict[tuple[int, int], tuple[Content, Value]], position: tuple[int, int]) -> Content | None:
    found = held.get(position)
    return None if found is None else found[0]


def _write_sheet(
    patch: PackagePatch,
    part: str,
    sheets: tuple[Sheet, Sheet],
    held: tuple[dict[tuple[int, int], tuple[Content, Value]], dict[tuple[int, int], tuple[Content, Value]]],
    looks: tuple[StylesPatch, Restyling],
) -> bool:
    """Write the cells ``held`` after that differ from those held before into the sheet ``part`` (the cells a sheet
    has with the value each shows, pivots' included: :func:`~claudia_computes_io.pivot_exchange.sheet_cells`), and the
    looks that changed; whether a formula changed."""
    before, after = sheets
    sheet = SheetPatch(patch.parts[part])
    notes = SheetNotes(patch, part, sheet)
    formulas = False
    for row, col in sorted(held[0].keys() | held[1].keys()):
        content = _content(held[1], (row, col))
        if _content(held[0], (row, col)) == content:
            continue
        cell = None if content is None else written(content, held[1][(row, col)][1])
        formulas |= sheet.put(row, col, cell)
        notes.set(row, col, None if cell is None else cell.note)
    notes.finish()
    restyle_sheet(sheet, *looks)
    sheet.resize_columns(changed_sizes(before.col_widths, after.col_widths))
    sheet.resize_rows(changed_sizes(before.row_heights, after.row_heights))
    patch.parts[part] = sheet.to_bytes()
    return formulas


def _resolve_target(source_dir: str, target: str) -> str:
    """An OPC relationship ``Target`` resolved against the directory of the part that references it: package-
    absolute (a leading ``/``) from the zip root, otherwise relative to ``source_dir`` (D147: openpyxl writes the
    workbook's own sheet relationships as package-absolute, so both forms have to be handled)."""
    return target[1:] if target.startswith("/") else posixpath.normpath(posixpath.join(source_dir, target))


def _sheet_part(members: dict[str, bytes], sheet_name: str) -> str:
    """The zip member holding ``sheet_name``'s XML, resolved through ``workbook.xml`` and its rels -- never assumed
    from sheet order, which openpyxl does not promise to keep stable across a save."""
    workbook = parse_xml(members["xl/workbook.xml"])
    rels = parse_xml(members["xl/_rels/workbook.xml.rels"])
    sheets = workbook.find(_qn("x", "sheets"))
    if sheets is None:
        raise ValueError("xl/workbook.xml has no <sheets>: not a well-formed workbook part")
    rid = next((el.get(_qn("r", "id")) for el in sheets if el.get("name") == sheet_name), None)
    if rid is None:
        raise ValueError(f"no sheet named {sheet_name!r}")
    target = next((rel.get("Target") for rel in rels if rel.get("Id") == rid), None)
    if target is None:
        raise ValueError(f"workbook.xml.rels has no relationship {rid!r}")
    return _resolve_target("xl", target)


def _header_and_rows(wb: openpyxl.Workbook, sheet_name: str, cell_range: str) -> tuple[list[str], list[tuple]]:
    ws = wb[sheet_name]
    rows = [tuple(cell.value for cell in row) for row in ws[cell_range]]
    if not rows:
        raise ValueError(f"{cell_range!r} on {sheet_name!r} is empty")
    header, data = [str(v) for v in rows[0]], rows[1:]
    if not data:
        raise ValueError(f"{cell_range!r} on {sheet_name!r} has no data rows below its header")
    return header, data


def _shared_items(header: list[str], rows: list[tuple], value_col: int) -> tuple[dict[int, list], dict[int, dict]]:
    """Every non-data column's distinct values, first-appearance order, and the index of each value within them."""
    other_cols = [col for col in range(len(header)) if col != value_col]
    items = {col: list(dict.fromkeys(row[col] for row in rows)) for col in other_cols}
    index = {col: {value: i for i, value in enumerate(values)} for col, values in items.items()}
    return items, index


def _cache_xml(
    header: list[str], rows: list[tuple], value_col: int, *, source_sheet: str, source_range: str
) -> tuple[str, str]:
    """The pivot cache's two parts: the field definitions (one per source column) and the records (one per row)."""
    amounts = [row[value_col] for row in rows]
    shared_items, shared_index = _shared_items(header, rows, value_col)

    def _cache_field(col: int, name: str) -> str:
        name = _attr(name)
        if col == value_col:
            return (
                f'<cacheField name="{name}" numFmtId="0"><sharedItems containsSemiMixedTypes="0" '
                f'containsString="0" containsNumber="1" minValue="{_attr(min(amounts))}" '
                f'maxValue="{_attr(max(amounts))}"/></cacheField>'
            )
        items = "".join(f'<s v="{_attr(v)}"/>' for v in shared_items[col])
        return f'<cacheField name="{name}" numFmtId="0"><sharedItems count="{len(shared_items[col])}">{items}</sharedItems></cacheField>'  # noqa: E501

    def _record(row: tuple) -> str:
        parts = [
            f'<n v="{_attr(row[col])}"/>' if col == value_col else f'<x v="{shared_index[col][row[col]]}"/>'
            for col in range(len(header))
        ]
        return f"<r>{''.join(parts)}</r>"

    cache_fields = "".join(_cache_field(col, name) for col, name in enumerate(header))
    cache_def = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1" '
        'refreshedBy="claudia-computes-io" refreshedDate="45600" createdVersion="6" refreshedVersion="6" '
        f'minRefreshableVersion="3" recordCount="{len(rows)}"><cacheSource type="worksheet">'
        f'<worksheetSource ref="{_attr(source_range)}" sheet="{_attr(source_sheet)}"/></cacheSource>'
        f'<cacheFields count="{len(header)}">{cache_fields}</cacheFields></pivotCacheDefinition>'
    )
    records = "".join(_record(row) for row in rows)
    cache_records = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<pivotCacheRecords xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'count="{len(rows)}">{records}</pivotCacheRecords>'
    )
    return cache_def, cache_records


def _pivot_table_xml(header: list[str], row_col: int, value_col: int, value_field: str, row_count: int) -> str:
    """The pivot table itself: ``row_field`` down the rows, the sum of ``value_field`` as the one data field."""

    def _pivot_field(col: int) -> str:
        if col == value_col:
            return '<pivotField dataField="1" showAll="0"/>'
        if col == row_col:
            items = "".join(f'<item x="{i}"/>' for i in range(row_count)) + '<item t="default"/>'
            return f'<pivotField axis="axisRow" showAll="0"><items count="{row_count + 1}">{items}</items></pivotField>'  # noqa: E501
        return '<pivotField showAll="0"/>'

    def _row_item(i: int) -> str:
        return "<i><x/></i>" if i == 0 else f'<i><x v="{i}"/></i>'

    pivot_fields = "".join(_pivot_field(col) for col in range(len(header)))
    row_items = "".join(_row_item(i) for i in range(row_count)) + '<i t="grand"><x/></i>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<pivotTableDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'name="PivotTable1" cacheId="0" applyNumberFormats="0" applyBorderFormats="0" applyFontFormats="0" '
        'applyPatternFormats="0" applyAlignmentFormats="0" applyWidthHeightFormats="1" dataCaption="Values" '
        'updatedVersion="6" minRefreshableVersion="3" useAutoFormatting="1" itemPrintTitles="1" createdVersion="6" '
        f'indent="0" outline="1" outlineData="1" multipleFieldFilters="0"><location ref="A1:B{row_count + 2}" '
        f'firstHeaderRow="1" firstDataRow="2" firstDataCol="1"/><pivotFields count="{len(header)}">{pivot_fields}'
        f'</pivotFields><rowFields count="1"><field x="{row_col}"/></rowFields>'
        f'<rowItems count="{row_count + 1}">{row_items}</rowItems><colItems count="1"><i/></colItems>'
        f'<dataFields count="1"><dataField name="Sum of {_attr(value_field)}" fld="{value_col}" baseField="0" '
        'baseItem="0"/></dataFields></pivotTableDefinition>'
    )


def _register_pivot_cache(members: dict[str, bytes]) -> None:
    """Wire the new pivot cache into the package: a content-type override, a workbook relationship, and the
    ``<pivotCaches>`` element ``workbook.xml`` needs to point at it -- the three parts a pivot cache always needs,
    whatever the pivot table built on top of it looks like."""
    content_types = parse_xml(members["[Content_Types].xml"])
    for part_name, content_type in (
        (
            "/xl/pivotCache/pivotCacheDefinition1.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml",
        ),
        (
            "/xl/pivotCache/pivotCacheRecords1.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml",
        ),
        (
            "/xl/pivotTables/pivotTable1.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml",
        ),
    ):
        override = etree.SubElement(content_types, _qn("ct", "Override"))
        override.set("PartName", part_name)
        override.set("ContentType", content_type)
    members["[Content_Types].xml"] = _tostring(content_types)

    workbook_rels = parse_xml(members["xl/_rels/workbook.xml.rels"])
    rel = etree.SubElement(workbook_rels, _qn("pr", "Relationship"))
    rel.set("Id", "rIdPivotCache1")
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition")
    rel.set("Target", "pivotCache/pivotCacheDefinition1.xml")
    members["xl/_rels/workbook.xml.rels"] = _tostring(workbook_rels)

    workbook_xml = parse_xml(members["xl/workbook.xml"])
    calc_pr = workbook_xml.find(_qn("x", "calcPr"))
    pivot_caches = etree.Element(_qn("x", "pivotCaches"))
    pivot_cache = etree.SubElement(pivot_caches, _qn("x", "pivotCache"))
    pivot_cache.set("cacheId", "0")
    pivot_cache.set(_qn("r", "id"), "rIdPivotCache1")
    (calc_pr.addnext if calc_pr is not None else workbook_xml.append)(pivot_caches)
    members["xl/workbook.xml"] = _tostring(workbook_xml)


def add_pivot_table(
    xlsx_bytes: bytes,
    *,
    source_sheet: str,
    source_range: str,
    row_field: str,
    value_field: str,
    pivot_sheet_name: str = "Pivot",
) -> bytes:
    """``xlsx_bytes`` with one pivot table added: ``row_field`` down the rows, the sum of ``value_field`` as the one
    data field, on a new (or existing empty) sheet ``pivot_sheet_name``. ``source_range`` is the whole table,
    header row first; every column in it becomes a cached field, so the pivot table can later be widened in Excel.

    Only one row field and one data field are built (as the spike validated); more fields, column fields and filters
    are not yet additive -- a later slice would widen this the same way, without touching openpyxl itself.
    """
    wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
    header, rows = _header_and_rows(wb, source_sheet, source_range)
    if row_field not in header or value_field not in header:
        raise ValueError(f"{row_field!r} and {value_field!r} must both be headers in {source_range!r}: {header}")
    row_col, value_col = header.index(row_field), header.index(value_field)
    row_count = len(list(dict.fromkeys(row[row_col] for row in rows)))

    if pivot_sheet_name not in wb.sheetnames:
        wb.create_sheet(pivot_sheet_name)
    base = BytesIO()
    wb.save(base)
    with zipfile.ZipFile(base) as z:
        members = {name: z.read(name) for name in z.namelist()}

    pivot_part = _sheet_part(members, pivot_sheet_name)
    cache_def, cache_records = _cache_xml(header, rows, value_col, source_sheet=source_sheet, source_range=source_range)
    pivot_table = _pivot_table_xml(header, row_col, value_col, value_field, row_count)
    _register_pivot_cache(members)

    sheet_rels_path = f"{posixpath.dirname(pivot_part)}/_rels/{posixpath.basename(pivot_part)}.rels"
    members[sheet_rels_path] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotTable" '
        b'Target="../pivotTables/pivotTable1.xml"/></Relationships>'
    )
    members["xl/pivotCache/pivotCacheDefinition1.xml"] = cache_def.encode("utf-8")
    members["xl/pivotCache/pivotCacheRecords1.xml"] = cache_records.encode("utf-8")
    members["xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords" '
        b'Target="pivotCacheRecords1.xml"/></Relationships>'
    )
    members["xl/pivotTables/pivotTable1.xml"] = pivot_table.encode("utf-8")
    members["xl/pivotTables/_rels/pivotTable1.xml.rels"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition" '
        b'Target="../pivotCache/pivotCacheDefinition1.xml"/></Relationships>'
    )

    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return out.getvalue()
