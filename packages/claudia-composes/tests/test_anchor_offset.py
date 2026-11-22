"""An object floats at a free offset from the character it hangs from (rotation-ui, open point 1).

Until now an object's top-left sat on its anchor character (D179, D907), so it could only jump from character to
character. ``dx`` and ``dy`` let it float into a margin or beside a paragraph while the anchor still follows the text.
"""

import pytest

from claudia_composes import MAX_ANCHOR_OFFSET, InsertText, JoinParagraphs, ParagraphAnchor, SplitParagraph, TextModel
from claudia_core import Document, MemoryStore, MoveObject, ObjectBody, VisualObject, paragraph_for


def text_with_a_box(anchor: ParagraphAnchor) -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, "Hello world"), author="ann")
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"))
    d.model.insert_object(VisualObject(box, anchor))
    return d


def placed(d: Document) -> tuple[str, int, int, int]:
    a = d.model.objects["o1"].anchor
    return a.paragraph, a.offset, a.dx, a.dy


def test_an_anchor_sits_on_its_character_unless_told_otherwise():
    a = ParagraphAnchor("b1", 4)
    assert (a.dx, a.dy) == (0, 0)
    assert a.to_data() == {"kind": "paragraph", "holder": "b1", "offset": 4, "dx": 0, "dy": 0}


def test_an_offset_round_trips():
    a = ParagraphAnchor("b1", 4, dx=-120, dy=36)
    assert ParagraphAnchor.from_data(a.to_data()) == a


def test_an_anchor_from_before_offsets_existed_reads_as_sitting_on_its_character():
    old = {"kind": "paragraph", "holder": "b1", "offset": 4}
    assert ParagraphAnchor.from_data(old) == ParagraphAnchor("b1", 4)


@pytest.mark.parametrize(
    "bad",
    [
        {"dx": 1.5},
        {"dx": True},
        {"dy": "3"},
        {"dx": MAX_ANCHOR_OFFSET + 1},
        {"dy": -MAX_ANCHOR_OFFSET - 1},
    ],
)
def test_an_offset_must_be_a_whole_number_within_reach(bad):
    with pytest.raises(ValueError, match="offset"):
        ParagraphAnchor.from_data({"kind": "paragraph", "holder": "b1", "offset": 0, **bad})


def test_the_limits_themselves_are_allowed():
    a = ParagraphAnchor.from_data(
        {"kind": "paragraph", "holder": "b1", "offset": 0, "dx": MAX_ANCHOR_OFFSET, "dy": -MAX_ANCHOR_OFFSET}
    )
    assert (a.dx, a.dy) == (MAX_ANCHOR_OFFSET, -MAX_ANCHOR_OFFSET)


def test_typing_before_the_object_keeps_its_offset():
    d = text_with_a_box(ParagraphAnchor("b1", 6, dx=40, dy=-10))
    d.execute(InsertText("b1", 0, "Oh. "), author="ben")
    assert placed(d) == ("b1", 10, 40, -10)
    d.undo("ben")
    assert placed(d) == ("b1", 6, 40, -10)


def test_splitting_and_joining_the_paragraph_keeps_the_offset():
    d = text_with_a_box(ParagraphAnchor("b1", 6, dx=40, dy=-10))
    d.execute(SplitParagraph("b1", 3, "b2", "body"), author="ann")
    assert placed(d) == ("b2", 3, 40, -10)
    d.execute(JoinParagraphs("b2", "b1", 3), author="ann")
    assert placed(d) == ("b1", 6, 40, -10)


def test_dragging_the_object_is_one_move_that_undo_takes_back():
    d = text_with_a_box(ParagraphAnchor("b1", 6))
    d.execute(MoveObject("o1", ParagraphAnchor("b1", 6, dx=260, dy=-48).to_data()), author="ann")
    assert placed(d) == ("b1", 6, 260, -48)
    d.undo("ann")
    assert placed(d) == ("b1", 6, 0, 0)


def test_the_model_refuses_an_offset_out_of_reach_even_when_built_in_code():
    d = text_with_a_box(ParagraphAnchor("b1", 6))
    box = d.model.objects["o1"]
    far = VisualObject(box.body, ParagraphAnchor("b1", 6, dx=MAX_ANCHOR_OFFSET + 1))
    with pytest.raises(ValueError, match="offset"):
        d.model.check_anchor(far.anchor, far.body)
