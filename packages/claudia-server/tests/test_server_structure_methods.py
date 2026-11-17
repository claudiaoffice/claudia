"""Lists, numbered headings and numbering schemes on the wire, the same in composes and creates (E9.21, E9.22, step D).

The methods work on paragraph ids in reading order: in a presentation the words of the text boxes, slide by slide,
so a list runs on from one text box to the next."""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")


def call(doc, name, params=None, account=ANN):
    methods = creates_methods if isinstance(doc.model, SlideModel) else composes_methods
    ctx = Context(doc, account, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    return methods.dispatch(ctx, name, params)


@pytest.fixture
def deck():
    """Two slides; on the first a title and a text box, on the second a title and two text boxes."""
    doc = Document(SlideModel.empty(), store=MemoryStore())
    second = call(doc, "add_slide")["slide"]
    ids = {}
    for name, slide in (("t1", "s1"), ("a", "s1"), ("t2", second), ("b", second), ("c", second)):
        given = {"slide": slide, "kind": "text", "x": 100, "y": 100, "w": 400, "h": 120, "text": name}
        ids[name] = call(doc, "add_object", given)["object"]
    for title in ("t1", "t2"):
        call(doc, "set_paragraph_style", {"id": ids[title], "style": "slide-title"})
    doc.ids = ids
    return doc


@pytest.fixture
def paper():
    doc = Document(TextModel(), store=MemoryStore())
    call(doc, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "Why\none\nAsked\nHow"})
    for block, style in (("b1", "heading-1"), ("b3", "heading-2"), ("b4", "heading-1")):
        call(doc, "set_style", {"block": block, "style": style})
    return doc


def markers(doc):
    return {k: v["marker"] for k, v in call(doc, "lists")["labels"].items()}


def test_both_apps_have_the_methods():
    wanted = {"lists", "make_list", "indent_item", "continue_list", "list_start", "number_headings"}
    wanted |= {"new_scheme", "change_scheme", "reset_scheme", "remove_scheme", "set_style_numbering"}
    assert wanted <= composes_methods.names()
    assert wanted <= creates_methods.names()


def test_a_list_runs_on_across_the_text_boxes_of_a_presentation(deck):
    ids = deck.ids
    call(deck, "make_list", {"blocks": [ids["a"], ids["b"], ids["c"]], "scheme": "numbers"})
    assert markers(deck) == {ids["a"]: "1.", ids["b"]: "2.", ids["c"]: "3."}
    call(deck, "indent_item", {"blocks": [ids["c"]], "by": 1})
    assert markers(deck)[ids["c"]] == "a."
    call(deck, "make_list", {"blocks": [ids["b"]], "scheme": "numbers"})  # asked for what it is: out of the list
    assert ids["b"] not in markers(deck)


def test_a_paragraph_the_document_does_not_have_is_a_command_error(deck):
    with pytest.raises(RequestError) as caught:
        call(deck, "make_list", {"blocks": ["o-nothing"], "scheme": "numbers"})
    assert caught.value.code == "command_error"


def test_number_all_slide_titles_numbers_the_title_style_and_switching_it_off_takes_it_back(deck):
    ids = deck.ids
    call(deck, "number_headings", {"on": True})
    assert markers(deck) == {ids["t1"]: "1", ids["t2"]: "2"}
    styles = {s["id"]: s for s in call(deck, "styles")}
    assert styles["slide-title"]["numbered"] == "outline"
    call(deck, "number_headings", {"on": False})
    assert markers(deck) == {}
    assert call(deck, "number_headings", {"on": False})["revision"] is not None, "nothing to do is no step"


def test_number_headings_numbers_every_heading_style_as_one_outline_in_one_step(paper):
    call(paper, "number_headings", {"on": True})
    blocks = {b["id"]: b for b in call(paper, "blocks")["blocks"]}
    assert {i: b["label"]["marker"] for i, b in blocks.items() if "label" in b} == {"b1": "1", "b3": "1.1", "b4": "2"}
    assert "item" not in blocks["b1"], "a numbered heading is numbered by its style, not an item of its own"
    call(paper, "undo")
    assert markers(paper) == {}, "the list, the scheme and the styles were one step"


def test_a_scheme_is_made_changed_reset_and_removed_through_the_numbering_manager(paper):
    made = call(paper, "new_scheme", {"like": "chapters", "name": "Appendix"})["scheme"]
    scheme = next(s for s in call(paper, "lists")["schemes"] if s["id"] == made)
    scheme["levels"][0] = {**scheme["levels"][0], "format": "upper-alpha", "before": "Appendix "}
    call(paper, "change_scheme", {"scheme": scheme})
    call(paper, "number_headings", {"on": True})
    call(paper, "list_start", {"list": "outline", "start": 1})
    lists = call(paper, "lists")["lists"]
    outline = next(each for each in lists if each["id"] == "outline")
    assert outline["scheme"] == "chapters"
    call(paper, "remove_scheme", {"scheme": made})
    assert made not in [s["id"] for s in call(paper, "lists")["schemes"]]
    chapters = next(s for s in call(paper, "lists")["schemes"] if s["id"] == "chapters")
    call(paper, "change_scheme", {"scheme": {**chapters, "gap": 1}})
    call(paper, "reset_scheme", {"scheme": "chapters"})
    assert next(s for s in call(paper, "lists")["schemes"] if s["id"] == "chapters") == chapters


def test_a_scheme_in_use_cannot_be_removed_and_a_bad_one_is_refused_with_a_sentence(paper):
    call(paper, "number_headings", {"on": True})
    with pytest.raises(RequestError, match="used by the list"):
        call(paper, "remove_scheme", {"scheme": "chapters"})
    with pytest.raises(RequestError, match="not a numbering scheme"):
        call(paper, "change_scheme", {"scheme": {"id": "chapters", "levels": []}})
    with pytest.raises(RequestError, match="built-in"):
        made = call(paper, "new_scheme", {"like": "numbers", "name": "Mine"})["scheme"]
        call(paper, "reset_scheme", {"scheme": made})


def test_a_heading_style_is_numbered_in_a_list_by_hand(paper):
    call(paper, "make_list", {"blocks": ["b2"], "scheme": "numbers"})
    (list_id,) = [each["id"] for each in call(paper, "lists")["lists"]]
    call(paper, "set_style_numbering", {"style": "heading-1", "numbering": list_id})
    assert markers(paper) == {"b1": "1.", "b2": "2.", "b4": "3."}
    with pytest.raises(RequestError, match="no list"):
        call(paper, "set_style_numbering", {"style": "heading-2", "numbering": "ghost"})


def test_a_viewer_may_read_the_lists_but_not_change_them(deck):
    assert call(deck, "lists", account=VERA)["schemes"]
    with pytest.raises(RequestError):
        call(deck, "number_headings", {"on": True}, account=VERA)


# ----------------------------------------------------------------------------- tables of contents and agendas (E)
def entries_of(doc, paragraph):
    return [(e["target"], e["number"], e["text"], e["place"]) for e in call(doc, "contents")["entries"][paragraph]]


def test_a_table_of_contents_goes_in_after_a_paragraph_with_its_title_in_one_step(paper):
    call(paper, "number_headings", {"on": True})
    made = call(paper, "insert_contents", {"block": "b1"})["block"]
    blocks = call(paper, "blocks")["blocks"]
    title, table = blocks[1], blocks[2]
    assert (title["style"], title["text"]) == ("contents-title", "Contents")
    assert table["id"] == made and table["generated"]["kind"] == "toc"
    assert [(e["target"], e["number"], e["style"]) for e in table["entries"]] == [
        ("b1", "1", "contents-1"),
        ("b3", "1.1", "contents-2"),
        ("b4", "2", "contents-1"),
    ]
    call(paper, "undo")
    assert len(call(paper, "blocks")["blocks"]) == 4, "title and table were one step"


def test_its_entries_follow_the_headings_and_its_options_change_in_one_step(paper):
    made = call(paper, "insert_contents", {"block": "b4"})["block"]
    call(paper, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 3, "text": "Why we did it"})
    assert entries_of(paper, made)[0] == ("b1", None, "Why we did it", None)
    call(
        paper,
        "set_contents",
        {
            "paragraph": made,
            "options": {"kind": "toc", "first": 2, "last": 2, "numbers": True, "places": True, "leader": "none"},
        },
    )
    assert [e[0] for e in entries_of(paper, made)] == ["b3"]
    with pytest.raises(RequestError, match="levels 1 to 9"):
        call(
            paper,
            "set_contents",
            {
                "paragraph": made,
                "options": {"kind": "toc", "first": 0, "last": 2, "numbers": True, "places": True, "leader": "none"},
            },
        )
    with pytest.raises(RequestError, match="not a table of contents"):
        call(
            paper,
            "set_contents",
            {
                "paragraph": "b1",
                "options": {"kind": "toc", "first": 1, "last": 2, "numbers": True, "places": True, "leader": "none"},
            },
        )


def test_typing_into_a_table_of_contents_is_refused_and_removing_it_keeps_its_title(paper):
    made = call(paper, "insert_contents", {"block": "b4"})["block"]
    with pytest.raises(RequestError):
        call(paper, "replace_text", {"block": made, "start": 0, "end_block": made, "end": 0, "text": "x"})
    call(paper, "remove_contents", {"block": made})
    blocks = call(paper, "blocks")["blocks"]
    assert [b["text"] for b in blocks][-1] == "Contents" and all("generated" not in b for b in blocks)
    with pytest.raises(RequestError, match="not a table of contents"):
        call(paper, "remove_contents", {"block": "b1"})


def test_an_agenda_lists_the_slide_titles_with_their_slide_numbers(deck):
    ids = deck.ids
    agenda = call(deck, "insert_agenda", {"slide": deck.model.slides[0]})["object"]
    assert entries_of(deck, agenda) == [(ids["t1"], None, "t1", "1"), (ids["t2"], None, "t2", "2")]
    call(deck, "number_headings", {"on": True})
    assert [e[1] for e in entries_of(deck, agenda)] == ["1", "2"]
    with pytest.raises(RequestError):
        call(deck, "set_text", {"id": agenda, "text": "typed"})
