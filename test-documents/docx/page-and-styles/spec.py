"""The page, the language and the style sheet of a docx are read into the model; changing them writes them over what
the file had and leaves the styles claudia does not know (and the paragraphs, which were not touched) as they were
(D454, D455)."""

from __future__ import annotations

from io import BytesIO

from docx import Document

from claudia_composes import PageSetup, TextModel
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert (model.page.paper, model.page.orientation) == ("a4", "landscape")
    assert model.language == "de-DE"
    assert [(b.style, b.text) for b in model.paragraphs] == [
        ("heading-1", "Minutes of the meeting"),
        ("body", "We met on Tuesday."),
    ]


def modify(model: TextModel) -> TextModel:
    model.page = PageSetup.preset("letter", page_numbers=True)
    model.language = "fr-FR"
    model.palette.set_colour("text", "#112233")
    return model


def after_checks(model: TextModel) -> None:
    assert (model.page.paper, model.page.orientation, model.page.page_numbers) == ("letter", "portrait", True)
    assert model.language == "fr-FR"


def the_style_claudia_does_not_know_stays(original: bytes, edited: bytes) -> None:
    document = Document(BytesIO(edited))
    assert document.styles["Marker"].font.bold is True
    assert document.styles["Normal"].font.color.rgb == (0x11, 0x22, 0x33)


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["word/fontTable.xml", "word/theme/theme1.xml"],
    preserve_elements=the_style_claudia_does_not_know_stays,
)
