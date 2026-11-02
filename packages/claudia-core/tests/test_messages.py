"""E1.6: durable commands, chat records, ephemeral messages."""

import pytest

from claudia_core import ChatPosted, EphemeralPublished, parse_chat
from claudia_core.messages import CHAT_MAX, EVERYBODY
from claudia_core.testing import Insert, Interval


def test_ephemeral_messages_are_delivered_but_never_stored(doc):
    got = []
    doc.subscribe(lambda e: got.append(e) if isinstance(e, EphemeralPublished) else None)
    before = list(doc.store.calls)
    doc.show_presence("ben", [Interval(0, 1)])
    doc.publish("preview", "ana", {"value": 3})
    doc.publish("typing", "ben")
    assert [e.message.kind for e in got] == ["presence", "preview", "typing"]
    assert doc.store.calls == before  # no store call of any kind
    assert len(doc.log) == 0 and doc.chat == []
    assert not doc.store.entries and not doc.store.chat and not doc.store.snapshots


def test_chat_goes_to_the_chat_store_and_not_to_the_log(doc):
    doc.execute(Insert(0, 1), author="ana")
    record = doc.post_chat("ana", "@ben please look at row 1", users=["ana", "ben", "ai"])
    assert (record.to, record.text, record.number) == ("ben", "please look at row 1", 1)
    assert str(record.at) == "main:1"
    assert doc.store.chat == [record] and len(doc.log) == 1
    assert doc.store.calls == ["append_entry", "append_chat"]


def test_chat_event(doc):
    got = []
    doc.subscribe(lambda e: got.append(e) if isinstance(e, ChatPosted) else None)
    doc.post_chat("ana", "hello everybody")
    assert got[0].record.to == EVERYBODY


def test_parse_chat_cases():
    users = ["ana", "Ben Miller", "ai"]
    assert parse_chat("hi all", users) == (EVERYBODY, "hi all")
    assert parse_chat("@all hi", users) == (EVERYBODY, "hi")
    assert parse_chat("@ai: what is the sum?", users) == ("ai", "what is the sum?")
    assert parse_chat("@ben miller see B4", users) == ("Ben Miller", "see B4")
    assert parse_chat("@carla hi") == ("carla", "hi")  # no user list: first word
    for bad in ("", "   ", "@", "@ai", "@zed hi"):
        with pytest.raises(ValueError):
            parse_chat(bad, users)
    with pytest.raises(ValueError):
        parse_chat("x" * (CHAT_MAX + 1))
