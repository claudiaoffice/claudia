"""A document's keys never appear in a log line or in the text of an object that might be logged (E2.7, SEC-23).

Keys are looked for in every form they could take in text: the bytes as Python prints them, hex and base64.
"""

from __future__ import annotations

import base64
import logging

from starlette.testclient import TestClient
from test_server_app import INSERT, Peer, refused

from claudia_core.testing import ListModel
from claudia_document_file import KdfParams, Part, unlock
from claudia_server.app import create_app
from claudia_server.hub import Hub
from claudia_server.sealed import SealedDocuments, _Held

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"


def forms(key: bytes) -> list[str]:
    return [repr(key), key.hex(), base64.b64encode(key).decode(), base64.urlsafe_b64encode(key).decode().rstrip("=")]


def leaked(text: str, keys) -> list[str]:
    return [form for key in keys for form in forms(key) if form in text]


def keys_now(tmp_path) -> list[bytes]:
    return list(unlock(tmp_path / "docs" / "plan.claudia", ANN, ANN_PW).keys.values())


def test_no_key_is_in_the_log_of_a_whole_session(tmp_path, caplog):
    """Through the server's door: create, invite, edit and chat (packed on the way), a wrong password, removing a
    person (which renews the keys), leaving (which seals the document) and coming back."""
    caplog.set_level(logging.DEBUG)
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP, pack_every=2)
    with TestClient(create_app(Hub(store), store)) as client:
        ann = Peer(client, user=ANN, password=ANN_PW, create=True)
        assert ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})["ok"]
        for _ in range(5):
            assert ann.request("apply", {"command": INSERT})["ok"]
        assert ann.request("chat", {"text": "a word"})["ok"]
        before = keys_now(tmp_path)
        assert refused(client, user=BEN, password="Wrong-Pass-1") == (4401, "unauthorized")
        assert ann.request("remove_person", {"name": BEN})["ok"]
        ann.close()
        again = Peer(client, user=ANN, password=ANN_PW)
        assert again.hello["ok"]
        again.close()
    after = keys_now(tmp_path)

    assert set(after) != set(before), "removing Ben should have renewed the keys"
    assert caplog.records, "the session should have logged something for this test to mean anything"
    assert leaked(caplog.text, before + after) == []


def test_the_keys_of_an_open_document_do_not_show_in_its_text():
    keys = {part: bytes([n]) * 32 for n, part in enumerate(Part, start=1)}
    assert leaked(repr(_Held(keys, store=None)), keys.values()) == []  # type: ignore[arg-type]
