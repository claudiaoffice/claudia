"""Leaving a document, handing over its ownership, and deleting it for good (E2.3), on the server."""

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_container import KdfParams
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import Credentials, ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
VERA, VERA_PW = "Cornelia", "Purple-Monkey-5"


def store_in(tmp_path, **options):
    return SealedDocuments(tmp_path, ListModel, kdf=CHEAP, **options)


def server(tmp_path, **options):
    store = store_in(tmp_path, **options)
    return TestClient(create_app(Hub(store), store))


def archive(tmp_path):
    return tmp_path / "docs" / "plan.claudia"


def make_document(tmp_path, **options):
    store = store_in(tmp_path, **options)
    store.add_user("plan", ANN, ANN_PW, "owner")
    store.create("plan")
    store.add_user("plan", BEN, BEN_PW, "editor")
    store.add_user("plan", VERA, VERA_PW, "viewer")
    return store


# --- the roster --------------------------------------------------------------------------------------------------


def test_the_roster_lists_everybody_not_just_who_is_connected(tmp_path):
    store = make_document(tmp_path)
    assert [(a.user, a.role) for a in store.list_people("plan")] == [
        (ANN, "owner"),
        (BEN, "editor"),
        (VERA, "viewer"),
    ]


# --- leaving -------------------------------------------------------------------------------------------------------


def test_an_editor_can_leave(tmp_path):
    store = make_document(tmp_path)
    assert store.leave("plan", BEN, BEN_PW) is True
    assert store.verify("plan", Credentials(BEN, BEN_PW)) is None
    assert [a.user for a in store.list_people("plan")] == [ANN, VERA]


def test_a_viewer_can_leave_too(tmp_path):
    store = make_document(tmp_path)
    assert store.leave("plan", VERA, VERA_PW) is True
    assert store.verify("plan", Credentials(VERA, VERA_PW)) is None


def test_the_only_owner_cannot_leave(tmp_path):
    store = make_document(tmp_path)
    with pytest.raises(ValueError, match="owner"):
        store.leave("plan", ANN, ANN_PW)


def test_a_wrong_password_leaves_nothing(tmp_path):
    store = make_document(tmp_path)
    assert store.leave("plan", BEN, "wrong-Pass-1") is False
    assert store.verify("plan", Credentials(BEN, BEN_PW)) is not None


# --- handing over ownership ------------------------------------------------------------------------------------


def test_the_owner_can_hand_over_to_an_editor(tmp_path):
    store = make_document(tmp_path)
    assert store.propose_owner_transfer("plan", ANN, ANN_PW, BEN) is True
    account = store.accept_owner_transfer("plan", BEN, BEN_PW)
    assert (account.user, account.role) == (BEN, "owner")
    assert store.verify("plan", Credentials(ANN, ANN_PW)).role == "editor"
    assert store.verify("plan", Credentials(BEN, BEN_PW)).role == "owner"


def test_a_wrong_proposing_password_is_refused_at_once(tmp_path):
    store = make_document(tmp_path)
    assert store.propose_owner_transfer("plan", ANN, "wrong-Pass-1", BEN) is False
    assert store.accept_owner_transfer("plan", BEN, BEN_PW) is None  # nothing was proposed


def test_only_the_current_owner_can_propose(tmp_path):
    store = make_document(tmp_path)
    with pytest.raises(ValueError, match="owner"):
        store.propose_owner_transfer("plan", BEN, BEN_PW, VERA)


def test_the_new_owner_must_already_be_an_editor(tmp_path):
    store = make_document(tmp_path)
    with pytest.raises(ValueError, match="editor"):
        store.propose_owner_transfer("plan", ANN, ANN_PW, VERA)


def test_a_wrong_accepting_password_does_not_go_through(tmp_path):
    store = make_document(tmp_path)
    store.propose_owner_transfer("plan", ANN, ANN_PW, BEN)
    assert store.accept_owner_transfer("plan", BEN, "wrong-Pass-1") is None
    assert store.verify("plan", Credentials(ANN, ANN_PW)).role == "owner"


def test_accepting_only_works_once(tmp_path):
    store = make_document(tmp_path)
    store.propose_owner_transfer("plan", ANN, ANN_PW, BEN)
    assert store.accept_owner_transfer("plan", BEN, BEN_PW) is not None
    assert store.accept_owner_transfer("plan", BEN, BEN_PW) is None


def test_somebody_else_cannot_accept_a_proposal_not_made_to_them(tmp_path):
    store = make_document(tmp_path)
    store.propose_owner_transfer("plan", ANN, ANN_PW, BEN)
    assert store.accept_owner_transfer("plan", VERA, VERA_PW) is None


def test_a_later_proposal_replaces_an_unaccepted_one(tmp_path):
    store = make_document(tmp_path)
    store.add_user("plan", "Dora", "Another-Pass-1", "editor")
    store.propose_owner_transfer("plan", ANN, ANN_PW, BEN)
    store.propose_owner_transfer("plan", ANN, ANN_PW, "Dora")
    assert store.accept_owner_transfer("plan", BEN, BEN_PW) is None
    account = store.accept_owner_transfer("plan", "Dora", "Another-Pass-1")
    assert account is not None and account.role == "owner"


def test_a_proposal_expires(tmp_path):
    now = [0.0]
    store = make_document(tmp_path, transfer_ttl=10.0, clock=lambda: now[0])
    store.propose_owner_transfer("plan", ANN, ANN_PW, BEN)
    now[0] = 11.0
    assert store.accept_owner_transfer("plan", BEN, BEN_PW) is None


# --- deleting --------------------------------------------------------------------------------------------------


def test_an_owner_can_delete_the_document(tmp_path):
    store = make_document(tmp_path)
    assert store.delete_document("plan", ANN, ANN_PW) is True
    assert not archive(tmp_path).exists()
    assert not store.exists("plan")


def test_a_wrong_password_deletes_nothing(tmp_path):
    store = make_document(tmp_path)
    assert store.delete_document("plan", ANN, "wrong-Pass-1") is False
    assert archive(tmp_path).exists()


def test_an_editor_cannot_delete_the_document(tmp_path):
    store = make_document(tmp_path)
    assert store.delete_document("plan", BEN, BEN_PW) is False
    assert archive(tmp_path).exists()


# --- over the wire ---------------------------------------------------------------------------------------------


def setup_wire(tmp_path):
    client = server(tmp_path).__enter__()
    ann = Peer(client, user=ANN, password=ANN_PW, create=True)
    ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})
    ann.request("add_user", {"name": VERA, "password": VERA_PW, "role": "viewer"})
    return client, ann


def test_the_roster_is_available_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    answer = ann.request("roster")
    ann.close()
    client.__exit__(None, None, None)
    assert answer["ok"]
    assert [item["user"] for item in answer["result"]] == [ANN, BEN, VERA]


def test_leaving_over_the_wire_tells_the_others(tmp_path):
    client, ann = setup_wire(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    ann.socket.receive_json()  # "joined", from Bertram's own connection just now
    answer = ben.request("leave", {"password": BEN_PW})
    assert answer["ok"] and answer["result"] == {"left": True}
    pushed = ann.socket.receive_json()
    assert pushed["event"] == "ephemeral" and pushed["data"]["kind"] == "person_left"
    assert pushed["data"]["data"] == {"user": BEN}
    ben.close()
    ann.close()
    client.__exit__(None, None, None)


def test_a_wrong_password_refuses_to_leave_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    answer = ben.request("leave", {"password": "wrong-Pass-1"})
    assert answer["error"]["code"] == "unauthorized"
    ben.close()
    ann.close()
    client.__exit__(None, None, None)


def test_proposing_and_accepting_ownership_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    proposed = ann.request("propose_owner", {"name": BEN, "password": ANN_PW})
    assert proposed["ok"] and proposed["result"] == {"proposed": BEN}
    accepted = ben.request("accept_owner", {"password": BEN_PW})
    assert accepted["ok"] and accepted["result"] == {"accepted": True}
    ben.close()
    ann.close()
    client.__exit__(None, None, None)


def test_only_the_owner_may_propose_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    answer = ben.request("propose_owner", {"name": ANN, "password": BEN_PW})
    assert answer["error"]["code"] == "forbidden"
    ben.close()
    ann.close()
    client.__exit__(None, None, None)


def test_deleting_the_document_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    answer = ann.request("delete_document", {"password": ANN_PW})
    assert answer["ok"] and answer["result"] == {"deleted": True}
    ann.close()
    client.__exit__(None, None, None)
    assert not archive(tmp_path).exists()


def test_only_an_owner_may_delete_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    answer = ben.request("delete_document", {"password": BEN_PW})
    assert answer["error"]["code"] == "forbidden"
    ben.close()
    ann.close()
    client.__exit__(None, None, None)
    assert archive(tmp_path).exists()


def test_exporting_content_over_the_wire(tmp_path):
    client, ann = setup_wire(tmp_path)
    answer = ann.request("export_content")
    ann.close()
    client.__exit__(None, None, None)
    assert answer["ok"]
    result = answer["result"]
    assert result["app"] == ListModel.app
    assert "state" in result and "exported_at" in result


def test_a_server_without_sealed_documents_has_none_of_these(tmp_path):
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, ScryptDirectory())) as client:
        ann = Peer(client, user="ann", password="Correct-Horse-9", create=True)
        assert ann.request("roster")["error"]["code"] == "unavailable"
        assert ann.request("leave", {"password": "Correct-Horse-9"})["error"]["code"] == "unavailable"
        assert ann.request("propose_owner", {"name": "ben", "password": "Correct-Horse-9"})["error"]["code"] in (
            "unavailable",
            "forbidden",
        )
        assert ann.request("delete_document", {"password": "Correct-Horse-9"})["error"]["code"] == "unavailable"
        ann.close()
