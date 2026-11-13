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

``xlsx_to_workbook`` and ``apply_edits_to_xlsx`` close the loop D217 opened for docx and D219 closed for pptx, now
for xlsx (D220): a worksheet becomes a :class:`~claudia_computes.Sheet` of cell contents, and re-exporting an
*edited* import patches only the sheets whose cells actually changed onto the original bytes (through
``claudia_opc_io.reconcile``), so a chart, an embedded image, a sheet claudia never touched survives untouched. The
reconcile strategy owns only the touched sheets' own worksheet XML parts, never ``xl/styles.xml`` or
``xl/sharedStrings.xml``: openpyxl drops the shared-string table on every save of its own accord (every string
becomes an inline string, regardless of how the source file encoded it), so a touched sheet never needs the shared
table and an untouched one keeps referencing the pristine, reconciled-back original; and openpyxl preserves a
workbook's exact style-index numbering through a round trip as long as no style, font or fill is touched, which
this module never does (cells carry no per-cell style in claudia's model -- styles apply only to floating objects,
out of scope here). Both findings were confirmed empirically against openpyxl itself before writing this, the same
way D147's pivot-table spike was; see the implementation note.
"""

from __future__ import annotations

import posixpath
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

import openpyxl
from lxml import etree
from openpyxl.comments import Comment

from claudia_computes import Content, Sheet, SheetId, WorkbookModel, content_of
from claudia_computes.values import ErrorValue, Value
from claudia_odf_io import Loss, LossLog
from claudia_opc_io import owns, reconcile

from .extensions import from_excel, restore_alternatives, to_excel, with_note
from .openformula import Untranslatable

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
    written = with_note(content)
    shown = written.content
    if shown is None:
        return None, written.note, None
    if shown["t"] != "formula":
        return shown["v"], written.note, None
    try:
        return to_excel(shown["v"]), written.note, None
    except Untranslatable as why:
        return _shown(value), written.note, Loss("formula", why.reason)


def _put(cell, content: Content, value: Value) -> Loss | None:  # noqa: ANN001 (openpyxl's own cell class)
    """Write ``content`` into an openpyxl cell, with its note."""
    cell.value, note, lost = _written(content, value)
    cell.comment = Comment(note, _NOTE_AUTHOR) if note is not None else None
    return lost


def xlsx_export_losses(model: WorkbookModel) -> tuple[Loss, ...]:
    """What :func:`workbook_to_xlsx` cannot say in Excel for ``model``, each as a code with how many:
    ``"formula"`` (with the reason, ``random`` for a draw Excel has no single formula for: written as its value) and
    ``"alternatives"`` (written as the first alternative with a note: only claudia reads the rest)."""
    losses = LossLog()
    for sheet in model.sheets.values():
        for position, content in sheet.cells.items():
            _, note, lost = _written(content, sheet.grid.get(position))
            if lost is not None:
                losses.add(lost.kind, lost.detail)
            if note is not None:
                losses.add("alternatives")
    return losses.result()


def workbook_to_xlsx(model: WorkbookModel) -> bytes:
    """A base xlsx of ``model``: one worksheet per sheet, each cell as its stored content (a formula as its text,
    with the leading ``=``; see ``_written`` for what is written differently). No styles, number formats or
    charts yet (E6.4, E6.9 are the full story)."""
    wb = openpyxl.Workbook()
    assert wb.active is not None  # a freshly constructed Workbook always starts with one
    wb.remove(wb.active)
    for sheet in model.sheets.values():
        ws = wb.create_sheet(title=sheet.name)
        for (row, col), content in sheet.cells.items():
            _put(ws.cell(row=row + 1, column=col + 1), content, sheet.grid.get((row, col)))
    if not wb.sheetnames:
        wb.create_sheet(title="Sheet1")
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _cell_content(cell) -> Content:  # noqa: ANN001 (openpyxl's own cell classes are not exported as one type)
    """``cell``'s content as claudia's own ``Content`` shape: ``None`` for an empty cell, a formula content
    (keeping the leading ``=``; the inverse functions of ``RAND()`` read as ``RANDOM``) for a formula cell,
    :func:`~claudia_computes.content_of` for anything else; a note claudia wrote gives the alternatives back."""
    if cell.value is None:
        return None
    if cell.data_type == "f":
        content: Content = {"t": "formula", "v": from_excel(cell.value) if isinstance(cell.value, str) else cell.value}
    else:
        content = content_of(cell.value)
    return restore_alternatives(content, cell.comment.text if cell.comment is not None else None)


def xlsx_to_workbook(xlsx_bytes: bytes) -> WorkbookModel:
    """``xlsx_bytes`` as a :class:`~claudia_computes.WorkbookModel`: one sheet per worksheet, in order, each
    non-empty cell becoming a constant or formula content. Styles, number formats, charts, pivot tables, images
    and anything else a worksheet can carry are simply not modeled -- claudia has no model for them, same as a
    table is invisible to ``docx_to_text`` (D217) or a picture to ``pptx_to_slides`` (D219)."""
    wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
    model = WorkbookModel()
    for index, name in enumerate(wb.sheetnames, start=1):
        sheet = Sheet(SheetId(f"s{index}"), name)
        for row_index, row in enumerate(wb[name].iter_rows()):
            for col_index, cell in enumerate(row):
                content = _cell_content(cell)
                if content is not None:
                    sheet.cells[(row_index, col_index)] = content
        model.sheets[sheet.id] = sheet
        model.open_container(str(sheet.id))
    model._calculate_loaded()  # noqa: SLF001 (the restore()-mirroring construction idiom; see model.py's own)
    return model


class UnsupportedEdit(Exception):
    """Raised by :func:`apply_edits_to_xlsx` for an edit it cannot patch onto the original file yet: adding,
    removing, renaming or reordering a sheet. Changing a cell's content (a constant or a formula) on a sheet
    that already existed in ``baseline`` is supported."""


def apply_edits_to_xlsx(original_bytes: bytes, baseline: WorkbookModel, current: WorkbookModel) -> bytes:
    """Re-export ``current`` to xlsx by patching only the sheets whose cells actually changed since ``baseline``
    (the model as it stood right after :func:`xlsx_to_workbook` imported ``original_bytes``) onto those same
    bytes, instead of rebuilding the file from the model alone -- so a chart, an embedded image, a sheet claudia
    never touched survives untouched (D220, following D217's docx and D219's pptx design). The parts
    :func:`claudia_opc_io.reconcile` is told claudia owns are exactly the touched sheets' own worksheet XML
    parts, resolved fresh each call through ``xl/workbook.xml`` and its rels -- never ``xl/styles.xml`` or
    ``xl/sharedStrings.xml`` (see this module's own docstring for why that is safe without the per-entry merge
    those two parts would otherwise need).

    Raises :class:`UnsupportedEdit` if a sheet was added, removed, renamed or reordered since ``baseline``.
    Changing an existing cell's content is supported; adding or removing cells on an existing sheet is too, since
    that is just another cell content changing to or from ``None``."""
    baseline_sheets = [(sheet.id, sheet.name) for sheet in baseline.sheets.values()]
    current_sheets = [(sheet.id, sheet.name) for sheet in current.sheets.values()]
    if baseline_sheets != current_sheets:
        raise UnsupportedEdit(
            "adding, removing, renaming or reordering a sheet cannot be patched onto the original file yet"
        )  # noqa: E501

    wb = openpyxl.load_workbook(BytesIO(original_bytes))
    with zipfile.ZipFile(BytesIO(original_bytes)) as z:
        members = {name: z.read(name) for name in z.namelist()}

    touched_parts: set[str] = set()
    for sheet_id, sheet_name in baseline_sheets:
        before_cells, after_cells = baseline.sheets[sheet_id].cells, current.sheets[sheet_id].cells
        if before_cells == after_cells:
            continue  # nothing about this sheet changed: leave its worksheet part exactly as is
        ws = wb[sheet_name]
        for position in before_cells.keys() | after_cells.keys():
            before, after = before_cells.get(position), after_cells.get(position)
            if before == after:
                continue
            row, col = position
            _put(ws.cell(row=row + 1, column=col + 1), after, current.sheets[sheet_id].grid.get(position))
        touched_parts.add(_sheet_part(members, sheet_name))

    patched = BytesIO()
    wb.save(patched)
    return reconcile(original_bytes, patched.getvalue(), owns(touched_parts))


def _resolve_target(source_dir: str, target: str) -> str:
    """An OPC relationship ``Target`` resolved against the directory of the part that references it: package-
    absolute (a leading ``/``) from the zip root, otherwise relative to ``source_dir`` (D147: openpyxl writes the
    workbook's own sheet relationships as package-absolute, so both forms have to be handled)."""
    return target[1:] if target.startswith("/") else posixpath.normpath(posixpath.join(source_dir, target))


def _sheet_part(members: dict[str, bytes], sheet_name: str) -> str:
    """The zip member holding ``sheet_name``'s XML, resolved through ``workbook.xml`` and its rels -- never assumed
    from sheet order, which openpyxl does not promise to keep stable across a save."""
    workbook = etree.fromstring(members["xl/workbook.xml"])
    rels = etree.fromstring(members["xl/_rels/workbook.xml.rels"])
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
    content_types = etree.fromstring(members["[Content_Types].xml"])
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

    workbook_rels = etree.fromstring(members["xl/_rels/workbook.xml.rels"])
    rel = etree.SubElement(workbook_rels, _qn("pr", "Relationship"))
    rel.set("Id", "rIdPivotCache1")
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheDefinition")
    rel.set("Target", "pivotCache/pivotCacheDefinition1.xml")
    members["xl/_rels/workbook.xml.rels"] = _tostring(workbook_rels)

    workbook_xml = etree.fromstring(members["xl/workbook.xml"])
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
