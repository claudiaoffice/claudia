"""Defined names and tables in xlsx files (D457): written on export, read on import, patched into a kept file."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import openpyxl
from claudia_computes_io import (
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_to_workbook,
    xlsx_unwritten_changes,
)
from claudia_computes_io.xlsx_names import reference_of
from lxml import etree
from test_xlsx_real_world import NAMED

from claudia_computes import CellRef, NamedRange, RangeRef, Sheet, SheetId, WorkbookModel
from claudia_odf_io import Loss

DATA, OTHER = SheetId("s1"), SheetId("s2")
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def box(sheet: SheetId, first: tuple[int, int], last: tuple[int, int] | None = None) -> RangeRef:
    return RangeRef(CellRef(*first, sheet), CellRef(*(last or first), sheet))


def a_model(*names: NamedRange, sheet_name: str = "Data") -> WorkbookModel:
    model = WorkbookModel()
    for sheet_id, name in ((DATA, sheet_name), (OTHER, "Other")):
        model.sheets[sheet_id] = Sheet(sheet_id, name)
        model.open_container(str(sheet_id))
    data = model.sheets[DATA]
    for position, content in {
        (0, 0): {"t": "text", "v": "Item"},
        (0, 1): {"t": "text", "v": "Amount"},
        (1, 0): {"t": "text", "v": "Tea"},
        (1, 1): {"t": "int", "v": 4},
        (2, 0): {"t": "text", "v": "Rice"},
        (2, 1): {"t": "int", "v": 6},
    }.items():
        data.cells[position] = content
    for named in names:
        model.names.put(named)
    model._calculate_loaded()
    return model


RATE = NamedRange("Rate", None, box(DATA, (1, 1)))
TABLE = NamedRange("Sales", None, box(DATA, (0, 0), (2, 1)), header=True)
LOCAL = NamedRange("Only", OTHER, box(OTHER, (0, 0), (0, 2)))


def names_of(model: WorkbookModel) -> list[NamedRange]:
    return model.names.sorted()


def parts_of(data: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(data)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def kinds(losses) -> dict[str, int]:
    return {(f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind): loss.count for loss in losses}


# -- the reference a file writes -------------------------------------------------------------------------------------
def test_a_reference_names_its_sheet_and_makes_the_corners_absolute():
    assert reference_of(box(DATA, (1, 1), (4, 2)), {DATA: "Data"}) == "Data!$B$2:$C$5"
    assert reference_of(box(DATA, (0, 0)), {DATA: "Bob's data"}) == "'Bob''s data'!$A$1"


# -- exporting -------------------------------------------------------------------------------------------------------
def test_a_range_is_written_as_a_defined_name_and_comes_back_as_it_was():
    out = workbook_to_xlsx(a_model(RATE))
    assert openpyxl.load_workbook(BytesIO(out)).defined_names["Rate"].attr_text == "Data!$B$2"
    assert names_of(xlsx_to_workbook(out)) == [RATE]


def test_a_name_of_one_sheet_is_a_defined_name_of_that_sheet():
    out = workbook_to_xlsx(a_model(LOCAL))
    assert openpyxl.load_workbook(BytesIO(out))["Other"].defined_names["Only"].attr_text == "Other!$A$1:$C$1"
    assert names_of(xlsx_to_workbook(out)) == [LOCAL]


def test_a_table_is_written_as_a_table_with_the_header_cells_as_its_columns():
    out = workbook_to_xlsx(a_model(TABLE))
    table = openpyxl.load_workbook(BytesIO(out))["Data"].tables["Sales"]
    assert (table.ref, table.displayName) == ("A1:B3", "Sales")
    assert [column.name for column in table.tableColumns] == ["Item", "Amount"]
    assert table.autoFilter is None
    assert names_of(xlsx_to_workbook(out)) == [TABLE]


def test_a_formula_that_uses_a_name_or_a_table_column_still_calculates_after_the_trip():
    model = a_model(RATE, TABLE)
    model.sheets[DATA].cells[(1, 3)] = {"t": "formula", "v": "=Rate*10"}
    model.sheets[DATA].cells[(0, 3)] = {"t": "formula", "v": "=SUM(Sales[Amount])"}
    model._calculate_loaded()
    back = xlsx_to_workbook(workbook_to_xlsx(model))
    assert back.sheets[DATA].cells[(1, 3)] == {"t": "formula", "v": "=Rate*10"}
    assert back.sheets[DATA].grid[(1, 3)] == 40
    assert back.sheets[DATA].cells[(0, 3)] == {"t": "formula", "v": "=SUM(Sales[Amount])"}
    assert back.sheets[DATA].grid[(0, 3)] == 10


def test_a_fresh_export_loses_no_name_it_can_write():
    assert xlsx_export_losses(a_model(RATE, TABLE, LOCAL)) == ()


def test_what_a_file_cannot_hold_of_a_name_is_a_loss():
    colourful = NamedRange("Sales", None, box(DATA, (0, 0), (2, 1)), header=True, grows=True, purpose="input")
    assert kinds(xlsx_export_losses(a_model(colourful))) == {"name:purpose": 1}
    assert kinds(xlsx_export_losses(a_model(NamedRange("Result", None, anchor=(DATA, 0, 5))))) == {"name:result": 1}


def test_a_table_whose_header_is_not_text_is_written_as_a_range_and_the_loss_says_so():
    model = a_model(TABLE)
    model.sheets[DATA].cells[(0, 1)] = {"t": "int", "v": 2026}
    model._calculate_loaded()
    assert kinds(xlsx_export_losses(model)) == {"name:table-header": 1}
    assert names_of(xlsx_to_workbook(workbook_to_xlsx(model))) == [NamedRange("Sales", None, TABLE.range)]


def test_a_table_whose_columns_have_one_name_twice_is_written_as_a_range_too():
    model = a_model(TABLE)
    model.sheets[DATA].cells[(0, 1)] = {"t": "text", "v": "ITEM"}
    model._calculate_loaded()
    assert kinds(xlsx_export_losses(model)) == {"name:table-header": 1}


# -- importing -------------------------------------------------------------------------------------------------------
def test_the_names_of_a_file_come_in_without_the_marks_of_how_they_were_written():
    names = names_of(xlsx_to_workbook(NAMED))
    assert [(named.name, named.range) for named in names] == [
        ("Rate", box(SheetId("s1"), (0, 0))),
        ("Local", box(SheetId("s1"), (0, 1))),
    ]


# -- editing a kept file ---------------------------------------------------------------------------------------------
def a_file(*names: NamedRange) -> bytes:
    return workbook_to_xlsx(a_model(*names))


def patched(original: bytes, change) -> tuple[bytes, WorkbookModel]:
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    change(current)
    return apply_edits_to_xlsx(original, baseline, current), current


def test_a_file_whose_names_did_not_change_comes_back_as_it_was():
    original = a_file(RATE, TABLE)
    out, _ = patched(original, lambda model: None)
    assert out == original


def test_a_name_made_in_claudia_is_added_and_the_names_of_the_file_stay():
    original = NAMED
    out, _ = patched(original, lambda model: model.names.put(NamedRange("Fresh", None, box(SheetId("s1"), (0, 1)))))
    workbook = parts_of(out)["xl/workbook.xml"].decode()
    assert 'name="Fresh"' in workbook
    assert 'name="Twice"' in workbook  # what the file names that the model cannot, stays
    assert 'name="_xlnm.Print_Area"' in workbook
    assert {named.name for named in xlsx_to_workbook(out).names} == {"Rate", "Local", "Fresh"}


def test_names_are_added_to_a_file_that_has_none_before_the_calculation_settings():
    original = a_file()
    out, _ = patched(
        original,
        lambda model: (
            model.names.put(NamedRange("Rate", None, box(DATA, (1, 1)))),
            model.names.put(NamedRange("Only", OTHER, box(OTHER, (0, 0)))),
        ),
    )
    root = etree.fromstring(parts_of(out)["xl/workbook.xml"])
    order = [etree.QName(element).localname for element in root]
    assert order.index("sheets") < order.index("definedNames") < order.index("calcPr")
    scoped = root.find(f"{{{MAIN}}}definedNames/{{{MAIN}}}definedName[@name='Only']")
    assert scoped.get("localSheetId") == "1"
    assert {named.name for named in xlsx_to_workbook(out).names} == {"Rate", "Only"}


def test_a_name_that_is_taken_out_goes_from_the_file_and_nothing_else_does():
    original = NAMED
    out, _ = patched(original, lambda model: model.names.put(None, (None, "rate")))
    workbook = parts_of(out)["xl/workbook.xml"].decode()
    assert 'name="Rate"' not in workbook
    assert 'name="Twice"' in workbook and 'name="Local"' in workbook


def test_a_name_that_points_somewhere_else_is_written_again_in_its_place():
    out, _ = patched(NAMED, lambda model: model.names.put(NamedRange("Rate", None, box(SheetId("s1"), (0, 0), (0, 1)))))
    assert xlsx_to_workbook(out).names.get((None, "rate")).range == box(SheetId("s1"), (0, 0), (0, 1))


def tables_of(data: bytes) -> dict[str, etree._Element]:
    return {name: etree.fromstring(part) for name, part in parts_of(data).items() if name.startswith("xl/tables/table")}


def test_a_table_made_in_claudia_is_a_new_part_the_sheet_points_at():
    out, _ = patched(a_file(), lambda model: model.names.put(TABLE))
    parts = parts_of(out)
    ((name, table),) = tables_of(out).items()
    assert (table.get("displayName"), table.get("ref"), table.get("id")) == ("Sales", "A1:B3", "1")
    assert [column.get("name") for column in table.iter(f"{{{MAIN}}}tableColumn")] == ["Item", "Amount"]
    assert f'PartName="/{name}"' in parts["[Content_Types].xml"].decode()
    assert "<tablePart " in parts["xl/worksheets/sheet1.xml"].decode()
    assert f"../tables/{name.rsplit('/', 1)[1]}" in parts["xl/worksheets/_rels/sheet1.xml.rels"].decode()
    assert names_of(xlsx_to_workbook(out)) == [TABLE]


def test_a_second_table_gets_an_id_and_a_name_of_its_own():
    original = a_file(TABLE)
    other = NamedRange("More", None, box(OTHER, (0, 0), (1, 1)), header=True)

    def change(model: WorkbookModel) -> None:
        model.sheets[OTHER].cells[(0, 0)] = {"t": "text", "v": "x"}
        model.sheets[OTHER].cells[(0, 1)] = {"t": "text", "v": "y"}
        model.names.put(other)

    out, _ = patched(original, change)
    assert sorted(table.get("id") for table in tables_of(out).values()) == ["1", "2"]
    assert {named.name for named in xlsx_to_workbook(out).names} == {"Sales", "More"}


def test_a_table_that_is_taken_out_takes_its_part_and_its_pointers_with_it():
    original = a_file(TABLE)
    out, _ = patched(original, lambda model: model.names.put(None, (None, "sales")))
    parts = parts_of(out)
    assert not tables_of(out)
    assert "tablePart" not in parts["xl/worksheets/sheet1.xml"].decode()
    assert "table" not in parts["[Content_Types].xml"].decode().replace("spreadsheetml.sheet", "")
    assert not xlsx_to_workbook(out).names


def test_a_table_that_gets_more_rows_is_resized_in_its_part_and_keeps_the_rest_of_it():
    original = with_style(a_file(TABLE))
    bigger = NamedRange("Sales", None, box(DATA, (0, 0), (5, 1)), header=True)
    out, _ = patched(original, lambda model: model.names.put(bigger))
    ((_, table),) = tables_of(out).items()
    assert table.get("ref") == "A1:B6"
    assert table.find(f"{{{MAIN}}}tableStyleInfo") is not None  # the file's own table style stays


def test_a_table_that_gets_a_column_is_written_again_with_its_columns():
    original = a_file(TABLE)
    wider = NamedRange("Sales", None, box(DATA, (0, 0), (2, 2)), header=True)

    def change(model: WorkbookModel) -> None:
        model.sheets[DATA].cells[(0, 2)] = {"t": "text", "v": "Note"}
        model.names.put(wider)

    out, _ = patched(original, change)
    ((_, table),) = tables_of(out).items()
    assert [column.get("name") for column in table.iter(f"{{{MAIN}}}tableColumn")] == ["Item", "Amount", "Note"]
    assert xlsx_to_workbook(out).names.get((None, "sales")).range == wider.range


def test_a_header_cell_that_is_edited_changes_the_name_of_its_column_in_the_table():
    original = a_file(TABLE)
    out, _ = patched(original, lambda model: model.store(model.sheets[DATA], 0, 1, {"t": "text", "v": "Total"}))
    ((_, table),) = tables_of(out).items()
    assert [column.get("name") for column in table.iter(f"{{{MAIN}}}tableColumn")] == ["Item", "Total"]


def test_a_header_cell_that_is_no_longer_text_turns_the_table_into_a_name_with_a_loss():
    original = a_file(TABLE)
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    current.store(current.sheets[DATA], 0, 1, {"t": "int", "v": 7})
    out = apply_edits_to_xlsx(original, baseline, current)
    assert not tables_of(out)
    assert 'name="Sales"' in parts_of(out)["xl/workbook.xml"].decode()
    assert xlsx_unwritten_changes(current, baseline) == (Loss("name", "table-header", 1),)


def test_what_a_patch_cannot_write_of_a_name_is_a_loss():
    original = a_file()
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    current.names.put(NamedRange("Result", None, anchor=(DATA, 0, 5)))
    current.names.put(NamedRange("Shaded", None, box(DATA, (0, 0)), header=True, purpose="input"))
    assert kinds(xlsx_unwritten_changes(current, baseline)) == {"name:purpose": 1, "name:result": 1}


def with_style(data: bytes) -> bytes:
    """``data`` with a table style on its first table, as Excel writes one."""
    parts = parts_of(data)
    name = next(name for name in parts if name.startswith("xl/tables/table"))
    parts[name] = parts[name].replace(
        b"</table>", b'<tableStyleInfo name="TableStyleMedium2" showRowStripes="1"/></table>'
    )
    return with_parts(data, parts)


def with_parts(data: bytes, parts: dict[str, bytes]) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as zf:
        for name, part in parts.items():
            zf.writestr(name, part)
    return out.getvalue()


def test_a_name_of_a_sheet_counts_the_sheets_the_model_does_not_have_too():
    """``localSheetId`` is the place among *all* the sheets: a chart sheet in front of a worksheet counts."""
    from test_xlsx_real_world import package, rows, with_workbook  # noqa: PLC0415

    data = with_workbook(
        package({"Plan": rows(), "Other": rows()}),
        after_sheets='<definedNames><definedName name="Mine" localSheetId="1">Other!$A$1</definedName></definedNames>',
    )
    assert names_of(xlsx_to_workbook(data)) == [NamedRange("Mine", SheetId("s2"), box(SheetId("s2"), (0, 0)))]
