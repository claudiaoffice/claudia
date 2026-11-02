"""Owners add people to their document (the way a second person gets in)."""

import json

import pytest
from starlette.testclient import TestClient

from claudia_core import Document, MemoryStore
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import Account, ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.protocol import Context, Limits, RequestError, core_methods

OWNER, EDITOR = Account("ann", "owner"), Account("ben", "editor")


def call(account, directory, params, doc_id="plan"):
    doc = Document(ListModel(), store=MemoryStore())
    ctx = Context(doc, account, Limits(), directory=directory, doc_id=doc_id)
    return core_methods.dispatch(ctx, "add_user", params)


@pytest.fixture
def directory():
    return ScryptDirectory(cost=2**4)


def test_an_owner_adds_a_person_who_can_then_log_in(directory):
    assert call(OWNER, directory, {"name": "Ben", "password": "a long password"}) == {"user": "Ben", "role": "editor"}
    from claudia_server.auth import Credentials

    assert directory.verify("plan", Credentials("ben", "a long password")).role == "editor"
    assert directory.verify("other", Credentials("ben", "a long password")) is None, "people belong to one document"


def test_a_viewer_can_be_added(directory):
    assert call(OWNER, directory, {"name": "Vera", "password": "a long password", "role": "viewer"})["role"] == "viewer"


def test_only_owners_add_people(directory):
    with pytest.raises(RequestError) as caught:
        call(EDITOR, directory, {"name": "Cy", "password": "a long password"})
    assert caught.value.code == "forbidden"


@pytest.mark.parametrize("role", ["owner", "admin", ""])
def test_the_roles_to_give_are_editor_and_viewer(directory, role):
    with pytest.raises(RequestError) as caught:
        call(OWNER, directory, {"name": "Cy", "password": "a long password", "role": role})
    assert caught.value.code == "bad_request"


@pytest.mark.parametrize(
    ("name", "password", "word"),
    [
        ("ai", "a long password", "assistant"),
        ("Cy", "short", "password"),
        ("ann", "a long password", "already"),
        ("", "a long password", "name"),
    ],
)
def test_names_and_passwords_that_are_not_acceptable_are_explained(directory, name, password, word):
    directory.add_user("plan", "Ann", "the owner password", "owner")
    with pytest.raises(RequestError) as caught:
        call(OWNER, directory, {"name": name, "password": password})
    assert caught.value.code == "command_error" and word in caught.value.message.casefold()


def test_a_server_that_does_not_manage_users_says_so():
    with pytest.raises(RequestError) as caught:
        call(OWNER, None, {"name": "Cy", "password": "a long password"})
    assert caught.value.code == "unavailable"


def test_the_password_is_never_in_an_error_or_a_log_line(directory, caplog):
    with pytest.raises(RequestError) as caught:
        call(OWNER, directory, {"name": "ai", "password": "my secret passphrase"})
    assert "secret" not in caught.value.message and "secret" not in caplog.text


def test_over_the_wire_the_second_person_gets_in():
    directory = ScryptDirectory(cost=2**4)
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, directory)) as client:

        def hello(user, password, create=False):
            socket = client.websocket_connect("/api/docs/plan/ws").__enter__()
            socket.send_text(
                json.dumps(
                    {"id": 1, "method": "hello", "params": {"user": user, "password": password, "create": create}}
                )
            )
            return socket, socket.receive_json()

        ann, welcome = hello("ann", "the owner password", create=True)
        assert welcome["ok"]
        ann.send_text(
            json.dumps({"id": 2, "method": "add_user", "params": {"name": "ben", "password": "ben's password"}})
        )
        while (frame := ann.receive_json()).get("id") != 2:
            pass
        assert frame["ok"] and frame["result"]["role"] == "editor"
        ben, welcome = hello("ben", "ben's password")
        assert welcome["ok"] and welcome["result"]["user"] == "ben"
        ben.__exit__(None, None, None)
        ann.__exit__(None, None, None)
