"""The picture follows the text: a changed container is rendered in the background and the result comes back as an edit.

The wire methods only change the text (see ``test_server_containers``). Here a whole hub runs, with a stand-in for the
render service, and what people connected to the document see is checked: the new picture as an ordinary edit, and a
``render_result`` event that says whether it worked and, if not, what is wrong with the text and on which line."""

import asyncio
import json

import pytest
from test_server_containers import StubService

from claudia_creates import SlideModel
from claudia_render import Diagnostic, RenderFailed, ToolUnavailable
from claudia_server import hub as hub_module
from claudia_server.auth import Account
from claudia_server.containers import RenderDesk
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider

ANN = Account("ann", "owner")
ADD = {"slide": "s1", "x": 10, "y": 10, "w": 300, "h": 120, "type": "boxer", "source": "hello"}


class Client:
    def __init__(self, hosted, account):
        self.frames = []
        self.connection = hosted.connect(account, lambda text: self.frames.append(json.loads(text)))
        self._next = 0

    def request(self, method, params=None):
        self._next += 1
        self.connection.handle(json.dumps({"id": self._next, "method": method, "params": params}))
        return self.frames[-1]

    def events(self, name):
        return [f["data"] for f in self.frames if f.get("event") == name]


@pytest.fixture(autouse=True)
def _quick(monkeypatch):
    monkeypatch.setattr(hub_module, "RENDER_DELAY", 0.02)


def scenario(body, *, service=None, desk=True):
    service = service or StubService()

    async def run():
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service) if desk else None)
        hosted = await hub.open("deck", create=True)
        await body(hosted, Client(hosted, ANN), service)

    asyncio.run(run())


def test_a_new_container_gets_its_picture_and_everybody_is_told():
    async def body(hosted, ann, service):
        added = ann.request("add_container", ADD)["result"]
        assert hosted.document.model.containers[added["container"]].image is None
        await hosted.rendered()
        assert hosted.document.model.containers[added["container"]].image is not None
        (told,) = ann.events("render_result")
        assert told["id"] == added["container"] and told["ok"] is True and told["diagnostics"] == []

    scenario(body)


def test_a_burst_of_typing_makes_one_picture_of_the_last_text():
    async def body(hosted, ann, service):
        added = ann.request("add_container", ADD)["result"]
        for text in ("h", "he", "hel"):
            ann.request("set_container_source", {"id": added["container"], "source": text})
        await hosted.rendered()
        assert [seen[1] for seen in service.seen] == ["hel"]

    scenario(body)


def test_a_text_the_tool_rejects_is_answered_with_the_line_and_the_old_picture_stays():
    async def body(hosted, ann, service):
        added = ann.request("add_container", ADD)["result"]
        await hosted.rendered()
        before = hosted.document.model.containers[added["container"]].image

        async def refuse(kind, source, params=None):
            raise RenderFailed("no such box", (Diagnostic("error", "no such box", 2, 5),))

        service.render = refuse
        ann.request("set_container_source", {"id": added["container"], "source": "FAIL"})
        await hosted.rendered()
        told = ann.events("render_result")[-1]
        assert told["ok"] is False and told["diagnostics"] == [Diagnostic("error", "no such box", 2, 5).to_data()]
        assert hosted.document.model.containers[added["container"]].image == before

    scenario(body)


def test_a_missing_tool_is_reported_as_unavailable_with_what_to_do():
    async def body(hosted, ann, service):
        async def missing(kind, source, params=None):
            raise ToolUnavailable("boxer", "boxer was not found. Install boxer and set tools.boxer.path.")

        service.render = missing
        ann.request("add_container", ADD)
        await hosted.rendered()
        told = ann.events("render_result")[-1]
        assert told["ok"] is False and told["unavailable"] == "boxer" and "Install boxer" in told["message"]

    scenario(body)


def test_a_server_without_a_service_makes_no_pictures_and_says_nothing():
    async def body(hosted, ann, service):
        assert ann.request("add_container", ADD)["error"]["code"] == "unavailable"
        await hosted.rendered()
        assert ann.events("render_result") == []

    scenario(body, desk=False)


def test_the_picture_that_a_job_took_in_does_not_start_another_job():
    async def body(hosted, ann, service):
        ann.request("add_container", ADD)
        await hosted.rendered()
        assert len(service.seen) == 1

    scenario(body)


def test_undo_after_the_picture_arrived_takes_the_picture_and_then_the_container_away():
    async def body(hosted, ann, service):
        added = ann.request("add_container", ADD)["result"]
        await hosted.rendered()
        model = hosted.document.model
        assert model.images
        assert "result" in ann.request("undo")  # the picture, an edit of the same person
        assert model.containers[added["container"]].image is None
        await hosted.rendered()
        assert "result" in ann.request("undo")
        assert model.objects == {} and model.containers == {} and model.images == {}

    scenario(body)


def test_a_picture_comes_back_after_the_text_is_undone_and_redone():
    async def body(hosted, ann, service):
        added = ann.request("add_container", ADD)["result"]
        await hosted.rendered()
        ann.request("set_container_source", {"id": added["container"], "source": "second"})
        await hosted.rendered()
        assert hosted.document.model.containers[added["container"]].source == "second"
        assert service.seen[-1][1] == "second"

    scenario(body)


def test_closing_the_document_stops_what_is_still_waiting():
    async def body(hosted, ann, service):
        ann.request("add_container", ADD)
        hosted.stop_rendering()
        await hosted.rendered()
        assert service.seen == []

    scenario(body)


def _reopen(hub, hosted):
    """The server restarts: the document is let go, and a new hub opens it from what was kept."""
    hosted.stop_rendering()
    return Hub(hub.provider, methods=creates_methods, renderings=hosted.renderings).open("deck")


def reopening_scenario(body):
    """A document with a container that never got its picture (the tool failed), the tool working again, and the
    document opened again. ``body(hub, first, service)`` runs with the first window's client still at hand."""

    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        working = service.render

        async def broken(kind, source, params=None):
            raise RenderFailed("Fatal Package fontspec Error: the font cannot be found")

        service.render = broken
        ann = Client(first, ANN)
        added = ann.request("add_container", ADD)["result"]
        await first.rendered()
        assert first.document.model.containers[added["container"]].image is None
        service.render = working
        await body(hub, first, service, added["container"])

    asyncio.run(run())


def test_a_container_without_a_picture_is_drawn_when_the_document_is_opened_again():
    async def body(hub, first, service, container):
        again = await _reopen(hub, first)
        await again.rendered()
        assert again.document.model.containers[container].image is not None
        assert [seen[1] for seen in service.seen] == ["hello"]

    reopening_scenario(body)


def test_a_container_that_has_its_picture_is_left_alone_when_the_document_is_opened_again():
    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        Client(first, ANN).request("add_container", ADD)
        await first.rendered()
        assert len(service.seen) == 1
        again = await _reopen(hub, first)
        await again.rendered()
        assert len(service.seen) == 1

    asyncio.run(run())


def test_an_empty_container_is_not_drawn_when_the_document_is_opened():
    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        Client(first, ANN).request("add_container", {**ADD, "source": "  "})
        again = await _reopen(hub, first)
        await again.rendered()
        assert service.seen == []

    asyncio.run(run())


def test_a_window_that_joins_after_a_failed_try_is_told_what_went_wrong():
    async def body(hub, first, service, container):
        late = Client(first, Account("bob", "editor"))
        (entry,) = late.request("containers")["result"]
        assert entry["id"] == container and entry["outcome"]["ok"] is False
        assert "Fatal Package fontspec Error" in entry["outcome"]["message"]

    reopening_scenario(body)


def test_a_container_that_is_drawn_has_no_failure_left_to_tell():
    async def body(hub, first, service, container):
        again = await _reopen(hub, first)
        await again.rendered()
        (entry,) = Client(again, ANN).request("containers")["result"]
        assert entry["image"] is not None and (entry["outcome"] is None or entry["outcome"]["ok"] is True)

    reopening_scenario(body)


def test_a_new_text_clears_the_old_failure_until_the_new_try_has_spoken():
    async def body(hub, first, service, container):
        ann = Client(first, ANN)
        ann.request("set_container_source", {"id": container, "source": "second"})
        (entry,) = ann.request("containers")["result"]
        assert entry["outcome"] is None  # the old complaint was about the old text
        await first.rendered()
        (entry,) = ann.request("containers")["result"]
        assert entry["outcome"]["ok"] is True

    reopening_scenario(body)


def test_a_container_on_a_sheet_is_rendered_and_its_frame_follows_the_picture():
    from claudia_computes import AddSheet, WorkbookModel
    from claudia_server.computes import computes_methods

    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(WorkbookModel), methods=computes_methods, renderings=RenderDesk(service))
        hosted = await hub.open("book", create=True)
        ann = Client(hosted, ANN)
        hosted.document.execute(AddSheet("s1", "Plan"), author="ann")
        (sheet,) = hosted.document.model.sheets
        added = ann.request(
            "add_container", {"sheet": sheet, "row": 2, "col": 3, "w": 300, "h": 120, "type": "boxer", "source": "hi"}
        )["result"]
        await hosted.rendered()
        model = hosted.document.model
        assert model.containers[added["container"]].image is not None
        (told,) = ann.events("render_result")
        assert told["ok"] is True
        (shown,) = model.containers.users(added["container"])
        assert model.get_object(shown).body.h != 120  # fitted to the picture's proportions by a ResizeObject

    asyncio.run(run())
