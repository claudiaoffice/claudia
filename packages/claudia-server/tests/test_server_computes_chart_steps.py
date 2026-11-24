"""A chart becomes a slide on the wire (E6.31 step 3, D1475): `insert_chart` makes a chart with its definition in one
step, on a new slide, on the slide shown or on a sheet; `move_to_slide` puts a chart of a sheet on a new slide;
`remove_object` takes a chart's definition and an emptied slide along. A slide made for a chart is the next free
"Slide n" in the language of the one who asked, and the chart keeps its name."""

import pytest
from test_server_computes import VERA, call, typed

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import SLIDE_HEIGHT, SLIDE_WIDTH, Document, MemoryStore
from claudia_server.protocol import RequestError


def _ref(row: int, col: int) -> dict:
    return {"row": row, "col": col, "sheet": "s1", "row_abs": False, "col_abs": False}


BAR = {"kind": "bar", "range": {"first": _ref(0, 0), "last": _ref(3, 1)}, "series_in": "columns", "title": "Sales"}


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    doc.execute(AddSheet("s2", "Costs"), author="ann")
    typed(doc, "s1", [(0, 0, "Region"), (0, 1, "Amount"), (1, 0, "East"), (1, 1, "300"), (2, 0, "West")])
    return doc


def tab_names(doc) -> list[tuple[str, str]]:
    return [(tab["kind"], tab["name"]) for tab in call(doc, "tabs")]


def as_slide(doc, name="Sales", after="s1", **kw):
    params = {"definition": BAR, "show_as": "slide", "name": name, "place": {"after": after}}
    return call(doc, "insert_chart", params, **kw)


def on_sheet(doc, name="Sales"):
    place = {"sheet": "s1", "row": 5, "col": 1, "w": 480, "h": 300}
    return call(doc, "insert_chart", {"definition": BAR, "show_as": "sheet", "name": name, "place": place})


def frame_of(doc, slide, object_id):
    (obj,) = [o for o in call(doc, "slide", {"slide": slide})["objects"] if o["id"] == object_id]
    return obj["anchor"]["x"], obj["anchor"]["y"], obj["w"], obj["h"]


# -- insert_chart -----------------------------------------------------------------------------------------------------
def test_a_chart_as_a_slide_is_slide_1_right_after_the_tab_and_the_chart_keeps_its_name(book):
    made = as_slide(book)
    assert tab_names(book) == [("sheet", "Sheet1"), ("slide", "Slide 1"), ("sheet", "Costs")]
    assert frame_of(book, made["slide"], made["object"]) == (0, 0, SLIDE_WIDTH, SLIDE_HEIGHT)
    assert call(book, "thing_details", {"id": made["object"]})["name"] == "Sales"


def test_the_slide_is_called_in_the_language_of_the_one_who_asked(book):
    as_slide(book, locale="de")
    assert ("slide", "Folie 1") in tab_names(book)


def test_one_undo_takes_the_slide_the_chart_and_its_definition_away(book):
    as_slide(book)
    book.undo("ann")
    assert tab_names(book) == [("sheet", "Sheet1"), ("sheet", "Costs")]
    assert call(book, "charts") == []


def test_a_second_chart_goes_on_the_slide_shown(book):
    made = as_slide(book)
    params = {"definition": BAR, "show_as": "on_slide", "name": "Sales 2", "place": {"slide": made["slide"]}}
    second = call(book, "insert_chart", params)
    assert second["slide"] == made["slide"]
    assert frame_of(book, made["slide"], second["object"]) == (
        SLIDE_WIDTH // 4,
        SLIDE_HEIGHT // 4,
        SLIDE_WIDTH // 2,
        SLIDE_HEIGHT // 2,
    )
    assert len(tab_names(book)) == 3


def test_a_chart_floats_on_a_sheet_with_a_definition_of_its_own(book):
    first, second = on_sheet(book, "One"), on_sheet(book, "Two")
    objects = {o["id"]: o for o in call(book, "objects", {"sheet": "s1"})["objects"]}
    assert objects[first["object"]]["ref"] != objects[second["object"]]["ref"]
    assert len(call(book, "charts")) == 2


def test_without_a_name_the_chart_is_the_next_free_chart_n(book):
    made = call(book, "insert_chart", {"definition": BAR, "show_as": "slide", "place": {"after": "s1"}})
    assert call(book, "thing_details", {"id": made["object"]})["name"] == "Chart 1"
    assert call(book, "free_name", {"kind": "chart"}) == {"name": "Chart 2"}
    assert call(book, "free_name", {"kind": "chart"}, locale="de") == {"name": "Diagramm 1"}  # (another word)


def test_a_name_another_thing_has_is_refused_and_nothing_is_made(book):
    with pytest.raises(RequestError, match="There is already a sheet called “Costs”"):
        as_slide(book, name="costs")
    assert len(tab_names(book)) == 2 and call(book, "charts") == []


@pytest.mark.parametrize(
    "show_as, place",
    [
        ("tab", {"after": "s1"}),
        ("slide", {"after": "nowhere"}),
        ("slide", {}),
        ("on_slide", {"slide": "s1"}),
        ("sheet", {"sheet": "nowhere", "row": 0, "col": 0, "w": 100, "h": 100}),
        ("sheet", {"sheet": "s1", "row": -1, "col": 0, "w": 100, "h": 100}),
        ("sheet", {"sheet": "s1", "row": 0, "col": 0}),
    ],
)
def test_a_place_that_does_not_fit_what_the_chart_is_shown_as_is_refused(book, show_as, place):
    with pytest.raises(RequestError):
        call(book, "insert_chart", {"definition": BAR, "show_as": show_as, "place": place})


def test_a_viewer_inserts_no_chart(book):
    with pytest.raises(RequestError, match="editor role"):
        as_slide(book, account=VERA)


# -- move_to_slide ----------------------------------------------------------------------------------------------------
def test_a_chart_of_a_sheet_moves_to_a_new_slide_after_its_sheet(book):
    made = on_sheet(book)
    moved = call(book, "move_to_slide", {"object": made["object"]})
    assert tab_names(book) == [("sheet", "Sheet1"), ("slide", "Slide 1"), ("sheet", "Costs")]
    assert frame_of(book, moved["slide"], made["object"]) == (0, 0, SLIDE_WIDTH, SLIDE_HEIGHT)
    assert call(book, "objects", {"sheet": "s1"})["objects"] == []
    assert call(book, "thing_details", {"id": made["object"]})["name"] == "Sales"
    book.undo("ann")
    assert [o["id"] for o in call(book, "objects", {"sheet": "s1"})["objects"]] == [made["object"]]
    assert len(tab_names(book)) == 2


def test_only_a_chart_on_a_sheet_moves_to_a_slide(book):
    made = as_slide(book)
    with pytest.raises(RequestError, match="on a sheet"):
        call(book, "move_to_slide", {"object": made["object"]})


def test_a_viewer_moves_no_chart(book):
    made = on_sheet(book)
    with pytest.raises(RequestError, match="editor role"):
        call(book, "move_to_slide", {"object": made["object"]}, account=VERA)


# -- remove_object ----------------------------------------------------------------------------------------------------
def test_removing_the_last_chart_of_a_slide_takes_the_slide_and_the_definition_along(book):
    made = as_slide(book)
    call(book, "remove_object", {"id": made["object"]})
    assert tab_names(book) == [("sheet", "Sheet1"), ("sheet", "Costs")]
    assert call(book, "charts") == []
    book.undo("ann")
    assert ("slide", "Slide 1") in tab_names(book)


def test_removing_a_chart_on_a_sheet_forgets_its_definition(book):
    made = on_sheet(book)
    call(book, "remove_object", {"id": made["object"]})
    assert call(book, "charts") == []


# -- the chart tab and the old chart names are gone (D1475, D1476) --------------------------------------------------
@pytest.mark.parametrize("method", ["add_chart", "remove_chart", "add_diagram_object", "define_diagram", "diagrams"])
def test_the_methods_of_the_chart_tab_and_the_old_chart_names_are_gone(book, method):
    with pytest.raises(RequestError, match="unknown|method"):
        call(book, method, {})
