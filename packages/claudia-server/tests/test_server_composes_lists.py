"""Lists in the text app: making, nesting and continuing them, and what ``blocks`` says about them (E9.21)."""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
AI = Account.assistant()


@pytest.fixture
def paper():
    """Four paragraphs, b1 to b4: one, two, three, four."""
    doc = Document(TextModel(), store=MemoryStore())
    call(doc, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "one\ntwo\nthree\nfour"})
    return doc


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params)


def blocks(doc):
    return {b["id"]: b for b in call(doc, "blocks")["blocks"]}


def markers(doc):
    return {i: b["label"]["marker"] for i, b in blocks(doc).items() if "label" in b}


def levels(doc):
    return {i: b["item"]["level"] for i, b in blocks(doc).items() if "item" in b}


def make(doc, ids, scheme="numbers", account=ANN):
    return call(doc, "make_list", {"blocks": ids, "scheme": scheme}, account)


# ----------------------------------------------------------------------------- reading
def test_the_methods_are_there():
    assert {"make_list", "indent_item", "continue_list", "list_start"} <= composes_methods.names()


def test_blocks_say_nothing_of_lists_where_there_are_none(paper):
    answer = call(paper, "blocks")
    assert answer["lists"] == []
    assert [s["id"] for s in answer["schemes"]] == ["bullets", "numbers"]
    assert answer["schemes"][1] == {"id": "numbers", "name": "Numbers", "kind": "number", "indent": 1.6, "gap": 0.25}
    assert all("item" not in b and "label" not in b for b in answer["blocks"])


def test_an_item_comes_with_its_list_its_level_and_its_label(paper):
    make(paper, ["b2", "b3"])
    answer = call(paper, "blocks")
    assert answer["lists"] == [{"id": "l1", "scheme": "numbers", "start": 1, "name": None}]
    two = blocks(paper)["b2"]
    assert two["item"] == {"list": "l1", "level": 0} and two["label"] == {"marker": "1.", "path": [1]}
    assert blocks(paper)["b3"]["label"]["marker"] == "2."


# ----------------------------------------------------------------------------- making
def test_making_a_list_is_one_step_and_undo_takes_all_of_it_back(paper):
    answer = make(paper, ["b1", "b2", "b3"], "bullets")
    assert answer["revision"] and markers(paper) == {"b1": "•", "b2": "•", "b3": "•"}
    call(paper, "undo")
    assert markers(paper) == {} and call(paper, "blocks")["lists"] == []


def test_a_list_made_later_is_a_new_one_and_starts_at_one(paper):
    make(paper, ["b1", "b2"])
    make(paper, ["b4"])
    assert markers(paper) == {"b1": "1.", "b2": "2.", "b4": "1."}
    assert [item["id"] for item in call(paper, "blocks")["lists"]] == ["l1", "l2"]


def test_the_paragraphs_are_taken_in_the_order_of_the_text_and_not_twice(paper):
    make(paper, ["b3", "b1", "b3"])
    assert markers(paper) == {"b1": "1.", "b3": "2."}


def test_asking_again_for_the_same_kind_takes_the_selection_out_of_its_list(paper):
    make(paper, ["b1", "b2", "b3"])
    make(paper, ["b2", "b3"])
    assert markers(paper) == {"b1": "1."}


def test_the_same_kind_asked_for_a_whole_list_removes_it_and_a_different_kind_changes_its_scheme(paper):
    make(paper, ["b1", "b2"], "numbers")
    make(paper, ["b1", "b2"], "bullets")  # exactly that list: it becomes bullets, it is not a second list
    assert markers(paper) == {"b1": "•", "b2": "•"} and len(call(paper, "blocks")["lists"]) == 1
    make(paper, ["b1"], "numbers")  # part of it: a new list, the rest stays
    assert markers(paper) == {"b1": "1.", "b2": "•"} and len(call(paper, "blocks")["lists"]) == 2


def test_a_new_list_keeps_the_levels_the_items_had(paper):
    make(paper, ["b1", "b2"], "bullets")
    call(paper, "indent_item", {"blocks": ["b2"], "by": 1})
    make(paper, ["b2"], "numbers")
    assert levels(paper) == {"b1": 0, "b2": 1}


def test_without_a_scheme_the_paragraphs_are_plain_again(paper):
    make(paper, ["b1", "b2"])
    call(paper, "make_list", {"blocks": ["b1", "b2", "b4"], "scheme": None})
    assert markers(paper) == {}
    assert len(call(paper, "blocks")["lists"]) == 1, "an empty list stays in the book: undo may need it"


def test_what_cannot_be_done_is_said(paper):
    for params in (
        {"blocks": ["b9"], "scheme": "numbers"},
        {"blocks": ["b1"], "scheme": "roman-spirals"},
    ):
        with pytest.raises(RequestError) as caught:
            call(paper, "make_list", params)
        assert caught.value.code == "command_error"
    with pytest.raises(RequestError) as caught:
        call(paper, "make_list", {"blocks": [], "scheme": "numbers"})
    assert caught.value.code == "bad_request"
    assert markers(paper) == {}


def test_a_return_in_an_item_through_replace_text_gives_another_item(paper):
    make(paper, ["b1"])
    call(paper, "replace_text", {"block": "b1", "start": 3, "end_block": "b1", "end": 3, "text": "\nmore"})
    assert markers(paper) == {"b1": "1.", "b5": "2."}


# ----------------------------------------------------------------------------- nesting
def test_indenting_moves_an_item_one_level_in_and_outdenting_back(paper):
    make(paper, ["b1", "b2", "b3"])
    call(paper, "indent_item", {"blocks": ["b2"], "by": 1})
    assert markers(paper) == {"b1": "1.", "b2": "a.", "b3": "2."}
    call(paper, "indent_item", {"blocks": ["b2"], "by": -1})
    assert markers(paper) == {"b1": "1.", "b2": "2.", "b3": "3."}


def test_an_item_cannot_go_deeper_than_one_below_the_item_above_it(paper):
    make(paper, ["b1", "b2", "b3"])
    for block, expected in (("b1", 0), ("b3", 1)):  # b1 has nothing above it; b3 has b2 (level 0)
        answer = call(paper, "indent_item", {"blocks": [block], "by": 1})
        assert levels(paper)[block] == expected
        assert answer["changed"] == (0 if block == "b1" else 1)
    again = call(paper, "indent_item", {"blocks": ["b3"], "by": 1})
    assert again["changed"] == 0 and levels(paper)["b3"] == 1


def test_a_selection_moves_in_together_one_level_and_as_one_step(paper):
    make(paper, ["b1", "b2", "b3", "b4"])
    answer = call(paper, "indent_item", {"blocks": ["b2", "b3", "b4"], "by": 1})
    assert answer["changed"] == 3 and levels(paper) == {"b1": 0, "b2": 1, "b3": 1, "b4": 1}
    call(paper, "undo")
    assert levels(paper) == {"b1": 0, "b2": 0, "b3": 0, "b4": 0}


def test_outdenting_a_first_level_item_does_nothing_and_leaves_it_to_the_caller(paper):
    make(paper, ["b1"])
    before = call(paper, "blocks")["revision"]
    answer = call(paper, "indent_item", {"blocks": ["b1"], "by": -1})
    assert answer["changed"] == 0 and call(paper, "blocks")["revision"] == before


def test_plain_paragraphs_are_left_alone_by_indenting(paper):
    make(paper, ["b1"])
    answer = call(paper, "indent_item", {"blocks": ["b1", "b2"], "by": 1})
    assert answer["changed"] == 0
    with pytest.raises(RequestError) as caught:
        call(paper, "indent_item", {"blocks": ["b1"], "by": 2})
    assert caught.value.code == "bad_request"


# ----------------------------------------------------------------------------- continuing and starting
def test_a_list_can_continue_the_one_before_it(paper):
    make(paper, ["b1", "b2"])
    make(paper, ["b4"])
    call(paper, "continue_list", {"block": "b4"})
    assert markers(paper) == {"b1": "1.", "b2": "2.", "b4": "3."}
    assert [item["id"] for item in call(paper, "blocks")["lists"]] == ["l1"]
    call(paper, "undo")
    assert markers(paper) == {"b1": "1.", "b2": "2.", "b4": "1."}


def test_there_has_to_be_an_earlier_list_of_the_same_kind_to_continue(paper):
    make(paper, ["b1"], "bullets")
    make(paper, ["b3"], "numbers")
    for block in ("b1", "b3", "b2"):
        with pytest.raises(RequestError) as caught:
            call(paper, "continue_list", {"block": block})
        assert caught.value.code == "command_error"


def test_a_list_can_start_at_another_number(paper):
    make(paper, ["b1", "b2"])
    call(paper, "list_start", {"list": "l1", "start": 5})
    assert markers(paper) == {"b1": "5.", "b2": "6."}
    call(paper, "undo")
    assert markers(paper) == {"b1": "1.", "b2": "2."}
    for bad in ({"list": "l1", "start": 0}, {"list": "l7", "start": 2}):
        with pytest.raises(RequestError) as caught:
            call(paper, "list_start", bad)
        assert caught.value.code == "command_error"


# ----------------------------------------------------------------------------- who may
@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("make_list", {"blocks": ["b1"], "scheme": "numbers"}),
        ("indent_item", {"blocks": ["b1"], "by": 1}),
        ("continue_list", {"block": "b1"}),
        ("list_start", {"list": "l1", "start": 2}),
    ],
)
def test_the_assistant_has_no_direct_write_path_into_the_structure_either(paper, name, params):
    with pytest.raises(RequestError) as caught:
        call(paper, name, params, AI)
    assert caught.value.code == "forbidden"


def test_a_colleagues_zone_keeps_a_list_change_out(paper):
    call(paper, "hold", {"block": "b2", "offset": 1, "words": 1}, BEN)
    with pytest.raises(RequestError) as caught:
        make(paper, ["b2"])
    assert caught.value.code == "locked"
    make(paper, ["b4"])  # elsewhere is free
