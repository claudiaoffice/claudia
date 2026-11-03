"""The recovery key on the server (E2.2, D75): made by the owner, shown once, and a way back in."""

import json

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer, refused

from claudia_container import KdfParams, parse_recovery_key, unlock_with_recovery
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import Credentials, ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
VERA, VERA_PW = "Cornelia", "Purple-Monkey-5"
NEW_PW = "Fresh-Start-42"


def store_in(tmp_path, **options):
    return SealedDocuments(tmp_path, ListModel, kdf=CHEAP, **options)


def server(tmp_path):
    store = store_in(tmp_path)
    return TestClient(create_app(Hub(store), store))


def archive(tmp_path):
    return tmp_path / "docs" / "plan.claudia"


# --- the store -------------------------------------------------------------------------------------------------------


def make_document(tmp_path):
    store = store_in(tmp_path)
    store.add_user("plan", ANN, ANN_PW, "owner")
    store.create("plan")
    store.add_user("plan", BEN, BEN_PW, "editor")
    store.add_user("plan", VERA, VERA_PW, "viewer")
    return store


def test_a_new_recovery_key_is_shown_as_thirteen_groups_of_four(tmp_path):
    store = make_document(tmp_path)
    text = store.new_recovery_key("plan")
    groups = text.split("-")
    assert len(groups) == 13 and all(len(g) == 4 for g in groups)
    assert unlock_with_recovery(archive(tmp_path), parse_recovery_key(text)) is not None


def test_the_key_is_not_kept_anywhere(tmp_path):
    store = make_document(tmp_path)
    text = store.new_recovery_key("plan")
    raw = parse_recovery_key(text)
    on_disk = b"".join(f.read_bytes() for f in tmp_path.rglob("*") if f.is_file())
    assert raw not in on_disk and text.replace("-", "").encode() not in on_disk
    assert not hasattr(store, "recovery_key_text")


def test_a_second_key_replaces_the_first(tmp_path):
    store = make_document(tmp_path)
    first = store.new_recovery_key("plan")
    second = store.new_recovery_key("plan")
    assert first != second
    assert unlock_with_recovery(archive(tmp_path), parse_recovery_key(first)) is None
    assert unlock_with_recovery(archive(tmp_path), parse_recovery_key(second)) is not None


def test_a_recovery_key_needs_an_open_document(tmp_path):
    make_document(tmp_path)
    with pytest.raises(ValueError, match="sealed"):
        store_in(tmp_path).new_recovery_key("plan")


def test_recovering_gives_a_person_a_new_password_and_the_same_role(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    fresh = store_in(tmp_path)  # a restart
    account = fresh.recover("plan", key, "bertram", NEW_PW)
    assert (account.user, account.role) == (BEN, "editor")
    assert fresh.verify("plan", Credentials(BEN, BEN_PW)) is None
    assert fresh.verify("plan", Credentials(BEN, NEW_PW)).role == "editor"


def test_after_recovering_the_document_can_be_opened_by_that_person(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    fresh = store_in(tmp_path)
    fresh.recover("plan", key, ANN, NEW_PW)
    assert fresh.open("plan") is not None


def test_somebody_new_who_has_the_key_becomes_an_owner(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    account = store_in(tmp_path).recover("plan", key, "Dora", NEW_PW)
    assert (account.user, account.role) == ("Dora", "owner")


def test_a_wrong_key_a_missing_document_and_a_wrong_document_are_the_same_answer(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    other = store_in(tmp_path)
    wrong = "-".join(["AAAA"] * 13)
    assert other.recover("plan", wrong, ANN, NEW_PW) is None
    assert other.recover("nothing-here", key, ANN, NEW_PW) is None
    assert other.recover("../x", key, ANN, NEW_PW) is None


def test_a_key_that_is_not_a_key_gets_a_sentence(tmp_path):
    make_document(tmp_path).new_recovery_key("plan")
    with pytest.raises(ValueError, match="recovery key"):
        store_in(tmp_path).recover("plan", "not a key", ANN, NEW_PW)


def test_a_weak_new_password_is_explained_and_changes_nothing(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    fresh = store_in(tmp_path)
    with pytest.raises(ValueError, match="capital letter"):
        fresh.recover("plan", key, ANN, "alllowercase1")
    assert fresh.verify("plan", Credentials(ANN, ANN_PW)) is not None


def test_the_reserved_name_cannot_be_recovered_into(tmp_path):
    key = make_document(tmp_path).new_recovery_key("plan")
    with pytest.raises(ValueError, match="AI assistant"):
        store_in(tmp_path).recover("plan", key, "AI", NEW_PW)


# --- over the wire ----------------------------------------------------------------------------------------------------


def test_a_new_document_says_that_it_was_just_made_and_an_old_one_does_not(tmp_path):
    with server(tmp_path) as client:
        first = Peer(client, user=ANN, password=ANN_PW, create=True)
        assert first.hello["result"]["created"] is True
        first.close()
        again = Peer(client, user=ANN, password=ANN_PW, create=True)
        assert again.hello["result"].get("created", False) is False
        again.close()


def test_the_owner_asks_for_a_recovery_key(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        answer = ann.request("new_recovery_key")
        ann.close()
    assert answer["ok"]
    key = answer["result"]["recovery_key"]
    assert len(key.split("-")) == 13
    assert unlock_with_recovery(archive(tmp_path), parse_recovery_key(key)) is not None


def test_only_an_owner_may_ask_for_a_recovery_key(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})
        ben = Peer(client, user=BEN, password=BEN_PW)
        assert ben.request("new_recovery_key")["error"]["code"] == "forbidden"
        ben.close()
        ann.close()


def test_a_server_without_sealed_documents_has_no_recovery_keys():
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, ScryptDirectory())) as client:
        ann = Peer(client, user="ann", password="Correct-Horse-9", create=True)
        assert ann.request("new_recovery_key")["error"]["code"] == "unavailable"
        ann.close()


def hello_with_key(client, key, user, password, doc="plan"):
    peer = Peer.__new__(Peer)
    peer.socket = client.websocket_connect(f"/api/docs/{doc}/ws").__enter__()
    peer.socket.send_text(
        json.dumps({"id": 1, "method": "hello", "params": {"user": user, "password": password, "recovery_key": key}})
    )
    peer.hello = peer.socket.receive_json()
    peer._next, peer.pushed = 1, []
    return peer


def test_the_recovery_key_lets_a_person_in_with_a_new_password_in_one_step(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        key = ann.request("new_recovery_key")["result"]["recovery_key"]
        ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})
        ann.close()
    with server(tmp_path) as client:  # a restart; Bertram has forgotten his password
        ben = hello_with_key(client, key, BEN, NEW_PW)
        assert ben.hello["ok"] and ben.hello["result"]["role"] == "editor" and ben.hello["result"]["user"] == BEN
        ben.close()
        again = Peer(client, user=BEN, password=NEW_PW)
        assert again.hello["ok"]
        again.close()
        assert refused(client, user=BEN, password=BEN_PW) == (4401, "unauthorized")


def test_a_wrong_recovery_key_is_turned_away_like_a_wrong_password(tmp_path):
    with server(tmp_path) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        ann.request("new_recovery_key")
        ann.close()
        wrong = "-".join(["AAAA"] * 13)
        peer = hello_with_key(client, wrong, ANN, NEW_PW)
        assert peer.hello["error"]["code"] == "unauthorized"
        peer.close()
        again = Peer(client, user=ANN, password=ANN_PW)  # nothing changed
        assert again.hello["ok"]
        again.close()


def test_a_recovery_key_for_a_document_that_does_not_exist_is_turned_away_the_same_way(tmp_path):
    with server(tmp_path) as client:
        peer = hello_with_key(client, "-".join(["AAAA"] * 13), ANN, NEW_PW, doc="nothing-here")
        assert peer.hello["error"]["code"] == "unauthorized"
        peer.close()


def test_a_key_that_is_not_a_key_is_told_so(tmp_path):
    with server(tmp_path) as client:
        Peer(client, user=ANN, password=ANN_PW, create=True).close()
        peer = hello_with_key(client, "not a key", ANN, NEW_PW)
        assert peer.hello["error"]["code"] == "bad_request"
        assert "recovery key" in peer.hello["error"]["message"]
        peer.close()
