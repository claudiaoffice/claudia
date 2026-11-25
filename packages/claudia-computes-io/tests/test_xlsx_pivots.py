"""Pivot tables in xlsx files (D625, D628): written as a cache and a pivot table definition with the cells they fill,
read back as live pivots when the engine makes the file's cells, and kept as they are in a kept file."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from io import BytesIO

import openpyxl
from claudia_computes_io import (
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_import_losses,
    xlsx_to_workbook,
    xlsx_unwritten_changes,
)
from claudia_computes_io.pivot_exchange import written_pivots
from claudia_computes_io.xlsx_pivots import has_room
from lxml import etree
from pivot_helpers import SALES, a_document, a_headerless_pivot_model, a_pivot_model, by_region_and_quarter, grid_of

from claudia_computes import (
    AddSheet,
    Aggregation,
    PivotFilter,
    PivotLabels,
    ValueField,
    WorkbookModel,
    create_pivot,
)
from claudia_core import Document, MemoryStore
from claudia_odf_io import LossLog
from claudia_opc_io import read_parts, write_parts

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"x": MAIN}
TABLE = "xl/pivotTables/pivotTable1.xml"
CACHE = "xl/pivotCache/pivotCacheDefinition1.xml"
RECORDS = "xl/pivotCache/pivotCacheRecords1.xml"


def kinds(losses) -> dict[str, int]:
    return {(f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind): loss.count for loss in losses}


def xml(data: bytes, part: str) -> etree._Element:
    return etree.fromstring(read_parts(data)[part])


def changed(data: bytes, part: str, edit: Callable[[etree._Element], None]) -> bytes:
    """``data`` with the XML of ``part`` edited by ``edit``."""
    parts = read_parts(data)
    root = etree.fromstring(parts[part])
    edit(root)
    parts[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return write_parts(parts)


def with_part(data: bytes, part: str, content: str) -> bytes:
    parts = read_parts(data)
    parts[part] = content.encode()
    return write_parts(parts)


def exported(definition=None, **kwargs) -> bytes:
    return workbook_to_xlsx(a_pivot_model(definition, **kwargs))


# -- writing ---------------------------------------------------------------------------------------------------------
def test_a_pivot_is_written_as_a_cache_a_table_and_the_parts_that_join_them():
    data = exported()
    parts = read_parts(data)
    assert {TABLE, CACHE, RECORDS} <= parts.keys()
    types = parts["[Content_Types].xml"].decode()
    for name, kind in ((TABLE, "pivotTable"), (CACHE, "pivotCacheDefinition"), (RECORDS, "pivotCacheRecords")):
        assert f'PartName="/{name}"' in types
        assert f"spreadsheetml.{kind}+xml" in types
    workbook = xml(data, "xl/workbook.xml")
    [cache] = workbook.findall("x:pivotCaches/x:pivotCache", NS)
    assert cache.get("cacheId") == "1"
    kids = [etree.QName(each).localname for each in workbook]
    assert kids.index("calcPr") < kids.index("pivotCaches") if "calcPr" in kids else True
    assert b"pivotTables/pivotTable1.xml" in parts["xl/worksheets/_rels/sheet2.xml.rels"]
    assert b"pivotCacheDefinition1.xml" in parts["xl/pivotTables/_rels/pivotTable1.xml.rels"]
    assert b"pivotCacheRecords1.xml" in parts["xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels"]


def test_the_table_says_where_it_is_and_which_field_is_where():
    table = xml(exported(), TABLE)
    assert table.get("name") == "P"
    assert table.find("x:location", NS).get("ref") == "A1:D6"
    assert table.get("compact") == "0" and table.get("outline") == "0"  # (the tabular layout: field names as headers)
    assert [each.get("axis") for each in table.findall("x:pivotFields/x:pivotField", NS)] == [
        "axisRow",
        "axisCol",
        None,
        None,
    ]
    assert [each.get("x") for each in table.findall("x:rowFields/x:field", NS)] == ["0"]
    assert [each.get("x") for each in table.findall("x:colFields/x:field", NS)] == ["1"]
    [value] = table.findall("x:dataFields/x:dataField", NS)
    assert (value.get("name"), value.get("fld"), value.get("subtotal")) == ("Sum of Amount", "2", None)
    assert table.get("grandTotalCaption") == "Total"


def test_the_items_of_a_field_are_listed_in_the_order_the_pivot_shows_them():
    table = xml(exported(), TABLE)
    cache = xml(exported(), CACHE)
    shared = [
        [each.get("v") for each in field.findall("x:sharedItems/x:s", NS)]
        for field in cache.findall("x:cacheFields/x:cacheField", NS)
    ]
    assert shared[0] == ["East", "North", "South"]  # (the pivot shows its members sorted, not as the source has them)
    assert shared[1] == ["Q1", "Q2"]
    rows = table.findall("x:rowItems/x:i", NS)
    assert [each.get("t") for each in rows] == [None, None, None, "grand"]
    assert [(each.find("x:x", NS).get("v") or "0") for each in rows[:3]] == ["0", "1", "2"]


def test_the_cache_holds_the_source_as_records_that_point_at_the_listed_items():
    cache = xml(exported(), CACHE)
    assert cache.get("refreshOnLoad") == "1"  # (Excel makes the table again when it opens the file)
    source = cache.find("x:cacheSource/x:worksheetSource", NS)
    assert (source.get("ref"), source.get("sheet")) == ("A1:D6", "Data")
    assert [each.get("name") for each in cache.findall("x:cacheFields/x:cacheField", NS)] == [
        "Region",
        "Quarter",
        "Amount",
        "Units",
    ]
    records = xml(exported(), RECORDS)
    assert records.get("count") == "5"
    first = records.find("x:r", NS)
    assert [(etree.QName(each).localname, each.get("v")) for each in first] == [
        ("x", "1"),  # North
        ("x", "0"),  # Q1
        ("n", "100"),  # (a number that is only added up is in the record itself)
        ("n", "1"),
    ]


def test_the_cells_of_a_pivot_are_in_the_sheet_as_values():
    wb = openpyxl.load_workbook(BytesIO(exported()))
    sheet = wb["Pivot"]
    assert [[cell.value for cell in line] for line in sheet["A1:D6"]] == grid_of(a_pivot_model(), "s2", 6, 4)
    assert not any(str(cell.value).startswith("=") for line in sheet["A1:D6"] for cell in line)


def test_totals_functions_and_names_are_written_as_asked():
    definition = by_region_and_quarter(
        total_row=False,
        total_column=True,
        values=(ValueField("Amount", Aggregation.AVERAGE, "Mean"), ValueField("Units", Aggregation.COUNT)),
    )
    table = xml(exported(definition), TABLE)
    # (Excel's "grand totals for rows" is the column at the right; "for columns" the row below)
    assert (table.get("rowGrandTotals"), table.get("colGrandTotals")) == ("1", "0")
    assert [(each.get("name"), each.get("subtotal")) for each in table.findall("x:dataFields/x:dataField", NS)] == [
        ("Mean", "average"),
        ("Count of Units", "count"),
    ]
    assert [each.get("x") for each in table.findall("x:colFields/x:field", NS)] == ["1", "-2"]  # (the values: field -2)
    assert table.find("x:colItems", NS) is None  # (several values: Excel makes the columns when it reads the file)
    assert table.find("x:location", NS).get("firstDataRow") == "3"


def test_a_filter_with_no_room_above_is_written_as_the_values_and_said():
    definition = by_region_and_quarter(
        rows=("Quarter",), columns=(), filters=(PivotFilter("Region", ("North", "East")),)
    )
    model = a_document(pivot=definition).model  # (the pivot is in the first row: no room for the buttons)
    [pivot] = written_pivots(model).pivots
    assert not has_room(model, pivot)
    data = workbook_to_xlsx(model)
    assert TABLE not in read_parts(data)
    assert kinds(xlsx_export_losses(model)) == {"pivot-table:room": 1}


def a_model_with_filter_room(keep=("North", "East")):
    """A pivot with a filter, put on row 3 so that the buttons of the filter have rows above."""
    doc = a_document()
    definition = by_region_and_quarter(rows=("Quarter",), columns=(), filters=(PivotFilter("Region", keep),))
    doc.execute(create_pivot(doc.model, "P", ("s2", 3, 0), definition, None, new_sheet="Pivot"), author="ana")
    return doc.model


def test_a_filter_with_room_above_is_written_as_a_pivot():
    model = a_model_with_filter_room()
    data = workbook_to_xlsx(model)
    table = xml(data, TABLE)
    assert table.find("x:location", NS).get("rowPageCount") == "1"
    [page] = table.findall("x:pageFields/x:pageField", NS)
    assert page.get("fld") == "0"
    region = table.findall("x:pivotFields/x:pivotField", NS)[0]
    assert region.get("axis") == "axisPage" and region.get("multipleItemSelectionAllowed") == "1"
    assert [(each.get("x"), each.get("h")) for each in region.findall("x:items/x:item", NS)] == [
        ("0", None),  # North
        ("1", "1"),  # South: hidden
        ("2", None),  # East
    ]
    assert kinds(xlsx_export_losses(model)) == {}


def test_a_filter_that_keeps_one_member_is_set_to_it():
    table = xml(workbook_to_xlsx(a_model_with_filter_room(("South",))), TABLE)
    [page] = table.findall("x:pageFields/x:pageField", NS)
    assert page.get("item") is not None
    assert not any(each.get("h") for each in table.iter(f"{{{MAIN}}}item"))


def test_a_pivot_that_cannot_be_written_as_one_is_written_as_the_values_and_said():
    model = a_headerless_pivot_model()
    data = workbook_to_xlsx(model)
    assert "xl/pivotTables/pivotTable1.xml" not in read_parts(data)
    assert openpyxl.load_workbook(BytesIO(data))["Pivot"]["A1"].value == "Sum of C"
    assert kinds(xlsx_export_losses(model)) == {"pivot-table:source": 1}


def test_a_fresh_export_says_nothing_of_a_pivot_it_wrote():
    assert kinds(xlsx_export_losses(a_pivot_model())) == {}


def test_two_pivots_are_two_caches():
    doc = a_document(pivot=by_region_and_quarter())
    doc.execute(
        create_pivot(doc.model, "Q", ("s2", 0, 6), by_region_and_quarter(columns=()), None),
        author="ana",
    )
    data = workbook_to_xlsx(doc.model)
    assert [each.get("cacheId") for each in xml(data, "xl/workbook.xml").findall("x:pivotCaches/x:pivotCache", NS)] == [
        "1",
        "2",
    ]
    back = xlsx_to_workbook(data)
    assert back.pivots.get("P") is not None and back.pivots.get("Q") is not None


def test_what_xml_cannot_hold_is_written_without_breaking_the_file():
    rows = (('Re<gi>on & "co"', "Quarter", "Amount", "Units"), ("A&B", "<Q1>", 1, 2), ("A B", "Q'2", 3, 4))
    doc = a_document(rows, pivot=by_region_and_quarter(rows=('Re<gi>on & "co"',)))
    data = workbook_to_xlsx(doc.model)
    assert openpyxl.load_workbook(BytesIO(data)) is not None
    cache = xml(data, CACHE)
    assert cache.findall("x:cacheFields/x:cacheField", NS)[0].get("name") == 'Re<gi>on & "co"'


def test_blank_and_number_in_one_field_are_written_as_what_they_are():
    rows = (
        ("Region", "Quarter", "Amount", "Units"),
        ("North", "Q1", 1.5, 1),
        ("", "Q1", 2, 2),
        ("South", "Q2", "", 3),
    )
    model = a_document(rows, pivot=by_region_and_quarter()).model
    data = workbook_to_xlsx(model)
    cache = xml(data, CACHE)
    amount = cache.findall("x:cacheFields/x:cacheField", NS)[2].find("x:sharedItems", NS)
    assert amount.get("containsNumber") == "1" and amount.get("containsBlank") == "1"
    assert amount.get("minValue") == "1.5" and amount.get("maxValue") == "2"
    records = [[etree.QName(each).localname for each in record] for record in xml(data, RECORDS)]
    assert records[2][2] == "m"


# -- round trip ------------------------------------------------------------------------------------------------------
def test_a_pivot_comes_back_as_the_pivot_it_was():
    model = a_pivot_model()
    data = workbook_to_xlsx(model)
    back = xlsx_to_workbook(data)
    assert back.pivots.get("P") == model.pivots.get("P")
    assert grid_of(back, "s2", 6, 4) == grid_of(model, "s2", 6, 4)
    assert back.sheet("s2").cells == {(0, 0): {"t": "formula", "v": '=PIVOT("P")'}}
    assert xlsx_import_losses(data) == ()


def test_the_choices_of_a_pivot_come_back():
    for definition in (
        by_region_and_quarter(total_row=False),
        by_region_and_quarter(total_column=False),
        by_region_and_quarter(total_row=False, total_column=False),
        by_region_and_quarter(columns=()),
        by_region_and_quarter(columns=(), rows=(), values=(ValueField("Amount", Aggregation.MAX),)),
        by_region_and_quarter(rows=(), values=(ValueField("Amount"), ValueField("Units", Aggregation.MIN))),
        by_region_and_quarter(
            values=(ValueField("Amount", Aggregation.AVERAGE), ValueField("Units", Aggregation.COUNT))
        ),
        by_region_and_quarter(values=(ValueField("Amount", Aggregation.SUM, "Revenue"),)),
        by_region_and_quarter(rows=("Units",), columns=("Quarter",), values=(ValueField("Amount"),)),
    ):
        model = a_pivot_model(definition)
        back = xlsx_to_workbook(workbook_to_xlsx(model))
        entry = back.pivots.get("P")
        assert entry is not None, definition
        assert entry.definition == definition, definition
        result = model.pivots.result("P")
        assert grid_of(back, "s2", result.height, result.width) == grid_of(model, "s2", result.height, result.width)


def test_a_filter_comes_back():
    model = a_model_with_filter_room()
    back = xlsx_to_workbook(workbook_to_xlsx(model))
    entry = back.pivots.get("P")
    assert entry is not None
    assert entry.definition == model.pivots.get("P").definition
    assert back.value("s2", 3, 0) == "Quarter"  # (the cells are where the file put them, under the filter's rows)


def test_blank_members_and_numbers_on_an_axis_come_back():
    rows = (
        ("Region", "Quarter", "Amount", "Units"),
        ("North", "Q1", 1.5, 1),
        ("", "Q1", 2, 2),
        ("South", "Q2", 4, 3),
    )
    model = a_document(rows, pivot=by_region_and_quarter(rows=("Units",))).model
    back = xlsx_to_workbook(workbook_to_xlsx(model))
    assert back.pivots.get("P") is not None
    assert grid_of(back, "s2", 5, 4) == grid_of(model, "s2", 5, 4)


def test_the_words_a_pivot_was_made_with_come_back_from_its_cells():
    labels = PivotLabels(total="Gesamt", sum_of="Summe von {field}")
    model = a_pivot_model(labels=labels)
    data = workbook_to_xlsx(model)
    assert xml(data, TABLE).get("grandTotalCaption") == "Gesamt"
    entry = xlsx_to_workbook(data).pivots.get("P")
    assert entry is not None
    assert entry.labels.total == "Gesamt"
    assert entry.definition.values == (ValueField("Amount", Aggregation.SUM, "Summe von Amount"),)


def test_a_source_that_is_a_table_is_read_by_its_name():
    data = changed(
        exported(),
        CACHE,
        lambda cache: _set_source(cache, name="Sales"),
    )
    back = xlsx_to_workbook(data)
    assert back.pivots.get("P") is not None


def _set_source(cache: etree._Element, *, name: str) -> None:
    source = cache.find("x:cacheSource/x:worksheetSource", NS)
    source.attrib.clear()
    source.set("name", name)


# -- what the model cannot hold --------------------------------------------------------------------------------------
def refused(edit: Callable[[etree._Element], None], part: str = CACHE, *, data: bytes | None = None) -> dict[str, int]:
    data = changed(data or exported(), part, edit)
    assert xlsx_to_workbook(data).pivots.get("P") is None  # (the cells stay the file's)
    assert xlsx_to_workbook(data).value("s2", 5, 3) == 510
    return kinds(xlsx_import_losses(data))


def test_a_cache_of_another_file_or_a_connection_stays_cells_and_is_said():
    def external(cache):
        cache.find("x:cacheSource", NS).set("type", "external")
        cache.find("x:cacheSource", NS).set("connectionId", "1")

    def another(cache):
        cache.find("x:cacheSource", NS).set("type", "consolidation")

    assert refused(external) == {"pivot-table:data-model": 1}
    assert refused(another) == {"pivot-table:external-source": 1}


def test_what_the_engine_cannot_do_is_said_with_its_name():
    def grouped(cache):
        etree.SubElement(cache.findall("x:cacheFields/x:cacheField", NS)[0], f"{{{MAIN}}}fieldGroup")

    def calculated(cache):
        cache.findall("x:cacheFields/x:cacheField", NS)[3].set("formula", "Amount*2")

    def show_as(table):
        table.find("x:dataFields/x:dataField", NS).set("showDataAs", "percentOfTotal")

    def product(table):
        table.find("x:dataFields/x:dataField", NS).set("subtotal", "product")

    def hidden(table):
        etree.SubElement(table.find("x:pivotFields/x:pivotField/x:items", NS), f"{{{MAIN}}}item", h="1", x="0")

    def descending(table):
        table.find("x:pivotFields/x:pivotField", NS).set("sortType", "descending")

    def chart(table):
        table.set("chartFormat", "1")

    def top(table):
        etree.SubElement(
            etree.SubElement(table, f"{{{MAIN}}}filters", count="1"), f"{{{MAIN}}}filter", fld="0", type="count", id="1"
        )

    for edit, part, detail in (
        (grouped, CACHE, "grouping"),
        (calculated, CACHE, "calculated-field"),
        (show_as, TABLE, "show-as"),
        (product, TABLE, "aggregation"),
        (hidden, TABLE, "hidden-items"),
        (descending, TABLE, "sort"),
        (chart, TABLE, "pivot-chart"),
        (top, TABLE, "top-n"),
    ):
        assert refused(edit, part) == {f"pivot-table:{detail}": 1}, detail


def test_a_pivot_a_slicer_reads_stays_cells_and_is_said():
    data = with_part(
        exported(),
        "xl/slicerCaches/slicerCache1.xml",
        f'<slicerCacheDefinition xmlns="{MAIN}"><pivotTables><pivotTable tabId="2" name="P"/></pivotTables>'
        "</slicerCacheDefinition>",
    )
    assert xlsx_to_workbook(data).pivots.get("P") is None
    assert kinds(xlsx_import_losses(data)) == {"pivot-table:slicer": 1}


def test_a_pivot_whose_cells_are_not_the_engines_stays_cells():
    def other_number(sheet):
        for cell in sheet.iter(f"{{{MAIN}}}c"):
            if cell.get("r") == "C2":
                cell.find("x:v", NS).text = "101"

    data = changed(exported(), "xl/worksheets/sheet1.xml", other_number)
    assert xlsx_to_workbook(data).pivots.get("P") is None
    assert kinds(xlsx_import_losses(data)) == {"pivot-table:different": 1}


def test_a_pivot_with_no_cache_part_stays_cells_and_is_said():
    parts = read_parts(exported())
    del parts[CACHE]
    data = write_parts(parts)
    assert kinds(xlsx_import_losses(data)) == {"pivot-table:source": 1}


# -- a kept file -----------------------------------------------------------------------------------------------------
def test_a_kept_file_keeps_its_pivot_when_nothing_changed():
    data = exported()
    baseline, current = xlsx_to_workbook(data), xlsx_to_workbook(data)
    assert apply_edits_to_xlsx(data, baseline, current) == data
    assert xlsx_unwritten_changes(current, baseline) == ()


def test_the_source_of_a_kept_pivot_edited_gives_the_new_numbers_and_asks_the_cache_to_be_read_again():
    data = changed(exported(), CACHE, lambda cache: cache.attrib.pop("refreshOnLoad"))
    baseline, current = xlsx_to_workbook(data), xlsx_to_workbook(data)
    current.sheet("s1").cells[(1, 2)] = {"t": "int", "v": 1000}  # North, Q1: 100 -> 1000
    current._calculate_loaded()
    assert xlsx_unwritten_changes(current, baseline) == ()  # (the definition is as it was; the numbers are written)
    out = apply_edits_to_xlsx(data, baseline, current)
    assert read_parts(out)[TABLE] == read_parts(data)[TABLE]
    assert xml(out, CACHE).get("refreshOnLoad") == "1"
    back = xlsx_to_workbook(out)
    assert back.value("s2", 3, 1) == 1000
    assert back.value("s2", 5, 1) == 1140  # the total of Q1
    assert back.pivots.get("P") is not None


def test_a_pivot_changed_in_a_kept_file_is_said_not_written():
    data = exported()
    baseline, current = xlsx_to_workbook(data), xlsx_to_workbook(data)
    entry = current.pivots.get("P")
    assert entry is not None
    current.pivots.put("P", replace(entry, definition=replace(entry.definition, total_row=False)))
    current._calculate_loaded()
    assert kinds(xlsx_unwritten_changes(current, baseline)) == {"pivot-table": 1}


def a_file_with_a_sheet_for_a_pivot() -> bytes:
    """The sales of :func:`a_document` and an empty sheet ``Pivot``, as an xlsx file."""
    doc = a_document()
    doc.execute(AddSheet("s2", "Pivot"), author="ana")
    return workbook_to_xlsx(doc.model)


def defined_in(data: bytes, name: str = "P", anchor=("s2", 0, 0), definition=None) -> WorkbookModel:
    """``data`` imported, with the pivot ``name`` defined in it where ``anchor`` says."""
    doc = Document(xlsx_to_workbook(data), store=MemoryStore())
    doc.execute(create_pivot(doc.model, name, anchor, definition or by_region_and_quarter()), author="ana")
    return doc.model


def test_api_a_pivot_defined_in_an_imported_file_is_in_the_export():
    data = a_file_with_a_sheet_for_a_pivot()
    baseline, current = xlsx_to_workbook(data), defined_in(data)
    losses = LossLog()
    out = apply_edits_to_xlsx(data, baseline, current, losses=losses)
    assert xlsx_unwritten_changes(current, baseline) == ()
    assert losses.result() == ()
    back = xlsx_to_workbook(out)
    assert back.pivots.get("P") == current.pivots.get("P")
    assert grid_of(back, "s2", 6, 4) == grid_of(current, "s2", 6, 4)
    assert xml(out, CACHE).get("refreshOnLoad") == "1"
    assert openpyxl.load_workbook(BytesIO(out))["Pivot"]._pivots  # noqa: SLF001


def test_api_a_pivot_defined_in_an_imported_file_that_has_one_gets_a_cache_of_its_own():
    data = exported()
    baseline, current = xlsx_to_workbook(data), defined_in(data, "Q", ("s2", 0, 6), by_region_and_quarter(columns=()))
    out = apply_edits_to_xlsx(data, baseline, current)
    assert xlsx_unwritten_changes(current, baseline) == ()
    caches = xml(out, "xl/workbook.xml").findall("x:pivotCaches", NS)
    assert [each.get("cacheId") for each in caches[0]] == ["1", "2"] and len(caches) == 1
    assert read_parts(out)[TABLE] == read_parts(data)[TABLE]
    back = xlsx_to_workbook(out)
    assert back.pivots.get("P") == baseline.pivots.get("P")
    assert back.pivots.get("Q") == current.pivots.get("Q")


def test_api_a_pivot_defined_in_an_imported_file_with_no_room_for_its_filter_is_its_values_and_said():
    data = a_file_with_a_sheet_for_a_pivot()
    definition = by_region_and_quarter(rows=("Quarter",), columns=(), filters=(PivotFilter("Region", ("North",)),))
    baseline, current = xlsx_to_workbook(data), defined_in(data, definition=definition)
    losses = LossLog()
    out = apply_edits_to_xlsx(data, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"pivot-table:room": 1}
    assert xlsx_unwritten_changes(current, baseline) == ()
    assert not [name for name in read_parts(out) if "pivot" in name]
    assert grid_of(xlsx_to_workbook(out), "s2", 4, 2) == grid_of(current, "s2", 4, 2)


def test_a_file_with_no_pivots_is_as_before():
    assert SALES  # (the data of the helpers)
    data = workbook_to_xlsx(a_document().model)
    assert "xl/workbook.xml" in read_parts(data)
    assert not [name for name in read_parts(data) if "pivot" in name]
