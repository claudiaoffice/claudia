"""Search in a workbook looks at the words on its slides too (UX-72, E6.31): a text box's or a shape's words are found
in tab order with the cells, are where the scope says, and are replaced in the same step as the cells."""

import pytest
from conftest import S1

from claudia_computes import AddSlide, SetCells, parse_input
from claudia_computes.search import EXTRA_PARTS, place_of, plan_replacement, replace_command, scan_workbook
from claudia_core import AddObject, ObjectBody, SlideAnchor, paragraph_for
from claudia_search import Query


def find(text: str, replace: str | None = None):
    data = {"mode": "text", "text": text, **({"replace": [{"text": replace}]} if replace is not None else {})}
    return Query.from_data(data).compile(EXTRA_PARTS)


@pytest.fixture
def book(doc):
    doc.execute(SetCells(S1, ((1, 0, parse_input("East")), (2, 0, parse_input("West")))), author="ana")
    doc.execute(AddSlide("p1", "Sales chart"), author="ana")
    body = ObjectBody("t1", "text", 600, 160, "plain-box", paragraph_for("t1", "body-text", "East leads", "ana"))
    doc.execute(AddObject(body, SlideAnchor("p1", 100, 100).to_data()), author="ana")
    return doc


def test_the_words_on_a_slide_are_found_after_the_cells_of_the_sheet_before_it(book):
    found = scan_workbook(book.model, find("East"), kinds=("text",))
    assert [m.at for m in found.matches] == [
        {"sheet": S1, "row": 1, "col": 0},
        {"slide": "p1", "object": "t1", "source": "box"},
    ]
    assert found.counts["text"] == 2


def test_the_scope_may_be_one_slide(book):
    found = scan_workbook(book.model, find("East"), kinds=("text",), tabs=["p1"])
    assert [m.at for m in found.matches] == [{"slide": "p1", "object": "t1", "source": "box"}]
    assert [m.at for m in scan_workbook(book.model, find("East"), kinds=("text",), tabs=[S1]).matches] == [
        {"sheet": S1, "row": 1, "col": 0}
    ]


def test_formulas_and_values_do_not_look_at_slides(book):
    assert scan_workbook(book.model, find("East"), kinds=("formulas", "values")).matches == []


def test_a_replacement_changes_cells_and_words_in_one_step_and_undo_takes_both_back(book):
    command = replace_command(book.model, plan_replacement(book.model, find("East", "Ost"), kinds=("text",)), "bob")
    book.execute(command, author="bob")
    assert book.model.sheet(S1).cells[(1, 0)] == {"t": "text", "v": "Ost"}
    words = book.model.get_object("t1").body.paragraph
    assert words.text == "Ost leads"
    assert [run.author for run in words.runs] == ["bob", "ana"]  # who wrote what stays is kept
    book.undo("bob")
    assert book.model.sheet(S1).cells[(1, 0)] == {"t": "text", "v": "East"}
    assert book.model.get_object("t1").body.paragraph.text == "East leads"


def test_an_object_somebody_holds_is_skipped_and_named(book):
    def held(at):
        return "ben" if at.get("object") == "t1" else None

    made = plan_replacement(book.model, find("East", "Ost"), kinds=("text",), held=held)
    assert [change.at for change in made.changes] == [{"sheet": S1, "row": 1, "col": 0}]
    assert [(skip.at, skip.reason, skip.by) for skip in made.skipped] == [
        ({"slide": "p1", "object": "t1", "source": "box"}, "locked", "ben")
    ]


@pytest.mark.parametrize(
    "at",
    [{"sheet": S1, "row": 0, "col": 0}, {"slide": "p1", "object": "t1", "source": "box"}],
)
def test_a_place_sent_back_is_read_as_a_cell_or_an_object(at):
    assert place_of(at) == at


@pytest.mark.parametrize("at", [{"slide": "p1"}, {"slide": "p1", "object": "t1", "source": "notes"}, {"sheet": S1}])
def test_a_place_that_is_neither_is_refused(at):
    with pytest.raises(ValueError, match="a place in a workbook"):
        place_of(at)
