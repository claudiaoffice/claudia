"""The owners' consent to a remote AI provider, in a live document (E7.11, D264).

Off by default; only owners change it; everybody in the document can read it; it is kept in the document file, so a
restart does not lose it and the administrator cannot give it. A server that keeps no files has none: always off.
"""

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_core.testing import ListModel
from claudia_document_file import KdfParams, read_audit, read_consent, unlock
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
VERA, VERA_PW = "Cornelia", "Purple-Monkey-5"


@pytest.fixture
def world(tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    client = TestClient(create_app(Hub(store), store)).__enter__()
    ann = Peer(client, user=ANN, password=ANN_PW, create=True)
    ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})
    ann.request("add_user", {"name": VERA, "password": VERA_PW, "role": "viewer"})
    peers = [ann]
    yield client, ann, peers, tmp_path
    for peer in peers:
        peer.close()
    client.__exit__(None, None, None)


def join(client, peers, user, password):
    peer = Peer(client, user=user, password=password)
    peers.append(peer)
    return peer


def consent(peer):
    answer = peer.request("ai_consent")
    assert answer["ok"], answer
    return answer["result"]


def allow(peer, allowed=True):
    return peer.request("set_ai_consent", {"allowed": allowed})


def test_nothing_is_allowed_until_an_owner_says_so_and_everybody_can_read_that(world):
    client, ann, peers, _ = world
    for peer in (ann, join(client, peers, BEN, BEN_PW), join(client, peers, VERA, VERA_PW)):
        assert consent(peer) == {
            "provider": "claude",
            "allowed": False,
            "by": None,
            "at": None,
            "owners": [ANN],
            "history": [],
            "answering": None,  # this server has no assistant
        }


def test_an_owner_allows_claude_and_the_record_says_who_and_when(world):
    client, ann, peers, _ = world
    answer = allow(ann)
    assert answer["ok"] and answer["result"]["allowed"] is True and answer["result"]["by"] == ANN
    for peer in (ann, join(client, peers, VERA, VERA_PW)):
        seen = consent(peer)
        assert seen["allowed"] is True and seen["by"] == ANN and seen["at"].endswith("Z")
        assert [(h["allowed"], h["who"]) for h in seen["history"]] == [(True, ANN)]


def test_an_owner_withdraws_it_again_and_both_decisions_stay_in_the_list(world):
    _, ann, _, _ = world
    allow(ann)
    answer = allow(ann, allowed=False)
    assert answer["result"]["allowed"] is False
    assert [h["allowed"] for h in consent(ann)["history"]] == [True, False]


def test_saying_the_same_again_records_nothing_new(world):
    _, ann, _, _ = world
    allow(ann)
    allow(ann)
    allow(ann, allowed=False)
    allow(ann, allowed=False)
    assert [h["allowed"] for h in consent(ann)["history"]] == [True, False]


def test_withdrawing_what_was_never_allowed_records_nothing(world):
    _, ann, _, _ = world
    allow(ann, allowed=False)
    assert consent(ann)["history"] == []


@pytest.mark.parametrize(("user", "password"), [(BEN, BEN_PW), (VERA, VERA_PW)])
def test_an_editor_or_a_viewer_cannot_change_it_and_nothing_is_recorded(world, user, password):
    client, ann, peers, _ = world
    answer = allow(join(client, peers, user, password))
    assert answer["ok"] is False and answer["error"]["code"] == "forbidden"
    assert consent(ann)["allowed"] is False and consent(ann)["history"] == []


def test_who_decided_is_the_account_and_never_what_a_client_says(world):
    _, ann, _, _ = world
    answer = ann.request("set_ai_consent", {"allowed": True, "who": "Somebody Else"})
    assert answer["ok"] is False and answer["error"]["code"] == "bad_request"
    assert consent(ann)["history"] == []


def test_it_is_kept_in_the_document_file_and_survives_a_restart(world):
    client, ann, peers, tmp_path = world
    allow(ann)
    peers.remove(ann)
    ann.close()
    client.__exit__(None, None, None)
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    with TestClient(create_app(Hub(store), store)) as again:
        ann2 = Peer(again, user=ANN, password=ANN_PW)
        try:
            assert consent(ann2)["allowed"] is True
        finally:
            ann2.close()
    unlocked = unlock(tmp_path / "docs" / "plan.claudia", ANN, ANN_PW)
    assert [
        (r.provider, r.allowed, r.who) for r in read_consent(tmp_path / "docs" / "plan.claudia", unlocked.keys)
    ] == [("claude", True, ANN)]


def heard(peer):
    peer.request("ping")  # frames pushed meanwhile arrive in front of the answer
    ephemeral = [f["data"] for f in peer.pushed if f.get("event") == "ephemeral"]
    return [d for d in ephemeral if d.get("kind") == "ai_consent_changed"]


def test_the_other_windows_hear_of_it_a_viewer_too(world):
    client, ann, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    vera = join(client, peers, VERA, VERA_PW)
    allow(ann)
    for other in (ben, vera):
        (event,) = heard(other)
        assert event["sender"] == ANN and event["data"]["allowed"] is True and event["data"]["by"] == ANN


def test_a_consent_is_neither_history_nor_the_record_of_what_left_the_document(world):
    _, ann, _, tmp_path = world
    before = ann.request("checkpoints")["result"]
    allow(ann)
    assert ann.request("audit_log")["result"] == []
    assert ann.request("checkpoints")["result"] == before
    unlocked = unlock(tmp_path / "docs" / "plan.claudia", ANN, ANN_PW)
    assert read_audit(tmp_path / "docs" / "plan.claudia", unlocked.keys) == []


def test_a_server_that_keeps_no_files_has_no_consent_and_cannot_give_it():
    hub = Hub(MemoryProvider(ListModel))
    with TestClient(create_app(hub, ScryptDirectory())) as client:
        ann = Peer(client, user="ann", password="correct horse battery", create=True)
        try:
            assert consent(ann)["allowed"] is False
            answer = allow(ann)
            assert answer["ok"] is False and answer["error"]["code"] == "unavailable"
        finally:
            ann.close()
