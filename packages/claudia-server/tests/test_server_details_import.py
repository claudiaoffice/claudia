"""A description and tags for a document that comes from a file: what the file already says, and what the person adds
(D438, D440; the manifest keeps them plain, D103)."""

import io
import zipfile

import pytest
from starlette.testclient import TestClient
from test_server_formats import made
from test_server_import import app_hub, hello, request, upload

from claudia_computes import WorkbookModel
from claudia_container import KdfParams
from claudia_server import create_app
from claudia_server.formats import file_details
from claudia_server.sealed import SealedDocuments
from claudia_server.suite import Module, Suite

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
CORE = (
    '<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/'
    'core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">{body}</cp:coreProperties>'
)
META = (
    '<?xml version="1.0"?><office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" xmlns:dc="http://purl.org/dc/elements/1.1/">'
    "<office:meta>{body}</office:meta></office:document-meta>"
)


def with_part(data: bytes, name: str, text: str) -> bytes:
    """``data`` with the part ``name`` replaced (or added) by ``text``."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            if info.filename != name:
                target.writestr(info, source.read(info))
        target.writestr(name, text)
    return buffer.getvalue()


def office(fmt: str, body: str) -> bytes:
    if fmt in ("xlsx", "docx", "pptx"):
        return with_part(made(fmt), "docProps/core.xml", CORE.format(body=body))
    return with_part(made(fmt), "meta.xml", META.format(body=body))


# ----------------------------------------------------------------------------------- what a file says about itself
@pytest.mark.parametrize("fmt", ["xlsx", "docx", "pptx"])
def test_an_ooxml_file_offers_its_description_and_keywords(fmt):
    data = office(fmt, "<dc:description>Q3 forecast</dc:description><cp:keywords>Finance, q3; draft</cp:keywords>")
    assert file_details(fmt, data) == ("Q3 forecast", ("finance", "q3", "draft"))


@pytest.mark.parametrize("fmt", ["ods", "odt", "odp"])
def test_an_opendocument_file_offers_its_description_and_keywords(fmt):
    data = office(
        fmt,
        "<dc:description>Q3 forecast</dc:description>"
        "<meta:keyword>Finance</meta:keyword><meta:keyword>q3</meta:keyword>",
    )
    assert file_details(fmt, data) == ("Q3 forecast", ("finance", "q3"))


def test_the_subject_stands_in_for_a_description_the_file_does_not_have():
    data = office("xlsx", "<dc:subject>Budget 2026</dc:subject>")
    assert file_details("xlsx", data) == ("Budget 2026", ())


@pytest.mark.parametrize("fmt", ["xlsx", "docx", "pptx", "ods", "odt", "odp"])
def test_a_file_that_says_nothing_offers_nothing(fmt):
    assert file_details(fmt, made(fmt)) == ("", ())


def test_what_does_not_fit_is_cut_down_and_never_refuses_the_file():
    words = ",".join(f"tag{i}" for i in range(40)) + ",this tag is much longer than thirty characters, fine"
    data = office("docx", f"<dc:description>{'x' * 5000}</dc:description><cp:keywords>{words}</cp:keywords>")
    description, tags = file_details("docx", data)
    assert len(description) <= 2000 and len(tags) <= 10 and all(len(tag) <= 30 for tag in tags)


def test_a_hostile_properties_part_is_read_as_nothing():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]>'
        + CORE.format(body="<dc:description>&a;</dc:description>").split("?>", 1)[1]
    )
    assert file_details("xlsx", with_part(made("xlsx"), "docProps/core.xml", bomb)) == ("", ())
    huge = CORE.format(body="<dc:description>" + "y" * 400_000 + "</dc:description>")
    assert file_details("xlsx", with_part(made("xlsx"), "docProps/core.xml", huge)) == ("", ())
    assert file_details("xlsx", with_part(made("xlsx"), "docProps/core.xml", "<<not xml")) == ("", ())


# --------------------------------------------------------------------------------------------- upload and import
def sealed_client(folder):
    store = SealedDocuments(folder, WorkbookModel, kdf=CHEAP)
    return TestClient(create_app(Suite([Module(app_hub(store, WorkbookModel), store)])))


def test_the_upload_answer_carries_what_the_file_says_for_the_person_to_keep_or_change(tmp_path):
    with sealed_client(tmp_path) as client:
        answer = upload(
            client, office("xlsx", "<dc:description>Q3</dc:description><cp:keywords>a, b</cp:keywords>")
        ).json()
        assert answer["description"] == "Q3" and answer["tags"] == ["a", "b"]
        plain = upload(client, made("xlsx")).json()
        assert plain["description"] == "" and plain["tags"] == []


def test_a_claudia_file_tells_its_own_details(tmp_path):
    with sealed_client(tmp_path / "home") as client, client.websocket_connect("/api/computes/docs/plan/ws") as ws:
        ws.send_json(hello(create=True))
        assert ws.receive_json()["ok"]
        assert request(ws, "set_details", {"password": "Correct-Horse-9", "description": "Plan", "tags": ["x"]})["ok"]
    data = (tmp_path / "home" / "docs" / "plan.claudia").read_bytes()
    with sealed_client(tmp_path / "away") as client:
        answer = upload(client, data, name="plan.claudia").json()
        assert answer["description"] == "Plan" and answer["tags"] == ["x"]


def test_an_import_takes_the_description_and_tags_the_person_chose(tmp_path):
    with sealed_client(tmp_path) as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token, description="The *2026* budget", tags=["Finance", "2026"]))
            answer = ws.receive_json()
            assert answer["ok"] and answer["result"]["imported"]["described"] is True
        (entry,) = client.get("/api/computes/docs").json()["documents"]
        assert entry["description"] == "The *2026* budget" and entry["tags"] == ["finance", "2026"]


def test_details_that_do_not_fit_stop_the_import_before_anything_is_made(tmp_path):
    with sealed_client(tmp_path) as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token, tags=["a,b"]))
            answer = ws.receive_json()
            assert not answer["ok"] and answer["error"]["code"] == "bad_request"
        assert client.get("/api/computes/docs").json()["documents"] == []
        assert client.post(f"/api/uploads/{token}/place").status_code in {404, 409, 422, 400}, "still held or gone"


@pytest.mark.parametrize("bad", [{"description": 5}, {"tags": "finance"}, {"tags": [1]}])
def test_details_of_the_wrong_kind_are_refused(tmp_path, bad):
    with sealed_client(tmp_path) as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token, **bad))
            answer = ws.receive_json()
            assert not answer["ok"] and answer["error"]["code"] == "bad_request"
