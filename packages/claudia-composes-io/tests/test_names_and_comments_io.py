"""Names and descriptions in docx and odt (E1.13, D1311, D1318).

A paragraph a person gave a name is a bookmark around its words; a description a person wrote is a review comment, when
the person who exports asks for it. Reading, a bookmark around exactly one paragraph is that paragraph's name; comments
are not read back as descriptions (A7)."""

import io
import zipfile

import pytest
from claudia_composes_io import Annotations, docx_to_text, odt_to_text, text_to_docx, text_to_odt
from docx import Document
from lxml import etree

from claudia_composes import Paragraph, TextModel

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def text() -> TextModel:
    return TextModel(
        [
            Paragraph("b1", "heading-1", "Why we did it"),
            Paragraph("b2", "body", "Collect the figures"),
            Paragraph("b3", "body", "Send them round"),
        ]
    )


def part(data: bytes, name: str) -> str:
    return zipfile.ZipFile(io.BytesIO(data)).read(name).decode()


def rewritten(data: bytes, name: str, old: str, new: str) -> bytes:
    """``data`` with ``old`` replaced by ``new`` in the part ``name``: a file as another program wrote it."""
    source = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            body = source.read(item.filename)
            if item.filename == name:
                assert old.encode() in body, f"{old!r} not in {name}"
                body = body.replace(old.encode(), new.encode())
            target.writestr(item, body)
    return out.getvalue()


def names_of(model: TextModel) -> dict[str, str]:
    return {thing: name for _kind, thing, name in model.named_things() if thing.startswith("b")}


NAMES = Annotations(names={"b2": "Budget summary"})
NOTES = Annotations(
    comments={"b2": "Check these against last year", "b3": "Ask Sam first"},
    author="Ann Example",
    when="2026-11-19T10:30:00Z",
)


# -- names are bookmarks ----------------------------------------------------------------------------------------
@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_a_given_name_comes_back_as_the_name_of_the_same_paragraph(write, read):
    back = read(write(text(), annotations=NAMES))
    assert names_of(back)["b2"] == "Budget summary"
    assert back.paragraph("b2").text == "Collect the figures"


@pytest.mark.parametrize("write", [text_to_docx, text_to_odt])
def test_without_annotations_nothing_is_a_name_bookmark(write):
    data = write(text())
    body = part(data, "word/document.xml" if write is text_to_docx else "content.xml")
    assert "bookmark" not in body


def test_word_cannot_hold_spaces_in_a_bookmark_so_the_docx_one_is_written_with_underscores():
    body = part(text_to_docx(text(), annotations=NAMES), "word/document.xml")
    assert 'w:name="Budget_summary"' in body


def test_odt_keeps_the_name_as_it_is():
    body = part(text_to_odt(text(), annotations=NAMES), "content.xml")
    assert 'text:name="Budget summary"' in body
    assert "text:bookmark-start" in body
    assert "text:bookmark-end" in body


def test_a_name_that_word_would_refuse_is_still_written_as_a_valid_bookmark():
    long = "É" + "x" * 58
    data = text_to_docx(text(), annotations=Annotations(names={"b2": "1st quarter", "b3": long}))
    document = Document(io.BytesIO(data))
    names = [e.get(f"{{{W}}}name") for e in document.element.iter(f"{{{W}}}bookmarkStart")]
    assert len(names) == 2
    assert all(n[0].isalpha() and len(n) <= 40 for n in names)


# -- reading names ----------------------------------------------------------------------------------------------
def a_word_file(*runs: str) -> bytes:
    """A docx with one paragraph; a run ``"<name"`` starts a bookmark, ``">name"`` ends it, anything else is words."""
    document = Document()
    paragraph = document.add_paragraph()
    for run in runs:
        if run[0] in "<>":
            tag = "w:bookmarkStart" if run[0] == "<" else "w:bookmarkEnd"
            element = paragraph._p.makeelement(f"{{{W}}}{tag[2:]}", {})
            element.set(f"{{{W}}}id", str(abs(hash(run[1:])) % 1000))
            if run[0] == "<":
                element.set(f"{{{W}}}name", run[1:])
            paragraph._p.append(element)
        else:
            paragraph.add_run(run)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def test_docx_bookmark_around_the_words_of_one_paragraph_is_its_name():
    back = docx_to_text(a_word_file("<Budget_summary", "Collect ", "the figures", ">Budget_summary"))
    assert names_of(back) == {"b1": "Budget summary"}


def test_docx_bookmark_around_a_part_of_the_words_names_nothing():
    assert names_of(docx_to_text(a_word_file("Collect ", "<Part", "the figures", ">Part"))) == {}
    assert names_of(docx_to_text(a_word_file("<Part", "Collect ", ">Part", "the figures"))) == {}


@pytest.mark.parametrize("technical", ["_Toc123456", "_Ref99", "_GoBack", "ref-b3", "_hidden"])
def test_docx_bookmarks_the_programs_make_are_not_names(technical):
    assert names_of(docx_to_text(a_word_file(f"<{technical}", "Collect", f">{technical}"))) == {}


def test_docx_first_usable_bookmark_is_taken_when_there_are_several():
    back = docx_to_text(a_word_file("<_GoBack", "<Intro", "Collect", ">Intro", ">_GoBack"))
    assert names_of(back) == {"b1": "Intro"}


def test_docx_the_same_name_twice_is_kept_apart():
    document = Document()
    for words in ("one", "two"):
        paragraph = document.add_paragraph(words)
        start = paragraph._p.makeelement(f"{{{W}}}bookmarkStart", {})
        start.set(f"{{{W}}}id", words)
        start.set(f"{{{W}}}name", "Same")
        end = paragraph._p.makeelement(f"{{{W}}}bookmarkEnd", {})
        end.set(f"{{{W}}}id", words)
        paragraph._p.insert(0, start)
        paragraph._p.append(end)
    out = io.BytesIO()
    document.save(out)
    assert sorted(names_of(docx_to_text(out.getvalue())).values()) == ["Same", "Same (2)"]


def test_docx_a_bookmark_around_a_headings_words_does_not_rename_it():
    document = Document()
    paragraph = document.add_heading("Why we did it", level=1)
    start = paragraph._p.makeelement(f"{{{W}}}bookmarkStart", {})
    start.set(f"{{{W}}}id", "1")
    start.set(f"{{{W}}}name", "Something_else")
    end = paragraph._p.makeelement(f"{{{W}}}bookmarkEnd", {})
    end.set(f"{{{W}}}id", "1")
    paragraph._p.insert(1, start)
    paragraph._p.append(end)
    out = io.BytesIO()
    document.save(out)
    back = docx_to_text(out.getvalue())
    assert [name for _kind, _thing, name in back.named_things()] == ["Why we did it"]


def test_odt_bookmark_around_the_words_of_one_paragraph_is_its_name():
    data = text_to_odt(text())
    data = rewritten(
        data,
        "content.xml",
        "Collect the figures",
        '<text:bookmark-start text:name="Budget summary"/>Collect the figures'
        '<text:bookmark-end text:name="Budget summary"/>',
    )
    assert names_of(odt_to_text(data))["b2"] == "Budget summary"


def test_odt_a_point_bookmark_or_one_around_a_part_names_nothing():
    base = text_to_odt(text())
    point = rewritten(
        base, "content.xml", "Collect the figures", '<text:bookmark text:name="Here"/>Collect the figures'
    )
    part_of = rewritten(
        base,
        "content.xml",
        "Collect the figures",
        'Collect <text:bookmark-start text:name="Part"/>the figures<text:bookmark-end text:name="Part"/>',
    )
    assert "b2" not in names_of(odt_to_text(point))
    assert "b2" not in names_of(odt_to_text(part_of))


# -- descriptions are review comments ---------------------------------------------------------------------------
def test_docx_comments_are_written_by_the_person_who_exports_on_the_day_of_export():
    document = Document(io.BytesIO(text_to_docx(text(), annotations=NOTES)))
    comments = list(document.comments)
    assert [c.text for c in comments] == ["Check these against last year", "Ask Sam first"]
    assert {c.author for c in comments} == {"Ann Example"}
    assert {c.timestamp.date().isoformat() for c in comments} == {"2026-11-19"}
    body = part(text_to_docx(text(), annotations=NOTES), "word/document.xml")
    assert body.count("commentRangeStart") == 2
    assert body.count("commentReference") == 2


def test_odt_comments_are_annotations_around_the_words():
    body = part(text_to_odt(text(), annotations=NOTES), "content.xml")
    assert body.count("<office:annotation ") == 2
    assert body.count("<office:annotation-end") == 2
    assert "<dc:creator>Ann Example</dc:creator>" in body
    assert "<dc:date>2026-11-19T10:30:00Z</dc:date>" in body
    assert "Check these against last year" in body


@pytest.mark.parametrize("write", [text_to_docx, text_to_odt])
def test_no_comments_unless_asked_for(write):
    data = write(text(), annotations=NAMES)  # a name alone writes no comment
    assert "Check these" not in b"".join(
        zipfile.ZipFile(io.BytesIO(data)).read(n) for n in zipfile.ZipFile(io.BytesIO(data)).namelist()
    ).decode(errors="ignore")
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "word/comments.xml" not in names


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_comments_are_not_read_back_as_descriptions(write, read):
    back = read(write(text(), annotations=NOTES))
    assert back.paragraph_descriptions == {}
    assert back.paragraph("b2").text == "Collect the figures"


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_a_comment_text_with_markup_characters_comes_out_as_it_went_in(write, read):
    notes = Annotations(comments={"b2": 'a < b & "c" > d'}, author="A & B", when="2026-11-19T10:30:00Z")
    data = write(text(), annotations=notes)
    etree.fromstring(part(data, "word/comments.xml" if write is text_to_docx else "content.xml").encode())
    assert read(data).paragraph("b2").text == "Collect the figures"


@pytest.mark.parametrize(("write", "read"), [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)])
def test_a_named_and_commented_paragraph_is_still_found_by_a_reference(write, read):
    from claudia_core import FIELD_CHAR, RefField

    model = TextModel(
        [
            Paragraph("b1", "body", "Collect"),
            Paragraph("b2", "body", f"see {FIELD_CHAR}", fields=(RefField("b1", "text"),)),
        ]
    )
    back = read(
        write(
            model,
            annotations=Annotations(
                names={"b1": "Source"}, comments={"b1": "why"}, author="A", when="2026-11-19T10:00:00Z"
            ),
        )
    )
    (referring,) = [b for b in back.paragraphs if b.fields]
    assert referring.fields[0].target == "b1"
    assert names_of(back)["b1"] == "Source"
