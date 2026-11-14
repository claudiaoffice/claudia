"""A new document starts with what its app needs, and none of it is its maker's undo step (UX-33).

At cfa2d91 the web client added a new workbook's first sheet itself, and set a new text's language itself (D915), as
the person's own first steps: her first Ctrl+Z took the sheet away ("This document has no sheet yet.") or offered
"Undo Language" in a document she had not touched. The server now runs the app's ``setup_commands`` once, when it
creates the document, as one ``core.Setup`` entry: in the history, under her name, but not undoable.
"""

import json

import pytest
from starlette.testclient import TestClient

from claudia_composes import TextModel
from claudia_computes import WorkbookModel
from claudia_core import Setup
from claudia_core.testing import ListModel
from claudia_creates import SlideModel
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider

PASSWORD = "correct horse battery"


def hello(client, *, create=True, locale=None, doc="plan"):
    socket = client.websocket_connect(f"/api/docs/{doc}/ws").__enter__()
    params = {"user": "ann", "password": PASSWORD, "create": create}
    if locale is not None:
        params["locale"] = locale
    socket.send_text(json.dumps({"id": 1, "method": "hello", "params": params}))
    answer = socket.receive_json()
    socket.__exit__(None, None, None)
    return answer


def made(model_cls, **kw):
    provider = MemoryProvider(model_cls)
    with TestClient(create_app(Hub(provider), ScryptDirectory(cost=2**4))) as client:
        answer = hello(client, **kw)
        assert answer["ok"], answer
    return provider


def entries(document):
    return list(document.log.path(document.revision))


def test_a_new_workbook_has_its_first_sheet_and_nothing_to_undo():
    document = made(WorkbookModel).open("plan")
    assert [(sheet.id, sheet.name) for sheet in document.model.sheets.values()] == [("s1", "Sheet1")]
    assert not document.history_for("ann").can_undo
    assert document.undo("ann") is None
    (first,) = entries(document)
    assert isinstance(first.command, Setup) and first.author == "ann"


@pytest.mark.parametrize("model_cls", [TextModel, SlideModel])
def test_a_new_text_or_deck_is_in_the_language_of_its_makers_interface_and_has_nothing_to_undo(model_cls):
    document = made(model_cls, locale="de").open("plan")
    assert document.model.language == "de"
    assert not document.history_for("ann").can_undo


def test_without_a_locale_the_language_is_the_servers_default():
    assert made(TextModel).open("plan").model.language == "en"


def test_setup_runs_once_not_on_every_later_hello():
    provider = MemoryProvider(WorkbookModel)
    with TestClient(create_app(Hub(provider), ScryptDirectory(cost=2**4))) as client:
        assert hello(client)["result"]["created"] is True
        again = hello(client)  # the flag may be passed again; the document is only opened
        assert again["ok"] and again["result"]["created"] is False
    assert len(entries(provider.open("plan"))) == 1


def test_an_app_with_nothing_to_set_up_writes_nothing():
    assert entries(made(ListModel).open("plan")) == []


def test_setup_survives_a_reopen_and_can_be_redacted_without_becoming_undoable():
    document = made(WorkbookModel).open("plan")
    (first,) = entries(document)
    assert isinstance(first.command.redacted(), Setup)
    assert first.command.redacted().undoable is False
