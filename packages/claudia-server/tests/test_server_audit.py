"""What leaves the document is recorded (E2.9, D1271) and the unencrypted export (D1270), on the server."""

import base64
import io
import json
import zipfile

import pytest
from starlette.testclient import TestClient
from test_server_app import Peer

from claudia_container import KdfParams, read_audit, read_export, unlock
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
    ann.request("chat", {"text": "a-private-remark"})
    peers = [ann]
    yield client, ann, peers, tmp_path
    for peer in peers:
        peer.close()
    client.__exit__(None, None, None)


def join(client, peers, user, password):
    peer = Peer(client, user=user, password=password)
    peers.append(peer)
    return peer


def rows(peer):
    answer = peer.request("audit_log")
    assert answer["ok"], answer
    return answer["result"]


def exported(peer, **params):
    answer = peer.request("export_claudia", params)
    assert answer["ok"], answer
    return answer["result"], base64.b64decode(answer["result"]["data"])


def test_a_new_document_has_nothing_recorded(world):
    _, ann, _, _ = world
    assert rows(ann) == []


def test_an_unencrypted_export_is_a_zip_with_the_content_and_is_recorded_for_the_one_who_made_it(world):
    _, ann, _, _ = world
    result, data = exported(ann)
    assert result["format"] == "claudia-unencrypted" and result["parts"] == ["content"]
    assert result["filename"] == "plan.claudia-export.zip"
    assert read_export(data).app == ListModel.app
    row = rows(ann)[0]
    assert (row["kind"], row["who"], row["format"], row["parts"]) == ("export", ANN, "claudia-unencrypted", ["content"])


def test_an_owner_can_include_history_and_chat_and_they_are_in_the_file_and_the_record(world):
    _, ann, _, _ = world
    result, data = exported(ann, include_history=True)
    assert result["parts"] == ["content", "history", "chat"]
    read = read_export(data)
    assert read.history is not None and read.chat is not None
    assert any(b"a-private-remark" in line for line in read.chat)
    assert rows(ann)[0]["parts"] == ["content", "history", "chat"]


def test_an_editor_may_export_the_content_but_not_the_history(world):
    client, _, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    assert exported(ben)[0]["parts"] == ["content"]
    refused = ben.request("export_claudia", {"include_history": True})
    assert not refused["ok"] and refused["error"]["code"] == "forbidden"
    assert [row["who"] for row in rows(ben)] == [BEN]


def test_a_viewer_may_export_the_content_and_it_is_recorded_under_her_name(world):
    client, _, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    assert exported(vera)[0]["parts"] == ["content"]
    refused = vera.request("export_claudia", {"include_history": True})
    assert not refused["ok"] and refused["error"]["code"] == "forbidden"


def test_a_viewer_cannot_read_the_record(world):
    client, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    exported(vera)
    answer = vera.request("audit_log")
    assert not answer["ok"] and answer["error"]["code"] == "forbidden"
    assert len(rows(ann)) == 1


def test_an_office_export_is_recorded_too(world):
    _, ann, _, _ = world
    ann.request("export_content")
    assert [(r["kind"], r["format"]) for r in rows(ann)] == [("export", "claudia-export 1")]


def test_a_print_and_a_pdf_are_recorded_with_the_name_of_the_connection(world):
    client, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    assert vera.request("report_output", {"kind": "print", "format": "print", "pages": 4})["ok"]
    assert vera.request("report_output", {"kind": "pdf", "format": "pdf", "pages": 4})["ok"]
    got = rows(ann)
    assert [(r["kind"], r["who"], r["pages"]) for r in got] == [("print", VERA, 4), ("pdf", VERA, 4)]


def test_who_cannot_be_chosen_by_the_client(world):
    client, ann, peers, _ = world
    vera = join(client, peers, VERA, VERA_PW)
    answer = vera.request("report_output", {"kind": "pdf", "format": "pdf", "pages": 1, "who": ANN})
    assert not answer["ok"] and answer["error"]["code"] == "bad_request"
    assert rows(ann) == []


@pytest.mark.parametrize(
    "params",
    [
        {"kind": "copy", "format": "pdf", "pages": 1},
        {"kind": "pdf", "format": "", "pages": 1},
        {"kind": "pdf", "format": "pdf", "pages": -1},
        {"kind": "pdf", "format": "x" * 41, "pages": 1},
    ],
)
def test_a_report_that_is_not_one_is_refused_and_not_recorded(world, params):
    _, ann, _, _ = world
    answer = ann.request("report_output", params)
    assert not answer["ok"] and answer["error"]["code"] == "bad_request"
    assert rows(ann) == []


def test_reports_are_limited_per_person_so_a_script_cannot_fill_the_file(world):
    _, ann, _, _ = world
    results = [ann.request("report_output", {"kind": "pdf", "format": "pdf", "pages": 1}) for _ in range(25)]
    assert [r["ok"] for r in results].count(True) == 20
    assert results[-1]["error"]["code"] == "too_many"
    assert len(rows(ann)) == 20


def test_the_record_is_in_the_file_sealed_under_the_history_key(world):
    _, ann, _, tmp_path = world
    exported(ann)
    ann.close()
    path = tmp_path / "docs" / "plan.claudia"
    data = path.read_bytes()
    assert ANN.encode() + b"claudia-unencrypted" not in data
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert [n for n in z.namelist() if n.startswith("audit/")]
    unlocked = unlock(path, ANN, ANN_PW)
    assert read_audit(path, unlocked.keys)[0].who == ANN


def test_the_record_survives_a_packing_and_a_reopen(world):
    client, ann, peers, tmp_path = world
    exported(ann)
    ann.request("chat", {"text": "more"})
    peers.remove(ann)
    ann.close()
    ann2 = join(client, peers, ANN, ANN_PW)
    assert len(rows(ann2)) == 1


def heard(peer):
    peer.request("ping")  # frames pushed meanwhile arrive in front of the answer
    ephemeral = [f["data"] for f in peer.pushed if f.get("event") == "ephemeral"]
    return [d for d in ephemeral if d.get("kind") == "audit_recorded"]


def test_the_other_windows_of_owners_and_editors_hear_of_it_but_a_viewer_does_not(world):
    client, ann, peers, _ = world
    ben = join(client, peers, BEN, BEN_PW)
    vera = join(client, peers, VERA, VERA_PW)
    exported(ann)
    assert len(heard(ben)) == 1
    assert heard(vera) == []


def test_the_export_zip_has_no_people_and_no_keys(world):
    _, ann, _, _ = world
    _, data = exported(ann, include_history=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        text = b"".join(z.read(n) for n in names)
    assert not {"slots.json", "people.bin", "manifest.json"} & set(names)
    assert b"Correct-Horse" not in text and b"scrypt" not in text and b"argon" not in text
    assert json.loads(zipfile.ZipFile(io.BytesIO(data)).read("export.json"))["exporter"] == ANN
