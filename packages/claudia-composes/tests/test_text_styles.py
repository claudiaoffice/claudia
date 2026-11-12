"""Styles in a text: CSS in the document, all based on Body text, deviations that name themselves later (E9.7, D73)."""

import pytest

from claudia_composes import BUILTIN_STYLES, Block, BlockAnchor, SetStyle, TextModel, next_style
from claudia_core import (
    Batch,
    ChangeStyle,
    CreateStyle,
    Document,
    MemoryStore,
    ObjectBody,
    RenameStyle,
    StyleDef,
    UndoConflict,
    VisualObject,
    paragraph_for,
)


# ----------------------------------------------------------------------------- the built-in styles
def test_a_new_text_has_the_built_in_styles_and_its_paragraph_styles_are_all_based_on_body_text():
    model = TextModel()
    ids = model.styles.ids()
    assert ids[0] == "body" and {"title", "heading-1", "heading-2", "quote", "remark", "definition"} <= set(ids)
    paragraphs = [i for i in ids if model.styles.get(i).kind == "paragraph"]
    assert all(model.styles.get(i).based_on == "body" for i in paragraphs[1:])
    assert all(style.name and style.purpose for style in model.styles)
    assert [s.id for s in BUILTIN_STYLES] == ids


def test_the_object_styles_have_the_kind_of_the_slot_they_are_for():
    """D305, D310: a shape's outline is an outline style of its own, the words in it a paragraph style; a picture's
    style is a box. The same ids in all three apps (E10.16)."""
    styles = TextModel().styles
    kinds = {style.id: style.kind for style in styles}
    assert (kinds["plain-shape"], kinds["shape-label"], kinds["plain-image"]) == ("outline", "paragraph", "box")
    assert set(styles.get("plain-shape").css) <= {"fill", "stroke", "stroke-width"}
    assert styles.get("plain-shape").based_on is None and styles.get("plain-image").based_on is None
    assert styles.get("shape-label").based_on == "body"
    assert all(kind == "paragraph" for sid, kind in kinds.items() if not sid.startswith(("plain-",)))


def test_the_look_of_every_built_in_paragraph_style_is_valid_css_with_a_size_and_a_font():
    model = TextModel()
    for style in model.styles:
        if style.kind != "paragraph":
            continue
        look = model.styles.computed(style.id)
        assert look["font-size"].endswith("pt") and look["font-family"] and look["color"]


def test_headings_have_their_own_font_and_inherit_the_rest_from_body_text():
    styles = TextModel().styles
    assert "Fraunces" in styles.computed("heading-1")["font-family"]
    assert "Fraunces" not in styles.computed("body")["font-family"]
    assert styles.computed("heading-1")["color"] == styles.computed("body")["color"]
    assert "font-family" not in styles.get("quote").css or "Fraunces" in styles.get("quote").css["font-family"]


def test_changing_body_text_changes_every_style_that_has_not_overridden_the_property():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(ChangeStyle("body", {"color": "#222222"}, ()), author="ann")
    assert d.model.styles.computed("heading-2")["color"] == "#222222"
    assert d.model.styles.computed("quote")["color"] != "#222222"  # the quote has a colour of its own


# ----------------------------------------------------------------------------- what follows a style
def test_after_a_heading_comes_body_text_and_body_text_stays():
    model = TextModel()
    assert next_style(model.styles, "heading-1") == "body"
    assert next_style(model.styles, "title") == "body"
    assert next_style(model.styles, "body") == "body"


def test_a_deviation_follows_the_style_it_comes_from():
    d = Document(TextModel(), store=MemoryStore())
    for style_id, parent, css in (
        ("body-changed", "body", {"font-size": "14pt"}),
        ("h1-changed", "heading-1", {"font-size": "22pt"}),
        ("h1-again", "h1-changed", {"color": "red"}),
    ):
        d.execute(CreateStyle(StyleDef(style_id, style_id, "", parent, css, True)), author="ann")
    assert next_style(d.model.styles, "body-changed") == "body-changed"  # more body text of the same look
    assert next_style(d.model.styles, "h1-changed") == "body"
    assert next_style(d.model.styles, "h1-again") == "body"


# ----------------------------------------------------------------------------- use
def test_a_style_is_in_use_while_a_paragraph_has_it():
    model = TextModel([Block("b1", "body"), Block("b2", "quote")])
    assert model.style_in_use("quote") and not model.style_in_use("remark")
    assert model.style_uses() == {"body": 1, "quote": 1}


def test_setting_a_style_made_by_a_command_and_refusing_one_that_does_not_exist():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(CreateStyle(StyleDef("note", "Note", "a small note", "body", {"font-size": "9pt"})), author="ann")
    d.execute(SetStyle("b1", "note"), author="ann")
    assert d.model.block("b1").style == "note"
    with pytest.raises(ValueError, match="no style"):
        d.execute(SetStyle("b1", "sparkly"), author="ann")


def test_a_paragraph_takes_only_a_paragraph_style():
    """A composes paragraph is one slot that reads text, paragraph and box (D304): an outline or a box style does
    not fit it (D316)."""
    d = Document(TextModel(), store=MemoryStore())
    for style in ("plain-shape", "plain-box", "plain-image"):
        with pytest.raises(ValueError, match="cannot be put on a paragraph"):
            d.execute(SetStyle("b1", style), author="ann")
    assert d.model.block("b1").style == "body"


def test_a_style_only_an_object_in_the_text_uses_is_in_use():
    """The model's own paragraphs are not the only users of its styles: the objects in the text are too — the
    object's own style and its words' style (D304)."""
    model = TextModel()
    assert not model.style_in_use("plain-box") and not model.style_in_use("body-text")
    box = ObjectBody("t1", "text", 200, 80, "plain-box", paragraph_for("t1", "quote", "hi"))
    model.insert_object(VisualObject(box, BlockAnchor("b1", 0)))
    assert model.style_in_use("plain-box") and model.style_in_use("quote")
    assert not model.style_in_use("remark")


# ----------------------------------------------------------------------------- deviating
def deviate(d, parent="heading-1", block="b1", author="ann", **css):
    book = d.model.styles
    name = book.provisional_name(parent)
    new = StyleDef(book.unique_id(name), name, "", parent, css, to_name=True)
    return d.execute(Batch((CreateStyle(new), SetStyle(block, new.id)), "Deviate"), author=author), new


def test_a_deviation_creates_the_style_and_applies_it_in_one_step_and_one_undo():
    d = Document(TextModel(), store=MemoryStore())
    _, new = deviate(d, "body", color="#5B4BC4")
    assert new.name == "Body text (changed)" and d.model.block("b1").style == new.id
    assert d.model.styles.get(new.id).to_name
    d.undo("ann")
    assert new.id not in d.model.styles and d.model.block("b1").style == "body"
    d.redo("ann")
    assert d.model.block("b1").style == new.id


def test_naming_a_deviation_ends_the_invitation():
    d = Document(TextModel(), store=MemoryStore())
    _, new = deviate(d, "body", color="#5B4BC4")
    d.execute(RenameStyle(new.id, "Accent", False), author="ann")
    assert (d.model.styles.get(new.id).name, d.model.styles.get(new.id).to_name) == ("Accent", False)
    assert d.model.styles.provisional_name("body") == "Body text (changed)"  # free again for the next one


def test_a_deviation_is_not_taken_back_while_somebody_else_uses_it():
    d = Document(TextModel([Block("b1", "body"), Block("b2", "body")]), store=MemoryStore())
    _, new = deviate(d, "body", color="#5B4BC4")
    d.execute(SetStyle("b2", new.id), author="ben")
    with pytest.raises(UndoConflict, match="in use"):
        d.undo("ann")
    assert d.model.block("b1").style == new.id, "the refused undo changed nothing, not even the half that would work"


def test_a_deviation_cannot_be_undone_after_a_colleague_changed_the_style():
    d = Document(TextModel(), store=MemoryStore())
    _, new = deviate(d, "body", color="#5B4BC4")
    d.execute(ChangeStyle(new.id, {"font-size": "15pt"}, ()), author="ben")
    with pytest.raises(UndoConflict):
        d.undo("ann")  # it would delete what ben just did


# ----------------------------------------------------------------------------- state
def test_the_styles_are_part_of_the_state_and_survive_a_snapshot():
    d = Document(TextModel(), store=MemoryStore())
    deviate(d, "heading-1", color="#5B4BC4")
    d.execute(ChangeStyle("quote", {"font-size": "15pt"}, ()), author="ben")
    state = d.model.serialize()
    again = TextModel.restore(state)
    assert again.serialize() == state
    assert again.styles.computed("quote")["font-size"] == "15pt"
    assert "heading-1-changed" in again.styles


def test_an_older_state_without_styles_gets_the_built_in_ones():
    old = {"blocks": [{"id": "b1", "style": "heading-1", "text": "Hi", "runs": [[2, "ann", None]]}], "suggestions": []}
    model = TextModel.restore(old)
    assert model.styles.ids() == [s.id for s in BUILTIN_STYLES]
    assert model.block("b1").style == "heading-1"


def test_replaying_the_log_gives_the_same_styles():
    d = Document(TextModel(), store=MemoryStore())
    deviate(d, "heading-1", color="#5B4BC4")
    d.execute(ChangeStyle("body", {"line-height": "1.5"}, ()), author="ben")
    d.undo("ben")
    assert d.materialize(d.revision).serialize() == d.model.serialize()
