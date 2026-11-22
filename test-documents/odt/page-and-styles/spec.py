"""The page, the language and the style sheet of an odt are read into the model; changing them writes them over what
the file had and leaves the styles claudia does not know (and the paragraphs, which were not touched) as they were
(D454, D455)."""

from __future__ import annotations

from claudia_composes import PageSetup, TextModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert (model.page.paper, model.page.orientation) == ("a4", "landscape")
    assert (model.page.margin_left, model.page.margin_top) == (56693, 56693)
    assert model.language == "de-DE"
    assert [b.text for b in model.paragraphs] == ["Minutes of the meeting", "We met on Tuesday."]


def modify(model: TextModel) -> TextModel:
    model.page = PageSetup.preset("letter", page_numbers=True)
    model.language = "fr-FR"
    model.palette.set_colour("text", "#112233")
    return model


def after_checks(model: TextModel) -> None:
    assert (model.page.paper, model.page.orientation, model.page.page_numbers) == ("letter", "portrait", True)
    assert model.language == "fr-FR"
    assert model.palette.colours()["text"] != "#112233"  # a file has no palette: the colour is in the styles


def the_style_claudia_does_not_know_stays(original: bytes, edited: bytes) -> None:
    styles = read_parts(edited)["styles.xml"].decode()
    assert 'style:name="Marker"' in styles and 'fo:font-weight="bold"' in styles
    assert 'fo:color="#112233"' in styles  # the colour the palette gives the body text is written into its style


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["content.xml", "meta.xml"],
    preserve_elements=the_style_claudia_does_not_know_stays,
)
