"""The page and the language of a docx: written from the model, read back, and changed in a kept file (D454)."""

from __future__ import annotations

import random
import zipfile
from io import BytesIO

import pytest
from claudia_composes_io import apply_edits_to_docx, docx_import_losses, docx_to_text, text_to_docx
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.shared import Twips

from claudia_composes import PageSetup, Paragraph, TextModel
from claudia_odf_io import Loss


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as package:
        return {name: package.read(name) for name in package.namelist()}


def saved(document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def a_file(**changes: object) -> bytes:
    """A file as Word would have it: the template's page (Letter) unless said otherwise."""
    document = Document()
    document.add_paragraph("words")
    section = document.sections[0]
    for name, value in changes.items():
        setattr(section, name, value)
    return saved(document)


def edit(original: bytes, **changes: object) -> bytes:
    baseline, current = docx_to_text(original), docx_to_text(original)
    for name, value in changes.items():
        setattr(current, name, value)
    return apply_edits_to_docx(original, baseline, current)


def again(model: TextModel) -> TextModel:
    return docx_to_text(text_to_docx(model))


def same_page(left: PageSetup, right: PageSetup) -> bool:
    """A file measures in twentieths of a point (50 mpt): a page is the same when it is the same to that."""
    fields = ("paper", "orientation", "page_numbers")
    sizes = ("width", "height", "margin_top", "margin_right", "margin_bottom", "margin_left")
    return all(getattr(left, f) == getattr(right, f) for f in fields) and all(
        abs(getattr(left, f) - getattr(right, f)) <= 25 for f in sizes
    )


# -- export and import -------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "page",
    [
        PageSetup(),
        PageSetup.preset("letter", orientation="landscape"),
        PageSetup.preset("a5", margin_left=20000, margin_top=30000, page_numbers=True),
        PageSetup("custom", 300000, 450000, "portrait", 20000, 21000, 22000, 23000, False),
        PageSetup("custom", 300000, 450000, "landscape", 20000, 21000, 22000, 23000, True),
    ],
)
def test_a_page_comes_back_as_it_was_written(page: PageSetup):
    assert same_page(again(TextModel(page=page)).page, page)


def test_the_page_is_the_page_size_of_the_first_section_and_lies_by_its_orientation():
    section = Document(BytesIO(text_to_docx(TextModel(page=PageSetup.preset("a4", orientation="landscape"))))).sections[
        0
    ]
    assert section.orientation == WD_ORIENT.LANDSCAPE and section.page_width > section.page_height


def test_the_numbers_of_the_pages_are_a_field_in_the_footer():
    data = text_to_docx(TextModel(page=PageSetup(page_numbers=True)))
    assert b"PAGE" in b"".join(data for name, data in parts(data).items() if name.startswith("word/footer"))
    assert not any(name.startswith("word/footer") for name in parts(text_to_docx(TextModel())))


@pytest.mark.parametrize("language", ["de", "de-AT", "en-GB", "sr-Latn-RS", None])
def test_a_language_comes_back_as_it_was_written(language: str | None):
    assert again(TextModel(language=language)).language == language


# -- reading what other programs write ---------------------------------------------------------------------------
def test_a_page_of_word_is_read_with_the_paper_it_is():
    page = docx_to_text(a_file()).page
    assert (page.paper, page.orientation, page.margin_left) == (
        "letter",
        "portrait",
        90000,
    )  # the template has 1.25 inches at the sides


def test_a4_as_word_measures_it_is_a4():
    assert docx_to_text(a_file(page_width=Twips(11906), page_height=Twips(16838))).page.paper == "a4"


def test_a_page_the_model_cannot_hold_is_reported_and_left_as_a_default():
    data = a_file(page_width=Twips(300), page_height=Twips(300))
    assert docx_to_text(data).page == PageSetup()
    assert Loss("page", "", 1) in docx_import_losses(data) and Loss("page", "", 1) not in docx_import_losses(a_file())


def test_numbers_made_with_a_complex_field_are_read():
    document = Document()
    document.add_paragraph("words")
    footer = document.sections[0].footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    for kind in ("begin", None, "separate", "end"):
        run = paragraph.add_run()
        if kind:
            run._r.append(_field_character(kind))
        else:
            run._r.append(_instruction(" PAGE "))
    assert docx_to_text(saved(document)).page.page_numbers is True


def _field_character(kind: str):
    from docx.oxml import OxmlElement

    element = OxmlElement("w:fldChar")
    element.set(qn("w:fldCharType"), kind)
    return element


def _instruction(text: str):
    from docx.oxml import OxmlElement

    element = OxmlElement("w:instrText")
    element.text = text
    return element


# -- patching ----------------------------------------------------------------------------------------------------
def test_nothing_changed_leaves_every_part_as_it_was():
    original = a_file()
    assert parts(edit(original)) == parts(original)


def test_a_changed_page_changes_the_section_and_no_other_part():
    original = a_file()
    edited = edit(original, page=PageSetup.preset("a4", margin_left=50000))
    assert same_page(docx_to_text(edited).page, PageSetup.preset("a4", margin_left=50000))
    assert {name for name, data in parts(edited).items() if data != parts(original)[name]} == {"word/document.xml"}


def test_page_numbers_are_added_to_a_file_without_a_footer_and_taken_out_again():
    original = a_file()
    numbered = edit(original, page=PageSetup.preset("letter", page_numbers=True, margin_left=72000, margin_top=72000))
    assert docx_to_text(numbered).page.page_numbers is True
    assert any(name.startswith("word/footer") for name in parts(numbered))
    assert Document(BytesIO(numbered)).sections[0].footer.is_linked_to_previous is False
    plain = apply_edits_to_docx(numbered, docx_to_text(numbered), _page_numbers(docx_to_text(numbered), False))
    assert docx_to_text(plain).page.page_numbers is False


def _page_numbers(model: TextModel, wanted: bool) -> TextModel:
    from dataclasses import replace

    model.page = replace(model.page, page_numbers=wanted)
    return model


def test_the_words_of_a_footer_stay_when_the_number_goes():
    document = Document()
    document.add_paragraph("words")
    footer = document.sections[0].footer
    footer.is_linked_to_previous = False
    footer.paragraphs[0].add_run("Page ")
    from docx.oxml import OxmlElement

    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " PAGE ")
    footer.paragraphs[0]._p.append(field)
    original = saved(document)
    assert docx_to_text(original).page.page_numbers is True
    edited = apply_edits_to_docx(original, docx_to_text(original), _page_numbers(docx_to_text(original), False))
    footer_xml = b"".join(data for name, data in parts(edited).items() if name.startswith("word/footer"))
    assert b"Page " in footer_xml and b"PAGE" not in footer_xml


def test_a_language_is_given_changed_and_taken_away():
    original = text_to_docx(TextModel(language="de-DE"))
    assert docx_to_text(edit(original, language="en-GB")).language == "en-GB"
    gone = edit(original, language=None)
    assert docx_to_text(gone).language is None
    assert {name for name, data in parts(edit(original, language="fr")).items() if data != parts(original)[name]} == {
        "word/styles.xml"
    }


def test_a_language_is_given_to_a_file_that_says_none():
    document = Document()
    document.add_paragraph("words")
    defaults = document.styles.element.find(qn("w:docDefaults"))
    document.styles.element.remove(defaults)
    original = saved(document)
    assert docx_to_text(original).language is None
    assert docx_to_text(edit(original, language="it")).language == "it"


def test_a_language_that_is_no_tag_is_no_language():
    document = Document()
    document.add_paragraph("words")
    lang = document.styles.element.find(
        qn("w:docDefaults") + "/" + qn("w:rPrDefault") + "/" + qn("w:rPr") + "/" + qn("w:lang")
    )
    lang.set(qn("w:val"), "not a tag at all")
    assert docx_to_text(saved(document)).language is None


def test_a_text_edited_in_the_same_run_is_edited_too():
    original = text_to_docx(TextModel([Paragraph("b1", "body", "words")]))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.page = PageSetup.preset("a5")
    current.language = "de"
    current.paragraphs[0] = Paragraph("b1", "body", "so words", current.paragraphs[0].runs)
    read = docx_to_text(apply_edits_to_docx(original, baseline, current))
    assert (read.page.paper, read.language, read.paragraphs[0].text) == ("a5", "de", "so words")


def test_whatever_is_changed_about_the_setup_the_file_says_it():
    rng = random.Random(456)
    original = a_file()
    for _ in range(60):
        page = PageSetup.preset(
            rng.choice(["a4", "a5", "letter", "legal"]),
            orientation=rng.choice(["portrait", "landscape"]),
            margin_left=rng.randrange(20000, 90000, 50),
            margin_top=rng.randrange(20000, 90000, 50),
            page_numbers=rng.random() < 0.5,
        )
        language = rng.choice([None, "de", "en-GB", "pt-BR", "zh-Hant-TW"])
        read = docx_to_text(edit(original, page=page, language=language))
        assert same_page(read.page, page) and read.language == language
