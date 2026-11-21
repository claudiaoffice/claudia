"""How the text flows round an object is part of where it hangs (D1061, D1064).

The wrap lives in the anchor beside ``dx`` and ``dy``, so it follows the text with the object. A text that never set
one reads as *over the text*, so no document written before changes; a new object starts *above and below*.
"""

import pytest

from claudia_composes import (
    DEFAULT_WRAP_GAP,
    MAX_WRAP_GAP,
    WRAPS,
    BlockAnchor,
    InsertText,
    JoinBlocks,
    SetObjectWrap,
    SplitBlock,
    TextModel,
)
from claudia_core import Document, MemoryStore, ObjectBody, VisualObject, paragraph_for


def text_with_a_box(anchor: BlockAnchor) -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, "Hello world"), author="ann")
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    d.model.insert_object(VisualObject(box, anchor))
    return d


def wrap_of(d: Document) -> tuple[str, int]:
    a = d.model.objects["o1"].anchor
    return a.wrap, a.gap


def test_the_four_modes_are_the_ones_the_mock_up_shows_in_the_order_the_key_cycles_them():
    assert WRAPS == ("over", "around", "above-below", "behind")


def test_an_anchor_floats_over_the_text_unless_told_otherwise_and_stores_nothing_for_it():
    a = BlockAnchor("b1", 4)
    assert (a.wrap, a.gap) == ("over", DEFAULT_WRAP_GAP)
    assert a.to_data() == {"kind": "block", "holder": "b1", "offset": 4, "dx": 0, "dy": 0}


def test_a_wrap_and_a_gap_are_stored_once_they_differ_from_the_default():
    assert BlockAnchor("b1", 4, wrap="around").to_data()["wrap"] == "around"
    assert "gap" not in BlockAnchor("b1", 4, wrap="around").to_data()
    data = BlockAnchor("b1", 4, wrap="above-below", gap=20).to_data()
    assert (data["wrap"], data["gap"]) == ("above-below", 20)


@pytest.mark.parametrize("wrap", WRAPS)
def test_a_wrap_round_trips(wrap):
    a = BlockAnchor("b1", 4, dx=10, dy=-5, wrap=wrap, gap=0)
    assert BlockAnchor.from_data(a.to_data()) == a


def test_an_anchor_from_before_wrapping_existed_reads_as_over_the_text():
    old = {"kind": "block", "holder": "b1", "offset": 4, "dx": 3, "dy": 4}
    assert BlockAnchor.from_data(old) == BlockAnchor("b1", 4, 3, 4)


@pytest.mark.parametrize(
    ("bad", "word"),
    [
        ({"wrap": "tight"}, "wrap"),
        ({"wrap": 3}, "wrap"),
        ({"gap": 1.5}, "gap"),
        ({"gap": True}, "gap"),
        ({"gap": -1}, "gap"),
        ({"gap": MAX_WRAP_GAP + 1}, "gap"),
    ],
)
def test_a_wrap_must_be_one_of_the_four_and_a_gap_a_whole_number_within_reach(bad, word):
    with pytest.raises(ValueError, match=word):
        BlockAnchor.from_data({"kind": "block", "holder": "b1", "offset": 0, **bad})


def test_typing_before_the_object_keeps_its_wrap():
    d = text_with_a_box(BlockAnchor("b1", 6, wrap="around", gap=12))
    d.execute(InsertText("b1", 0, "Oh. "), author="ben")
    assert wrap_of(d) == ("around", 12)
    d.undo("ben")
    assert wrap_of(d) == ("around", 12)


def test_splitting_and_joining_the_paragraph_keeps_the_wrap():
    d = text_with_a_box(BlockAnchor("b1", 6, wrap="above-below", gap=3))
    d.execute(SplitBlock("b1", 3, "b2", "body"), author="ann")
    assert d.model.objects["o1"].anchor.block == "b2"
    assert wrap_of(d) == ("above-below", 3)
    d.execute(JoinBlocks("b2", "b1", 3), author="ann")
    assert wrap_of(d) == ("above-below", 3)


def test_setting_the_wrap_changes_nothing_else_about_the_anchor_and_undo_takes_it_back():
    d = text_with_a_box(BlockAnchor("b1", 6, dx=40, dy=-10))
    d.execute(SetObjectWrap("o1", "around", 16), author="ann")
    a = d.model.objects["o1"].anchor
    assert (a.block, a.offset, a.dx, a.dy, a.wrap, a.gap) == ("b1", 6, 40, -10, "around", 16)
    d.undo("ann")
    a = d.model.objects["o1"].anchor
    assert (a.block, a.offset, a.dx, a.dy, a.wrap, a.gap) == ("b1", 6, 40, -10, "over", DEFAULT_WRAP_GAP)


def test_the_history_says_what_was_done():
    cases = {
        "over": "over the text",
        "around": "around",
        "above-below": "above and below",
        "behind": "behind the text",
    }
    for wrap, words in cases.items():
        command = SetObjectWrap("o1", wrap, DEFAULT_WRAP_GAP)
        assert command.label == "Wrap text"
        assert words in command.summary


def test_a_command_survives_the_log():
    command = SetObjectWrap("o1", "behind", 4)
    assert SetObjectWrap.from_data(command.to_data(), TextModel.registry) == command


def test_a_wrap_nobody_knows_is_refused_and_leaves_the_text_as_it_was():
    d = text_with_a_box(BlockAnchor("b1", 6))
    with pytest.raises(ValueError, match="wrap"):
        d.execute(SetObjectWrap("o1", "tight", 8), author="ann")
    assert wrap_of(d) == ("over", DEFAULT_WRAP_GAP)


def test_the_model_refuses_a_wrap_built_in_code_too():
    d = text_with_a_box(BlockAnchor("b1", 6))
    box = d.model.objects["o1"]
    with pytest.raises(ValueError, match="wrap"):
        d.model.check_anchor(BlockAnchor("b1", 6, wrap="tight"), box.body)
