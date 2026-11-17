"""Typing into the words of a text box character by character (step G): the kernel's InsertText and DeleteText on any
paragraph, so a colleague's edit keeps the words of others theirs, where a whole replacement gave them all to whoever
saved last."""

import pytest
from conftest import add, text_box

from claudia_core import (
    Batch,
    DeleteText,
    Document,
    InsertText,
    MemoryStore,
    ObjectsChanged,
    Run,
    SetGenerated,
    Toc,
    encode,
    word_changes,
)
from claudia_creates import SlideModel


@pytest.fixture
def deck():
    d = Document(SlideModel.empty(), store=MemoryStore())
    d.execute(add(text_box("a", text="Why we did it")), author="ann")
    return d


def words(deck, object_id="a"):
    paragraph = deck.model.get_object(object_id).body.paragraph
    return paragraph.text, [(r.length, r.author) for r in paragraph.runs]


def test_typing_and_deleting_keep_who_wrote_which_words_and_undo_puts_them_back(deck):
    events = []
    deck.subscribe(events.append)
    deck.execute(InsertText("a", 3, " exactly"), author="bob")
    assert words(deck) == ("Why exactly we did it", [(3, "ana"), (8, "bob"), (10, "ana")])
    assert any(isinstance(e, ObjectsChanged) for e in events)
    deck.execute(DeleteText("a", 0, 3), author="bob")
    assert words(deck)[0] == " exactly we did it"
    deck.undo("bob")
    deck.undo("bob")
    assert words(deck) == ("Why we did it", [(13, "ana")])


def test_only_what_differs_is_changed_so_the_rest_stays_its_writer_s(deck):
    steps = word_changes("a", "Why we did it", "Why we really did it")
    assert steps == (InsertText("a", 7, "really "),)
    deck.execute(Batch(steps, "Edit text"), author="bob")
    assert words(deck) == ("Why we really did it", [(7, "ana"), (7, "bob"), (6, "ana")])
    assert word_changes("a", "same", "same") == ()
    assert word_changes("a", "abc", "aXc") == (DeleteText("a", 1, 1), InsertText("a", 1, "X"))


def test_an_agenda_takes_no_typing_and_a_picture_has_no_words(deck):
    deck.execute(add(text_box("g", text="")), author="ann")
    deck.execute(SetGenerated("g", Toc(1, 1)), author="ann")
    with pytest.raises(ValueError, match="agenda takes no typing"):
        deck.execute(InsertText("g", 0, "x"), author="ann")
    with pytest.raises(IndexError):
        deck.execute(InsertText("a", 99, "x"), author="ann")
    with pytest.raises(IndexError):
        deck.execute(DeleteText("a", 10, 9), author="ann")


def test_a_command_is_written_down_and_read_back_under_the_kernel_s_kind(deck):
    typed = InsertText("a", 1, "x", (Run(1, "ann"),))
    assert SlideModel.registry.decode(encode(typed)) == typed
    assert typed.kind == "core.InsertText" and DeleteText.kind == "core.DeleteText"


def test_undoing_typing_after_an_undone_delete_that_cut_into_it_takes_out_exactly_the_typing(deck):
    """CODE-43: a delete that took the start of the typed words with it, undone at once, then the typing undone. The
    pair changed nothing, so the typing's undo is not moved by it (it used to cut "a note" to "a sote")."""
    deck.execute(add(text_box("n", text="a note")), author="ana")
    deck.execute(InsertText("n", 1, " short"), author="ben")
    deck.execute(DeleteText("n", 0, 2), author="ben")
    deck.undo("ben")
    assert words(deck, "n")[0] == "a short note"
    deck.undo("ben")
    assert words(deck, "n")[0] == "a note"
    deck.redo("ben")
    assert words(deck, "n")[0] == "a short note"
