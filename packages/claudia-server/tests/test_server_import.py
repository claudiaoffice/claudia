"""Opening a file from the person's computer (D438-D442): upload it, make a document of it, download it again."""

import base64
import io
import zipfile

import pytest
from starlette.testclient import TestClient
from test_server_formats import made

from claudia_computes import (
    CellRef,
    DefineName,
    NamedRange,
    RangeRef,
    ResizeLines,
    SetCells,
    WorkbookModel,
    parse_input,
)
from claudia_server import Hub, MemoryProvider, create_app, methods_for
from claudia_server.sealed import SealedDocuments
from claudia_server.suite import Module, Suite

PASSWORD = "Correct-Horse-9"
EXTRA = "customXml/claudia-test.xml"  # a part Claudia does not know: it must survive the round trip


def with_extra_part(data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        target.writestr(EXTRA, "<kept/>")
    return buffer.getvalue()


def workbook_server(**options):
    suite = Suite([Module(app_hub(MemoryProvider(WorkbookModel), WorkbookModel), _directory())])
    return TestClient(create_app(suite, **options))


def app_hub(provider, model=None):
    """A hub with the methods of its app, as the command line makes it."""
    model = model or provider.model_cls
    return Hub(provider, methods=methods_for(model))


def _directory():
    from claudia_server import ScryptDirectory

    return ScryptDirectory(cost=2**4)


def upload(client, data, name="Budget 2026.xlsx", **headers):
    return client.post("/api/uploads", content=data, headers={"x-claudia-name": name, **headers})


def hello(user="ann", password=PASSWORD, **extra):
    return {"id": 1, "method": "hello", "params": {"user": user, "password": password, **extra}}


def request(ws, method, params, request_id=2):
    ws.send_json({"id": request_id, "method": method, "params": params})
    while True:
        frame = ws.receive_json()
        if frame.get("id") == request_id:
            return frame


def hosted(client, app, doc_id):
    return client.app.state.suite.module(app).hub._documents[doc_id]


# ------------------------------------------------------------------------------------------------ the upload
def test_an_upload_says_what_the_file_is_and_changes_nothing():
    with workbook_server() as client:
        answer = upload(client, made("xlsx")).json()
        assert answer["format"] == "xlsx" and answer["app"] == "computes" and answer["hosted"]
        assert answer["suggested_id"] == "Budget-2026" and answer["kind"] == "Excel workbook"
        assert answer["name"] == "Budget 2026.xlsx" and len(answer["upload"]) > 20
        assert client.get("/api/docs").json()["documents"] == []


@pytest.mark.parametrize(("data", "status"), [(b"%PDF-1.7", 415), (b"PK\x03\x04garbage", 415), (b"x" * 2048, 413)])
def test_files_that_cannot_be_opened_or_are_too_large_are_refused(data, status):
    with workbook_server() as client:
        client.app.state.gateway.uploads.max_bytes = 1024
        assert upload(client, data).status_code == status


def test_with_an_access_secret_only_those_who_know_it_may_upload():
    secret = "s" * 20
    with workbook_server(access_secret=secret) as client:
        assert upload(client, made("xlsx")).status_code == 401
        ok = upload(client, made("xlsx"), authorization=f"Bearer {secret}")
        assert ok.status_code == 200


def test_only_so_many_uploads_wait_from_one_address():
    with workbook_server() as client:
        statuses = [upload(client, made("xlsx")).status_code for _ in range(6)]
    assert statuses[:4] == [200] * 4 and statuses[4:] == [503, 503]


# ------------------------------------------------------------------------------------------- import and round trip
def test_an_imported_workbook_keeps_its_file_and_gives_it_back_with_only_the_edits():
    original = with_extra_part(made("xlsx"))
    with workbook_server() as client:
        token = upload(client, original).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            welcome = ws.receive_json()
            assert welcome["ok"], welcome
            imported = welcome["result"]["imported"]
            assert imported["format"] == "xlsx" and imported["kept"] and imported["name"] == "Budget 2026.xlsx"
            doc = hosted(client, "computes", "budget").document
            assert [e.command.kind for e in doc.log.path(doc.revision)] == ["core.Import"]
            doc.execute(SetCells("s1", ((0, 0, parse_input("99")),)), author="ann")
            answer = request(ws, "export_office", {"format": "xlsx"})["result"]
        assert answer["patched"] is True
        back = base64.b64decode(answer["data"])
        with zipfile.ZipFile(io.BytesIO(back)) as archive:
            assert archive.read(EXTRA) == b"<kept/>", "what Claudia does not know is still there"
        from claudia_computes_io import xlsx_to_workbook

        book = xlsx_to_workbook(back)
        assert book.serialize()["sheets"][0]["cells"][0][2] is not None
        assert upload(client, original).status_code == 200  # the token was used up; a new upload is fine


def test_a_patched_download_says_what_the_edits_it_could_not_write_were():
    with workbook_server() as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "computes", "budget").document
            doc.execute(SetCells("s1", ((0, 0, parse_input("7")),)), author="ann")
            assert request(ws, "export_office", {"format": "xlsx"})["result"]["losses"] == []
            rate = NamedRange("Rate", None, RangeRef(CellRef(0, 0, "s1"), CellRef(0, 0, "s1")), purpose="input")
            doc.execute(DefineName(rate), author="ann")
            answer = request(ws, "export_office", {"format": "xlsx"})["result"]
        assert answer["patched"] is True
        assert answer["losses"] == [{"kind": "name", "detail": "purpose", "count": 1}]


@pytest.mark.parametrize("fmt", ["xlsx", "ods"])
def test_a_resized_column_is_in_the_patched_download_and_no_loss(fmt):
    with workbook_server() as client:
        token = upload(client, made(fmt), name=f"Budget 2026.{fmt}").json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "computes", "budget").document
            doc.execute(ResizeLines("s1", "col", ((0, 120.0),)), author="ann")
            doc.execute(ResizeLines("s1", "row", ((2, 40.0),)), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
        assert answer["patched"] is True and answer["losses"] == []
        from claudia_computes_io import ods_to_workbook, xlsx_to_workbook

        back = (xlsx_to_workbook if fmt == "xlsx" else ods_to_workbook)(base64.b64decode(answer["data"]))
        sheet = back.sheets["s1"]
        assert (sheet.col_widths.get(0), sheet.row_heights.get(2)) == (120, 40)


@pytest.mark.parametrize("fmt", ["xlsx", "ods"])
def test_a_name_defined_in_the_workbook_is_in_the_patched_download_and_no_loss(fmt):
    sales = NamedRange("Sales", None, RangeRef(CellRef(0, 0, "s1"), CellRef(0, 1, "s1")))
    with workbook_server() as client:
        token = upload(client, made(fmt), name=f"Budget 2026.{fmt}").json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "computes", "budget").document
            doc.execute(DefineName(sales), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
        assert answer["patched"] is True and answer["losses"] == []
        from claudia_computes_io import ods_to_workbook, xlsx_to_workbook

        back = (xlsx_to_workbook if fmt == "xlsx" else ods_to_workbook)(base64.b64decode(answer["data"]))
        assert [named.name for named in back.names] == ["Sales"]


def test_a_patched_ods_download_carries_what_the_patch_itself_lost(monkeypatch):
    def patch(original, baseline, current, *, losses, info):
        losses.add("stale-reference", "Sheet1")
        return original

    monkeypatch.setattr("claudia_server.computes.apply_edits_to_ods", patch)
    with workbook_server() as client:
        token = upload(client, made("ods")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            answer = request(ws, "export_office", {"format": "ods"})["result"]
        assert answer["patched"] is True
        assert answer["losses"] == [{"kind": "stale-reference", "detail": "Sheet1", "count": 1}]


def test_the_file_is_not_kept_when_the_person_says_so_and_the_download_is_written_anew():
    with workbook_server() as client:
        token = upload(client, with_extra_part(made("xlsx"))).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token, keep_original=False))
            assert ws.receive_json()["result"]["imported"]["kept"] is False
            answer = request(ws, "export_office", {"format": "xlsx"})["result"]
        assert "patched" not in answer
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(answer["data"]))) as archive:
            assert EXTRA not in archive.namelist()


def test_another_format_is_written_anew():
    with workbook_server() as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            ws.receive_json()
            answer = request(ws, "export_office", {"format": "ods"})["result"]
        assert "patched" not in answer and answer["format"] == "ods"


@pytest.mark.parametrize(
    ("address", "extra", "words"),
    [
        ("/api/computes/docs/budget/ws", {"upload": "no-such-token", "create": True}, "no longer here"),
        ("/api/computes/docs/budget/ws", {"upload": "TOKEN"}, "needs create"),
    ],
)
def test_a_wrong_token_or_a_missing_create_is_refused(address, extra, words):
    with workbook_server() as client:
        token = upload(client, made("xlsx")).json()["upload"]
        extra = {k: (token if v == "TOKEN" else v) for k, v in extra.items()}
        with client.websocket_connect(address) as ws:
            ws.send_json(hello(**extra))
            answer = ws.receive_json()
    assert not answer["ok"] and words in answer["error"]["message"]


def test_a_file_cannot_become_a_document_of_another_app_or_replace_one():
    suite = Suite(
        [Module(app_hub(MemoryProvider(WorkbookModel), WorkbookModel), _directory())]
        + [Module(app_hub(MemoryProvider(_text_model()), _text_model()), _directory())]
    )
    with TestClient(create_app(suite)) as client:
        token = upload(client, made("xlsx")).json()["upload"]
        with client.websocket_connect("/api/composes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert "cannot become a document of composes" in ws.receive_json()["error"]["message"]
        with client.websocket_connect("/api/computes/docs/taken/ws") as ws:
            ws.send_json(hello(create=True))
            assert ws.receive_json()["ok"]
        with client.websocket_connect("/api/docs/taken/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert "here already" in ws.receive_json()["error"]["message"]


def _text_model():
    from claudia_composes import TextModel

    return TextModel


@pytest.mark.parametrize("fmt", ["docx", "odt", "ods", "pptx", "odp"])
def test_every_format_becomes_a_document_of_its_app_and_comes_back_patched(fmt):
    from claudia_composes import TextModel
    from claudia_creates import SlideModel
    from claudia_server.formats import FORMATS

    app = FORMATS[fmt][0]
    model = {"computes": WorkbookModel, "composes": TextModel, "creates": SlideModel}[app]
    suite = Suite([Module(app_hub(MemoryProvider(model), model), _directory())])
    with TestClient(create_app(suite)) as client:
        token = upload(client, made(fmt), name=f"file.{fmt}").json()["upload"]
        with client.websocket_connect(f"/api/{app}/docs/file/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["result"]["imported"]["format"] == fmt
            answer = request(ws, "export_office", {"format": fmt})["result"]
    assert answer.get("patched") is True, answer.get("losses")


def test_a_docx_comes_back_patched_with_the_paragraphs_split_and_joined_and_its_table_kept():
    import docx

    from claudia_composes import JoinBlocks, SplitBlock, TextModel

    document = docx.Document()
    document.add_paragraph("Hello world")
    document.add_paragraph("Second")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "kept cell"
    document.add_paragraph("Third")
    out = io.BytesIO()
    document.save(out)
    suite = Suite([Module(app_hub(MemoryProvider(TextModel), TextModel), _directory())])
    with TestClient(create_app(suite)) as client:
        token = upload(client, out.getvalue(), name="file.docx").json()["upload"]
        with client.websocket_connect("/api/composes/docs/file/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "composes", "file").document
            doc.execute(SplitBlock("b1", 5, "n1", "body"), author="ann")
            doc.execute(JoinBlocks("b3", "b2", 6), author="ann")
            answer = request(ws, "export_office", {"format": "docx"})["result"]
    assert answer["patched"] is True and not any(loss["kind"] == "not-patched" for loss in answer["losses"])
    back = docx.Document(io.BytesIO(base64.b64decode(answer["data"])))
    assert [p.text for p in back.paragraphs] == ["Hello", " world", "SecondThird"]
    assert back.tables[0].cell(0, 0).text == "kept cell"


def made_by_ann(asset):
    from claudia_core import ImageImport

    return ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": "",
            "imported_by": "ann",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": None,
        }
    )


@pytest.mark.parametrize("fmt", ["docx", "odt"])
def test_a_picture_of_a_file_is_an_object_of_the_text_and_its_new_description_is_patched_into_the_file(fmt):
    import struct

    from claudia_composes_io import docx_to_text, odt_to_text, text_to_docx, text_to_odt

    from claudia_composes import DEFAULT_STYLE, Block, BlockAnchor, TextModel
    from claudia_core import DescribeObject, ImageAsset, ObjectBody, VisualObject, decode_image

    header = b"GIF89a" + struct.pack("<HHBBB", 40, 20, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, 40, 20) + b"\x00" + b"\x02\x01\x00\x00"
    asset: ImageAsset = decode_image(header + frame + b"\x3b")
    start = TextModel([Block("b1", DEFAULT_STYLE, "Hello world")])
    start.define_image(asset)
    start.insert_object(
        VisualObject(
            ObjectBody("o1", "image", 200, 100, "plain-image", ref=asset.id, imported=made_by_ann(asset)),
            BlockAnchor("b1", 5),
        )
    )
    written, read = (text_to_docx, docx_to_text) if fmt == "docx" else (text_to_odt, odt_to_text)
    suite = Suite([Module(app_hub(MemoryProvider(TextModel), TextModel), _directory())])
    with TestClient(create_app(suite)) as client:
        token = upload(client, written(start), name=f"file.{fmt}").json()["upload"]
        with client.websocket_connect("/api/composes/docs/file/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "composes", "file").document
            assert doc.model.get_object("o1").anchor == BlockAnchor("b1", 5)
            doc.execute(DescribeObject("o1", "a small picture"), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
    assert answer["patched"] is True and not any(loss["kind"] == "not-patched" for loss in answer["losses"])
    back = read(base64.b64decode(answer["data"]))
    found = back.get_object("o1")
    assert (found.body.description, found.anchor) == ("a small picture", BlockAnchor("b1", 5))
    assert back.images[found.body.image].data == asset.data


@pytest.mark.parametrize("fmt", ["docx", "odt"])
def test_a_text_box_of_a_file_is_an_object_of_the_text_and_its_new_words_are_patched_into_the_file(fmt):
    from claudia_composes_io import docx_to_text, odt_to_text, text_to_docx, text_to_odt

    from claudia_composes import DEFAULT_STYLE, Block, BlockAnchor, TextModel
    from claudia_core import ObjectBody, SetText, VisualObject, paragraph_for

    start = TextModel([Block("b1", DEFAULT_STYLE, "Hello world")])
    body = ObjectBody("o1", "text", 300, 100, "plain-box", paragraph_for("o1", "body", "Some words"))
    start.insert_object(VisualObject(body, BlockAnchor("b1", 5)))
    written, read = (text_to_docx, docx_to_text) if fmt == "docx" else (text_to_odt, odt_to_text)
    suite = Suite([Module(app_hub(MemoryProvider(TextModel), TextModel), _directory())])
    with TestClient(create_app(suite)) as client:
        token = upload(client, written(start), name=f"file.{fmt}").json()["upload"]
        with client.websocket_connect("/api/composes/docs/file/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "composes", "file").document
            (found,) = doc.model.objects.values()
            assert (found.body.kind, found.anchor) == ("text", BlockAnchor("b1", 5))
            doc.execute(SetText(found.id, "Other words"), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
    assert answer["patched"] is True and not any(loss["kind"] == "not-patched" for loss in answer["losses"])
    (back,) = read(base64.b64decode(answer["data"])).objects.values()
    assert (back.body.paragraph.text, back.anchor) == ("Other words", BlockAnchor("b1", 5))


# --------------------------------------------------------------------------------- sealed: kept across a restart
def test_the_kept_file_survives_packing_and_a_restart(tmp_path):
    def server():
        store = SealedDocuments(tmp_path, WorkbookModel)
        return TestClient(create_app(Suite([Module(app_hub(store), store)])))

    original = with_extra_part(made("xlsx"))
    with server() as client:
        token = upload(client, original).json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["result"]["imported"]["kept"]
    assert b"<kept/>" not in (tmp_path / "docs" / "budget.claudia").read_bytes(), "sealed in the file"
    with server() as client, client.websocket_connect("/api/computes/docs/budget/ws") as ws:
        ws.send_json(hello())
        assert ws.receive_json()["ok"]
        answer = request(ws, "export_office", {"format": "xlsx"})["result"]
    assert answer["patched"] is True


# -------------------------------------------------------------------------------------------- a Claudia file
def test_a_claudia_file_goes_in_as_it_is_and_opens_with_its_own_people(tmp_path):
    home, away = tmp_path / "home", tmp_path / "away"

    def server(folder):
        store = SealedDocuments(folder, WorkbookModel)
        return TestClient(create_app(Suite([Module(app_hub(store), store)])))

    with server(home) as client, client.websocket_connect("/api/computes/docs/plan/ws") as ws:
        ws.send_json(hello(create=True))
        assert ws.receive_json()["ok"]
    data = (home / "docs" / "plan.claudia").read_bytes()
    with server(away) as client:
        answer = upload(client, data, name="plan.claudia").json()
        assert (answer["format"], answer["app"], answer["id"], answer["exists"]) == (
            "claudia",
            "computes",
            "plan",
            False,
        )
        placed = client.post(f"/api/uploads/{answer['upload']}/place")
        assert placed.json() == {"app": "computes", "id": "plan"}
        with client.websocket_connect("/api/computes/docs/plan/ws") as ws:
            ws.send_json(hello())
            assert ws.receive_json()["ok"]
        again = upload(client, data, name="plan.claudia").json()
        assert again["exists"] is True
        assert client.post(f"/api/uploads/{again['upload']}/place").status_code == 409
        assert client.post("/api/uploads/no-such-token/place").status_code == 404


def test_a_server_that_keeps_documents_in_memory_cannot_take_a_file_in(tmp_path):
    store = SealedDocuments(tmp_path, WorkbookModel)
    with (
        TestClient(create_app(Suite([Module(app_hub(store), store)]))) as client,
        client.websocket_connect("/api/computes/docs/plan/ws") as ws,
    ):
        ws.send_json(hello(create=True))
        ws.receive_json()
    data = (tmp_path / "docs" / "plan.claudia").read_bytes()
    with workbook_server() as client:
        token = upload(client, data, name="plan.claudia").json()["upload"]
        assert client.post(f"/api/uploads/{token}/place").status_code == 422


@pytest.mark.parametrize("fmt", ["pptx", "odp"])
def test_a_deck_with_a_picture_comes_back_patched_with_the_picture_turned_and_described_and_no_loss(fmt):
    import struct

    from claudia_creates_io import odp_to_slides, pptx_to_slides, slides_to_odp, slides_to_pptx

    from claudia_core import (
        DescribeObject,
        ImageImport,
        MoveObject,
        ObjectBody,
        RotateObject,
        SetLanguage,
        VisualObject,
        decode_image,
    )
    from claudia_creates import SlideAnchor, SlideModel
    from claudia_server.formats import FORMATS

    header = b"GIF89a" + struct.pack("<HHBBB", 40, 20, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, 40, 20) + b"\x00" + b"\x02\x01\x00\x00"
    asset = decode_image(header + frame + b"\x3b")
    deck = SlideModel.empty()
    deck.define_image(asset)
    record = ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": "a picture",
            "imported_by": "ana",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": None,
        }
    )
    body = ObjectBody("o1", "image", 400, 200, "plain-image", ref=asset.id, imported=record, description="before")
    deck.insert_object(VisualObject(body, SlideAnchor("s1", 100, 150)))
    data = slides_to_pptx(deck) if fmt == "pptx" else slides_to_odp(deck)
    app = FORMATS[fmt][0]
    suite = Suite([Module(app_hub(MemoryProvider(SlideModel), SlideModel), _directory())])
    with TestClient(create_app(suite)) as client:
        token = upload(client, data, name=f"deck.{fmt}").json()["upload"]
        with client.websocket_connect(f"/api/{app}/docs/deck/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, app, "deck").document
            # turned by 15 degrees the picture's outline still lies on the slide here (D1022)
            doc.execute(MoveObject("o1", SlideAnchor("s1", 60, 80).to_data()), author="ann")
            doc.execute(RotateObject("o1", 15), author="ann")
            doc.execute(DescribeObject("o1", "after"), author="ann")
            if fmt == "odp":
                doc.execute(SetLanguage("de"), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
    assert answer["patched"] is True and answer["losses"] == []
    back = (pptx_to_slides if fmt == "pptx" else odp_to_slides)(base64.b64decode(answer["data"]))
    found = next(iter(back.objects.values()))
    assert (found.anchor.x, found.anchor.y, found.body.rotation, found.body.description) == (60, 80, 15, "after")
    assert back.images[found.body.image].data == asset.data


@pytest.mark.parametrize("fmt", ["ods", "xlsx"])
def test_a_workbook_with_charts_comes_back_patched_with_a_chart_moved_and_described_and_no_loss(fmt):
    from pathlib import Path

    from claudia_computes_io import ods_to_workbook, xlsx_to_workbook

    from claudia_computes import CellAnchor
    from claudia_core import DescribeObject, MoveObject

    library = Path(__file__).resolve().parents[3] / "test-documents" / fmt / "charts" / f"source.{fmt}"
    original = library.read_bytes()
    with workbook_server() as client:
        token = upload(client, original, name=f"Sales.{fmt}").json()["upload"]
        with client.websocket_connect("/api/computes/docs/budget/ws") as ws:
            ws.send_json(hello(create=True, upload=token))
            assert ws.receive_json()["ok"]
            doc = hosted(client, "computes", "budget").document
            doc.execute(MoveObject("o1", CellAnchor("s1", 14, 2).to_data()), author="ann")
            doc.execute(DescribeObject("o1", "Sales per region"), author="ann")
            answer = request(ws, "export_office", {"format": fmt})["result"]
    assert answer["patched"] is True and answer["losses"] == []
    back = (ods_to_workbook if fmt == "ods" else xlsx_to_workbook)(base64.b64decode(answer["data"]))
    found = back.objects["o1"]
    assert (found.anchor, found.body.description) == (CellAnchor("s1", 14, 2), "Sales per region")
    assert set(back.diagrams) == {"c1", "c2"}
