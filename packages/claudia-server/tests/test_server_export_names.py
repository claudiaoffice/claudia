"""Names and descriptions in an exported Word or OpenDocument file (E1.13, D1311, D1318, A4-A6): a name a person gave
is a bookmark, what a person wrote about a paragraph is a review comment when the exporting person ticks the box."""

import base64
import io
import zipfile
from datetime import UTC, datetime

import pytest
from claudia_composes_io import docx_to_text, odt_to_text
from docx import Document as WordDocument
from test_server_thing_names import ANN, on_text

from claudia_composes import InsertText, SetStyle, SplitBlock, TextModel
from claudia_core import Document, MemoryStore


@pytest.fixture
def text():
    """A heading "Introduction" (b1) and a paragraph (b2)."""
    doc = Document(TextModel(), store=MemoryStore())
    doc.execute(InsertText("b1", 0, "Introduction"), author="ann")
    doc.execute(SetStyle("b1", "heading-1"), author="ann")
    doc.execute(SplitBlock("b1", 12, "b2", "body"), author="ann")
    doc.execute(InsertText("b2", 0, "The quick brown fox."), author="ann")
    return doc


def exported(doc, fmt="docx", *, comments=False, account=ANN, locale="en"):
    params = {"format": fmt}
    if comments:
        params["description_comments"] = True
    answer = on_text(doc, "export_office", params, account=account, locale=locale)
    return base64.b64decode(answer["data"]), answer


def parts(data):
    zf = zipfile.ZipFile(io.BytesIO(data))
    return {name: zf.read(name).decode("utf-8", "ignore") for name in zf.namelist() if name.endswith(".xml")}


def describe(doc, thing, name, description):
    on_text(doc, "name_and_describe", {"id": thing, "name": name, "description": description})


def test_a_name_a_person_gave_is_a_bookmark_in_the_word_file_and_comes_back_as_the_name(text):
    describe(text, "b2", "Budget summary", "")
    data, _ = exported(text)
    assert 'w:name="Budget_summary"' in parts(data)["word/document.xml"]
    back = docx_to_text(data)
    assert back.thing_name("b2") == "Budget summary"


def test_a_name_a_person_gave_is_a_bookmark_in_the_odt(text):
    describe(text, "b2", "Budget summary", "")
    data, _ = exported(text, "odt")
    assert 'text:name="Budget summary"' in parts(data)["content.xml"]
    assert odt_to_text(data).thing_name("b2") == "Budget summary"


@pytest.mark.parametrize("fmt", ["docx", "odt"])
def test_a_name_that_was_only_worked_out_is_not_written(text, fmt):
    data, _ = exported(text, fmt)  # b1 is called by its title, b2 by "Paragraph 1"
    body = parts(data)["word/document.xml" if fmt == "docx" else "content.xml"]
    assert "bookmark" not in body


def test_a_generic_name_in_another_language_is_not_written_either(text):
    text.execute(SplitBlock("b2", 3, "b3", "body", name="Absatz 7"), author="ann")
    data, _ = exported(text, locale="de")
    assert "Absatz" not in parts(data)["word/document.xml"]


def test_a_description_is_a_review_comment_when_the_box_is_ticked(text):
    describe(text, "b2", "", "Check against last year")
    data, answer = exported(text, comments=True)
    comments = list(WordDocument(io.BytesIO(data)).comments)
    assert [(c.text, c.author) for c in comments] == [("Check against last year", "ann")]
    assert comments[0].timestamp.date() == datetime.now(UTC).date()
    assert not any(loss["kind"] == "descriptions" for loss in answer.get("losses", []))


def test_a_description_is_an_annotation_in_the_odt(text):
    describe(text, "b2", "", "Check against last year")
    data, _ = exported(text, "odt", comments=True)
    body = parts(data)["content.xml"]
    assert "<dc:creator>ann</dc:creator>" in body
    assert "Check against last year" in body
    assert f"<dc:date>{datetime.now(UTC).date().isoformat()}" in body


@pytest.mark.parametrize("fmt", ["docx", "odt"])
def test_a_description_is_not_written_unless_the_box_is_ticked(text, fmt):
    describe(text, "b2", "", "Check against last year")
    data, _ = exported(text, fmt)
    assert not any("Check against last year" in xml for xml in parts(data).values())


def test_a_heading_description_is_a_comment_too_and_its_title_is_no_bookmark(text):
    describe(text, "b1", "Introduction", "The reason for the whole thing")
    data, _ = exported(text, comments=True)
    assert [c.text for c in WordDocument(io.BytesIO(data)).comments] == ["The reason for the whole thing"]
    assert "bookmarkStart" not in parts(data)["word/document.xml"]


def test_the_box_with_nothing_described_writes_no_comments(text):
    data, _ = exported(text, comments=True)
    assert "word/comments.xml" not in zipfile.ZipFile(io.BytesIO(data)).namelist()
