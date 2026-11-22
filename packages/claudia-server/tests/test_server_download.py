"""File ▸ Download: the sealed Claudia file of a document, for one person (D110, D1270, E2.12), on the server."""

import base64
import io
import json
import zipfile

from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_core.testing import ListModel
from claudia_document_file import KdfParams, unlock
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN, ANN_PW = "Annabelle", "Correct-Horse-9"
BEN, BEN_PW = "Bertram", "Battery-Staple-7"
VERA, VERA_PW = "Cornelia", "Purple-Monkey-5"


def open_server(tmp_path):
    store = SealedDocuments(tmp_path, ListModel, kdf=CHEAP)
    client = TestClient(create_app(Hub(store), store)).__enter__()
    ann = Peer(client, user=ANN, password=ANN_PW, create=True)
    ann.request("add_user", {"name": BEN, "password": BEN_PW, "role": "editor"})
    ann.request("add_user", {"name": VERA, "password": VERA_PW, "role": "viewer"})
    ann.request("chat", {"text": "a-line-for-the-history-tests"})
    return client, ann


def downloaded(peer, password):
    answer = peer.request("download_claudia", {"password": password})
    assert answer["ok"], answer
    return answer["result"], base64.b64decode(answer["result"]["data"])


def slots_of(data):
    return len(json.loads(zipfile.ZipFile(io.BytesIO(data)).read("slots.json"))["slots"])


def kept(tmp_path, data):
    target = tmp_path / "kept" / "plan.claudia"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)
    return target


def test_an_owner_downloads_the_whole_file_with_what_was_just_said_in_it(tmp_path):
    client, ann = open_server(tmp_path)
    result, data = downloaded(ann, ANN_PW)
    ann.close()
    client.__exit__(None, None, None)
    assert result["format"] == "claudia"
    assert result["content_type"] == "application/x-claudia-document"
    assert result["filename"] == "plan.claudia"
    assert slots_of(data) == 3
    copy = kept(tmp_path, data)
    unlocked = unlock(copy, ANN, ANN_PW)
    assert unlocked is not None and unlocked.role == "owner"


def test_an_editor_gets_a_file_that_only_her_own_password_opens(tmp_path):
    client, ann = open_server(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    _, data = downloaded(ben, BEN_PW)
    ben.close()
    ann.close()
    client.__exit__(None, None, None)
    copy = kept(tmp_path, data)
    assert slots_of(data) == 1
    assert unlock(copy, BEN, BEN_PW) is not None
    assert unlock(copy, ANN, ANN_PW) is None


def test_a_viewer_may_download_her_part(tmp_path):
    """A viewer can only be connected while an editor holds the document open (E2.11 will change that)."""
    client, ann = open_server(tmp_path)
    vera = Peer(client, user=VERA, password=VERA_PW)
    result, data = downloaded(vera, VERA_PW)
    vera.close()
    ann.close()
    client.__exit__(None, None, None)
    assert result["parts"] == ["content"]
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert slots_of(data) == 1
    assert not any(name.startswith(("history/", "chat/")) for name in names)
    assert "head.bin" not in names
    copy = kept(tmp_path, data)
    assert unlock(copy, VERA, VERA_PW) is not None


def test_the_password_is_asked_again_and_a_wrong_one_gets_nothing(tmp_path):
    client, ann = open_server(tmp_path)
    answer = ann.request("download_claudia", {"password": "wrong-Pass-1"})
    ann.close()
    client.__exit__(None, None, None)
    assert answer["error"]["code"] == "unauthorized"


def test_somebody_elses_password_is_not_yours(tmp_path):
    client, ann = open_server(tmp_path)
    ben = Peer(client, user=BEN, password=BEN_PW)
    answer = ben.request("download_claudia", {"password": ANN_PW})
    ben.close()
    ann.close()
    client.__exit__(None, None, None)
    assert answer["error"]["code"] == "unauthorized"


def test_a_server_without_sealed_documents_has_no_such_file(tmp_path):
    with TestClient(create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory())) as client:
        ann = Peer(client, user="ann", password=ANN_PW, create=True)
        assert ann.request("download_claudia", {"password": ANN_PW})["error"]["code"] == "unavailable"
        ann.close()
