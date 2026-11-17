"""What kind of file a person brought, and what an import makes of it (D438, D440)."""

import io
import zipfile

import pytest

from claudia_server.formats import CLAUDIA, FORMATS, UnknownFormat, import_state, sniff


def made(fmt: str) -> bytes:
    """A small file of ``fmt``, written by Claudia's own writers."""
    if fmt in ("xlsx", "ods"):
        from claudia_computes_io import workbook_to_ods, workbook_to_xlsx

        from claudia_computes import AddSheet, SetCells, WorkbookModel, parse_input
        from claudia_core import Document, MemoryStore

        doc = Document(WorkbookModel(), store=MemoryStore())
        doc.execute(AddSheet("s1", "Sheet1"), author="ann")
        doc.execute(SetCells("s1", ((0, 0, parse_input("41")), (1, 0, parse_input("=A1+1")))), author="ann")
        return workbook_to_xlsx(doc.model) if fmt == "xlsx" else workbook_to_ods(doc.model)
    if fmt in ("docx", "odt"):
        from claudia_composes_io import text_to_docx, text_to_odt

        from claudia_composes import TextModel

        model = TextModel.restore({**TextModel.empty().serialize()})
        return text_to_docx(model) if fmt == "docx" else text_to_odt(model)
    from claudia_creates_io import slides_to_odp, slides_to_pptx

    from claudia_creates import SlideModel

    return slides_to_pptx(SlideModel.empty()) if fmt == "pptx" else slides_to_odp(SlideModel.empty())


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_every_format_is_recognised_by_its_bytes_and_imports_into_its_app(fmt):
    data = made(fmt)
    found = sniff(data)
    assert (found.fmt, found.app) == (fmt, FORMATS[fmt][0])
    state, losses = import_state(fmt, data)
    assert isinstance(state, dict) and isinstance(losses, list)


def test_a_claudia_document_is_recognised_by_its_first_entry(tmp_path):
    from claudia_container import KdfParams, create_document

    path = tmp_path / "plan.claudia"
    create_document(
        path,
        name="plan",
        app="computes",
        owner="ann",
        password="Correct-Horse-9",
        kdf=KdfParams(iterations=1, memory_kib=64, lanes=1),
    )
    assert sniff(path.read_bytes()).fmt == CLAUDIA


@pytest.mark.parametrize(
    "data",
    [b"", b"%PDF-1.7 not a zip", b"PK\x03\x04 broken zip", None],
)
def test_anything_else_is_refused(data):
    if data is None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("readme.txt", "a zip, but not a document")
        data = buffer.getvalue()
    with pytest.raises(UnknownFormat):
        sniff(data)


def test_the_name_does_not_decide():
    """A workbook called report.docx is still a workbook: the bytes decide."""
    assert sniff(made("xlsx")).fmt == "xlsx"


@pytest.mark.parametrize("fmt", ["docx", "xlsx", "pptx", "odt", "ods", "odp"])
def test_a_zip_bomb_is_refused_before_any_reader_opens_it(fmt, monkeypatch):
    """SEC-15: a few kilobytes that unpack to hundreds of MiB would be read whole by the office library, in a worker
    with no memory cap. The sizes in the archive's directory are enough to refuse it, whatever the format says it is."""
    from claudia_opc_io import PackageRefused
    from claudia_server import formats

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        archive.writestr("word/document.xml", bytes(300 * 1024 * 1024))  # 300 MiB of zeros: about 300 KiB packed
    assert len(bomb.getvalue()) < 1024 * 1024

    def opened(*_):
        raise AssertionError("a reader opened the bomb")

    monkeypatch.setattr(formats, "_reader", lambda _fmt: (opened, None))
    with pytest.raises(PackageRefused, match="document.xml"):
        import_state(fmt, bomb.getvalue())
