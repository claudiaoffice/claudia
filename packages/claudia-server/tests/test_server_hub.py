"""Hosting documents: which are open, who is connected, what each of them receives (ported from the demo's hub tests).

No sockets: a connection is given a ``send`` callable, here a list, exactly as the WebSocket endpoint does.
"""

import asyncio
import json

import pytest

from claudia_core import Revision
from claudia_core.testing import FakeClock, Insert, Interval, ListModel
from claudia_server.auth import Account
from claudia_server.hub import Hub, HubError, MemoryProvider
from claudia_server.protocol import Limits, core_methods

INSERT = {"k": "list.Insert", "s": 1, "d": {"index": 0, "value": 5}}


class Client:
    """A connected person: everything the server sent is in ``frames``."""

    def __init__(self, hosted, account, *, locale=None):
        self.frames: list[dict] = []
        kwargs = {} if locale is None else {"locale": locale}
        self.connection = hosted.connect(account, lambda text: self.frames.append(json.loads(text)), **kwargs)
        self._next = 0

    def request(self, method, params=None):
        self._next += 1
        self.connection.handle(json.dumps({"id": self._next, "method": method, "params": params}))
        return self.frames[-1]

    def events(self, name):
        return [f["data"] for f in self.frames if f.get("event") == name]

    def forget(self):
        self.frames.clear()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def provider(clock):
    return MemoryProvider(ListModel, clock=clock.time, lock_clock=clock.lock_time)


@pytest.fixture
def make_hub(provider, clock):
    def make(**options):
        options.setdefault("clock", clock.lock_time)
        return Hub(provider, **options)

    return make


@pytest.fixture
def hub(make_hub):
    return make_hub()


@pytest.fixture
def hosted(hub):
    return asyncio.run(hub.open("plan", create=True))


# ------------------------------------------------------------------------------------------ documents
def test_create_open_and_not_found(hub):
    async def scenario():
        with pytest.raises(HubError) as missing:
            await hub.open("plan")
        assert missing.value.code == "not_found"
        created = await hub.open("plan", create=True)
        assert await hub.open("plan") is created, "one open document per id"
        assert hub.exists("plan") and not hub.exists("other")

    asyncio.run(scenario())


def test_creation_can_be_switched_off(make_hub):
    hub = make_hub(allow_create=False)
    with pytest.raises(HubError) as refused:
        asyncio.run(hub.open("plan", create=True))
    assert refused.value.code == "not_found"


@pytest.mark.parametrize("bad", ["", "../etc/passwd", "a/b", "a b", "x" * 65, ".hidden", "-dash", "a\nb", 7, None])
def test_document_ids_cannot_escape_or_surprise(hub, bad):
    with pytest.raises(HubError) as refused:
        asyncio.run(hub.open(bad, create=True))
    assert refused.value.code == "bad_request"


def test_a_document_that_cannot_be_opened_is_a_bad_request_not_a_crash(provider, make_hub):
    def broken(doc_id):
        raise ValueError("the file is damaged")

    provider.create("plan")
    provider.open = broken
    with pytest.raises(HubError) as refused:
        asyncio.run(make_hub().open("plan"))
    assert refused.value.code == "bad_request" and "damaged" in refused.value.message


def test_a_reopened_document_has_its_state_and_history(provider, make_hub, ann):
    async def scenario():
        first = make_hub()
        hosted = await first.open("plan", create=True)
        Client(hosted, ann).request("apply", {"command": INSERT})
        return await make_hub().open("plan")  # another hub on the same storage, as after a restart

    again = asyncio.run(scenario())
    assert again.document.model.items == [5] and again.document.revision == Revision("main", 1)
    assert again.document.history_for("ann").can_undo, "undo steps come back with the log"


# ------------------------------------------------------------------------------------------ requests
def test_every_request_gets_exactly_one_response(hosted, ann):
    client = Client(hosted, ann)
    client.forget()
    for raw in ('{"id": 1, "method": "ping"}', "not json", '{"id": 2, "method": "nope"}', '{"id": 3}', "[]"):
        before = len(client.frames)
        client.connection.handle(raw)
        assert len(client.frames) == before + 1 and "ok" in client.frames[-1], raw
    assert client.frames[1]["error"]["code"] == "bad_request" and client.frames[2]["error"]["code"] == "unknown_method"


def test_the_welcome_describes_the_document_and_the_people_in_it(hosted):
    ann, ben = Account("ann", "owner"), Account("ben", "editor")
    first = Client(hosted, ann)
    second = Client(hosted, ben)
    first.request("apply", {"command": INSERT})
    first.request("save_checkpoint", {"label": "start"})
    welcome = Client(hosted, Account("cleo", "viewer")).connection.welcome()
    assert (welcome["user"], welcome["role"], welcome["doc"], welcome["app"]) == ("cleo", "viewer", "plan", "test-list")
    assert welcome["revision"] == "main:2" and welcome["line"] == "main" and welcome["limits"]["max_text"] > 0
    assert sorted(p["user"] for p in welcome["people"]) == ["ann", "ben"]
    assert [c["label"] for c in welcome["checkpoints"]] == ["start"]
    assert second.connection.id != first.connection.id and first.connection.color != second.connection.color


def test_welcome_carries_the_connections_own_locale_and_falls_back_on_a_malformed_one(hosted):
    """E5.7, D31: the locale travels with the connection, not the document — each window gets its own back."""
    plain = Client(hosted, Account("ann", "owner"))
    assert plain.connection.welcome()["locale"] == "en"
    german = Client(hosted, Account("ben", "editor"), locale="de-DE")
    assert german.connection.welcome()["locale"] == "de-DE"
    garbled = Client(hosted, Account("cleo", "viewer"), locale="not a locale!")
    assert garbled.connection.welcome()["locale"] == "en"


def test_internal_errors_do_not_leak_details(hosted, ann):
    table = core_methods.extended()

    @table.method("boom")
    def _boom(ctx):
        """Fails."""
        raise RuntimeError("secret path /srv/keys")

    hosted.methods = table
    client = Client(hosted, ann)
    frame = client.request("boom")
    assert frame["error"] == {"code": "internal", "message": "internal server error"}
    assert client.request("ping")["ok"], "the connection survives"


def test_a_result_that_cannot_be_sent_becomes_an_internal_error(hosted, ann):
    table = core_methods.extended()

    @table.method("nan")
    def _nan(ctx):
        """Returns a value JSON cannot carry."""
        return {"x": float("nan")}

    hosted.methods = table
    assert Client(hosted, ann).request("nan")["error"]["code"] == "internal"


# ------------------------------------------------------------------------------------------ updates
def test_events_reach_everyone_and_arrive_before_the_response(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.forget(), ben.forget()
    response = ann.request("apply", {"command": INSERT})
    assert response["ok"] and ann.frames[-1] is response, "the response is last"
    assert [e["revision"] for e in ann.events("command")] == ["main:1"] and ben.events("command")[0]["author"] == "ann"
    assert ann.frames.index(next(f for f in ann.frames if f.get("event") == "command")) < len(ann.frames) - 1


def test_history_events_go_to_their_author_only(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.forget(), ben.forget()
    ann.request("apply", {"command": INSERT})
    assert ann.events("history")[-1]["undo_label"] == "Insert 5" and ben.events("history") == []


def test_each_user_has_their_own_undo_history(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.request("apply", {"command": INSERT})
    ben.request("apply", {"command": {"k": "list.Insert", "s": 1, "d": {"index": 1, "value": 6}}})
    assert ann.request("undo")["result"]["applied"] and hosted.document.model.items == [6]
    assert ben.request("history")["result"]["can_undo"] is True


def test_viewers_see_everything_but_cannot_write(hosted):
    ann, vera = Client(hosted, Account("ann", "owner")), Client(hosted, Account("vera", "viewer"))
    ann.request("apply", {"command": INSERT})
    assert vera.events("command")
    assert vera.request("apply", {"command": INSERT})["error"]["code"] == "forbidden"


def test_a_broken_client_never_breaks_the_edit(hosted):
    ann = Client(hosted, Account("ann", "owner"))

    def dead(text):
        raise BrokenPipeError

    broken = hosted.connect(Account("ben", "editor"), dead)
    assert ann.request("apply", {"command": INSERT})["ok"]
    assert broken.broken, "the transport is told to drop it"
    assert ann.request("apply", {"command": INSERT})["ok"]


def test_chat_for_one_person_reaches_only_sender_and_recipient(hosted):
    ann, ben, cleo = (Client(hosted, Account(n, "editor")) for n in ("ann", "ben", "cleo"))
    ann.request("chat", {"text": "@ben the secret"})
    ann.request("chat", {"text": "hello everybody"})
    assert [c["text"] for c in ben.events("chat")] == ["the secret", "hello everybody"]
    assert [c["text"] for c in ann.events("chat")] == ["the secret", "hello everybody"]
    assert [c["text"] for c in cleo.events("chat")] == ["hello everybody"]


def test_a_restore_moves_everybody_and_edits_in_flight_are_refused(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.request("apply", {"command": INSERT})
    ann.request("save_checkpoint", {"label": "good"})
    ann.request("apply", {"command": INSERT})
    seen_by_ben = ben.request("ping")["result"]["revision"]  # main:3
    ann.forget(), ben.forget()
    hosted.document.restore_checkpoint(1, author="ann")  # the server-side act (the wire method waits for the rules)
    for client in (ann, ben):
        assert [e["new"] for e in client.events("branch")] == ["restore-1"] and client.events("rebuilt")
    stale = ben.request("apply", {"command": INSERT, "base": seen_by_ben})
    assert stale["error"]["code"] == "stale" and hosted.document.model.items == [5]
    assert ben.request("snapshot")["result"]["line"] == "restore-1"
    assert ben.request("apply", {"command": INSERT, "base": ben.request("ping")["result"]["revision"]})["ok"]


# ------------------------------------------------------------------------------------------ people
def test_joining_and_leaving_are_announced(hosted):
    ann = Client(hosted, Account("ann", "owner"))
    ann.forget()
    ben = Client(hosted, Account("ben", "editor"))
    assert ann.events("joined") == [{"id": ben.connection.id, "user": "ben", "color": ben.connection.color}]
    ben.connection.close()
    assert ann.events("left") == [{"id": ben.connection.id, "user": "ben"}]
    assert hosted.users() == ["ann"]


def test_closing_unsubscribes_but_keeps_the_undo_steps(hosted):
    ann = Client(hosted, Account("ann", "owner"))
    ann.request("apply", {"command": INSERT})
    ann.connection.close()
    ann.forget()
    hosted.document.execute(Insert(0, 1), author="ben")
    assert ann.frames == [] and hosted.document.history_for("ann").can_undo
    ann.connection.close()  # closing twice is harmless


def test_connection_limit_counts_people(make_hub):
    hub = make_hub(max_connections=2)
    hosted = asyncio.run(hub.open("plan", create=True))
    Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    with pytest.raises(HubError) as refused:
        hosted.connect(Account("cleo", "editor"), lambda text: None)
    assert refused.value.code == "unavailable"
    hosted.connect(Account.assistant(), lambda text: None)  # the assistant is not a person


def test_limits_come_from_the_hub(make_hub):
    hosted = asyncio.run(make_hub(limits=Limits(max_text=5)).open("plan", create=True))
    client = Client(hosted, Account("ann", "owner"))
    assert client.connection.welcome()["limits"]["max_text"] == 5
    assert client.request("chat", {"text": "toolong"})["error"]["code"] == "bad_request"


def test_colours_are_reused_only_when_everybody_is_taken(hosted):
    clients = [Client(hosted, Account(f"user{i}", "editor")) for i in range(9)]
    assert len({c.connection.color for c in clients[:8]}) == 8
    clients[3].connection.close()
    assert Client(hosted, Account("later", "editor")).connection.color == clients[3].connection.color


# ---------------------------------------------------------------------------------- presence and locks
def test_presence_is_shared_but_not_echoed(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.forget(), ben.forget()
    ben.request("presence", {"regions": [{"kind": "interval", "start": 0, "end": 2}]})
    shown = ann.events("ephemeral")
    assert shown and shown[0]["kind"] == "presence" and shown[0]["sender"] == "ben" and ben.events("ephemeral") == []
    assert [p["user"] for p in Client(hosted, Account("cleo", "viewer")).connection.welcome()["presence"]] == ["ben"]


def test_a_lock_rejects_everybody_else_and_ends_with_the_last_connection_of_its_owner(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ben.request("lock", {"regions": [{"kind": "interval", "start": 0, "end": 1}]})
    assert ann.request("apply", {"command": INSERT})["error"]["code"] == "locked"
    second_window = Client(hosted, Account("ben", "editor"))
    ben.connection.close()
    assert ann.request("apply", {"command": INSERT})["error"]["code"] == "locked", "his other window keeps it"
    second_window.connection.close()
    assert ann.request("apply", {"command": INSERT})["ok"]
    assert hosted.document.presence.of("ben") is None


def test_a_lock_lapses_when_its_owner_goes_quiet(make_hub, clock):
    hub = make_hub(edit_timeout=30)
    hosted = asyncio.run(hub.open("plan", create=True))
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ben.request("lock", {"regions": [{"kind": "interval", "start": 0, "end": 1}]})
    ann.forget()
    clock.advance(29)
    hub.sweep()
    assert ann.request("apply", {"command": INSERT})["error"]["code"] == "locked"
    clock.advance(2)
    hub.sweep()
    assert ann.events("ephemeral")[-1]["data"]["locked"] is False, "others are told the lock is gone"
    assert ann.request("apply", {"command": INSERT})["ok"]
    assert hosted.document.presence.of("ben") is not None, "his presence stays"


def test_a_lock_moves_with_the_edits_of_others(hosted):
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.request("apply", {"command": INSERT})
    ann.request("apply", {"command": {"k": "list.Insert", "s": 1, "d": {"index": 1, "value": 6}}})
    ben.request("lock", {"regions": [{"kind": "interval", "start": 1, "end": 2}]})
    assert ann.request("apply", {"command": INSERT})["ok"]  # inserted in front of his element
    assert hosted.document.presence.of("ben").regions == (Interval(2, 3),)


# ------------------------------------------------------------------------------------------ housekeeping
def test_idle_documents_are_unloaded_but_busy_ones_are_not(make_hub, clock):
    hub = make_hub(idle_unload=60)
    quiet = asyncio.run(hub.open("quiet", create=True))
    busy = asyncio.run(hub.open("busy", create=True))
    present = Client(busy, Account("ann", "owner"))
    clock.advance(61)
    hub.sweep()
    assert hub.is_loaded("busy") and not hub.is_loaded("quiet")
    assert asyncio.run(hub.open("quiet")) is not quiet, "it is loaded again from storage"
    present.connection.close()
    clock.advance(61)
    hub.sweep()
    assert not hub.is_loaded("busy")


def test_start_and_stop_run_the_housekeeping(make_hub):
    async def scenario():
        hub = make_hub(sweep_interval=0.01)
        await hub.start()
        await asyncio.sleep(0.03)
        await hub.stop()
        await hub.stop()  # twice is harmless

    asyncio.run(scenario())


def test_the_worker_pool_is_reachable_and_stopped_with_the_hub(make_hub):
    async def scenario():
        hub = make_hub(max_workers=2)
        assert await hub.workers.submit(pow, 2, 10) == 1024
        await hub.stop()  # lets the pool's processes go; harmless to call again
        await hub.stop()

    asyncio.run(scenario())


def test_the_hub_bounds_its_worker_pool_queue(make_hub):
    hub = make_hub(max_waiting=3)
    assert hub.workers.max_waiting == 3


def test_a_workbook_document_gets_a_heavy_dispatcher_sharing_the_hubs_pool():
    """Only a workbook has heavy formula calls to dispatch (D37, D177); ``ListModel`` (every other test in this
    file) has no ``calc`` at all, so this one builds its own hub on ``WorkbookModel`` instead."""
    from claudia_computes import WorkbookModel

    async def scenario():
        hub = Hub(MemoryProvider(WorkbookModel))
        hosted = await hub.open("book", create=True)
        assert hosted.heavy_dispatch is not None
        assert hosted.heavy_dispatch.workers is hub.workers

    asyncio.run(scenario())


def test_a_non_workbook_document_gets_no_heavy_dispatcher(hosted):
    assert hosted.heavy_dispatch is None


# ------------------------------------------------------------------------------------------ per-viewer masking (E10.8)
def test_an_events_to_data_for_is_used_per_connection_when_the_app_offers_it():
    """``_on_event`` calls an event's own ``to_data_for(viewer)`` when it has one (creates' ``ObjectsChanged``,
    which masks an imported image's source path), instead of the one shared ``to_data()`` every other event uses."""
    import base64
    import struct

    from claudia_creates import SlideModel
    from claudia_server.creates import creates_methods

    def tiny_gif() -> str:
        header = b"GIF89a" + struct.pack("<HHBBB", 20, 10, 0, 0, 0)
        frame = b"\x2c" + struct.pack("<HHHH", 0, 0, 20, 10) + b"\x00" + b"\x02\x01\x00\x00"
        return base64.b64encode(header + frame + b"\x3b").decode("ascii")

    hub = Hub(MemoryProvider(SlideModel), methods=creates_methods)
    hosted = asyncio.run(hub.open("talk", create=True))
    ann, ben = Client(hosted, Account("ann", "owner")), Client(hosted, Account("ben", "editor"))
    ann.forget(), ben.forget()

    ann.request(
        "add_image",
        {
            "slide": "s1",
            "x": 0,
            "y": 0,
            "w": 400,
            "h": 200,
            "data": tiny_gif(),
            "alt": "a chart",
            "source_name": "chart.gif",
            "source_path": "/Users/ann/Documents/chart.gif",
        },
    )

    (seen_by_ann,) = ann.events("objects")[-1]["changed"]
    (seen_by_ben,) = ben.events("objects")[-1]["changed"]
    assert seen_by_ann["imported"]["source_path"] == "/Users/ann/Documents/chart.gif"
    assert seen_by_ben["imported"]["source_path"] is None
    assert seen_by_ben["imported"]["source"] == "disk" and seen_by_ben["imported"]["imported_by"] == "ann"
