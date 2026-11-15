"""Named ranges and tables in ods files (D457): written on export, read on import, patched into a kept file."""

from __future__ import annotations

from claudia_computes_io import (
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    ods_unwritten_changes,
    workbook_to_ods,
)
from claudia_computes_io.ods_names import address_of, range_of
from test_ods import an_ods, blank, content_of, formula, kinds, num, row, table, text

from claudia_computes import CellRef, NamedRange, RangeRef, Sheet, SheetId, WorkbookModel
from claudia_odf_io import Loss

DATA, OTHER = SheetId("s1"), SheetId("s2")


def box(sheet: SheetId, first: tuple[int, int], last: tuple[int, int] | None = None) -> RangeRef:
    return RangeRef(CellRef(*first, sheet), CellRef(*(last or first), sheet))


def a_model(*names: NamedRange, sheet_name: str = "Data") -> WorkbookModel:
    model = WorkbookModel()
    for sheet_id, name in ((DATA, sheet_name), (OTHER, "Other")):
        sheet = Sheet(sheet_id, name)
        model.sheets[sheet_id] = sheet
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


# -- the address a file writes ---------------------------------------------------------------------------------------
def test_an_address_names_its_sheet_and_the_corners():
    assert address_of(box(DATA, (1, 1), (4, 2)), {DATA: "Data"}) == "$Data.$B$2:.$C$5"


def test_a_cell_is_its_own_corner_and_a_sheet_name_with_a_blank_or_a_quote_is_quoted():
    assert address_of(box(DATA, (0, 0)), {DATA: "Bob's data"}) == "$'Bob''s data'.$A$1"


def test_an_address_is_read_in_the_forms_the_programs_write():
    ids = {"Data": DATA, "My data": OTHER}.get
    expected = box(DATA, (1, 1), (4, 2))
    assert range_of("$Data.$B$2:.$C$5", ids) == expected
    assert range_of("Data.B2:Data.C5", ids) == expected
    assert range_of("$'My data'.$A$1", ids) == box(OTHER, (0, 0))


def test_an_address_that_is_no_range_of_one_sheet_is_not_read():
    ids = {"Data": DATA, "Other": OTHER}.get
    for text_of in ("", "Data.A1:Other.B2", "Nowhere.A1", "$Data.$A:.$A", "$Data.$A$1:.$B$2 $Data.$D$1", "A1"):
        assert range_of(text_of, ids) is None


# -- exporting -------------------------------------------------------------------------------------------------------
def test_a_range_is_written_as_a_named_range_and_comes_back_as_it_was():
    model = a_model(RATE)
    out = workbook_to_ods(model)
    assert (
        '<table:named-range table:name="Rate" table:base-cell-address="$Data.$B$2" '
        'table:cell-range-address="$Data.$B$2"/>'
    ) in content_of(out)
    assert names_of(ods_to_workbook(out)) == [RATE]


def test_a_table_is_written_as_a_database_range_with_its_header_and_comes_back_as_it_was():
    out = workbook_to_ods(a_model(TABLE))
    assert (
        '<table:database-range table:name="Sales" table:target-range-address="Data.A1:.B3" '
        'table:contains-header="true"/>'
    ) in content_of(out)
    assert names_of(ods_to_workbook(out)) == [TABLE]


def test_a_name_of_one_sheet_is_written_inside_that_sheet():
    out = workbook_to_ods(a_model(LOCAL))
    content = content_of(out)
    sheet = content[content.index('table:name="Other"') :]
    assert 'table:name="Only"' in sheet.split("</table:table>")[0]
    assert names_of(ods_to_workbook(out)) == [LOCAL]


def test_a_formula_that_uses_a_name_still_calculates_after_the_trip():
    model = a_model(RATE)
    model.sheets[DATA].cells[(1, 3)] = {"t": "formula", "v": "=Rate*10"}
    model._calculate_loaded()
    back = ods_to_workbook(workbook_to_ods(model))
    assert back.sheets[DATA].cells[(1, 3)] == {"t": "formula", "v": "=Rate*10"}
    assert back.sheets[DATA].grid[(1, 3)] == 40


def test_a_formula_that_names_a_table_column_is_written_as_its_value_because_openformula_has_no_columns():
    model = a_model(TABLE)
    model.sheets[DATA].cells[(0, 3)] = {"t": "formula", "v": "=SUM(Sales[Amount])"}
    model._calculate_loaded()
    assert model.sheets[DATA].grid[(0, 3)] == 10
    assert Loss("formula", "reference", 1) in ods_export_losses(model)
    back = ods_to_workbook(workbook_to_ods(model))
    assert back.sheets[DATA].cells[(0, 3)] == {"t": "int", "v": 10}


def test_a_fresh_export_loses_no_name_it_can_write():
    assert ods_export_losses(a_model(RATE, TABLE, LOCAL)) == ()


def test_what_a_file_cannot_hold_of_a_name_is_a_loss():
    colourful = NamedRange("Sales", None, box(DATA, (0, 0), (2, 1)), header=True, grows=True, purpose="input")
    model = a_model(colourful)
    assert kinds(ods_export_losses(model)) == {"name:purpose": 1}
    sql = NamedRange("Result", None, anchor=(DATA, 0, 5))
    assert kinds(ods_export_losses(a_model(sql))) == {"name:result": 1}


def test_a_table_of_one_sheet_is_written_as_a_range_and_the_loss_says_so():
    scoped = NamedRange("Mine", OTHER, box(OTHER, (0, 0), (1, 1)), header=True)
    model = a_model(scoped)
    assert kinds(ods_export_losses(model)) == {"name:table-scope": 1}
    assert names_of(ods_to_workbook(workbook_to_ods(model))) == [NamedRange("Mine", OTHER, box(OTHER, (0, 0), (1, 1)))]


# -- importing -------------------------------------------------------------------------------------------------------
GLOBAL = (
    "<table:named-expressions>"
    '<table:named-range table:name="Total" table:base-cell-address="$Data.$A$1" '
    'table:cell-range-address="$Data.$A$1:.$A$2"/>'
    '<table:named-range table:name="Broken" table:cell-range-address="$Nowhere.$A$1"/>'
    '<table:named-expression table:name="Pi" table:expression="of:=3.14"/>'
    "</table:named-expressions>"
    "<table:database-ranges>"
    '<table:database-range table:name="Plain" table:target-range-address="Data.A1:.B2" '
    'table:contains-header="true"/>'
    '<table:database-range table:name="Filtered" table:target-range-address="Data.A1:.B2">'
    "<table:filter/></table:database-range>"
    '<table:database-range table:name="Headless" table:target-range-address="Data.A1:.B2" '
    'table:contains-header="false"/>'
    "</table:database-ranges>"
)
A_FILE = an_ods(table("Data", row(num("1"), num("2")) + row(num("3"), num("4"))), after=GLOBAL)


def test_the_ranges_and_tables_a_file_names_come_in_and_what_the_model_cannot_name_is_counted():
    model = ods_to_workbook(A_FILE)
    assert names_of(model) == [
        NamedRange("Plain", None, box(DATA, (0, 0), (1, 1)), header=True),
        NamedRange("Total", None, box(DATA, (0, 0), (1, 0))),
    ]
    assert kinds(ods_import_losses(A_FILE)) == {"named-range": 2, "filter": 2}


def test_a_name_inside_a_sheet_is_the_names_of_that_sheet():
    local = (
        '<table:named-expressions><table:named-range table:name="Mine" '
        'table:cell-range-address="$Data.$B$1"/></table:named-expressions>'
    )
    data = an_ods(f'<table:table table:name="Data"><table:table-column/>{row(num("1"), num("2"))}{local}</table:table>')
    assert names_of(ods_to_workbook(data)) == [NamedRange("Mine", DATA, box(DATA, (0, 1)))]
    assert ods_import_losses(data) == ()


def test_a_formula_that_uses_a_name_of_the_file_is_a_formula_in_the_model():
    named = (
        '<table:named-expressions><table:named-range table:name="Rate" '
        'table:cell-range-address="$Data.$A$1"/></table:named-expressions>'
    )
    data = an_ods(table("Data", row(num("4"), formula("of:=[.A1]*Rate", 16))), after=named)
    model = ods_to_workbook(data)
    assert model.sheets[DATA].cells[(0, 1)] == {"t": "formula", "v": "=A1*Rate"}
    assert model.sheets[DATA].grid[(0, 1)] == 16


# -- editing a kept file ---------------------------------------------------------------------------------------------
def test_a_file_whose_names_did_not_change_comes_back_as_it_was():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    assert apply_edits_to_ods(A_FILE, baseline, current) == A_FILE


def test_a_name_made_in_claudia_is_added_and_the_names_of_the_file_stay():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(NamedRange("Rate", None, box(DATA, (1, 1))))
    out = apply_edits_to_ods(A_FILE, baseline, current)
    content = content_of(out)
    assert 'table:name="Rate"' in content
    assert 'table:name="Pi"' in content  # the file's own expression stays
    assert 'table:name="Filtered"' in content
    assert {named.name for named in ods_to_workbook(out).names} == {"Plain", "Total", "Rate"}
    assert content.count("<table:named-expressions>") == 1  # (it went into the one the file has)


def test_a_table_made_in_claudia_is_added_beside_the_file_s_database_ranges():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(NamedRange("Fresh", None, box(DATA, (0, 0), (1, 1)), header=True))
    out = apply_edits_to_ods(A_FILE, baseline, current)
    assert names_of(ods_to_workbook(out))[0].name == "Fresh"
    assert content_of(out).count("<table:database-ranges>") == 1


def test_a_name_that_is_taken_out_goes_from_the_file_and_nothing_else_does():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(None, (None, "total"))
    out = apply_edits_to_ods(A_FILE, baseline, current)
    assert content_of(out) == content_of(A_FILE).replace(
        '<table:named-range table:name="Total" table:base-cell-address="$Data.$A$1" '
        'table:cell-range-address="$Data.$A$1:.$A$2"/>',
        "",
    )


def test_a_name_that_points_somewhere_else_is_rewritten_in_place():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(NamedRange("Total", None, box(DATA, (0, 0), (1, 1))))
    out = apply_edits_to_ods(A_FILE, baseline, current)
    assert 'table:cell-range-address="$Data.$A$1:.$B$2"' in content_of(out)
    assert ods_to_workbook(out).names.get((None, "total")).range == box(DATA, (0, 0), (1, 1))


def test_names_are_added_to_a_file_that_has_none_after_its_sheets():
    data = an_ods(table("Data", row(num("1"))))
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    current.names.put(NamedRange("A_name", None, box(DATA, (0, 0))))
    current.names.put(NamedRange("Grid", None, box(DATA, (0, 0)), header=True))
    out = apply_edits_to_ods(data, baseline, current)
    content = content_of(out)
    assert content.index("</table:table>") < content.index("<table:named-expressions>")
    assert content.index("<table:named-expressions>") < content.index("<table:database-ranges>")
    assert {named.name for named in ods_to_workbook(out).names} == {"A_name", "Grid"}


def test_a_name_of_a_sheet_is_added_inside_the_sheet():
    data = an_ods(table("Data", row(num("1"))), table("Other", row(num("2"))))
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    current.names.put(NamedRange("Here", OTHER, box(OTHER, (0, 0))))
    out = apply_edits_to_ods(data, baseline, current)
    assert names_of(ods_to_workbook(out)) == [NamedRange("Here", OTHER, box(OTHER, (0, 0)))]


def test_what_a_patch_cannot_write_of_a_name_is_a_loss():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(NamedRange("Result", None, anchor=(DATA, 0, 5)))
    current.names.put(NamedRange("Shaded", None, box(DATA, (0, 0)), header=True, purpose="input"))
    assert kinds(ods_unwritten_changes(current, baseline)) == {"name:purpose": 1, "name:result": 1}
    assert kinds(ods_unwritten_changes(baseline, baseline)) == {}


def test_a_name_that_is_the_same_as_a_cell_of_the_text_is_untouched_by_a_changed_cell():
    data = an_ods(table("Data", row(text("a"), blank())), after=GLOBAL)
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    current.sheets[DATA].cells[(0, 1)] = {"t": "int", "v": 5}
    out = apply_edits_to_ods(data, baseline, current)
    assert content_of(out).count("table:named-range") == content_of(data).count("table:named-range")


# -- what LibreOffice writes, and what changes with the sheets -------------------------------------------------------
def test_a_table_the_way_libreoffice_writes_it_comes_in_with_its_header():
    databases = (
        '<table:database-ranges><table:database-range table:name="Sales" '
        'table:target-range-address="Data.A1:Data.B2"/></table:database-ranges>'
    )
    data = an_ods(table("Data", row(num("1"), num("2")) + row(num("3"), num("4"))), after=databases)
    assert names_of(ods_to_workbook(data)) == [NamedRange("Sales", None, box(DATA, (0, 0), (1, 1)), header=True)]


def test_a_name_of_a_name_the_file_has_twice_is_the_first_and_the_second_is_counted():
    twice = (
        '<table:named-expressions><table:named-range table:name="Rate" table:cell-range-address="$Data.$A$1"/>'
        '<table:named-range table:name="RATE" table:cell-range-address="$Data.$B$1"/></table:named-expressions>'
    )
    data = an_ods(table("Data", row(num("1"), num("2"))), after=twice)
    assert [(named.name, named.range) for named in names_of(ods_to_workbook(data))] == [("Rate", box(DATA, (0, 0)))]
    assert kinds(ods_import_losses(data)) == {"named-range": 1}


def test_a_name_of_a_sheet_that_is_added_comes_with_the_sheet():
    original = an_ods(table("Data", row(num("1"))))
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    current.sheets[OTHER] = Sheet(OTHER, "Extra")
    current.open_container("s2")
    current.names.put(NamedRange("Fresh", OTHER, box(OTHER, (0, 0))))
    out = apply_edits_to_ods(original, baseline, current)
    assert names_of(ods_to_workbook(out)) == [NamedRange("Fresh", OTHER, box(OTHER, (0, 0)))]


def test_the_names_of_a_sheet_that_is_removed_go_with_it_and_a_name_that_pointed_into_it_goes_too():
    inside = (
        '<table:named-expressions><table:named-range table:name="Mine" '
        'table:cell-range-address="$Other.$A$1"/></table:named-expressions>'
    )
    after = (
        '<table:named-expressions><table:named-range table:name="Far" '
        'table:cell-range-address="$Other.$A$1"/></table:named-expressions>'
    )
    original = an_ods(
        table("Data", row(num("1"))),
        f'<table:table table:name="Other"><table:table-column/>{row(num("2"))}{inside}</table:table>',
        after=after,
    )
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    del current.sheets[OTHER]
    current.names.put(None, (OTHER, "mine"))
    current.names.put(None, (None, "far"))
    out = apply_edits_to_ods(original, baseline, current)
    assert names_of(ods_to_workbook(out)) == []
    assert "Far" not in content_of(out)


def test_a_name_that_points_into_a_sheet_that_got_another_name_is_written_again_with_the_new_one():
    original = an_ods(
        table("Data", row(num("1"))),
        after=(
            '<table:named-expressions><table:named-range table:name="Far" '
            'table:cell-range-address="$Data.$A$1"/></table:named-expressions>'
        ),
    )
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    current.sheets[DATA].name = "Renamed"
    out = apply_edits_to_ods(original, baseline, current)
    assert 'table:cell-range-address="$Renamed.$A$1"' in content_of(out)
    assert names_of(ods_to_workbook(out)) == [NamedRange("Far", None, box(DATA, (0, 0)))]


def test_a_name_that_changed_its_form_goes_and_comes_in_the_other_one():
    baseline, current = ods_to_workbook(A_FILE), ods_to_workbook(A_FILE)
    current.names.put(NamedRange("Total", None, box(DATA, (0, 0), (1, 0)), header=True))
    current.names.put(NamedRange("Plain", None, box(DATA, (0, 0), (1, 1))))
    out = apply_edits_to_ods(A_FILE, baseline, current)
    back = ods_to_workbook(out)
    assert back.names.get((None, "total")).header
    assert not back.names.get((None, "plain")).header
