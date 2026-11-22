"""The styles of a docx: every paragraph style of the model written as a Word style with its look and the colours of
its palette, and replaced in a kept file when the model changed them (D455)."""

from __future__ import annotations

import zipfile
from io import BytesIO

from claudia_composes_io import apply_edits_to_docx, docx_export_losses, docx_to_text, text_to_docx
from docx import Document
from docx.oxml.ns import qn

from claudia_composes import Paragraph, TextModel
from claudia_core import StyleDef
from claudia_odf_io import Loss


def model_of(*paragraphs: tuple[str, str]) -> TextModel:
    return TextModel([Paragraph(f"b{i}", style, text) for i, (style, text) in enumerate(paragraphs, start=1)])


def with_style(css: dict[str, str], *, name: str = "Call out") -> TextModel:
    model = model_of(("callout", "words"))
    model.styles.add(StyleDef("callout", name, "", "body", css))
    return model


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as package:
        return {name: package.read(name) for name in package.namelist()}


def word_style(data: bytes, name: str):
    return Document(BytesIO(data)).styles[name]


def test_the_built_in_styles_are_the_styles_word_has_for_them_with_the_look_of_the_model():
    data = text_to_docx(model_of(("title", "t"), ("heading-1", "h"), ("body", "b")))
    title = word_style(data, "Title")
    assert title.font.size.pt == 30 and title.font.name.startswith("Fraunces")
    assert word_style(data, "Normal").font.color.rgb == (0x1F, 0x1A, 0x33)
    assert word_style(data, "Heading 1").font.size.pt == 19


def test_a_heading_keeps_the_place_it_has_in_a_document():
    heading = word_style(text_to_docx(model_of(("heading-1", "h"))), "Heading 1")
    assert heading.paragraph_format.keep_with_next is True
    assert heading.element.pPr.find(qn("w:outlineLvl")) is not None


def test_the_colour_a_style_names_is_the_colour_of_the_palette_role_it_names():
    model = with_style({"color": "@accent"})
    assert word_style(text_to_docx(model), "Call out").font.color.rgb == (0x5B, 0x4B, 0xC4)
    model.palette.set_colour("accent", "#112233")
    assert word_style(text_to_docx(model), "Call out").font.color.rgb == (0x11, 0x22, 0x33)


def test_a_style_has_its_spacing_its_line_height_and_its_alignment():
    model = with_style({"margin-top": "6pt", "margin-bottom": "12pt", "line-height": "1.5", "text-align": "justify"})
    paragraph = word_style(text_to_docx(model), "Call out").paragraph_format
    assert (paragraph.space_before.pt, paragraph.space_after.pt, paragraph.line_spacing) == (6, 12, 1.5)
    assert paragraph.alignment == 3


def test_a_border_and_a_background_are_written_into_the_style_in_the_order_a_file_wants():
    properties = word_style(text_to_docx(model_of(("quote", "q"))), "Quote").element.pPr
    border = properties.find(qn("w:pBdr")).find(qn("w:left"))
    assert (border.get(qn("w:val")), border.get(qn("w:color")), border.get(qn("w:sz"))) == ("single", "F2A057", "18")
    order = [child.tag for child in properties]
    assert order.index(qn("w:pBdr")) < order.index(qn("w:spacing"))
    shaded = word_style(text_to_docx(with_style({"background-color": "@accent/8"})), "Call out").element.pPr
    assert shaded.find(qn("w:shd")).get(qn("w:fill")) == "F2F1FA"


def test_a_style_is_based_on_the_style_the_model_bases_it_on():
    assert word_style(text_to_docx(with_style({})), "Call out").base_style.name == "Normal"


def test_a_paragraph_has_the_style_of_its_name_and_a_custom_one_never_takes_the_name_of_another():
    data = text_to_docx(with_style({}, name="Heading 7"))
    document = Document(BytesIO(data))
    assert document.paragraphs[0].style.name == "Heading 7 2"
    assert document.styles["Heading 7"].name == "Heading 7"


def test_hyphenation_is_the_documents_and_a_style_that_says_none_switches_it_off_for_itself():
    data = text_to_docx(model_of(("title", "t")))
    document = Document(BytesIO(data))
    assert document.settings.element.find(qn("w:autoHyphenation")) is not None
    assert word_style(data, "Title").element.pPr.find(qn("w:suppressAutoHyphens")) is not None


def test_what_a_file_cannot_say_of_a_style_is_a_loss_and_a_style_the_model_lacks_is_one_too():
    model = with_style({"word-spacing": "3pt"})
    model.paragraphs.append(Paragraph("b9", "missing", "x"))
    assert docx_export_losses(model) == (Loss("style", "missing"), Loss("style-property", "callout: word-spacing"))


def test_the_default_styles_export_without_a_loss():
    assert docx_export_losses(model_of(("title", "t"), ("quote", "q"), ("body", "b"))) == ()


def test_the_paragraphs_read_from_a_file_have_the_styles_they_were_written_with():
    again = docx_to_text(text_to_docx(model_of(("heading-1", "h"), ("quote", "q"), ("body", "b"))))
    assert [b.style for b in again.paragraphs] == ["heading-1", "quote", "body"]


def test_a_kept_file_is_left_as_it_is_when_the_styles_did_not_change():
    original = text_to_docx(model_of(("body", "b")))
    baseline = docx_to_text(original)
    patched = apply_edits_to_docx(original, baseline, docx_to_text(original))
    assert parts(patched)["word/styles.xml"] == parts(original)["word/styles.xml"]


def test_a_changed_palette_colour_replaces_the_styles_that_use_it_and_leaves_the_others():
    original = text_to_docx(model_of(("body", "b")))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.palette.set_colour("text", "#112233")
    patched = apply_edits_to_docx(original, baseline, current)
    assert word_style(patched, "Normal").font.color.rgb == (0x11, 0x22, 0x33)
    assert word_style(patched, "Title").font.size == word_style(original, "Title").font.size


def test_a_style_made_after_the_file_was_read_is_added_and_used_by_the_paragraph_that_has_it():
    original = text_to_docx(model_of(("body", "b")))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.styles.add(StyleDef("callout", "Call out", "", "body", {"font-style": "italic"}))
    current.paragraphs[0] = Paragraph(current.paragraphs[0].id, "callout", "b")
    patched = Document(BytesIO(apply_edits_to_docx(original, baseline, current)))
    assert patched.paragraphs[0].style.name == "Call out" and patched.styles["Call out"].font.italic is True


def test_a_style_has_its_decoration_its_indents_and_a_line_height_in_points():
    model = with_style(
        {
            "text-decoration": "underline line-through",
            "margin-left": "12pt",
            "margin-right": "6pt",
            "line-height": "18pt",
            "border-top": "none",
        }
    )
    word = word_style(text_to_docx(model), "Call out")
    assert (word.font.underline, word.font.strike) == (True, True)
    assert (word.paragraph_format.left_indent.pt, word.paragraph_format.right_indent.pt) == (12, 6)
    assert word.paragraph_format.line_spacing.pt == 18
    assert word.element.pPr.find(qn("w:pBdr")).find(qn("w:top")).get(qn("w:val")) == "nil"


def test_a_style_that_is_based_on_none_is_based_on_none():
    model = model_of(("callout", "words"))
    model.styles.add(StyleDef("callout", "Call out", "", None, {"font-size": "10pt"}))
    assert word_style(text_to_docx(model), "Call out").base_style is None


def test_hyphenation_is_off_in_a_document_whose_body_is_not_hyphenated_and_a_style_that_wants_it_is_a_loss():
    model = with_style({"hyphens": "auto", "padding-top": "4pt"})
    model.styles.set_css("body", {"font-size": "12pt"})
    assert Document(BytesIO(text_to_docx(model))).settings.element.find(qn("w:autoHyphenation")) is None
    assert docx_export_losses(model) == (
        Loss("style-property", "callout: hyphens"),
        Loss("style-property", "callout: padding"),
    )


def test_every_heading_has_its_outline_level_in_word_counting_from_nought():
    model = model_of(("heading-4", "h"), ("chapter", "c"), ("body", "b"))
    model.styles.add(StyleDef("chapter", "Chapter", "a chapter", "body", {}, heading_level=1))
    data = text_to_docx(model)
    for name, level in (("Heading 4", "3"), ("Chapter", "0")):
        style = word_style(data, name)
        assert style.element.pPr.find(qn("w:outlineLvl")).get(qn("w:val")) == level, name
        assert style.paragraph_format.keep_with_next is True, name
    assert word_style(data, "Normal").element.pPr is None or (
        word_style(data, "Normal").element.pPr.find(qn("w:outlineLvl")) is None
    )


def test_a_heading_that_is_made_body_text_loses_the_outline_level_word_gave_its_style():
    model = model_of(("heading-2", "h"))
    model.styles.set_heading_level("heading-2", "body")
    assert word_style(text_to_docx(model), "Heading 2").element.pPr.find(qn("w:outlineLvl")) is None


def test_word_headings_come_back_as_the_headings_of_the_text():
    model = docx_to_text(text_to_docx(model_of(("heading-3", "c"), ("heading-6", "f"))))
    assert [b.style for b in model.paragraphs] == ["heading-3", "heading-6"]
