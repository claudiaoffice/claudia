"""The methods for named ranges, tables and queries (E6.5, D600): what a client reads to draw tables and the Names
manager, and what it sends to define, rename and remove names and to put a query in a cell."""

import pytest
from test_server_computes import call, typed

from claudia_computes import WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.protocol import RequestError

TABLE = [
    (0, 0, "Region"),
    (0, 1, "Units"),
    (0, 2, "Unit price"),
    (1, 0, "North"),
    (1, 1, "10"),
    (1, 2, "2.5"),
    (2, 0, "South"),
    (2, 1, "4"),
    (2, 2, "10"),
]
AREA = {"sheet": "s1", "row0": 0, "col0": 0, "row1": 2, "col1": 2}


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    call(doc, "add_sheet", {"name": "Data"})
    typed(doc, "s1", TABLE)
    return doc


def window(book, row0, row1, col0, col1):
    """The cells of a window as ``{(row, col): content}``."""
    shown = call(book, "cells", {"sheet": "s1", "row0": row0, "row1": row1, "col0": col0, "col1": col1})
    return {(r, c): content for r, c, content in shown["cells"]}


def define(book, **changes):
    definition = {"name": "Sales", "range": AREA, "header": True, "grows": True, "purpose": "input", **changes}
    return call(book, "define_name", {"definition": definition})


def test_a_new_workbook_has_no_names(book):
    assert call(book, "names")["names"] == []


def test_a_table_is_defined_and_described(book):
    define(book, column_purposes=[[2, "calc"]])
    (sales,) = call(book, "names")["names"]
    assert sales["name"] == "Sales" and sales["kind"] == "range" and sales["scope"] is None
    assert sales["header"] and sales["grows"] and sales["purpose"] == "input"
    assert sales["a1"] == "Data!A1:C3" and sales["region"] == AREA and sales["rows"] == 2
    assert sales["columns"] == [
        {"name": "Region", "type": "text", "purpose": "input"},
        {"name": "Units", "type": "int", "purpose": "input"},
        {"name": "Unit price", "type": "real", "purpose": "calc"},
    ]


def test_a_name_is_used_in_a_formula_and_follows_the_table_as_it_grows(book):
    define(book)
    typed(book, "s1", [(0, 5, "=SUM(Sales[Units])"), (3, 0, "East"), (3, 1, "6")])
    assert window(book, 0, 0, 5, 5)[(0, 5)]["v"] == 20
    assert call(book, "names")["names"][0]["region"]["row1"] == 3


def test_a_range_without_a_header_has_no_header_rows(book):
    define(book, name="Cells", header=False, purpose="data")
    (named,) = call(book, "names")["names"]
    assert not named["header"] and named["rows"] == 3
    assert [c["name"] for c in named["columns"]] == ["A", "B", "C"]


def test_a_sheet_scoped_name_is_listed_after_the_workbook_ones(book):
    define(book, name="Mine", scope="s1")
    define(book, name="Everyone")
    assert [(n["name"], n["scope"]) for n in call(book, "names")["names"]] == [("Everyone", None), ("Mine", "s1")]


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "A1"},
        {"name": "has space"},
        {"purpose": "loud"},
        {"scope": "nope"},
        {"range": {**AREA, "sheet": "nope"}},
        {"range": {**AREA, "row1": -1}},
        {"range": {"sheet": "s1"}},
        {"colour": "red"},
    ],
)
def test_a_wrong_definition_is_a_bad_request(book, bad):
    with pytest.raises(RequestError) as caught:
        define(book, **bad)
    assert caught.value.code in {"bad_request", "command_error"}


def test_a_definition_needs_a_range_or_an_anchor_not_both(book):
    for extra in ({"anchor": {"sheet": "s1", "row": 0, "col": 5}}, {"range": None}):
        with pytest.raises(RequestError):
            define(book, **extra)


def test_renaming_rewrites_the_formulas_and_removing_leaves_the_cells(book):
    define(book)
    typed(book, "s1", [(0, 5, "=SUM(Sales[Units])")])
    call(book, "rename_name", {"old": "Sales", "new": "Orders", "scope": None})
    assert window(book, 0, 0, 5, 5)[(0, 5)]["f"] == "=SUM(Orders[Units])"
    call(book, "remove_name", {"name": "Orders", "scope": None})
    assert call(book, "names")["names"] == []
    assert window(book, 0, 0, 5, 5)[(0, 5)]["v"] == "#NAME?"


def test_renaming_or_removing_a_name_that_does_not_exist_is_a_command_error(book):
    for method, params in (
        ("rename_name", {"old": "Nope", "new": "Other", "scope": None}),
        ("remove_name", {"name": "Nope", "scope": None}),
    ):
        with pytest.raises(RequestError) as caught:
            call(book, method, params)
        assert caught.value.code == "command_error"


def test_a_name_change_is_one_step_in_the_history_that_can_be_undone(book):
    define(book)
    call(book, "undo", {})
    assert call(book, "names")["names"] == []


def test_a_viewer_cannot_define_a_name(book):
    from test_server_computes import VERA

    from claudia_server.auth import Account

    assert isinstance(VERA, Account)
    with pytest.raises(RequestError) as caught:
        call(book, "define_name", {"definition": {"name": "X", "range": AREA}}, account=VERA)
    assert caught.value.code in {"forbidden", "read_only"}


# ------------------------------------------------------------------------------------ queries
def test_a_preview_runs_a_query_without_changing_the_document(book):
    define(book)
    before = call(book, "names")["revision"]
    shown = call(book, "sql_preview", {"query": "SELECT Region, Units FROM Sales ORDER BY Units", "sheet": "s1"})
    assert shown["ok"] and shown["columns"] == ["Region", "Units"]
    assert shown["rows"] == [["South", 4], ["North", 10]] and shown["row_count"] == 2 and shown["ms"] >= 0
    assert call(book, "names")["revision"] == before


def test_a_preview_cuts_the_rows_it_sends_but_counts_them(book):
    define(book)
    shown = call(book, "sql_preview", {"query": "SELECT * FROM Sales", "sheet": "s1", "limit": 1})
    assert len(shown["rows"]) == 1 and shown["row_count"] == 2


def test_a_preview_of_a_wrong_query_says_why(book):
    define(book)
    shown = call(book, "sql_preview", {"query": "SELECT Revnue FROM Sales", "sheet": "s1"})
    assert not shown["ok"] and shown["error"]["code"] == "#SQL!" and "no such column" in shown["error"]["detail"]


def test_a_preview_refuses_anything_but_reading(book):
    shown = call(book, "sql_preview", {"query": "DROP TABLE x", "sheet": "s1"})
    assert not shown["ok"]


def test_a_preview_has_a_limit_on_the_rows_it_sends(book):
    with pytest.raises(RequestError):
        call(book, "sql_preview", {"query": "SELECT 1", "sheet": "s1", "limit": 100000})


def test_applying_a_query_fills_cells_and_names_the_result_in_one_step(book):
    define(book)
    call(
        book,
        "define_sql",
        {"sheet": "s1", "row": 5, "col": 0, "query": "SELECT Region FROM Sales ORDER BY 1", "name": "Regions"},
    )
    cells = {
        (r, c): v
        for r, c, v in call(book, "cells", {"sheet": "s1", "row0": 5, "row1": 8, "col0": 0, "col1": 0})["cells"]
    }
    assert cells[(5, 0)]["v"] == "Region" and cells[(5, 0)]["f"].startswith("=SQL(")
    assert cells[(6, 0)] == {"t": "text", "v": "North", "spill": True, "from": [5, 0]}
    regions = next(n for n in call(book, "names")["names"] if n["name"] == "Regions")
    assert regions["kind"] == "result" and regions["purpose"] == "result" and regions["a1"] == "Data!A6:A8"
    assert regions["columns"] == [{"name": "Region", "type": "text", "purpose": "result"}] and regions["rows"] == 2
    call(book, "undo", {})
    assert [n["name"] for n in call(book, "names")["names"]] == ["Sales"]


def test_applying_a_query_again_replaces_the_name_of_its_result(book):
    define(book)
    where = {"sheet": "s1", "row": 5, "col": 0}
    call(book, "define_sql", {**where, "query": "SELECT 1 AS a", "name": "First"})
    call(book, "define_sql", {**where, "query": "SELECT 2 AS b", "name": "Second"})
    assert [n["name"] for n in call(book, "names")["names"]] == ["Sales", "Second"]


def test_a_cell_that_shows_a_result_cannot_be_typed_into(book):
    call(book, "define_sql", {"sheet": "s1", "row": 5, "col": 0, "query": "SELECT 1 AS a UNION SELECT 2", "name": None})
    with pytest.raises(RequestError) as caught:
        typed(book, "s1", [(6, 0, "mine")])
    assert caught.value.code == "command_error" and "SQL" in caught.value.message


def test_a_chart_may_read_a_named_table_and_follows_it(book):
    define(book)
    given = {"kind": "bar", "source": "Sales", "source_scope": None}
    diagram = call(book, "define_diagram", {"definition": given})["diagram"]
    (listed,) = call(book, "diagrams")
    assert listed["source"] == "Sales" and "range" not in listed
    first = call(book, "chart_figure", {"diagram": diagram})["figure"]
    assert first["data"][0]["x"] == ["North", "South"]
    typed(book, "s1", [(3, 0, "East"), (3, 1, "6"), (3, 2, "5")])  # typed right below: the table grows
    again = call(book, "chart_figure", {"diagram": diagram})["figure"]
    assert again["data"][0]["x"] == ["North", "South", "East"]


def test_a_chart_cannot_read_a_name_that_does_not_exist(book):
    with pytest.raises(RequestError) as caught:
        call(book, "define_diagram", {"definition": {"kind": "bar", "source": "Nope"}})
    assert caught.value.code == "command_error" and "Nope" in str(caught.value)
