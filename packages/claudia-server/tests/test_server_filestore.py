"""The demo's file store: documents and users survive a restart (stand-in for the container, E2)."""

import json
import os
import sys

import pytest

from claudia_core import Document
from claudia_core.testing import Insert, ListModel
from claudia_server.auth import Credentials
from claudia_server.filestore import FileDirectory, FileProvider

POSITIONS = [0, 0, 1]


def fill(doc, author="ann"):
    for i, value in enumerate((5, 6, 7)):
        doc.execute(Insert(POSITIONS[i], value), author=author)


def reopen(tmp_path):
    return FileProvider(tmp_path, ListModel)


def test_a_document_comes_back_after_a_restart(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    doc = provider.create("plan")
    fill(doc)
    doc.save_checkpoint("ann", "first")
    doc.post_chat("ann", "hello everybody")
    revision = doc.revision

    again = reopen(tmp_path)
    assert again.exists("plan") and not again.exists("other")
    back = again.open("plan")
    assert back.revision == revision
    assert back.model.items == doc.model.items
    assert [c.label for c in back.checkpoints] == ["first"]
    assert [r.text for r in back.chat] == ["hello everybody"]
    assert back.history_for("ann").can_undo  # undo steps come from the log


def test_a_restored_line_and_its_hidden_future_survive(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    doc = provider.create("plan")
    fill(doc)
    doc.save_checkpoint("ann", "mark")
    doc.execute(Insert(0, 99), author="ann")
    doc.restore_checkpoint(1, "ann")
    line = doc.branch

    back = reopen(tmp_path).open("plan")
    assert back.branch == line and back.model.items == doc.model.items
    assert back.side_revisions() == doc.side_revisions() != []


def test_discarding_and_redacting_are_persisted(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    doc = provider.create("plan")
    fill(doc)
    doc.save_checkpoint("ann", "mark")
    doc.execute(Insert(0, 99), author="ann")
    doc.restore_checkpoint(1, "ann")
    gone = doc.discard_side_history()
    assert gone
    first = doc.log.path(doc.revision)[0].rev
    doc.redact([first], author="ann")

    back = reopen(tmp_path).open("plan")
    assert back.side_revisions() == []
    assert back.log.get(first).redacted
    assert back.model.items == doc.model.items


def test_a_half_written_last_line_is_ignored(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    doc = provider.create("plan")
    fill(doc)
    journal = tmp_path / "docs" / "plan" / "journal.jsonl"
    with journal.open("ab") as handle:
        handle.write(b'{"t": "entry", "d": {"rev": "main:9", "par')  # the power went out mid-write
    back = reopen(tmp_path).open("plan")
    assert back.model.items == doc.model.items


def test_a_damaged_line_in_the_middle_is_an_error_not_a_guess(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    fill(provider.create("plan"))
    journal = tmp_path / "docs" / "plan" / "journal.jsonl"
    lines = journal.read_text().splitlines()
    lines[1] = "not json"
    journal.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="journal"):
        reopen(tmp_path).open("plan")


def test_documents_are_listed_newest_first(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    fill(provider.create("old"))
    os.utime(tmp_path / "docs" / "old" / "journal.jsonl", (1_000, 1_000))
    fill(provider.create("new"))
    listed = reopen(tmp_path).documents()
    assert [d.id for d in listed] == ["new", "old"]
    assert listed[0].app == "test-list" and listed[0].modified.endswith("Z")


def test_a_document_id_cannot_leave_the_folder(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    for bad in ("../x", "a/b", "", ".hidden", "x" * 80):
        with pytest.raises(ValueError):
            provider.create(bad)
        assert not provider.exists(bad)


def test_creating_twice_is_refused(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    provider.create("plan")
    with pytest.raises(ValueError, match="exists"):
        provider.create("plan")


# ------------------------------------------------------------------------------------------------ users
def test_users_survive_a_restart_and_keep_their_password(tmp_path):
    directory = FileDirectory(tmp_path, cost=2**4)
    directory.add_user("plan", "Ann", "correct horse battery", "owner")
    directory.add_user("plan", "Ben", "another good password", "editor")

    again = FileDirectory(tmp_path, cost=2**4)
    ann = again.verify("plan", Credentials("ann", "correct horse battery"))
    assert ann is not None and ann.user == "Ann" and ann.role == "owner"
    assert again.verify("plan", Credentials("ann", "wrong password")) is None
    assert again.verify("other", Credentials("ann", "correct horse battery")) is None
    again.remove_user("plan", "ben")
    assert FileDirectory(tmp_path, cost=2**4).verify("plan", Credentials("ben", "another good password")) is None


def test_no_password_is_stored_as_it_is(tmp_path):
    FileDirectory(tmp_path, cost=2**4).add_user("plan", "Ann", "correct horse battery", "owner")
    text = (tmp_path / "users.json").read_text()
    assert "correct horse battery" not in text
    assert json.loads(text)["users"][0]["salt"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_user_file_is_private(tmp_path):
    FileDirectory(tmp_path, cost=2**4).add_user("plan", "Ann", "correct horse battery", "owner")
    assert (tmp_path / "users.json").stat().st_mode & 0o077 == 0


def test_the_hub_opens_a_stored_document(tmp_path):
    """The Document class itself is unchanged: ``Document.open`` is how the provider builds it."""
    provider = FileProvider(tmp_path, ListModel)
    fill(provider.create("plan"))
    assert isinstance(reopen(tmp_path).open("plan"), Document)
