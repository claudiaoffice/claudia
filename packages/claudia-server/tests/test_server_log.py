"""The ``log`` method: the readable history that the panel shows."""

from claudia_core.testing import Insert
from claudia_server.auth import Account
from claudia_server.protocol import Context, Limits, core_methods

ANN = Account("ann", "owner")


def call(doc, name, params=None):
    return core_methods.dispatch(Context(doc, ANN, Limits(), users=lambda: ["ann"]), name, params)


def test_the_log_lists_the_visible_history_with_sentences(doc):
    doc.execute(Insert(0, 1), author="ann")
    doc.execute(Insert(0, 2), author="ben")
    entries = call(doc, "log")
    assert [e["revision"] for e in entries] == ["main:1", "main:2"]
    assert entries[1]["author"] == "ben" and entries[1]["summary"] == "Insert 2" and entries[1]["origin"] == "do"
    assert set(entries[0]) == {"revision", "author", "origin", "time", "label", "summary", "of"}


def test_undo_entries_say_what_they_reverse(doc):
    doc.execute(Insert(0, 1), author="ann")
    doc.undo("ann")
    last = call(doc, "log")[-1]
    assert last["origin"] == "undo" and last["of"] == "main:1"


def test_the_log_returns_the_newest_entries_when_limited(doc):
    for i in range(5):
        doc.execute(Insert(0, i), author="ann")
    assert [e["revision"] for e in call(doc, "log", {"limit": 2})] == ["main:4", "main:5"]


def test_a_side_line_is_not_in_the_log(doc):
    doc.execute(Insert(0, 1), author="ann")
    doc.save_checkpoint("ann", "mark")
    doc.execute(Insert(0, 2), author="ann")
    doc.restore_checkpoint(1, "ann")
    revisions = [e["revision"] for e in call(doc, "log")]
    assert "main:3" not in revisions and revisions[-1].startswith("restore-1")


# ------------------------------------------------------------------------------------------------ chat_log
def chat_as(doc, user, text):
    doc.post_chat(user, text, users=["ann", "ben", "cy"])


def test_the_chat_log_has_what_the_account_may_read(doc):
    chat_as(doc, "ann", "hello everybody")
    chat_as(doc, "ann", "@ben just for you")
    chat_as(doc, "ben", "@ann and back")
    chat_as(doc, "cy", "@ben nothing for ann")
    texts = [m["text"] for m in call(doc, "chat_log")]
    assert texts == ["hello everybody", "just for you", "and back"]


def test_the_chat_log_gives_the_newest_messages_when_limited(doc):
    for i in range(5):
        chat_as(doc, "ann", f"message {i}")
    assert [m["number"] for m in call(doc, "chat_log", {"limit": 2})] == [4, 5]
