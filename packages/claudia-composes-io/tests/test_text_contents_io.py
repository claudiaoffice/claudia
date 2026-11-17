"""A table of contents in docx and odt (E9.31, step E): written with its entries and without page numbers, read back
as a generated paragraph whose entries are derived again."""

import io
import zipfile

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_to_text,
    odt_export_losses,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)
from docx import Document

from claudia_composes import Block, TextModel
from claudia_core import Toc


def contents() -> TextModel:
    return TextModel(
        [
            Block("b1", "contents-title", "Contents"),
            Block("b2", "body", generated=Toc(1, 2)),
            Block("b3", "heading-1", "Why"),
            Block("b4", "heading-2", "Asked"),
            Block("b5", "heading-3", "Deep"),
        ]
    )


def shape(model: TextModel) -> list[tuple]:
    return [(b.style, b.text, b.generated) for b in model.blocks]


def part(data: bytes, name: str) -> str:
    return zipfile.ZipFile(io.BytesIO(data)).read(name).decode()


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_a_table_of_contents_comes_back_as_one_generated_paragraph_in_its_place(write, read):
    back = read(write(contents()))
    assert shape(back) == shape(contents())
    (table,) = [b for b in back.blocks if b.generated]
    assert [e.text for e in back.structure.entries(table.id)] == ["Why", "Asked"]


def test_docx_writes_word_s_toc_field_with_the_entries_and_asks_word_to_update_the_pages():
    data = text_to_docx(contents())
    document = part(data, "word/document.xml")
    assert 'TOC \\o "1-2" \\h \\z \\u' in document and "Table of Contents" in document
    assert ">Why<" in document and ">Asked<" in document and ">Deep<" not in document.split("w:sdtContent")[1]
    assert "updateFields" in part(data, "word/settings.xml")
    assert [s.name for s in Document(io.BytesIO(data)).styles if s.name.startswith("toc ")][:2] == ["toc 1", "toc 2"]


def test_a_word_toc_field_without_a_content_control_is_read_too():
    word = Document()
    word.add_paragraph("Why", style="Heading 1")
    first = word.add_paragraph()
    first._p.append(_field("begin"))  # noqa: SLF001
    first._p.append(_instruction(' TOC \\o "2-3" '))  # noqa: SLF001
    first._p.append(_field("separate"))  # noqa: SLF001
    first.add_run("an old entry")
    word.add_paragraph("another old entry")._p.append(_field("end"))  # noqa: SLF001
    word.add_paragraph("after", style="Heading 2")
    out = io.BytesIO()
    word.save(out)
    back = docx_to_text(out.getvalue())
    assert [(b.text, b.generated) for b in back.blocks] == [("Why", None), ("", Toc(2, 3)), ("after", None)]


def _field(kind):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run, char = OxmlElement("w:r"), OxmlElement("w:fldChar")
    char.set(qn("w:fldCharType"), kind)
    run.append(char)
    return run


def _instruction(text):
    from docx.oxml import OxmlElement

    run, said = OxmlElement("w:r"), OxmlElement("w:instrText")
    said.text = text
    run.append(said)
    return run


def test_odt_writes_a_table_of_content_and_says_that_its_pages_are_missing():
    data = text_to_odt(contents())
    content = part(data, "content.xml")
    assert "text:table-of-content " in content and 'text:outline-level="2"' in content
    assert [loss.kind for loss in odt_export_losses(contents())] == ["toc-pages"]
    no_places = contents()
    no_places.blocks[1] = Block("b2", "body", generated=Toc(1, 2, places=False))
    assert odt_export_losses(no_places) == ()


@pytest.mark.parametrize(
    ("write", "read", "patch"),
    [(text_to_docx, docx_to_text, apply_edits_to_docx), (text_to_odt, odt_to_text, apply_edits_to_odt)],
)
def test_a_kept_file_with_a_table_of_contents_is_written_anew_not_patched(write, read, patch):
    original = write(contents())
    with pytest.raises(UnsupportedEdit, match="table of contents"):
        patch(original, read(original), read(original))


def test_word_is_asked_to_update_once_and_a_toc_field_without_levels_lists_1_to_3():
    from claudia_composes_io._docx_contents import ask_word_to_update, contents_in
    from docx.oxml.ns import qn

    word = Document()
    settings = word.settings.element
    for child in list(settings):
        settings.remove(child)
    ask_word_to_update(word)
    ask_word_to_update(word)
    assert [child.tag for child in settings] == [qn("w:updateFields")]
    paragraph = word.add_paragraph()
    paragraph._p.append(_instruction(" TOC \\h "))  # noqa: SLF001
    assert contents_in(paragraph._p) == Toc(1, 3)  # noqa: SLF001
    assert contents_in(word.add_paragraph("plain")._p) is None  # noqa: SLF001


def test_an_odt_table_of_content_without_a_readable_level_lists_levels_1_to_9():
    from claudia_composes_io._odt_contents import TABLE_OF_CONTENT, read_contents
    from lxml import etree

    table = etree.Element(TABLE_OF_CONTENT)
    assert read_contents(table) == Toc(1, 9)
    source = etree.SubElement(table, TABLE_OF_CONTENT.replace("table-of-content", "table-of-content-source"))
    source.set(TABLE_OF_CONTENT.replace("table-of-content", "outline-level"), "many")
    assert read_contents(table) == Toc(1, 9)
    source.set(TABLE_OF_CONTENT.replace("table-of-content", "outline-level"), "2")
    assert read_contents(table) == Toc(1, 2)
