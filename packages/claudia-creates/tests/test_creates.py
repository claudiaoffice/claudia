import pytest

from claudia_core import CommandLog, Document, MemoryStore, Revision, UndoConflict
from claudia_core.testing import FakeClock
from claudia_creates import AddSlide, ObjectSet, PutObject, RemoveObject, SlideModel


@pytest.fixture
def doc():
    clock = FakeClock()
    d = Document(SlideModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(AddSlide("intro"), author="ana")
    d.execute(PutObject("title", {"slide": "intro", "x": 10, "text": "Hello"}), author="ana")
    return d


def test_put_remove_and_undo(doc):
    doc.execute(PutObject("title", {"slide": "intro", "x": 50, "text": "Hello"}), author="ana")
    assert doc.model.objects["title"]["x"] == 50
    doc.undo("ana")
    assert doc.model.objects["title"]["x"] == 10
    doc.execute(RemoveObject("title"), author="ana")
    doc.undo("ana")
    assert "title" in doc.model.objects


def test_object_set_region_follows_removals_and_is_a_lock(doc):
    doc.execute(PutObject("logo", {"slide": "intro", "x": 0, "text": ""}), author="ana")
    doc.show_presence("ai", [ObjectSet("intro", frozenset({"title", "logo"}))])
    doc.execute(RemoveObject("logo"), author="ana")
    assert doc.presence.of("ai").regions == (ObjectSet("intro", frozenset({"title"})),)
    doc.execute(RemoveObject("title"), author="ana")
    assert doc.presence.of("ai") is None
    region = ObjectSet("intro", frozenset({"a"}))
    assert doc.model.region_from_data(region.to_data()) == region


def test_undo_never_overwrites_a_colleagues_change_to_the_same_object(doc):
    doc.execute(PutObject("title", {"slide": "intro", "x": 20, "text": "Hello"}), author="ana")
    doc.execute(PutObject("title", {"slide": "intro", "x": 30, "text": "Hello"}), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")


def test_redaction_keeps_the_object_and_drops_its_words(doc):
    doc.execute(PutObject("note", {"slide": "intro", "x": 1, "text": "confidential figures"}), author="ben")
    doc.redact([Revision("main", 3)])
    assert doc.model.objects["note"]["text"] == ""
    again = Document.open(SlideModel, CommandLog.from_data(doc.log.to_data(), SlideModel.registry))
    assert again.model.serialize() == doc.model.serialize()
