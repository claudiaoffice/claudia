"""Deleting a style in a presentation (E1.10, D226): the shapes and text boxes that have it keep their look."""

from conftest import add, put, shape_object, text_box

from claudia_core import CreateStyle, StyleDef, plan_delete_style


def test_a_shape_is_assigned_another_style_and_its_words_keep_their_look_when_the_styles_they_have_are_deleted(doc):
    doc.execute(
        CreateStyle(StyleDef("glow", "Glow", "a lit shape", None, {"fill": "#ffee00"}, kind="outline")), author="ana"
    )
    doc.execute(CreateStyle(StyleDef("loud", "Loud", "big words", "body-text", {"font-size": "90px"})), author="ana")
    put(doc, shape_object("r1", style="glow"))
    doc.execute(add(text_box("t1", style="loud")), author="ana")
    looks = {"r1": doc.model.styles.computed("glow"), "t1": doc.model.styles.computed("loud")}

    doc.execute(plan_delete_style(doc.model, "glow", how="assign", target="plain-shape"), author="ana")
    doc.execute(plan_delete_style(doc.model, "loud", how="rebase", target="body-text"), author="ana")

    shape, box = doc.model.get_object("r1").body, doc.model.get_object("t1").body
    assert shape.style == "plain-shape"  # assigned: it looks like the plain shape now
    assert doc.model.styles.computed(box.style) == looks["t1"]
    assert doc.model.styles.computed(box.paragraph.style) == looks["t1"]
    assert not {"glow", "loud"} & set(doc.model.styles.ids())
    doc.undo("ana")
    doc.undo("ana")
    assert (doc.model.get_object("r1").body.style, doc.model.get_object("t1").body.style) == ("glow", "loud")
