"""text_to_docx: a base export, and open suggestions written as native Word tracked changes."""

from __future__ import annotations

from io import BytesIO

import docx

from claudia_composes import DEFAULT_STYLE, Block, Suggestion, TextModel, TextRange
from claudia_composes_io import text_to_docx


def model_with_blocks(*texts: str) -> TextModel:
    blocks = [Block(f"b{i}", DEFAULT_STYLE, text) for i, text in enumerate(texts, start=1)]
    return TextModel(blocks)


def test_paragraphs_keep_their_text_and_order():
    model = model_with_blocks("First paragraph.", "Second paragraph.")
    document = docx.Document(BytesIO(text_to_docx(model)))
    assert [p.text for p in document.paragraphs] == ["First paragraph.", "Second paragraph."]


def test_a_title_block_maps_to_words_title_style():
    model = TextModel([Block("b1", "title", "Claudia")])
    document = docx.Document(BytesIO(text_to_docx(model)))
    style = document.paragraphs[0].style
    assert style is not None and style.name == "Title"


def test_a_custom_style_falls_back_to_normal():
    model = TextModel([Block("b1", "my-custom-style", "Text")])
    document = docx.Document(BytesIO(text_to_docx(model)))
    style = document.paragraphs[0].style
    assert style is not None and style.name == "Normal"


def test_an_open_suggestion_becomes_a_tracked_change_and_the_plain_text_is_gone():
    model = model_with_blocks("The committee rejected the proposal.")
    anchor = TextRange("b1", 14, 22)  # "rejected"
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "rejected", "approved", "tone")
    document = docx.Document(BytesIO(text_to_docx(model)))
    paragraph = document.paragraphs[0]
    # python-docx's own `.text` only looks at runs that are direct children of the paragraph: a tracked word
    # moved under w:ins/w:del is invisible to it, same as the spike found -- this is exactly that behaviour.
    assert paragraph.text == "The committee  the proposal."
    xml = paragraph._p.xml
    assert "<w:delText" in xml and "rejected" in xml
    assert "<w:ins" in xml and "approved" in xml


def test_a_remark_with_no_replacement_is_left_out():
    model = model_with_blocks("Some text here.")
    anchor = TextRange("b1", 0, 4)
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "Some", None, "just a remark")
    document = docx.Document(BytesIO(text_to_docx(model)))
    assert document.paragraphs[0].text == "Some text here."


def test_track_suggestions_false_exports_plain_text():
    model = model_with_blocks("The committee rejected the proposal.")
    anchor = TextRange("b1", 14, 22)
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "rejected", "approved", "tone")
    document = docx.Document(BytesIO(text_to_docx(model, track_suggestions=False)))
    assert document.paragraphs[0].text == "The committee rejected the proposal."


def test_markup_survives_a_python_docx_round_trip():
    model = model_with_blocks("The committee rejected the proposal.")
    anchor = TextRange("b1", 14, 22)
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "rejected", "approved", "tone")
    out = BytesIO(text_to_docx(model))
    document = docx.Document(out)
    resaved = BytesIO()
    document.save(resaved)
    reloaded = docx.Document(resaved)
    xml = reloaded.paragraphs[0]._p.xml
    assert "<w:delText" in xml and "rejected" in xml
    assert "<w:ins" in xml and "approved" in xml
