"""Speaker notes and planned times of a slide (E10.2, D342, D343): both are document content, so setting them is a
command with an exact inverse; both survive the log and a snapshot; removing a slide and undoing it brings them back."""

import pytest

from claudia_core import CommandLog, Document, UndoConflict
from claudia_creates import (
    MAX_NOTES_LENGTH,
    MAX_SLIDE_SECONDS,
    AddSlide,
    RemoveSlide,
    SetSlideNotes,
    SetSlideTime,
    SlideModel,
)


@pytest.fixture
def doc():
    return Document(SlideModel.empty())


def events_of(doc):
    seen = []
    doc.bus.subscribe(lambda e: seen.append(e.to_data()) if hasattr(e, "to_data") else None)
    return seen


def test_a_new_slide_has_no_notes_and_no_planned_time():
    model = SlideModel.empty()
    assert model.notes_of("s1") == ""
    assert model.time_of("s1") is None
    assert model.total_time() == 0


def test_setting_notes_is_one_undoable_step_with_an_event(doc):
    seen = events_of(doc)
    doc.execute(SetSlideNotes("s1", "Start from the **2019** baseline."), author="ann")
    assert doc.model.notes_of("s1") == "Start from the **2019** baseline."
    assert {"type": "slide_notes", "slide": "s1", "notes": "Start from the **2019** baseline."} in seen
    doc.undo("ann")
    assert doc.model.notes_of("s1") == ""
    doc.redo("ann")
    assert doc.model.notes_of("s1").startswith("Start from")


def test_notes_are_kept_as_written_except_for_line_ends(doc):
    doc.execute(SetSlideNotes("s1", "one\r\ntwo\rthree\n- four"), author="ann")
    assert doc.model.notes_of("s1") == "one\ntwo\nthree\n- four"


@pytest.mark.parametrize("bad", [None, 5, "a\x00b", "x" * (MAX_NOTES_LENGTH + 1)])
def test_notes_that_cannot_be_kept_are_refused(doc, bad):
    with pytest.raises(ValueError, match="notes"):
        doc.execute(SetSlideNotes("s1", bad), author="ann")


def test_empty_notes_clear_the_notes(doc):
    doc.execute(SetSlideNotes("s1", "something"), author="ann")
    doc.execute(SetSlideNotes("s1", ""), author="ann")
    assert doc.model.serialize()["notes"] == {}


def test_notes_of_an_unknown_slide_are_refused(doc):
    with pytest.raises(ValueError, match="unknown slide"):
        doc.execute(SetSlideNotes("nope", "x"), author="ann")
    with pytest.raises(ValueError, match="unknown slide"):
        doc.execute(SetSlideTime("nope", 60), author="ann")


def test_a_planned_time_is_whole_seconds_and_can_be_cleared(doc):
    seen = events_of(doc)
    doc.execute(SetSlideTime("s1", 120), author="ann")
    assert doc.model.time_of("s1") == 120
    assert {"type": "slide_time", "slide": "s1", "seconds": 120} in seen
    doc.execute(SetSlideTime("s1", None), author="ann")
    assert doc.model.time_of("s1") is None
    doc.undo("ann")
    assert doc.model.time_of("s1") == 120
    doc.undo("ann")
    assert doc.model.time_of("s1") is None


@pytest.mark.parametrize("bad", [0, -5, 1.5, True, "60", MAX_SLIDE_SECONDS + 1])
def test_a_planned_time_that_makes_no_sense_is_refused(doc, bad):
    with pytest.raises(ValueError, match="time"):
        doc.execute(SetSlideTime("s1", bad), author="ann")


def test_the_total_is_the_sum_of_the_planned_times(doc):
    doc.execute(AddSlide("s2"), author="ann")
    doc.execute(AddSlide("s3"), author="ann")
    doc.execute(SetSlideTime("s1", 60), author="ann")
    doc.execute(SetSlideTime("s3", 150), author="ann")
    assert doc.model.total_time() == 210  # s2 has none and counts as nothing


def test_removing_a_slide_and_undoing_it_brings_notes_and_time_back(doc):
    doc.execute(AddSlide("s2"), author="ann")
    doc.execute(SetSlideNotes("s2", "keep me"), author="ann")
    doc.execute(SetSlideTime("s2", 90), author="ann")
    doc.execute(RemoveSlide("s2"), author="ann")
    assert (doc.model.notes.get("s2"), doc.model.times.get("s2")) == (None, None)
    doc.undo("ann")
    assert doc.model.slides == ["s1", "s2"]
    assert (doc.model.notes_of("s2"), doc.model.time_of("s2")) == ("keep me", 90)


def test_adding_a_slide_with_notes_and_time_reads_back_as_written():
    command = AddSlide("s2", 1, notes="hello", seconds=30)
    again = AddSlide.from_data(command.to_data(), SlideModel.registry)
    assert again == command
    assert AddSlide.from_data({"id": "s2", "at": None}, SlideModel.registry) == AddSlide("s2")


def test_redacting_an_added_slide_drops_its_notes():
    assert AddSlide("s2", 1, notes="secret", seconds=30).redacted() == AddSlide("s2", 1)


def test_notes_and_times_survive_the_log_and_a_snapshot(doc):
    doc.execute(SetSlideNotes("s1", "n"), author="ann")
    doc.execute(SetSlideTime("s1", 45), author="ann")
    log = CommandLog.from_data(doc.log.to_data(), SlideModel.registry)
    again = Document.open(SlideModel, log).model
    assert (again.notes_of("s1"), again.time_of("s1")) == ("n", 45)
    state = doc.model.serialize()
    assert state["notes"] == {"s1": "n"} and state["times"] == {"s1": 45}
    assert SlideModel.restore(state).time_of("s1") == 45


def test_a_snapshot_of_schema_7_opens_without_notes_or_times(doc):
    state = doc.model.serialize()
    del state["notes"], state["times"]
    old = SlideModel.restore(state)
    assert (old.notes_of("s1"), old.time_of("s1"), old.total_time()) == ("", None, 0)
    assert SlideModel.state_schema == 10  # 9: notes and times; 10: rendered text containers (D390)


def test_undoing_my_notes_after_a_colleague_changed_them_is_refused(doc):
    doc.execute(SetSlideNotes("s1", "mine"), author="ann")
    doc.execute(SetSlideNotes("s1", "theirs"), author="bob")
    with pytest.raises(UndoConflict):
        doc.undo("ann")
    assert doc.model.notes_of("s1") == "theirs"


def test_a_colleague_changing_another_slides_notes_does_not_stop_my_undo(doc):
    doc.execute(AddSlide("s2"), author="ann")
    doc.execute(SetSlideTime("s1", 60), author="ann")
    doc.execute(SetSlideTime("s2", 90), author="bob")
    doc.undo("ann")
    assert (doc.model.time_of("s1"), doc.model.time_of("s2")) == (None, 90)
