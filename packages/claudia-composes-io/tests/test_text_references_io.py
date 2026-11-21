"""References in docx and odt (step H): written as Word's REF/PAGEREF fields and OpenDocument's bookmark references to
a bookmark at their target, with what they read as now; read back as references to the same paragraphs."""

import io
import zipfile
from dataclasses import replace

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_to_text,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)

from claudia_composes import Paragraph, TextModel
from claudia_core import FIELD_CHAR, CreateList, Document, ListDef, ListItem, MemoryStore, RefField, SetListItem


def referring() -> TextModel:
    paragraphs = [
        Paragraph("b1", "heading-1", "Why we did it"),
        Paragraph("b2", "body", "Collect"),
        Paragraph(
            "b3",
            "body",
            f"see {FIELD_CHAR} and {FIELD_CHAR} on {FIELD_CHAR}.",
            fields=(
                RefField("b2"),
                RefField("b1", "text"),
                RefField("b1", "page"),
            ),
        ),
    ]
    d = Document(TextModel(paragraphs), store=MemoryStore())
    d.execute(CreateList(ListDef("l1", "numbers")), author="ann")
    d.execute(SetListItem("b2", ListItem("l1", 0)), author="ann")
    return d.model


def part(data: bytes, name: str) -> str:
    return zipfile.ZipFile(io.BytesIO(data)).read(name).decode()


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_references_come_back_as_references_to_the_same_paragraphs(write, read):
    back = read(write(referring()))
    (third,) = [b for b in back.paragraphs if b.fields]
    assert third.text.count(FIELD_CHAR) == 3
    targets = {b.id: b.text for b in back.paragraphs}
    assert [(targets[f.target], f.show) for f in third.fields] == [
        ("Collect", "number"),
        ("Why we did it", "text"),
        ("Why we did it", "page"),
    ]


def test_docx_writes_word_s_fields_with_what_they_read_as_and_a_bookmark_at_the_target():
    document = part(text_to_docx(referring()), "word/document.xml")
    assert "REF _Ref_b2 \\r \\h" in document and "REF _Ref_b1 \\h" in document and "PAGEREF _Ref_b1 \\h" in document
    assert 'w:name="_Ref_b1"' in document and ">Why we did it<" in document
    assert FIELD_CHAR not in document


def test_odt_writes_bookmark_references_with_what_they_read_as():
    content = part(text_to_odt(referring()), "content.xml")
    assert 'text:reference-format="number"' in content and 'text:ref-name="ref-b2"' in content
    assert 'text:reference-format="page"' in content and '<text:bookmark text:name="ref-b1"/>' in content
    assert FIELD_CHAR not in content


def test_a_reference_whose_bookmark_starts_no_paragraph_comes_in_as_its_words():
    data = text_to_odt(referring())
    files = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as copy:
        for name in files.namelist():
            body = files.read(name)
            if name == "content.xml":
                body = body.replace(b'<text:bookmark text:name="ref-b1"/>', b"")
            copy.writestr(files.getinfo(name), body)
    third = odt_to_text(out.getvalue()).paragraphs[2]
    assert third.fields == (RefField("b2"),)
    assert third.text.startswith(f"see {FIELD_CHAR} and Why we did it on ")


@pytest.mark.parametrize(("write", "patch"), [(text_to_docx, apply_edits_to_docx), (text_to_odt, apply_edits_to_odt)])
def test_a_kept_file_with_references_is_written_anew_not_patched(write, patch):
    with pytest.raises(UnsupportedEdit, match="references"):
        patch(write(referring()), referring(), referring())


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_a_reference_to_a_thing_that_is_no_paragraph_is_written_as_its_words(write, read):
    from claudia_composes import ParagraphAnchor
    from claudia_core import ObjectBody, VisualObject, paragraph_for

    model = TextModel(
        [Paragraph("b1", "body", f"{FIELD_CHAR} and\t{FIELD_CHAR}", fields=(RefField("o1", "name"), RefField("b1")))]
    )
    box = ObjectBody("o1", "text", 200, 80, "plain-box", paragraph_for("o1", "body", "a note"), name="Budget")
    model.insert_object(VisualObject(box, ParagraphAnchor("b1", 0)))
    back = read(write(model))
    assert back.paragraphs[0].text.startswith("Budget and\t")
    assert back.paragraphs[0].fields == (RefField("b1"),)


def test_other_word_fields_are_read_as_what_they_show():
    from docx import Document as WordDocument

    data = text_to_docx(referring())
    document = WordDocument(io.BytesIO(data))
    third = document.paragraphs[2]._p  # noqa: SLF001
    from claudia_composes_io._docx_references import _char, _instruction, _run

    third.extend([_char("begin"), _instruction("PAGE"), _char("separate"), _run(text="7"), _char("end")])
    out = io.BytesIO()
    document.save(out)
    back = docx_to_text(out.getvalue())
    assert back.paragraphs[2].text.endswith(".7") and len(back.paragraphs[2].fields) == 3


@pytest.mark.parametrize(("write", "name"), [(text_to_docx, "word/document.xml"), (text_to_odt, "content.xml")])
def test_a_reference_in_the_words_of_a_text_box_is_written_as_what_it_reads_as(write, name):
    from claudia_composes import ParagraphAnchor
    from claudia_core import ObjectBody, VisualObject, paragraph_for

    model = referring()
    words = replace(paragraph_for("o1", "body", f"see {FIELD_CHAR}"), fields=(RefField("b2"),))
    model.insert_object(VisualObject(ObjectBody("o1", "text", 200, 80, "plain-box", words), ParagraphAnchor("b1", 0)))
    xml = part(write(model), name)
    assert "see 1" in xml and FIELD_CHAR not in xml
