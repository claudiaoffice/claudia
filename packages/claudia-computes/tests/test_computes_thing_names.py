"""Names of sheets, charts and other objects (D550): one namespace, and a sheet whose rename makes the formulas that
read it follow."""

import pytest
from conftest import S1, chart_spec, put_image, reopen
from names_helpers import at, code, define, fill, region_of, shown

from claudia_computes import AddSheet, CellAnchor, RemoveSheet, SheetId, WorkbookModel, chart_steps
from claudia_computes.chart_steps import NewChart
from claudia_core import RenameThing


def a_chart(doc, object_id: str = "o1", name: str = "Revenue", spec_id: str = "c1"):
    chart = NewChart(spec_id, object_id, name, chart_spec(spec_id).to_data())
    doc.execute(chart_steps.on_sheet(doc.model, chart, CellAnchor(SheetId(S1), 4, 2), 400, 200), author="ana")


# -- what has a name ------------------------------------------------------------------------------------------
def test_sheets_and_charts_are_named_things(doc):
    a_chart(doc)
    things = sorted(doc.model.named_things())
    assert things == [("chart", "o1", "Revenue"), ("sheet", S1, "Sheet1")]
    assert doc.model.thing_name(S1) == "Sheet1"
    assert doc.model.thing_name("o1") == "Revenue"


def test_an_objects_name_is_in_the_same_list(doc):
    put_image(doc, "i1")
    doc.execute(RenameThing("i1", "Logo"), author="ana")
    assert ("image", "i1", "Logo") in doc.model.named_things()
    assert doc.model.thing_name("i1") == "Logo"


def test_a_thing_that_is_not_there_is_an_error(doc):
    with pytest.raises(ValueError, match="no object|unknown"):
        doc.model.thing_name("nothing")


def test_a_new_workbooks_first_sheet_is_called_by_the_word_of_its_makers_language():
    """UX-87: it was "Sheet1" for everybody, while the web offers a German person "Blatt2" as her next sheet. This
    package carries no catalog: the server passes in how a word is said in her language."""
    german = {"Sheet": "Blatt"}.get
    (first,) = WorkbookModel.setup_commands("de", translate=lambda word: german(word, word))
    assert first == AddSheet(SheetId("s1"), "Blatt1")


def test_a_new_workbooks_first_sheet_is_sheet1_where_the_word_is_not_translated():
    (first,) = WorkbookModel.setup_commands(None, translate=lambda word: word)
    assert first == AddSheet(SheetId("s1"), "Sheet1")


# -- one namespace --------------------------------------------------------------------------------------------
def test_a_chart_cannot_take_the_name_of_a_sheet(doc):
    with pytest.raises(ValueError, match="There is already a sheet called “Sheet1”"):
        a_chart(doc, name="sheet1")
    assert "o1" not in doc.model.objects


def test_a_sheet_cannot_take_the_name_of_a_chart(doc):
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


def test_two_sheets_or_two_charts_of_one_name_are_refused_with_the_sentence_of_a_taken_name(doc):
    with pytest.raises(ValueError, match="There is already a sheet called “sheet1”"):
        doc.execute(AddSheet("s2", "sheet1"), author="ana")
    a_chart(doc)
    with pytest.raises(ValueError, match="There is already a chart called “Revenue”"):
        a_chart(doc, "o2", "revenue", "c2")


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
    doc.execute(chart_steps.removal(doc.model, ["o1"]), author="ana")
    doc.execute(AddSheet("s2", "Revenue"), author="ana")
    assert ("sheet", "s2", "Revenue") in doc.model.named_things()


# -- the log and the snapshot ---------------------------------------------------------------------------------
def test_names_survive_a_reopened_log_and_a_snapshot(doc):
    a_chart(doc)
    put_image(doc, "i1")
    doc.execute(RenameThing("i1", "Logo"), author="ana")
    doc.execute(RenameThing("o1", "Takings"), author="ana")

    again = reopen(doc)
    assert sorted(again.model.named_things()) == sorted(doc.model.named_things())

    restored = WorkbookModel.restore(doc.model.serialize())
    assert sorted(restored.named_things()) == sorted(doc.model.named_things())


# -- documents are forever ------------------------------------------------------------------------------------
def test_an_old_log_with_two_sheets_of_one_name_still_replays():
    """Before names were shared nothing stopped two things from having the same name."""
    old = {"k": "computes.AddSheet", "s": 1, "d": {"id": "s1", "name": "Sales", "index": None}}
    sheet = WorkbookModel.registry.decode(old)
    assert sheet.legacy_names
    assert sheet.to_data()["legacy_names"] is True


def test_a_new_command_does_not_write_the_legacy_marker(doc):
    assert "legacy_names" not in AddSheet("s2", "Data").to_data()


def test_undoing_the_removal_of_an_ordinary_sheet_is_checked_again_but_works(doc):
    doc.execute(AddSheet("s2", "Data"), author="ana")
    doc.execute(RemoveSheet("s2"), author="ana")
    doc.undo("ana")
    assert doc.model.sheet("s2").name == "Data"
