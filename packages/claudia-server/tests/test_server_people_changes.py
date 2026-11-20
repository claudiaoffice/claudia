"""Changing a role and removing a person in an open document, with the keys renewed (E2.3, D1263, D1274)."""

import json

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer, refused

from claudia_container import KdfParams, read_state, unlock
from claudia_container.slots import Domain
from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.hub import Hub
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
    ann.request("chat", {"text": "before the change"})
    peers = [ann]
    yield client, store, ann, peers, tmp_path / "docs" / "plan.claudia"
    for peer in peers:
        peer.close()
    client.__exit__(None, None, None)


def join(client, peers, user, password):
    peer = Peer(client, user=user, password=password)
    peers.append(peer)
    return peer


def events(peer, kind):
    return [f for f in peer.pushed if f.get("event") == "ephemeral" and f["data"]["kind"] == kind]


def say(peer, text):
    return peer.request("chat", {"text": text})


# --- changing a role -----------------------------------------------------------------------------------------------


def test_an_owner_lowers_an_editor_and_says_that_keys_were_renewed(world):
    client, _, ann, peers, _ = world
    join(client, peers, BEN, BEN_PW)
    answer = ann.request("change_role", {"name": BEN, "role": "viewer"})
    assert answer["ok"], answer
    assert answer["result"] == {"user": BEN, "role": "viewer", "renewed": True}


def test_the_lowered_persons_open_window_has_the_new_role_at_once(world):
    client, _, ann, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    assert say(ben, "still an editor")["ok"]
    ann.request("change_role", {"name": BEN, "role": "viewer"})
    again = say(ben, "now a viewer")
    assert not again["ok"] and again["error"]["code"] == "forbidden"
    assert events(ben, "role_changed")
    history = ben.request("history")  # a viewer is shown nothing of the history (D1261)
    assert not history["ok"]


def test_a_raised_viewers_open_window_may_write_at_once_and_no_keys_were_renewed(world):
    client, _, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    assert not say(vera, "nope")["ok"]
    answer = ann.request("change_role", {"name": VERA, "role": "editor"})
    assert answer["result"]["renewed"] is False
    assert say(vera, "now I may")["ok"]


def test_a_document_keeps_working_after_a_renewal_and_opens_again_with_the_new_keys(world):
    client, store, ann, peers, path = world
    ann.request("change_role", {"name": BEN, "role": "viewer"})
    assert say(ann, "after the change")["ok"]
    for peer in peers:
        peer.close()
    peers.clear()
    store.release("plan")
    keys = unlock(path, ANN, ANN_PW).keys  # her slot was behind: it is brought up to date now
    texts = read_state(path, keys).chat
    assert b"before the change" in b"".join(texts) and b"after the change" in b"".join(texts)
    again = join(client, peers, ANN, ANN_PW)
    assert again.hello["ok"]


def test_somebody_who_was_away_logs_in_after_the_renewal(world):
    client, _, ann, peers, _ = world
    ann.request("change_role", {"name": BEN, "role": "viewer"})
    vera = join(client, peers, VERA, VERA_PW)  # a viewer who stays: she had a letter
    assert vera.hello["result"]["role"] == "viewer"
    ben = join(client, peers, BEN, BEN_PW)
    assert ben.hello["result"]["role"] == "viewer"


def test_only_an_owner_changes_roles_and_removes_people(world):
    client, _, _, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    for method, params in (("change_role", {"name": VERA, "role": "editor"}), ("remove_person", {"name": VERA})):
        answer = ben.request(method, params)
        assert not answer["ok"] and answer["error"]["code"] == "forbidden"


def test_an_owner_is_not_changed_here(world):
    _, _, ann, _, _ = world
    for method, params in (("change_role", {"name": ANN, "role": "viewer"}), ("remove_person", {"name": ANN})):
        answer = ann.request(method, params)
        assert not answer["ok"] and answer["error"]["code"] == "command_error"


def test_a_role_must_be_editor_or_viewer(world):
    _, _, ann, _, _ = world
    answer = ann.request("change_role", {"name": BEN, "role": "owner"})
    assert not answer["ok"] and answer["error"]["code"] == "bad_request"


def test_somebody_who_is_not_here_is_a_sentence(world):
    _, _, ann, _, _ = world
    calls = (("change_role", {"name": "Nobody", "role": "editor"}), ("remove_person", {"name": "Nobody"}))
    for method, params in calls:
        answer = ann.request(method, params)
        assert not answer["ok"] and "Nobody" in answer["error"]["message"]


# --- removing a person ---------------------------------------------------------------------------------------------


def test_a_removed_person_cannot_log_in_again_and_her_open_window_answers_nothing_more(world):
    client, _, ann, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    answer = ann.request("remove_person", {"name": BEN})
    assert answer["ok"] and answer["result"] == {"user": BEN}
    answer_later = say(ben, "am I still here?")
    assert not answer_later["ok"] and answer_later["error"]["code"] == "forbidden"
    assert events(ben, "person_removed")  # she was told before her next request was refused
    assert [p["user"] for p in ann.request("roster")["result"]] == [ANN, VERA]
    assert refused(client, user=BEN, password=BEN_PW) == (4401, "unauthorized")


def test_everybody_else_stays_connected_and_is_told(world):
    client, _, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    ann.request("remove_person", {"name": BEN})
    roster = vera.request("roster")
    assert roster["ok"] and BEN not in [p["user"] for p in roster["result"]]
    assert events(vera, "person_removed")  # a viewer is told names too (D1261)


def test_the_removed_persons_old_keys_open_nothing_in_the_file_afterwards(world):
    _, _, ann, _, path = world
    ben_keys = unlock(path, BEN, BEN_PW).keys
    ann.request("remove_person", {"name": BEN})
    ann.request("chat", {"text": "written after the removal"})
    from claudia_container import TamperedDocument

    with pytest.raises(TamperedDocument):
        read_state(path, ben_keys)
    assert set(ben_keys) == set(Domain)


def test_what_the_wire_sends_names_nobody_who_may_not_read_it(world):
    client, _, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    ann.request("change_role", {"name": BEN, "role": "viewer"})
    ann.request("chat", {"text": "x"})
    assert all("before the change" not in json.dumps(f) for f in vera.pushed)
