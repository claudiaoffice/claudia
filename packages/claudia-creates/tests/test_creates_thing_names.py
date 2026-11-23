"""Names of objects and slides (D550): one namespace, a rename that undoes, and slides that keep their name."""

import pytest
from conftest import add, put, reopen, text_box

from claudia_core import RenameThing, clean_name
from claudia_creates import AddSlide, RemoveSlide


def named(obj_id: str, name: str, **changes):
    box = text_box(obj_id, **changes)
    return box.with_body(name=name)


# -- objects --------------------------------------------------------------------------------------------------
def test_an_object_can_carry_a_name(doc):
    put(doc, named("t1", "Intro"))
    assert doc.model.get("t1").body.name == "Intro"
    assert doc.model.thing_name("t1") == "Intro"


def test_two_objects_cannot_have_the_same_name_however_it_is_written(doc):
    put(doc, named("t1", "Figure 1"))
    with pytest.raises(ValueError, match="There is already a text box called “Figure 1”"):
        put(doc, named("t2", "figure 1", y=300))
    assert "t2" not in doc.model.objects, "a refused command changes nothing"


def test_a_name_must_be_written_tidily_when_it_arrives_in_a_body(doc):
    with pytest.raises(ValueError, match="without spaces around it"):
        put(doc, named("t1", " Intro"))


def test_things_without_a_name_do_not_clash(doc):
    put(doc, text_box("t1"))
    put(doc, text_box("t2", y=300))
    assert doc.model.names_in_use() == []


# -- renaming -------------------------------------------------------------------------------------------------
def test_an_object_is_renamed_and_undo_gives_the_old_name_back(doc):
    put(doc, named("t1", "Intro"))
    doc.execute(RenameThing("t1", "  Opening   words "), author="ana")
    assert doc.model.get("t1").body.name == "Opening words"

    doc.undo("ana")
    assert doc.model.get("t1").body.name == "Intro"


def test_renaming_an_unnamed_object_and_undoing_it_makes_it_unnamed_again(doc):
    put(doc, text_box("t1"))
    doc.execute(RenameThing("t1", "Intro"), author="ana")
    doc.undo("ana")
    assert doc.model.get("t1").body.name == ""


def test_a_rename_to_a_name_somebody_has_is_refused_with_a_sentence_that_says_who(doc):
    put(doc, named("t1", "Intro"))
    put(doc, named("t2", "Outro", y=300))
    with pytest.raises(ValueError, match="There is already a text box called “Intro”"):
        doc.execute(RenameThing("t2", "INTRO"), author="ana")
    assert doc.model.get("t2").body.name == "Outro"


def test_renaming_a_thing_to_its_own_name_in_other_capitals_is_fine(doc):
    put(doc, named("t1", "Intro"))
    doc.execute(RenameThing("t1", "INTRO"), author="ana")
    assert doc.model.get("t1").body.name == "INTRO"


def test_renaming_something_that_is_not_there_is_refused(doc):
    with pytest.raises(ValueError, match="no object|nothing"):
        doc.execute(RenameThing("nope", "x"), author="ana")


# -- slides share the namespace ----------------------------------------------------------------------------------
def test_a_slide_can_be_named_and_renamed(doc):
    doc.execute(RenameThing("s1", "Method"), author="ana")
    assert doc.model.thing_name("s1") == "Method"
    doc.undo("ana")
    assert doc.model.thing_name("s1") == ""


def test_a_slide_and_an_object_cannot_share_a_name(doc):
    doc.execute(RenameThing("s1", "Method"), author="ana")
    with pytest.raises(ValueError, match="There is already a slide called “Method”"):
        put(doc, named("t1", "method"))

    put(doc, named("t1", "Steps"))
    with pytest.raises(ValueError, match="There is already a text box called “Steps”"):
        doc.execute(RenameThing("s1", "steps"), author="ana")


def test_a_slide_brought_back_by_undo_has_its_name_and_a_new_slide_may_be_named_when_it_is_added(doc):
    doc.execute(AddSlide("s2", None, name="Results"), author="ana")
    assert doc.model.thing_name("s2") == "Results"
    doc.execute(RemoveSlide("s2"), author="ana")
    doc.undo("ana")
    assert doc.model.thing_name("s2") == "Results"


def test_a_new_slide_cannot_take_a_name_somebody_has(doc):
    doc.execute(RenameThing("s1", "Method"), author="ana")
    with pytest.raises(ValueError, match="There is already a slide called “Method”"):
        doc.execute(AddSlide("s2", None, name="method"), author="ana")


# -- the names are part of the document ---------------------------------------------------------------------------
def test_names_survive_a_rebuild_from_the_log_and_a_snapshot(doc):
    doc.execute(RenameThing("s1", "Method"), author="ana")
    put(doc, named("t1", "Figure 1"))
    again = reopen(doc)
    assert again.model.serialize() == doc.model.serialize()
    assert sorted(again.model.names_in_use()) == ["Figure 1", "Method"]

    restored = type(doc.model).restore(doc.model.serialize())
    assert restored.thing_name("s1") == "Method"


def test_a_snapshot_written_before_names_still_restores(doc):
    state = doc.model.serialize()
    del state["names"]
    assert type(doc.model).restore(state).thing_name("s1") == ""


def test_clean_name_is_what_the_command_stores():
    assert clean_name("  a  b ") == "a b"


def test_add_helper_is_still_the_plain_command():
    assert add(text_box("t9")).body.name == ""
