"""The scripted stand-in for a model: a handful of phrases it understands, an honest answer to everything else."""

import pytest

from claudia_computes import AddSheet, CellRegion, SetCells, WorkbookModel
from claudia_core import Document, MemoryStore
from claudia_server.assistant import Call, Say, Task
from claudia_server.standin import ScriptedEngine


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Budget"), author="ann")
    doc.execute(AddSheet("s2", "Plan"), author="ann")
    return doc


def plan(book, text, sender="ann"):
    return ScriptedEngine().plan(Task(sender, text, book))


def cells_of(steps):
    (call,) = [s for s in steps if isinstance(s, Call)]
    return call.method, call.params


def test_fill_writes_the_same_input_into_every_cell(book):
    method, params = cells_of(plan(book, "fill B2:B3 with 10"))
    assert method == "set_cells" and params["sheet"] == "s1"
    assert params["cells"] == [{"row": 1, "col": 1, "input": "10"}, {"row": 2, "col": 1, "input": "10"}]


def test_it_works_on_the_sheet_the_asker_is_looking_at(book):
    book.show_presence("ann", [CellRegion.of("s2", 0, 0, 0, 0)])
    assert cells_of(plan(book, "set A1 to hello"))[1]["sheet"] == "s2"
    assert cells_of(plan(book, "set A1 to hello", sender="ben"))[1]["sheet"] == "s1", (
        "ben looks at nothing: first sheet"
    )


@pytest.mark.parametrize(
    "text",
    ["set C4 to hello", "Set c4 to hello.", "write hello in C4", "please put hello into C4"],
)
def test_single_cell_phrases(book, text):
    assert cells_of(plan(book, text))[1]["cells"] == [{"row": 3, "col": 2, "input": "hello"}]


def test_clear_empties_cells(book):
    assert cells_of(plan(book, "clear A1:B1"))[1]["cells"] == [
        {"row": 0, "col": 0, "input": ""},
        {"row": 0, "col": 1, "input": ""},
    ]


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("sum A1:A3 into A4", "6"),
        ("total of A1:A3 in A4", "6"),
        ("average A1:A3 into A4", "2"),
        ("max A1:A3 into A4", "3"),
        ("min A1:A3 into A4", "1"),
        ("count A1:A3 into A4", "3"),
    ],
)
def test_summaries_are_computed_here_and_written_as_numbers(book, text, answer):
    book.execute(
        SetCells(
            "s1",
            (
                (0, 0, {"t": "int", "v": 1}),
                (1, 0, {"t": "int", "v": 2}),
                (2, 0, {"t": "int", "v": 3}),
                (3, 0, {"t": "text", "v": "x"}),
            ),
        ),
        author="ann",
    )
    steps = plan(book, text)
    assert cells_of(steps)[1]["cells"] == [{"row": 3, "col": 0, "input": answer}]
    assert any(isinstance(s, Say) and "number" in s.text for s in steps), "it says that this is a value, not a formula"


def test_summing_nothing_is_explained(book):
    steps = plan(book, "sum A1:A3 into A4")
    assert [type(s) for s in steps] == [Say] and "no numbers" in steps[0].text


def test_add_sheet(book):
    assert cells_of(plan(book, "add sheet Forecast 2027")) == ("add_sheet", {"name": "Forecast 2027"})


def test_the_example_builds_a_small_budget(book):
    steps = plan(book, "build an example budget")
    calls = [s for s in steps if isinstance(s, Call)]
    assert len(calls) >= 3 and all(c.method == "set_cells" for c in calls)
    typed = {(c["row"], c["col"]): c["input"] for call in calls for c in call.params["cells"]}
    assert typed[(0, 0)] == "Item" and typed[(0, 1)] == "Amount"
    assert any(isinstance(s, Say) for s in steps)


def test_every_edit_shows_where_the_assistant_is_working(book):
    (call,) = [s for s in plan(book, "set C4 to hello") if isinstance(s, Call)]
    assert call.focus and call.focus[0]["kind"] == "cells"


@pytest.mark.parametrize("text", ["hello", "help", "what can you do?"])
def test_greetings_and_help_list_what_it_can_do(book, text):
    (say,) = plan(book, text)
    assert isinstance(say, Say) and "fill" in say.text and "stand-in" in say.text


def test_anything_else_is_answered_honestly(book):
    (say,) = plan(book, "forecast the next five years of revenue")
    assert "stand-in" in say.text and "help" in say.text


def test_without_a_sheet_it_asks_for_one():
    empty = Document(WorkbookModel(), store=MemoryStore())
    (say,) = plan(empty, "fill A1:A3 with 5")
    assert "sheet" in say.text


def test_huge_ranges_are_refused(book):
    (say,) = plan(book, "fill A1:Z999 with 1")
    assert "at most" in say.text
