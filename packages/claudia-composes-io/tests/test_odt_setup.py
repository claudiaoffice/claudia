"""The page and the language of an odt: written from the model, read back, and changed in a kept file (D454).
What the file says of them is what the model says; what the edit does not touch is as it was."""

from __future__ import annotations

import random

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_odt,
    odt_import_losses,
    odt_to_text,
    text_to_odt,
)
from lxml import etree
from test_odt import DECLS, HEAD, an_odt

from claudia_composes import PageSetup, TextModel
from claudia_core import Run
from claudia_odf_io import NS, Loss, problems
from claudia_opc_io import read_parts


def styles_xml(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["styles.xml"])


def layout_of(data: bytes) -> etree._Element:
    found = styles_xml(data).find("office:automatic-styles/style:page-layout/style:page-layout-properties", NS)
    assert found is not None
    return found


def a_libre_styles(layout: str = "", master: str = "", default: str = "") -> str:
    """The ``styles.xml`` of a file as LibreOffice writes one, with the page, the master page and the default style
    as given."""
    return (
        f'{HEAD}<office:document-styles {DECLS} office:version="1.3"><office:styles>{default}'
        '<style:style style:name="Standard" style:family="paragraph" style:class="text"/></office:styles>'
        f"<office:automatic-styles>{layout}</office:automatic-styles>"
        f"<office:master-styles>{master}</office:master-styles></office:document-styles>"
    )


A4 = (
    '<style:page-layout style:name="Mpm1"><style:page-layout-properties fo:page-width="21.001cm" '
    'fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="2cm" fo:margin-bottom="2cm" '
    'fo:margin-left="2cm" fo:margin-right="2cm"/></style:page-layout>'
)
MASTER = '<style:master-page style:name="Standard" style:page-layout-name="Mpm1"/>'
FILE = a_libre_styles(A4, MASTER)


def a_file(styles: str = FILE) -> bytes:
    return an_odt('<text:p text:style-name="Standard">words</text:p>', styles=styles)


def edit(original: bytes, **changes: object) -> bytes:
    baseline, current = odt_to_text(original), odt_to_text(original)
    for name, value in changes.items():
        setattr(current, name, value)
    return apply_edits_to_odt(original, baseline, current)


def again(model: TextModel) -> TextModel:
    return odt_to_text(text_to_odt(model))


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
    data = text_to_odt(TextModel(page=page))
    assert problems(data) == [] and odt_to_text(data).page == page


def test_the_page_is_a_page_layout_that_the_master_page_names():
    data = text_to_odt(TextModel(page=PageSetup.preset("letter", orientation="landscape")))
    layout = layout_of(data)
    assert layout.get(f"{{{NS['style']}}}print-orientation") == "landscape"
    assert layout.get(f"{{{NS['fo']}}}page-width") == "792pt" and layout.get(f"{{{NS['fo']}}}page-height") == "612pt"


def test_the_numbers_of_the_pages_are_a_field_in_the_footer():
    data = text_to_odt(TextModel(page=PageSetup(page_numbers=True)))
    footer = styles_xml(data).find("office:master-styles/style:master-page/style:footer", NS)
    assert footer is not None and footer.find(".//text:page-number", NS) is not None
    assert text_to_odt(TextModel()) and styles_xml(text_to_odt(TextModel())).find(".//style:footer", NS) is None


@pytest.mark.parametrize("language", ["de", "de-AT", "en-GB", "sr-Latn-RS", None])
def test_a_language_comes_back_as_it_was_written(language: str | None):
    assert again(TextModel(language=language)).language == language


def test_a_text_without_a_language_says_none():
    assert b"fo:language" not in read_parts(text_to_odt(TextModel()))["styles.xml"]


# -- reading what other programs write ---------------------------------------------------------------------------
def test_a_page_in_another_unit_or_lying_on_its_side_is_read():
    layout = (
        '<style:page-layout style:name="Mpm1"><style:page-layout-properties fo:page-width="11in" '
        'fo:page-height="8.5in" fo:margin="1in"/></style:page-layout>'
    )
    page = odt_to_text(a_file(a_libre_styles(layout, MASTER))).page
    assert (page.paper, page.orientation, page.margin_left) == ("letter", "landscape", 72000)


def test_a_file_that_says_no_page_is_a_default_page():
    assert odt_to_text(a_file(a_libre_styles())).page == PageSetup()


def test_the_language_libreoffice_writes_is_read():
    default = (
        '<style:default-style style:family="paragraph"><style:text-properties fo:language="de" fo:country="CH"/>'
        "</style:default-style>"
    )
    assert odt_to_text(a_file(a_libre_styles(A4, MASTER, default))).language == "de-CH"
    none = default.replace('fo:language="de" fo:country="CH"', 'fo:language="zxx" fo:country="none"')
    assert odt_to_text(a_file(a_libre_styles(A4, MASTER, none))).language is None


def test_a_page_the_model_cannot_hold_is_reported_and_left_as_a_default():
    layout = A4.replace('fo:page-width="21.001cm"', 'fo:page-width="2cm"')
    data = a_file(a_libre_styles(layout, MASTER))
    assert odt_to_text(data).page == PageSetup()
    assert Loss("page", "", 1) in odt_import_losses(data)
    assert Loss("page", "", 1) not in odt_import_losses(a_file())


# -- patching ----------------------------------------------------------------------------------------------------
def test_nothing_changed_is_the_file_itself():
    original = a_file()
    assert edit(original) == original


def test_a_changed_paper_changes_the_layout_and_nothing_else():
    original = a_file()
    edited = edit(original, page=PageSetup.preset("letter", margin_left=50000))
    assert problems(edited) == []
    assert odt_to_text(edited).page == PageSetup.preset("letter", margin_left=50000)
    parts, was = read_parts(edited), read_parts(original)
    assert {name for name in parts if parts[name] != was[name]} == {"styles.xml"}
    assert parts["styles.xml"].replace(b"612pt", b"") != was["styles.xml"]  # and the rest of styles.xml is as it was
    assert b'style:name="Standard" style:family="paragraph" style:class="text"/>' in parts["styles.xml"]


def test_a_page_turned_on_its_side_is_written_with_the_long_side_first():
    edited = edit(a_file(), page=PageSetup(orientation="landscape"))
    layout = layout_of(edited)
    assert layout.get(f"{{{NS['style']}}}print-orientation") == "landscape"
    assert odt_to_text(edited).page.orientation == "landscape"


def test_page_numbers_are_added_to_a_master_page_without_a_footer_and_taken_out_again():
    original = a_file()
    numbered = edit(
        original,
        page=PageSetup(margin_left=56693, margin_right=56693, margin_top=56693, margin_bottom=56693, page_numbers=True),
    )
    assert odt_to_text(numbered).page.page_numbers is True and problems(numbered) == []
    assert b'style:name="Footer"' in read_parts(numbered)["styles.xml"]
    plain = apply_edits_to_odt(numbered, odt_to_text(numbered), _with(odt_to_text(numbered), page_numbers=False))
    assert odt_to_text(plain).page.page_numbers is False


def _with(model: TextModel, **page: object) -> TextModel:
    from dataclasses import replace

    model.page = replace(model.page, **page)
    return model


def test_a_footer_of_the_file_keeps_its_words_when_the_number_goes():
    footer = (
        '<style:footer><text:p text:style-name="Standard">Page <text:page-number text:select-page="current">1'
        "</text:page-number></text:p></style:footer>"
    )
    original = a_file(a_libre_styles(A4, MASTER.replace("/>", f">{footer}</style:master-page>")))
    assert odt_to_text(original).page.page_numbers is True
    edited = apply_edits_to_odt(original, odt_to_text(original), _with(odt_to_text(original), page_numbers=False))
    assert b"Page" in read_parts(edited)["styles.xml"] and b"page-number" not in read_parts(edited)["styles.xml"]


@pytest.mark.parametrize(
    "footer",
    ['<style:footer><text:p text:style-name="Standard">Draft</text:p></style:footer>', "<style:footer/>"],
    ids=["a footer with a paragraph", "a footer without one"],
)
def test_a_footer_of_the_file_gets_the_number_in_it_and_keeps_what_it_has(footer: str):
    original = a_file(a_libre_styles(A4, MASTER.replace("/>", f">{footer}</style:master-page>")))
    assert odt_to_text(original).page.page_numbers is False
    edited = apply_edits_to_odt(original, odt_to_text(original), _with(odt_to_text(original), page_numbers=True))
    assert odt_to_text(edited).page.page_numbers is True and problems(edited) == []
    assert (b"Draft" in read_parts(edited)["styles.xml"]) == ("Draft" in footer)


def test_a_language_is_given_changed_and_taken_away():
    default = (
        '<style:default-style style:family="paragraph">'
        '<style:text-properties fo:language="de" fo:country="DE"/></style:default-style>'
    )
    original = a_file(a_libre_styles(A4, MASTER, default))
    assert odt_to_text(edit(original, language="en-GB")).language == "en-GB"
    assert odt_to_text(edit(original, language="sr-Latn-RS")).language == "sr-Latn-RS"
    gone = edit(original, language=None)
    assert odt_to_text(gone).language is None and b'fo:language="de"' not in read_parts(gone)["styles.xml"]
    given = edit(a_file(), language="fr")
    assert odt_to_text(given).language == "fr" and problems(given) == []


def test_a_language_is_added_to_a_default_style_without_text_properties():
    default = '<style:default-style style:family="paragraph"><style:paragraph-properties/></style:default-style>'
    assert odt_to_text(edit(a_file(a_libre_styles(A4, MASTER, default)), language="it")).language == "it"


def test_a_file_without_a_page_layout_cannot_be_given_a_page():
    with pytest.raises(UnsupportedEdit, match="page layout"):
        edit(a_file(a_libre_styles()), page=PageSetup.preset("letter"))


def test_a_file_without_styles_cannot_be_given_a_language():
    original = a_file()
    parts = read_parts(original)
    parts.pop("styles.xml")
    from claudia_opc_io import write_parts

    with pytest.raises(UnsupportedEdit, match="styles.xml"):
        edit(write_parts(parts), language="de")


def test_the_text_edited_in_the_same_run_is_edited_too():
    original = a_file()
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.page = PageSetup.preset("a5")
    current.language = "de"
    current.insert("b1", 0, "so ", [Run(3, None)])
    edited = apply_edits_to_odt(original, baseline, current)
    again_ = odt_to_text(edited)
    assert (again_.page.paper, again_.language, again_.blocks[0].text) == ("a5", "de", "so words")


def test_whatever_is_changed_about_the_setup_the_file_says_it():
    rng = random.Random(455)
    original = a_file()
    for _ in range(100):
        page = PageSetup.preset(
            rng.choice(["a4", "a5", "letter", "legal"]),
            orientation=rng.choice(["portrait", "landscape"]),
            margin_left=rng.randrange(20000, 90000, 1000),
            margin_top=rng.randrange(20000, 90000, 1000),
            page_numbers=rng.random() < 0.5,
        )
        language = rng.choice([None, "de", "en-GB", "pt-BR", "zh-Hant-TW"])
        edited = edit(original, page=page, language=language)
        assert problems(edited) == []
        read = odt_to_text(edited)
        assert (read.page, read.language) == (page, language)
        assert odt_to_text(edit(edited, page=PageSetup(), language="ru")).language == "ru"
