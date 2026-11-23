"""Names of sheets, chart tabs and objects (D550): one namespace, a chart tab renamed with an undo, and a sheet whose
rename is refused until formulas can follow it."""

import pytest
from conftest import S1, chart_spec, put_chart_spec, put_image, reopen
from names_helpers import at, code, define, fill, region_of, shown

from claudia_computes import AddChart, AddSheet, RemoveChart, RemoveSheet, WorkbookModel
from claudia_core import Document, MemoryStore, RenameThing


def a_chart(doc, chart_id: str = "t1", name: str = "Revenue", spec_id: str = "c1"):
    put_chart_spec(doc, spec_id)
    doc.execute(AddChart(chart_id, name, spec_id), author="ana")


# -- what has a name ------------------------------------------------------------------------------------------
def test_sheets_and_chart_tabs_are_named_things(doc):
    a_chart(doc)
    things = sorted(doc.model.named_things())
    assert things == [("chart", "t1", "Revenue"), ("sheet", S1, "Sheet1")]
    assert doc.model.thing_name(S1) == "Sheet1"
    assert doc.model.thing_name("t1") == "Revenue"


def test_an_objects_name_is_in_the_same_list(doc):
    put_image(doc, "i1")
    doc.execute(RenameThing("i1", "Logo"), author="ana")
    assert ("image", "i1", "Logo") in doc.model.named_things()
    assert doc.model.thing_name("i1") == "Logo"


def test_a_thing_that_is_not_there_is_an_error(doc):
    with pytest.raises(ValueError, match="no object|unknown"):
        doc.model.thing_name("nothing")


# -- one namespace --------------------------------------------------------------------------------------------
def test_a_chart_tab_cannot_take_the_name_of_a_sheet(doc):
    put_chart_spec(doc)
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        doc.execute(AddChart("t1", "sheet1", "c1"), author="ana")
    assert "t1" not in doc.model.charts


def test_a_sheet_cannot_take_the_name_of_a_chart_tab(doc):
    a_chart(doc, name="Revenue")
    with pytest.raises(ValueError, match="There is already a chart called “Revenue”"):
        doc.execute(AddSheet("s2", "REVENUE"), author="ana")
    assert "s2" not in doc.model.sheets


def test_a_sheet_cannot_take_the_name_of_an_object(doc):
    put_image(doc, "i1", name="Logo")
    with pytest.raises(ValueError, match="There is already a picture called “Logo”"):
        doc.execute(AddSheet("s2", "logo"), author="ana")


def test_an_object_cannot_take_the_name_of_a_sheet(doc):
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        put_image(doc, "i1", name="sheet1")
    put_image(doc, "i2")
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        doc.execute(RenameThing("i2", "SHEET1"), author="ana")


def test_the_old_messages_for_two_sheets_or_two_charts_are_kept(doc):
    with pytest.raises(ValueError, match="a sheet called 'sheet1' exists"):
        doc.execute(AddSheet("s2", "sheet1"), author="ana")
    a_chart(doc)
    with pytest.raises(ValueError, match="a chart called 'revenue' exists"):
        doc.execute(AddChart("t2", "revenue", "c1"), author="ana")


# -- renaming a chart tab -------------------------------------------------------------------------------------
def test_a_chart_tab_is_renamed_and_undo_gives_the_old_name_back(doc):
    a_chart(doc)
    doc.execute(RenameThing("t1", "  Takings  "), author="ana")
    assert doc.model.chart("t1").name == "Takings"
    assert doc.model.chart("t1").spec_id == "c1", "only the name changes"

    doc.undo("ana")
    assert doc.model.chart("t1").name == "Revenue"


def test_a_chart_tab_keeps_its_place_in_the_tab_order_when_renamed(doc):
    put_chart_spec(doc)
    for chart_id, name in (("t1", "One"), ("t2", "Two"), ("t3", "Three")):
        doc.execute(AddChart(chart_id, name, "c1"), author="ana")
    doc.execute(RenameThing("t2", "Deux"), author="ana")
    assert list(doc.model.charts) == ["t1", "t2", "t3"]


def test_a_chart_tab_cannot_lose_its_name(doc):
    a_chart(doc)
    with pytest.raises(ValueError, match="needs a name"):
        doc.execute(RenameThing("t1", ""), author="ana")
    assert doc.model.chart("t1").name == "Revenue"


def test_a_chart_tab_may_be_renamed_to_its_own_name_written_differently(doc):
    a_chart(doc)
    doc.execute(RenameThing("t1", "REVENUE"), author="ana")
    assert doc.model.chart("t1").name == "REVENUE"


# -- sheets ---------------------------------------------------------------------------------------------------
def source(doc, address, sheet=S1):
    row, col = at(address)
    return doc.model.sheet(sheet).cells[(row, col)]["v"]


def two_sheets(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    fill(doc, {"A1": 5, "A2": 7}, sheet="s2")
    fill(doc, {"A1": "=Data!A1+Data!A2", "B1": "=SUM(Data!A1:A2)", "C1": "=A2", "A2": 1})


def test_a_sheet_is_renamed_and_the_formulas_that_read_it_follow(doc):
    two_sheets(doc)
    doc.execute(RenameThing("s2", "Takings"), author="ana")
    assert doc.model.sheet("s2").name == "Takings"
    assert source(doc, "A1") == "=Takings!A1+Takings!A2"
    assert source(doc, "B1") == "=SUM(Takings!A1:A2)"
    assert source(doc, "C1") == "=A2", "a formula that reads its own sheet is not touched"
    assert (shown(doc, "A1"), shown(doc, "B1")) == (12, 12)


def test_a_name_with_spaces_or_quotes_is_quoted_in_the_formulas(doc):
    two_sheets(doc)
    doc.execute(RenameThing("s2", "Q1 plan"), author="ana")
    assert source(doc, "A1") == "='Q1 plan'!A1+'Q1 plan'!A2"
    assert shown(doc, "A1") == 12
    assert reopen(doc).model.sheet(S1).cells[at("A1")]["v"] == source(doc, "A1")


def test_undoing_a_sheet_rename_gives_the_name_and_every_formula_back_as_it_was_typed(doc):
    two_sheets(doc)
    before = {a: source(doc, a) for a in ("A1", "B1", "C1")}
    doc.execute(RenameThing("s2", "Takings"), author="ana")
    doc.undo("ana")
    assert doc.model.sheet("s2").name == "Data"
    assert {a: source(doc, a) for a in ("A1", "B1", "C1")} == before
    assert shown(doc, "A1") == 12
    doc.redo("ana")
    assert source(doc, "A1") == "=Takings!A1+Takings!A2" and shown(doc, "A1") == 12


def test_it_is_one_step_in_the_history(doc):
    two_sheets(doc)
    steps = len(doc.log)
    doc.execute(RenameThing("s2", "Takings"), author="ana")
    assert len(doc.log) == steps + 1


def test_a_formula_that_named_a_sheet_there_was_none_of_is_not_touched(doc):
    two_sheets(doc)
    fill(doc, {"D1": "=Takings!A1"})
    assert source(doc, "D1") == "=#REF!", "it never kept the sheet's name"
    doc.execute(RenameThing("s2", "Takings"), author="ana")
    assert source(doc, "D1") == "=#REF!" and code(doc, "D1") == "#REF!"


def test_the_name_of_a_sheet_is_free_in_the_whole_document(doc):
    two_sheets(doc)
    define(doc, "Revenue", "A1:B2")
    for taken, match in (("Sheet1", "a sheet"), ("sheet1", "a sheet"), ("Revenue", "a named range")):
        with pytest.raises(ValueError, match=f"There is already {match} called"):
            doc.execute(RenameThing("s2", taken), author="ana")
    assert doc.model.sheet("s2").name == "Data"


def test_a_sheet_may_change_the_capitals_of_its_own_name_and_cannot_lose_its_name(doc):
    two_sheets(doc)
    doc.execute(RenameThing("s2", "DATA"), author="ana")
    assert source(doc, "A1") == "=DATA!A1+DATA!A2"
    with pytest.raises(ValueError, match="needs some text|needs a name"):
        doc.execute(RenameThing("s2", ""), author="ana")


def test_names_that_point_at_a_sheet_follow_it_by_id(doc):
    two_sheets(doc)
    define(doc, "Revenue", "A1:A2", sheet="s2")
    doc.execute(RenameThing("s2", "Takings"), author="ana")
    assert region_of(doc, "Revenue") == "Takings!A1:A2"


def test_a_removed_sheet_gives_its_name_back_for_somebody_else(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    doc.execute(RemoveSheet("s2"), author="ana")
    doc.execute(AddSheet("s3", "Data"), author="ana")
    assert doc.model.sheet("s3").name == "Data"


def test_removing_a_chart_frees_its_name(doc):
    a_chart(doc)
    doc.execute(RemoveChart("t1"), author="ana")
    doc.execute(AddSheet("s2", "Revenue"), author="ana")
    assert ("sheet", "s2", "Revenue") in doc.model.named_things()


# -- the log and the snapshot ---------------------------------------------------------------------------------
def test_names_survive_a_reopened_log_and_a_snapshot(doc):
    a_chart(doc)
    put_image(doc, "i1")
    doc.execute(RenameThing("i1", "Logo"), author="ana")
    doc.execute(RenameThing("t1", "Takings"), author="ana")

    again = reopen(doc)
    assert sorted(again.model.named_things()) == sorted(doc.model.named_things())

    restored = WorkbookModel.restore(doc.model.serialize())
    assert sorted(restored.named_things()) == sorted(doc.model.named_things())


# -- documents are forever ------------------------------------------------------------------------------------
def test_an_old_log_with_a_sheet_and_a_chart_of_one_name_still_replays():
    """Before names were shared nothing stopped a sheet and a chart tab from having the same name."""
    old = [
        {"k": "computes.AddSheet", "s": 1, "d": {"id": "s1", "name": "Sales", "index": None}},
        {"k": "computes.AddChart", "s": 1, "d": {"id": "t1", "name": "sales", "spec_id": "c1", "index": None}},
    ]
    registry = WorkbookModel.registry
    sheet, chart = (registry.decode(envelope) for envelope in old)
    assert sheet.legacy_names and chart.legacy_names
    assert sheet.to_data()["legacy_names"] is True


def test_a_new_command_does_not_write_the_legacy_marker(doc):
    assert "legacy_names" not in AddSheet("s2", "Data").to_data()
    assert "legacy_names" not in AddChart("t1", "Revenue", "c1").to_data()


def test_undoing_the_removal_of_an_ordinary_sheet_is_checked_again_but_works(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    doc.execute(RemoveSheet("s2"), author="ana")
    doc.undo("ana")
    assert doc.model.sheet("s2").name == "Data"


def test_an_old_workbook_with_a_sheet_and_a_chart_of_one_name_opens_and_still_works():
    spec = chart_spec().to_data()
    old = [
        {"k": "computes.AddSheet", "s": 1, "d": {"id": "s1", "name": "Sales", "index": None}},
        {"k": "core.DefineAsset", "s": 1, "d": {"asset_kind": "diagram", "data": spec}},
        {"k": "computes.AddChart", "s": 1, "d": {"id": "t1", "name": "sales", "spec_id": spec["id"], "index": None}},
    ]
    registry = WorkbookModel.registry
    commands = [registry.decode(envelope) for envelope in old]
    doc = Document(WorkbookModel(), store=MemoryStore())
    for command in commands:
        doc.execute(command, author="ana")

    assert [name for _kind, _id, name in doc.model.named_things()] == ["Sales", "sales"]
    put_image(doc, "i1")
    with pytest.raises(ValueError, match="There is already a sheet called “Sales”"):
        doc.execute(RenameThing("i1", "SALES"), author="ana")
