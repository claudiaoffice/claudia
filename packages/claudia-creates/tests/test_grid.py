"""Snapping an object to the grid, and releasing it again (E10.15).

The grid itself is only a helper the view draws — it is never part of the slide and has no state here at all.
What *is* real, persisted document state is each object's own choice to follow it: a boolean on the object,
changed by its own command (:class:`SetSnap`) with its own history entry, so it survives a reload and keeps
applying even when a colleague has the grid hidden."""

import pytest
from conftest import add, move, put, reopen, resize, text_box

from claudia_core import UndoConflict, UnknownCommand, encode
from claudia_creates import RemoveObject, SetSnap, SlideModel


# -- a new object snaps by default, and can be released and returned ------------------------------------------
def test_a_new_object_snaps_to_the_grid_by_default(doc):
    put(doc, text_box())
    assert doc.model.get("t1").body.snap is True


def test_an_object_is_released_from_the_grid_and_returned_to_it_and_both_can_be_undone(doc):
    put(doc, text_box())
    doc.execute(SetSnap("t1", False), author="ana")
    assert doc.model.get("t1").body.snap is False

    doc.execute(SetSnap("t1", True), author="ana")
    assert doc.model.get("t1").body.snap is True

    doc.undo("ana")
    assert doc.model.get("t1").body.snap is False, "undo of the second change brings the release back"
    doc.undo("ana")
    assert doc.model.get("t1").body.snap is True, "undo of the release brings the default back"


def test_releasing_an_object_that_is_not_there_is_refused(doc):
    with pytest.raises(ValueError, match="ghost"):
        doc.execute(SetSnap("ghost", False), author="ana")


# -- snap is independent of placement and words ----------------------------------------------------------------
def test_moving_and_resizing_do_not_touch_whether_an_object_snaps(doc):
    put(doc, text_box())
    doc.execute(SetSnap("t1", False), author="ana")
    doc.execute(move("t1", 300, 250), author="ana")
    doc.execute(resize("t1", 300, 250, 500, 200), author="ana")
    assert doc.model.get("t1").body.snap is False, "placement changes leave a released object released"


def test_a_move_and_a_colleagues_release_do_not_get_in_each_others_way(doc):
    put(doc, text_box())
    doc.execute(move("t1", 150, 150), author="ana")
    doc.execute(SetSnap("t1", False), author="ben")
    doc.undo("ana")
    assert (doc.model.get("t1").anchor.x, doc.model.get("t1").anchor.y) == (100, 100)
    assert doc.model.get("t1").body.snap is False, "ben's release stays"


def test_undo_of_a_snap_change_is_refused_when_a_colleague_changed_it_again(doc):
    put(doc, text_box())
    doc.execute(SetSnap("t1", False), author="ana")
    doc.execute(SetSnap("t1", True), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert doc.model.get("t1").body.snap is True


# -- removing and bringing an object back keeps its snap choice -------------------------------------------------
def test_an_object_keeps_its_released_state_through_removal_and_undo(doc):
    put(doc, text_box())
    doc.execute(SetSnap("t1", False), author="ana")
    doc.execute(RemoveObject("t1"), author="ana")
    doc.undo("ana")
    assert doc.model.get("t1").body.snap is False


# -- the history reads like sentences --------------------------------------------------------------------------
def test_the_history_has_labels_and_sentences_for_snap_changes():
    assert SetSnap("t1", False).label == "Release from grid"
    assert SetSnap("t1", True).label == "Snap to grid"
    assert "Released" in SetSnap("t1", False).summary
    assert "Snapped" in SetSnap("t1", True).summary


# -- documents are forever ---------------------------------------------------------------------------------------
def test_set_snap_round_trips_and_is_namespaced():
    command = SetSnap("t1", False)
    assert command.kind.startswith("core.")  # snap is shared by all three apps (E10.16)
    assert SlideModel.registry.decode(encode(command)) == command


def test_a_snap_change_survives_the_log_and_a_model_survives_its_snapshot(doc):
    put(doc, text_box())
    doc.execute(SetSnap("t1", False), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert SlideModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_the_old_creates_namespaced_add_object_is_no_longer_read(doc):
    """E10.16 moved the object commands into ``claudia_core``, so their ``kind`` changed from
    ``creates.AddObject`` to ``core.AddObject``. A ``CommandRegistry`` keys upcasters by ``(kind, schema)`` and
    has no way to alias one kind to another, so a log written before this change cannot be replayed — accepted
    deliberately, this being pre-release (D177). The error says so plainly rather than failing obscurely."""
    old = {"k": "creates.AddObject", "s": 2, "d": {"object": {}, "at": None}}
    with pytest.raises(UnknownCommand, match="creates.AddObject"):
        SlideModel.registry.decode(old)


def test_a_snap_field_that_is_not_a_bool_is_refused(doc):
    with pytest.raises(ValueError, match="snap"):
        doc.execute(add(text_box(snap=1)), author="ana")
    with pytest.raises(ValueError, match="snap"):
        doc.execute(add(text_box(snap="true")), author="ana")
