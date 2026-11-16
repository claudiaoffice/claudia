"""E1.8: redaction keeps kind, ids and place in the order, and drops the content."""

import json

import pytest

from claudia_core import (
    CommandLog,
    Document,
    Rebuilt,
    RedactedEvent,
    RedactionError,
    Revision,
)
from claudia_core.testing import Insert, ListModel, Replace

SECRET = 424242


def secret_doc(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Insert(1, SECRET), author="ben")  # main:2
    doc.execute(Replace(0, 5), author="ana")
    doc.save_checkpoint("ana", "before")
    doc.execute(Insert(2, 9), author="ana")
    return doc


def test_the_content_is_gone_everywhere(make_doc):
    doc = secret_doc(make_doc)
    doc.cache_snapshot()
    assert str(SECRET) in json.dumps(doc.store.snapshots[-1].to_data())
    doc.redact([Revision("main", 2)], author="ana")
    assert str(SECRET) not in json.dumps(doc.log.to_data())
    assert str(SECRET) not in json.dumps(doc.model.serialize())
    assert str(SECRET) not in json.dumps({str(r): e.to_data() for r, e in doc.store.entries.items()})
    assert doc.store.snapshots == []  # caches built from the content were dropped
    assert str(SECRET) not in json.dumps([s.command.to_data() for s in doc.history_for("ben")._undo])


def test_entry_keeps_its_place_and_identity(make_doc):
    doc = secret_doc(make_doc)
    before = doc.log.get(Revision("main", 2))
    doc.redact([Revision("main", 2)])
    after = doc.log.get(Revision("main", 2))
    kept = ("rev", "parent", "author", "time")
    assert [getattr(after, k) for k in kept] == [getattr(before, k) for k in kept]
    assert after.redacted and after.command.kind == "list.Insert" and after.command.index == 1
    assert after.command.value == 0


def test_redaction_is_itself_logged_without_content(make_doc):
    doc = secret_doc(make_doc)
    applied = doc.redact([Revision("main", 2)], author="ana")
    entry = doc.log.get(applied.revision)
    assert entry.command.kind == "core.Redaction" and entry.author == "ana"
    assert entry.command.to_data() == {"targets": ["main:2"]}


def test_replay_of_the_stored_log_is_deterministic(make_doc):
    doc = secret_doc(make_doc)
    doc.redact([Revision("main", 2)])
    for _ in range(2):
        again = Document.open(ListModel, CommandLog.from_data(doc.log.to_data(), ListModel.registry))
        assert again.model.serialize() == doc.model.serialize()
    assert doc.model.items == [5, 0, 9]  # the secret became the neutral value; structure is intact


def test_purge_hooks_and_events(make_doc):
    doc = secret_doc(make_doc)
    purged, events = [], []
    doc.on_purge(purged.append)
    doc.subscribe(lambda e: events.append(type(e).__name__) if isinstance(e, (RedactedEvent, Rebuilt)) else None)
    doc.redact([Revision("main", 2)])
    assert purged == [(Revision("main", 2),)]
    assert events == ["Redacted", "Rebuilt"]


def test_undo_steps_made_from_redacted_content_are_dropped(make_doc):
    doc = secret_doc(make_doc)
    assert doc.history_for("ben").can_undo
    doc.redact([Revision("main", 2)])
    assert not doc.history_for("ben").can_undo  # the stack held the secret in its inverse
    assert doc.history_for("ana").can_undo  # others are rebuilt from the redacted log


def test_presence_is_cleared_by_the_rebuild(make_doc):
    from claudia_core.testing import Interval

    doc = secret_doc(make_doc)
    doc.show_presence("ben", [Interval(0, 1)])
    doc.redact([Revision("main", 2)])
    assert doc.presence.holds() == []


def test_things_that_cannot_be_redacted(make_doc):
    doc = secret_doc(make_doc)
    with pytest.raises(RedactionError):
        doc.redact([])
    with pytest.raises(RedactionError):
        doc.redact([Revision("main", 99)])
    with pytest.raises(RedactionError):
        doc.redact([Revision("main", 4)])  # the checkpoint record holds no content
    doc.redact([Revision("main", 2)])
    with pytest.raises(RedactionError):
        doc.redact([Revision("main", 2)])
