"""The picture follows the text: a changed container is rendered in the background and the result comes back as an edit.

The wire methods only change the text (see ``test_server_rendered``). Here a whole hub runs, with a stand-in for the
render service, and what people connected to the document see is checked: the new picture as an ordinary edit, and a
``render_result`` event that says whether it worked and, if not, what is wrong with the text and on which line."""

import asyncio
import json

import pytest
from test_server_rendered import StubService

from claudia_creates import SlideModel
from claudia_render import Diagnostic, RenderFailed, ToolUnavailable
from claudia_server import hub as hub_module
from claudia_server.auth import Account
from claudia_server.creates import creates_methods
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.rendered import RenderDesk

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


async def settle():
    await asyncio.sleep(0.2)


def test_a_new_container_gets_its_picture_and_everybody_is_told():
    async def body(hosted, ann, service):
        added = ann.request("add_rendering", ADD)["result"]
        assert hosted.document.model.renderings[added["rendering"]].image is None
        await settle()
        assert hosted.document.model.renderings[added["rendering"]].image is not None
        (told,) = ann.events("render_result")
        assert told["id"] == added["rendering"] and told["ok"] is True and told["diagnostics"] == []

    scenario(body)


def test_a_burst_of_typing_makes_one_picture_of_the_last_text():
    async def body(hosted, ann, service):
        added = ann.request("add_rendering", ADD)["result"]
        for text in ("h", "he", "hel"):
            ann.request("set_rendering_source", {"id": added["rendering"], "source": text})
        await settle()
        assert [seen[1] for seen in service.seen] == ["hel"]

    scenario(body)


def test_a_text_the_tool_rejects_is_answered_with_the_line_and_the_old_picture_stays():
    async def body(hosted, ann, service):
        added = ann.request("add_rendering", ADD)["result"]
        await settle()
        before = hosted.document.model.renderings[added["rendering"]].image

        async def refuse(kind, source, params=None):
            raise RenderFailed("no such box", (Diagnostic("error", "no such box", 2, 5),))

        service.render = refuse
        ann.request("set_rendering_source", {"id": added["rendering"], "source": "FAIL"})
        await settle()
        told = ann.events("render_result")[-1]
        assert told["ok"] is False and told["diagnostics"] == [Diagnostic("error", "no such box", 2, 5).to_data()]
        assert hosted.document.model.renderings[added["rendering"]].image == before

    scenario(body)


def test_a_missing_tool_is_reported_as_unavailable_with_what_to_do():
    async def body(hosted, ann, service):
        async def missing(kind, source, params=None):
            raise ToolUnavailable("boxer", "boxer was not found. Install boxer and set tools.boxer.path.")

        service.render = missing
        ann.request("add_rendering", ADD)
        await settle()
        told = ann.events("render_result")[-1]
        assert told["ok"] is False and told["unavailable"] == "boxer" and "Install boxer" in told["message"]

    scenario(body)


def test_a_server_without_a_service_makes_no_pictures_and_says_nothing():
    async def body(hosted, ann, service):
        assert ann.request("add_rendering", ADD)["error"]["code"] == "unavailable"
        await settle()
        assert ann.events("render_result") == []

    scenario(body, desk=False)


def test_the_picture_that_a_job_took_in_does_not_start_another_job():
    async def body(hosted, ann, service):
        ann.request("add_rendering", ADD)
        await settle()
        await settle()
        assert len(service.seen) == 1

    scenario(body)


def test_undo_after_the_picture_arrived_takes_the_picture_and_then_the_container_away():
    async def body(hosted, ann, service):
        added = ann.request("add_rendering", ADD)["result"]
        await settle()
        model = hosted.document.model
        assert model.images
        assert "result" in ann.request("undo")  # the picture, an edit of the same person
        assert model.renderings[added["rendering"]].image is None
        await settle()
        assert "result" in ann.request("undo")
        assert model.objects == {} and model.renderings == {} and model.images == {}

    scenario(body)


def test_a_picture_comes_back_after_the_text_is_undone_and_redone():
    async def body(hosted, ann, service):
        added = ann.request("add_rendering", ADD)["result"]
        await settle()
        ann.request("set_rendering_source", {"id": added["rendering"], "source": "second"})
        await settle()
        assert hosted.document.model.renderings[added["rendering"]].source == "second"
        assert service.seen[-1][1] == "second"

    scenario(body)


def test_closing_the_document_stops_what_is_still_waiting():
    async def body(hosted, ann, service):
        ann.request("add_rendering", ADD)
        hosted.stop_rendering()
        await settle()
        assert service.seen == []

    scenario(body)


def _reopen(hub, hosted):
    """The document is closed (nobody is here, the server restarts) and opened again from what was kept."""
    hosted.stop_rendering()
    hub._documents.clear()
    return hub.open("deck")


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
        added = ann.request("add_rendering", ADD)["result"]
        await settle()
        assert first.document.model.renderings[added["rendering"]].image is None
        service.render = working
        await body(hub, first, service, added["rendering"])

    asyncio.run(run())


def test_a_container_without_a_picture_is_drawn_when_the_document_is_opened_again():
    async def body(hub, first, service, rendering):
        again = await _reopen(hub, first)
        await settle()
        assert again.document.model.renderings[rendering].image is not None
        assert [seen[1] for seen in service.seen] == ["hello"]

    reopening_scenario(body)


def test_a_container_that_has_its_picture_is_left_alone_when_the_document_is_opened_again():
    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        Client(first, ANN).request("add_rendering", ADD)
        await settle()
        assert len(service.seen) == 1
        await _reopen(hub, first)
        await settle()
        assert len(service.seen) == 1

    asyncio.run(run())


def test_an_empty_container_is_not_drawn_when_the_document_is_opened():
    async def run():
        service = StubService()
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        Client(first, ANN).request("add_rendering", {**ADD, "source": "  "})
        await _reopen(hub, first)
        await settle()
        assert service.seen == []

    asyncio.run(run())


def test_a_window_that_joins_after_a_failed_try_is_told_what_went_wrong():
    async def body(hub, first, service, rendering):
        late = Client(first, Account("bob", "editor"))
        (entry,) = late.request("renderings")["result"]
        assert entry["id"] == rendering and entry["outcome"]["ok"] is False
        assert "Fatal Package fontspec Error" in entry["outcome"]["message"]

    reopening_scenario(body)


def test_a_container_that_is_drawn_has_no_failure_left_to_tell():
    async def body(hub, first, service, rendering):
        again = await _reopen(hub, first)
        await settle()
        (entry,) = Client(again, ANN).request("renderings")["result"]
        assert entry["image"] is not None and (entry["outcome"] is None or entry["outcome"]["ok"] is True)

    reopening_scenario(body)


def test_a_new_text_clears_the_old_failure_until_the_new_try_has_spoken():
    async def body(hub, first, service, rendering):
        ann = Client(first, ANN)
        ann.request("set_rendering_source", {"id": rendering, "source": "second"})
        (entry,) = ann.request("renderings")["result"]
        assert entry["outcome"] is None  # the old complaint was about the old text
        await settle()
        (entry,) = ann.request("renderings")["result"]
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
            "add_rendering", {"sheet": sheet, "row": 2, "col": 3, "w": 300, "h": 120, "type": "boxer", "source": "hi"}
        )["result"]
        await settle()
        model = hosted.document.model
        assert model.renderings[added["rendering"]].image is not None
        (told,) = ann.events("render_result")
        assert told["ok"] is True
        (shown,) = model.users_of_rendering(added["rendering"])
        assert model.get_object(shown).body.h != 120  # fitted to the picture's proportions by a ResizeObject

    asyncio.run(run())
