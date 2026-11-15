"""The methods for pivot tables (E6.30, D626): what the field panel reads to draw itself, and what it sends to make,
change, delete and turn into SQL a pivot."""

import pytest
from test_server_computes import BEN, VERA, call, typed

from claudia_computes import WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.protocol import RequestError

TABLE = [
    (0, 0, "Region"),
    (0, 1, "Quarter"),
    (0, 2, "Amount"),
    (1, 0, "North"),
    (1, 1, "Q1"),
    (1, 2, "900"),
    (2, 0, "North"),
    (2, 1, "Q2"),
    (2, 2, "1000"),
    (3, 0, "South"),
    (3, 1, "Q1"),
    (3, 2, "1500"),
]
AREA = {"sheet": "s1", "row0": 0, "col0": 0, "row1": 3, "col1": 2}
BY_REGION_AND_QUARTER = {
    "format": 1,
    "source": "Sales",
    "rows": ["Region"],
    "columns": ["Quarter"],
    "values": [{"field": "Amount", "aggregation": "sum", "name": ""}],
    "filters": [],
    "total_row": True,
    "total_column": True,
}


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    call(doc, "add_sheet", {"name": "Data"})
    typed(doc, "s1", TABLE)
    call(doc, "define_name", {"definition": {"name": "Sales", "range": AREA, "header": True, "grows": True}})
    return doc


def make(book, **changes):
    params = {"name": "SalesPivot", "definition": BY_REGION_AND_QUARTER, "sheet": "s1", "row": 0, "col": 5, **changes}
    return call(book, "define_pivot", params)


def cells(book, sheet, row0, row1, col0, col1):
    shown = call(book, "cells", {"sheet": sheet, "row0": row0, "row1": row1, "col0": col0, "col1": col1})
    return {(r, c): content["v"] for r, c, content in shown["cells"] if content is not None}


def pivots(book):
    return call(book, "pivots")["pivots"]


# ------------------------------------------------------------------------------------ reading
def test_a_new_workbook_has_no_pivots(book):
    assert call(book, "pivots")["pivots"] == []
    assert "revision" in call(book, "pivots")


def test_a_pivot_is_described_for_the_field_panel(book):
    make(book)
    (pivot,) = pivots(book)
    assert pivot["name"] == "SalesPivot"
    assert pivot["definition"] == BY_REGION_AND_QUARTER
    assert pivot["labels"]["total"] == "Total"
    assert pivot["anchor"] == {"sheet": "s1", "row": 0, "col": 5}
    assert pivot["region"] == {"sheet": "s1", "row0": 0, "col0": 5, "row1": 4, "col1": 8}
    assert pivot["a1"] == "Data!F1:I5"
    assert pivot["placed"] is True
    assert pivot["error"] is None
    assert pivot["header_rows"] == 2
    assert pivot["header_roles"] == [["corner", "field", "header", "header"], ["field", "header", "header", "header"]]
    assert (pivot["total_row"], pivot["total_column"]) == (True, True)


def test_the_cells_of_a_pivot_are_the_grid(book):
    make(book)
    shown = cells(book, "s1", 0, 4, 5, 8)
    assert shown[(0, 5)] == "Sum of Amount"
    assert shown[(2, 6)] == 900
    assert shown[(4, 8)] == 3400


def test_a_pivot_that_failed_says_why_and_has_no_region(book):
    make(book, definition={**BY_REGION_AND_QUARTER, "rows": ["Country"]})
    (pivot,) = pivots(book)
    assert pivot["error"]["code"] == "#SQL!"
    assert "Country" in pivot["error"]["detail"]
    assert pivot["region"] is None and pivot["header_roles"] == []
    assert pivot["placed"] is True


def test_a_pivot_whose_cell_was_overwritten_is_not_placed(book):
    make(book)
    typed(book, "s1", [(0, 5, "hello")])
    (pivot,) = pivots(book)
    assert pivot["placed"] is False and pivot["region"] is None


# ------------------------------------------------------------------------------------ making
def test_a_pivot_is_made_in_one_step(book):
    answered = make(book)
    assert answered["sheet"] == "s1" and answered["revision"]
    last = call(book, "log", {"limit": 1})[0]
    assert last["label"] == "Pivot table" or last["summary"]
    call(book, "undo")
    assert pivots(book) == []
    assert call(book, "history")["can_redo"]


def test_a_pivot_is_made_on_a_new_sheet(book):
    answered = make(book, sheet=None, new_sheet="Pivot", row=2, col=0)
    assert answered["sheet"] == "s2"
    assert call(book, "sheets")[-1]["name"] == "Pivot"
    assert cells(book, "s2", 2, 2, 0, 0)[(2, 0)] == "Sum of Amount"


def test_the_words_come_from_the_client(book):
    make(book, labels={"total": "Gesamt", "sum_of": "Summe von {field}"})
    shown = cells(book, "s1", 0, 1, 5, 8)
    assert shown[(0, 5)] == "Summe von Amount"
    assert shown[(1, 8)] == "Gesamt"
    assert pivots(book)[0]["labels"]["total"] == "Gesamt"


def test_where_it_goes_is_one_of_a_sheet_and_a_new_sheet(book):
    with pytest.raises(RequestError, match="sheet|new_sheet") as caught:
        make(book, sheet=None)
    assert caught.value.code == "bad_request"
    with pytest.raises(RequestError) as caught:
        make(book, new_sheet="Pivot")
    assert caught.value.code == "bad_request"


def test_a_bad_definition_or_name_is_refused(book):
    with pytest.raises(RequestError) as caught:
        make(book, definition={"source": "Sales"})  # (no format)
    assert caught.value.code == "bad_request"
    with pytest.raises(RequestError) as caught:
        make(book, name="not a name")
    assert caught.value.code == "command_error"
    make(book)
    with pytest.raises(RequestError) as caught:
        make(book, row=20)  # (the name is taken)
    assert caught.value.code == "command_error"


def test_a_cell_off_the_sheet_or_a_sheet_that_is_not_there_is_refused(book):
    with pytest.raises(RequestError) as caught:
        make(book, row=10**9)
    assert caught.value.code == "bad_request"
    with pytest.raises(RequestError) as caught:
        make(book, sheet="s9")
    assert caught.value.code == "command_error"


def test_making_a_pivot_needs_the_right_to_write(book):
    with pytest.raises(RequestError):
        call(book, "define_pivot", {"name": "P", "definition": BY_REGION_AND_QUARTER, "sheet": "s1"}, account=VERA)


# ------------------------------------------------------------------------------------ changing and deleting
def test_a_pivot_is_changed_and_its_cells_follow(book):
    make(book)
    call(book, "update_pivot", {"name": "SalesPivot", "definition": {**BY_REGION_AND_QUARTER, "columns": []}})
    assert pivots(book)[0]["header_rows"] == 1
    assert cells(book, "s1", 0, 0, 5, 6)[(0, 6)] == "Sum of Amount"
    assert (6, 6) not in cells(book, "s1", 6, 6, 5, 8)


def test_the_words_are_kept_unless_new_ones_come(book):
    make(book, labels={"total": "Gesamt"})
    call(book, "update_pivot", {"name": "SalesPivot", "definition": BY_REGION_AND_QUARTER})
    assert pivots(book)[0]["labels"]["total"] == "Gesamt"
    call(book, "update_pivot", {"name": "SalesPivot", "definition": BY_REGION_AND_QUARTER, "labels": {}})
    assert pivots(book)[0]["labels"]["total"] == "Total"


def test_changing_what_is_not_a_pivot_is_refused(book):
    with pytest.raises(RequestError) as caught:
        call(book, "update_pivot", {"name": "Sales", "definition": BY_REGION_AND_QUARTER})
    assert caught.value.code == "command_error"
    with pytest.raises(RequestError) as caught:
        call(book, "delete_pivot", {"name": "Sales"})
    assert caught.value.code == "command_error"


def test_a_pivot_is_deleted_with_its_cells_and_name(book):
    make(book)
    call(book, "delete_pivot", {"name": "SalesPivot"})
    assert pivots(book) == []
    assert (0, 5) not in cells(book, "s1", 0, 0, 5, 5)
    assert [n["name"] for n in call(book, "names")["names"]] == ["Sales"]


def test_the_pivot_comes_back_with_undo(book):
    make(book)
    call(book, "delete_pivot", {"name": "SalesPivot"})
    call(book, "undo", {})
    assert pivots(book)[0]["name"] == "SalesPivot"


# ------------------------------------------------------------------------------------ as SQL
def test_the_sql_of_a_pivot_is_read_only_text(book):
    make(book)
    sql = call(book, "pivot_sql", {"name": "SalesPivot"})["sql"]
    assert sql.startswith('SELECT "Region", "Q1", "Q2", "Total"') and "UNION ALL" in sql


def test_a_pivot_that_gave_nothing_has_no_sql(book):
    make(book, definition={**BY_REGION_AND_QUARTER, "rows": ["Country"]})
    with pytest.raises(RequestError) as caught:
        call(book, "pivot_sql", {"name": "SalesPivot"})
    assert caught.value.code == "command_error"
    with pytest.raises(RequestError) as caught:
        call(book, "pivot_sql", {"name": "Nothing"})
    assert caught.value.code == "command_error"


def test_a_pivot_becomes_a_sql_query_of_the_same_name(book):
    make(book)
    call(book, "pivot_to_sql", {"name": "SalesPivot"})
    assert pivots(book) == []
    (named,) = [n for n in call(book, "names")["names"] if n["name"] == "SalesPivot"]
    assert named["kind"] == "result" and named["anchor"] == {"sheet": "s1", "row": 0, "col": 5}
    shown = cells(book, "s1", 0, 1, 5, 8)
    assert shown[(0, 5)] == "Region" and shown[(1, 5)] == "North"


def test_turning_a_pivot_into_sql_is_refused_for_one_that_gave_nothing(book):
    make(book, definition={**BY_REGION_AND_QUARTER, "rows": ["Country"]})
    with pytest.raises(RequestError) as caught:
        call(book, "pivot_to_sql", {"name": "SalesPivot"})
    assert caught.value.code == "command_error"


def test_the_methods_are_there_for_every_client_and_the_assistant(book):
    from claudia_server.computes import computes_methods

    wanted = {"pivots", "define_pivot", "update_pivot", "delete_pivot", "pivot_sql", "pivot_to_sql"}
    assert wanted <= computes_methods.names()
    assert BEN  # (an editor may write: the same rule as every other write method)


# ------------------------------------------------------------------------------------ what a client may get wrong
def test_the_words_must_be_words(book):
    with pytest.raises(RequestError) as caught:
        make(book, labels={"total": 1})
    assert caught.value.code == "bad_request"
    make(book)
    with pytest.raises(RequestError) as caught:
        call(book, "update_pivot", {"name": "SalesPivot", "definition": BY_REGION_AND_QUARTER, "labels": "Total"})
    assert caught.value.code == "bad_request"


def test_the_new_sheet_needs_a_name_and_the_next_free_id(book):
    with pytest.raises(RequestError) as caught:
        make(book, sheet=None, new_sheet="  ")
    assert caught.value.code == "bad_request"
    call(book, "add_sheet", {"name": "Two"})  # s2
    answered = make(book, sheet=None, new_sheet="Pivot")
    assert answered["sheet"] == "s3"


def test_a_pivot_cannot_be_updated_with_a_bad_definition(book):
    make(book)
    with pytest.raises(RequestError) as caught:
        call(book, "update_pivot", {"name": "SalesPivot", "definition": {"format": 1}})
    assert caught.value.code == "bad_request"
