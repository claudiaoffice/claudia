"""Names over the wire (D550): the server gives every new thing a name of its own, anybody may rename it, and a
document from before names gets them on request."""

import pytest
from test_server_computes import tiny_gif
from test_server_creates import add_image, add_shape, add_text, call

from claudia_computes import AddSheet, WorkbookModel
from claudia_core import Document, MemoryStore, RenameThing
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.computes import computes_methods
from claudia_server.i18n import translate
from claudia_server.protocol import Context, Limits, RequestError

BEN = Account("ben", "editor")
VERA = Account("vera", "viewer")


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Sheet1"), author="ann")
    return doc


ANN = Account("ann", "owner")


def on_book(doc, name, params=None, account=ANN, locale="en"):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0, locale=locale)
    return computes_methods.dispatch(ctx, name, params)


def name_of(doc, thing: str) -> str:
    return doc.model.thing_name(thing)


# -- slides and their objects -------------------------------------------------------------------------------------
def test_a_new_slide_gets_the_first_free_default_name(deck):
    first = call(deck, "add_slide")["slide"]
    second = call(deck, "add_slide")["slide"]
    assert (name_of(deck, first), name_of(deck, second)) == ("Slide 1", "Slide 2")


def test_the_slide_list_says_each_slides_name(deck):
    call(deck, "add_slide")
    assert [s["name"] for s in call(deck, "slides")] == ["", "Slide 1"]


def test_new_objects_are_named_by_what_they_are_and_counted_per_name(deck):
    text = add_text(deck)
    shape = add_shape(deck)
    again = add_text(deck, y=300)
    picture = add_image(deck)
    assert [name_of(deck, o) for o in (text, shape, again, picture)] == [
        "Text box 1",
        "Shape 1",
        "Text box 2",
        "Picture 1",
    ]


def test_a_default_name_skips_a_name_somebody_took(deck):
    first = add_text(deck)
    call(deck, "rename_thing", {"id": first, "name": "Text box 2"})
    second = add_text(deck, y=300)
    assert name_of(deck, second) == "Text box 1"
    third = add_text(deck, y=500)
    assert name_of(deck, third) == "Text box 3"


def test_a_removed_things_default_name_comes_free_again(deck):
    first = add_text(deck)
    call(deck, "remove_object", {"id": first})
    assert name_of(deck, add_text(deck, y=300)) == "Text box 1"


def test_default_names_are_said_in_the_language_of_the_one_who_made_the_thing(deck):
    ctx = Context(deck, Account("ann", "owner"), Limits(), users=lambda: ["ann"], lock_seconds=30.0, locale="de")
    from claudia_server.creates import creates_methods

    made = creates_methods.dispatch(
        ctx, "add_object", {"slide": "s1", "kind": "text", "x": 1, "y": 1, "w": 400, "h": 100}
    )["object"]
    assert name_of(deck, made) == f"{translate('Text box', 'de')} 1"


# -- renaming -----------------------------------------------------------------------------------------------------
def test_anyone_who_may_edit_renames_a_thing_and_the_old_name_is_free_again(deck):
    box = add_text(deck)
    done = call(deck, "rename_thing", {"id": box, "name": "  Intro  "}, account=BEN)
    assert done["revision"] is not None
    assert name_of(deck, box) == "Intro"
    other = add_text(deck, y=300)
    call(deck, "rename_thing", {"id": other, "name": "Text box 1"})
    assert name_of(deck, other) == "Text box 1"


def test_a_slide_is_renamed_like_an_object(deck):
    call(deck, "rename_thing", {"id": "s1", "name": "Title"})
    assert call(deck, "slides")[0]["name"] == "Title"


def test_a_viewer_cannot_rename(deck):
    box = add_text(deck)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": box, "name": "Mine"}, account=VERA)
    assert caught.value.code == "forbidden"
    assert name_of(deck, box) == "Text box 1"


def test_a_clash_is_refused_with_the_name_of_the_one_who_has_it(deck):
    one = add_text(deck)
    two = add_text(deck, y=300)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": two, "name": "TEXT BOX 1"})
    assert caught.value.code == "command_error"
    assert "There is already a text box called “Text box 1”" in str(caught.value.message)
    assert name_of(deck, one) == "Text box 1"


def test_a_clash_is_said_in_the_language_of_the_one_who_asked(book):
    """A refusal of the model reaches a German person in German (CODE-78, D1510)."""
    on_book(book, "add_sheet", {"name": "Costs"})
    with pytest.raises(RequestError) as caught:
        on_book(book, "rename_thing", {"id": "s1", "name": "costs"}, locale="de")
    assert caught.value.to_dict("de")["message"] == "Es gibt schon ein Tabellenblatt namens „Costs“"
    assert caught.value.to_dict("en")["message"] == "There is already a sheet called “Costs”"


def test_a_name_without_text_is_refused_in_german_too(book):
    with pytest.raises(RequestError) as caught:
        on_book(book, "rename_thing", {"id": "s1", "name": "   "}, locale="de")
    assert caught.value.to_dict("de")["message"] == "Ein Name braucht etwas Text"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 61])
def test_a_name_must_have_some_text_and_not_too_much(deck, bad):
    box = add_text(deck)
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": box, "name": bad})
    assert caught.value.code == "bad_request"
    assert name_of(deck, box) == "Text box 1"


def test_renaming_something_that_is_not_there_is_an_error(deck):
    with pytest.raises(RequestError) as caught:
        call(deck, "rename_thing", {"id": "nothing", "name": "Name"})
    assert caught.value.code == "command_error"


def test_a_rename_by_somebody_else_does_not_stop_the_first_from_undoing_their_own_work(deck):
    box = add_text(deck)
    call(deck, "rename_thing", {"id": box, "name": "Intro"})
    deck.undo("ann")
    assert name_of(deck, box) == "Text box 1"


# -- documents from before names ----------------------------------------------------------------------------------
def test_name_unnamed_names_what_has_no_name_and_leaves_the_rest(deck):
    # a document made before names: a slide and two objects without any
    box = add_text(deck)
    other = add_text(deck, y=300)
    for thing in (box, other, "s1"):
        deck.execute(RenameThing(thing, ""), author="ann")
    deck.execute(RenameThing(other, "Keep"), author="ann")

    done = call(deck, "name_unnamed")
    assert done["named"] == 2
    assert name_of(deck, box) == "Text box 1"
    assert name_of(deck, "s1") == "Slide 1"
    assert name_of(deck, other) == "Keep"


def test_name_unnamed_with_nothing_to_name_does_not_touch_the_log(deck):
    add_text(deck)
    call(deck, "name_unnamed")  # the first slide of a new deck has no name yet
    before = deck.revision
    assert call(deck, "name_unnamed") == {"named": 0, "revision": before.to_data() if before else None}
    assert deck.revision == before


def test_name_unnamed_is_one_step_in_the_history(deck):
    for thing in (add_text(deck), add_shape(deck), "s1"):
        deck.execute(RenameThing(thing, ""), author="ann")
    before = deck.revision
    call(deck, "name_unnamed")
    assert deck.revision.seq == before.seq + 1


# -- computes -----------------------------------------------------------------------------------------------------
def test_a_picture_on_a_sheet_gets_a_default_name_that_the_sheets_names_do_not_take(book):
    first = on_book(book, "add_image", _image_params())["object"]
    assert name_of(book, first) == "Picture 1"


def test_a_sheet_is_renamed_and_the_formulas_that_read_it_follow(book):
    on_book(book, "add_sheet", {"name": "Data"})
    on_book(book, "set_cells", {"sheet": "s1", "cells": [{"row": 0, "col": 0, "input": "=Data!A1"}]})
    on_book(book, "rename_thing", {"id": "s1", "name": "Takings"})
    assert name_of(book, "s1") == "Takings"
    on_book(book, "rename_thing", {"id": next(i for i in book.model.sheets if i != "s1"), "name": "Figures"})
    cells = on_book(book, "cells", {"sheet": "s1", "row0": 0, "row1": 0, "col0": 0, "col1": 0})["cells"]
    assert "Figures!A1" in str(cells)
    assert [s["name"] for s in on_book(book, "sheets")] == ["Takings", "Figures"]


def test_a_sheet_cannot_take_the_name_of_a_named_range(book):
    on_book(book, "add_sheet", {"name": "Data"})
    area = {"sheet": "s1", "row0": 0, "col0": 0, "row1": 1, "col1": 1}
    on_book(book, "define_name", {"definition": {"name": "Revenue", "range": area}})
    with pytest.raises(RequestError) as caught:
        on_book(book, "rename_thing", {"id": "s1", "name": "revenue"})
    assert "There is already a named range called “Revenue”" in str(caught.value.message)


def test_a_new_sheet_may_not_take_the_name_of_a_picture(book):
    picture = on_book(book, "add_image", _image_params())["object"]
    on_book(book, "rename_thing", {"id": picture, "name": "Logo"})
    with pytest.raises(RequestError) as caught:
        on_book(book, "add_sheet", {"name": "logo"})
    assert "There is already a picture called “Logo”" in str(caught.value.message)


def _image_params() -> dict:
    return {
        "sheet": "s1",
        "row": 2,
        "col": 2,
        "w": 400,
        "h": 200,
        "data": tiny_gif(400, 200),
        "alt": "a sample picture",
        "source_name": "pic.gif",
    }


# -- paragraphs of a text (D554) -------------------------------------------------------------------------------------
@pytest.fixture
def text():
    from claudia_composes import InsertText, SetStyle, SplitParagraph, TextModel

    doc = Document(TextModel(), store=MemoryStore())
    doc.execute(InsertText("b1", 0, "Introduction"), author="ann")
    doc.execute(SetStyle("b1", "heading-1"), author="ann")
    doc.execute(SplitParagraph("b1", 12, "b2", "body"), author="ann")
    doc.execute(InsertText("b2", 0, "The quick brown fox."), author="ann")
    return doc


def on_text(doc, name, params=None, account=ANN, locale="en"):
    from claudia_server.composes import composes_methods

    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0, locale=locale)
    return composes_methods.dispatch(ctx, name, params)


def test_a_heading_is_called_by_its_words_and_pointing_at_it_writes_nothing(text):
    revision = text.revision
    answer = on_text(text, "name_thing", {"id": "b1"})
    assert answer == {"name": "Introduction", "revision": revision.to_data()}


def test_a_paragraph_pointed_at_is_named_by_what_it_is_in_the_language_of_the_one_who_points(text):
    assert on_text(text, "name_thing", {"id": "b2"}, locale="de")["name"] == translate("Paragraph", "de") + " 1"


def test_a_thing_that_has_a_name_keeps_it_and_nothing_is_written(text):
    on_text(text, "rename_thing", {"id": "b2", "name": "Fox"})
    revision = text.revision
    assert on_text(text, "name_thing", {"id": "b2"}) == {"name": "Fox", "revision": revision.to_data()}


def test_a_paragraph_cannot_take_the_words_of_a_heading_for_a_name(text):
    with pytest.raises(RequestError, match="already a heading called"):
        on_text(text, "rename_thing", {"id": "b2", "name": "introduction"})


def test_a_heading_cannot_be_renamed_because_its_words_are_its_name(text):
    with pytest.raises(RequestError, match="called by its words"):
        on_text(text, "rename_thing", {"id": "b1", "name": "Intro"})
    assert name_of(text, "b1") == "Introduction"


def test_naming_something_that_is_not_there_is_refused(text):
    with pytest.raises(RequestError) as caught:
        on_text(text, "name_thing", {"id": "b99"})
    assert caught.value.code == "command_error"


def test_the_paragraphs_say_their_names(text):
    on_text(text, "rename_thing", {"id": "b2", "name": "Fox"})
    paragraphs = {b["id"]: b for b in on_text(text, "paragraphs")["paragraphs"]}
    assert paragraphs["b2"]["name"] == "Fox" and paragraphs["b1"]["name"] == "Introduction"


def test_a_viewer_cannot_name_a_paragraph(text):
    with pytest.raises(RequestError):
        on_text(text, "name_thing", {"id": "b2"}, account=VERA)
    assert name_of(text, "b2") == ""


def test_name_thing_names_an_object_too(deck):
    box = add_text(deck)
    deck.execute(RenameThing(box, ""), author="ann")
    assert call(deck, "name_thing", {"id": box})["name"] == "Text box 1"


# -- a new paragraph has a name from the start (D1310) ---------------------------------------------------------------
def test_a_paragraph_made_by_typing_enter_has_a_name_at_once(text):
    answer = on_text(
        text, "replace_text", {"paragraph": "b2", "start": 20, "end_paragraph": "b2", "end": 20, "text": "\n"}
    )
    assert name_of(text, answer["paragraph"]) == "Paragraph 1"


def test_a_paste_of_lines_names_each_new_paragraph_with_the_next_free_number(text):
    on_text(text, "rename_thing", {"id": "b2", "name": "Paragraph 2"})
    answer = on_text(
        text, "replace_text", {"paragraph": "b2", "start": 20, "end_paragraph": "b2", "end": 20, "text": "\nA\nB\nC"}
    )
    names = [name_of(text, b.id) for b in text.model.paragraphs if b.id != "b1"]
    assert names == ["Paragraph 2", "Paragraph 1", "Paragraph 3", "Paragraph 4"]
    assert answer["paragraph"] == text.model.paragraphs[-1].id


def test_added_paragraphs_have_names_in_the_language_of_the_one_who_adds_them(text):
    on_text(text, "add_paragraphs", {"text": "one\ntwo", "after": "b2"}, locale="de")
    names = [name_of(text, b.id) for b in text.model.paragraphs[2:]]
    assert names == [translate("Paragraph", "de") + " 1", translate("Paragraph", "de") + " 2"]


def test_a_list_item_made_by_typing_enter_is_a_paragraph_by_name(text):
    from claudia_core import CreateList, ListDef, ListItem, SetListItem

    text.execute(CreateList(ListDef("l1", "bullets")), author="ann")
    text.execute(SetListItem("b2", ListItem("l1")), author="ann")
    answer = on_text(
        text, "replace_text", {"paragraph": "b2", "start": 20, "end_paragraph": "b2", "end": 20, "text": "\n"}
    )
    assert name_of(text, answer["paragraph"]) == "Paragraph 1"


def test_the_name_of_a_paragraph_that_is_made_is_part_of_the_one_step(text):
    on_text(text, "replace_text", {"paragraph": "b2", "start": 20, "end_paragraph": "b2", "end": 20, "text": "\n"})
    text.undo("ann")
    assert text.model.names_in_use() == ["Introduction"]


def test_name_unnamed_names_the_paragraphs_a_text_from_before_names_holds(text):
    answer = on_text(text, "name_unnamed")
    assert answer["named"] == 1 and name_of(text, "b2") == "Paragraph 1"
    assert name_of(text, "b1") == "Introduction", "a heading is called by its words, which is a name"


# -- Name & describe… is one step (D1317, D1318) -----------------------------------------------------------------------
def test_the_details_of_a_paragraph_are_its_name_its_words_and_that_it_cannot_be_decoration(text):
    on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": "Check this"})
    assert on_text(text, "thing_details", {"id": "b2"}) == {
        "id": "b2",
        "kind": "paragraph",
        "name": "Fox",
        "name_fixed": False,
        "description": "Check this",
        "drawn": False,
        "decorative": False,
    }


def test_the_details_of_a_heading_say_that_its_name_is_fixed(text):
    details = on_text(text, "thing_details", {"id": "b1"})
    assert (details["kind"], details["name"], details["name_fixed"]) == ("heading", "Introduction", True)


def test_name_and_describe_changes_both_in_one_step_and_one_undo_takes_both_back(text):
    answer = on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": "Check the date"})
    assert answer["name"] == "Fox" and answer["description"] == "Check the date"
    assert text.model.thing_description("b2") == "Check the date" and name_of(text, "b2") == "Fox"
    text.undo("ann")
    assert text.model.thing_description("b2") == "" and name_of(text, "b2") == ""


def test_name_and_describe_with_nothing_changed_writes_nothing(text):
    on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": ""})
    revision = text.revision
    answer = on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": ""})
    assert text.revision == revision and answer["revision"] == revision.to_data()


def test_only_the_description_changes_when_the_name_is_the_same(text):
    on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": ""})
    on_text(text, "name_and_describe", {"id": "b2", "name": "fox", "description": "note"})
    assert name_of(text, "b2") == "fox", "capitals a person changes are hers to change"


def test_a_heading_is_described_but_not_renamed(text):
    on_text(text, "name_and_describe", {"id": "b1", "name": "Introduction", "description": "Opening"})
    assert text.model.thing_description("b1") == "Opening"
    with pytest.raises(RequestError, match="called by its words"):
        on_text(text, "name_and_describe", {"id": "b1", "name": "Intro", "description": "Opening"})


def test_a_refused_name_stops_the_description_too(text):
    with pytest.raises(RequestError):
        on_text(text, "name_and_describe", {"id": "b2", "name": "introduction", "description": "x"})
    assert text.model.thing_description("b2") == ""


def test_a_thing_that_has_a_name_cannot_lose_it_in_the_dialog(text):
    on_text(text, "rename_thing", {"id": "b2", "name": "Fox"})
    with pytest.raises(RequestError, match="needs some text"):
        on_text(text, "name_and_describe", {"id": "b2", "name": "", "description": ""})


def test_a_viewer_cannot_name_and_describe(text):
    with pytest.raises(RequestError):
        on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": "x"}, account=VERA)


def test_a_picture_is_described_with_the_decoration_tick_and_a_paragraph_is_not(deck):
    picture = add_image(deck)
    call(deck, "name_and_describe", {"id": picture, "name": "Logo", "description": "", "decorative": True})
    assert call(deck, "thing_details", {"id": picture})["decorative"] is True
    assert call(deck, "thing_details", {"id": picture})["drawn"] is True


def test_a_picture_needs_words_or_the_tick(deck):
    picture = add_image(deck)
    with pytest.raises(RequestError):
        call(deck, "name_and_describe", {"id": picture, "name": "Logo", "description": "", "decorative": False})


def test_the_tick_is_refused_for_something_that_is_not_drawn(text):
    with pytest.raises(RequestError, match="decorat"):
        on_text(text, "name_and_describe", {"id": "b2", "name": "Fox", "description": "", "decorative": True})


# -- a name a person chose and a name a thing got by being made (D1311) ------------------------------------------------
@pytest.mark.parametrize("name", ["Paragraph 12", "paragraph 3", "Slide 1", "Text box 7", "Picture 2"])
def test_a_name_made_with_the_thing_is_generic(name):
    from claudia_server.thing_names import is_generic_name

    assert is_generic_name(name)


def test_a_name_in_another_language_is_generic_too():
    from claudia_server.thing_names import is_generic_name

    assert is_generic_name(translate("Paragraph", "de") + " 12")


@pytest.mark.parametrize(
    "name", ["Terms", "Paragraph", "Paragraph 1a", "Terms 12", "My Paragraph 3", "Paragraph 3 (2)"]
)
def test_a_name_a_person_chose_is_not(name):
    from claudia_server.thing_names import is_generic_name

    assert not is_generic_name(name)


# -- a sheet, a chart tab, a range (D1317) --------------------------------------------------------------------------
def test_a_sheet_is_named_and_described_in_one_step_and_the_formulas_follow(book):
    on_book(book, "name_and_describe", {"id": "s1", "name": "Plan", "description": "Q4 budget"})
    assert (name_of(book, "s1"), book.model.thing_description("s1")) == ("Plan", "Q4 budget")
    book.undo("ann")
    assert (name_of(book, "s1"), book.model.thing_description("s1")) == ("Sheet1", "")


def test_a_cell_range_without_a_name_is_named_and_described_together(book):
    box = {"sheet": "s1", "row0": 1, "col0": 1, "row1": 3, "col1": 2}
    answer = on_book(book, "name_and_describe_range", {"range": box, "name": "Rates", "description": "Tax rates"})
    assert book.model.thing_name(answer["id"]) == "Rates"
    assert book.model.thing_description(answer["id"]) == "Tax rates"
    book.undo("ann")
    assert list(book.model.names) == [], "one Undo takes the name and the words back"


def test_a_cell_range_needs_a_name_when_it_is_described(book):
    box = {"sheet": "s1", "row0": 1, "col0": 1, "row1": 3, "col1": 2}
    with pytest.raises(RequestError, match="needs some text"):
        on_book(book, "name_and_describe_range", {"range": box, "name": "", "description": "words"})


def test_a_cell_range_cannot_take_a_name_somebody_has(book):
    box = {"sheet": "s1", "row0": 1, "col0": 1, "row1": 3, "col1": 2}
    with pytest.raises(RequestError):
        on_book(book, "name_and_describe_range", {"range": box, "name": "sheet1", "description": ""})


def test_a_named_range_is_renamed_and_described_in_the_dialog(book):
    box = {"sheet": "s1", "row0": 1, "col0": 1, "row1": 3, "col1": 2}
    made = on_book(book, "name_and_describe_range", {"range": box, "name": "Rates", "description": ""})
    on_book(book, "name_and_describe", {"id": made["id"], "name": "TaxRates", "description": "now words"})
    assert (name_of(book, made["id"]), book.model.thing_description(made["id"])) == ("TaxRates", "now words")
    assert on_book(book, "thing_details", {"id": made["id"]})["kind"] == "range"
