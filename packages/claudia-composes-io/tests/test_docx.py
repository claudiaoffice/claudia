"""text_to_docx/docx_to_text: a base export and import, and open suggestions as native Word tracked changes."""

from __future__ import annotations

from io import BytesIO

import docx
import pytest
from claudia_composes_io import UnsupportedEdit, apply_edits_to_docx, docx_to_text, text_to_docx

from claudia_composes import DEFAULT_STYLE, Block, Suggestion, TextModel, TextRange


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


def _docx_bytes(document: docx.Document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def test_docx_to_text_imports_paragraphs_in_order():
    document = docx.Document()
    document.add_paragraph("First.")
    document.add_paragraph("Second.")
    model = docx_to_text(_docx_bytes(document))
    assert [b.id for b in model.blocks] == ["b1", "b2"]
    assert [b.text for b in model.blocks] == ["First.", "Second."]


def test_docx_to_text_maps_a_built_in_style_back_to_claudias_id():
    document = docx.Document()
    document.add_paragraph("Claudia", style="Title")
    model = docx_to_text(_docx_bytes(document))
    assert model.blocks[0].style == "title"


def test_docx_to_text_falls_back_to_default_style_for_normal_and_unmapped_styles():
    document = docx.Document()
    document.add_paragraph("Plain text.")  # Word's own default is "Normal"
    document.add_paragraph("A bullet.", style="List Bullet")  # a real style, just not one _WORD_STYLE knows
    model = docx_to_text(_docx_bytes(document))
    assert model.blocks[0].style == DEFAULT_STYLE
    assert model.blocks[1].style == DEFAULT_STYLE


def test_docx_to_text_round_trips_through_text_to_docx():
    original = TextModel(
        [
            Block("b1", "title", "Claudia"),
            Block("b2", "heading-1", "Introduction"),
            Block("b3", DEFAULT_STYLE, "Body text."),
        ]
    )
    model = docx_to_text(text_to_docx(original))
    assert [(b.style, b.text) for b in model.blocks] == [
        ("title", "Claudia"),
        ("heading-1", "Introduction"),
        (DEFAULT_STYLE, "Body text."),
    ]


def test_docx_to_text_on_a_fresh_document_imports_its_one_default_empty_paragraph():
    # python-docx's own blank template already has one paragraph (empty, "Normal"); there is no zero-paragraph
    # case to import, so this is what "empty document" actually means.
    model = docx_to_text(_docx_bytes(docx.Document()))
    assert [(b.style, b.text, b.runs) for b in model.blocks] == [(DEFAULT_STYLE, "", ())]


def test_apply_edits_patches_only_the_changed_paragraph_and_preserves_a_table():
    document = docx.Document()
    document.add_paragraph("First paragraph.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "A"
    table.rows[0].cells[1].text = "B"
    document.add_paragraph("Second paragraph.")
    original_bytes = _docx_bytes(document)

    baseline = docx_to_text(original_bytes)
    current = TextModel(
        [
            Block("b1", baseline.blocks[0].style, "Edited first paragraph."),
            Block("b2", baseline.blocks[1].style, baseline.blocks[1].text),
        ]
    )

    out = apply_edits_to_docx(original_bytes, baseline, current)
    reopened = docx.Document(BytesIO(out))
    assert reopened.paragraphs[0].text == "Edited first paragraph."
    assert reopened.paragraphs[1].text == "Second paragraph."
    assert reopened.tables[0].rows[0].cells[0].text == "A"
    assert reopened.tables[0].rows[0].cells[1].text == "B"


def test_apply_edits_changes_a_blocks_style():
    document = docx.Document()
    document.add_paragraph("Body text.")
    original_bytes = _docx_bytes(document)

    baseline = docx_to_text(original_bytes)
    current = TextModel([Block("b1", "heading-1", baseline.blocks[0].text)])

    out = apply_edits_to_docx(original_bytes, baseline, current)
    reopened = docx.Document(BytesIO(out))
    style = reopened.paragraphs[0].style
    assert style is not None and style.name == "Heading 1"


def test_apply_edits_renders_a_new_open_suggestion_as_a_tracked_change():
    document = docx.Document()
    document.add_paragraph("The committee rejected the proposal.")
    original_bytes = _docx_bytes(document)

    baseline = docx_to_text(original_bytes)
    current = TextModel([Block("b1", baseline.blocks[0].style, baseline.blocks[0].text)])
    anchor = TextRange("b1", 14, 22)  # "rejected"
    current.suggestions["s1"] = Suggestion("s1", "Claudia AI", anchor, "rejected", "approved", "tone")

    out = apply_edits_to_docx(original_bytes, baseline, current)
    reopened = docx.Document(BytesIO(out))
    xml = reopened.paragraphs[0]._p.xml
    assert "<w:delText" in xml and "rejected" in xml
    assert "<w:ins" in xml and "approved" in xml


def test_apply_edits_raises_unsupported_edit_when_a_block_is_added():
    document = docx.Document()
    document.add_paragraph("Only paragraph.")
    original_bytes = _docx_bytes(document)

    baseline = docx_to_text(original_bytes)
    current = TextModel([*baseline.blocks, Block("b2", DEFAULT_STYLE, "A new paragraph.")])

    with pytest.raises(UnsupportedEdit):
        apply_edits_to_docx(original_bytes, baseline, current)


def test_apply_edits_raises_unsupported_edit_when_a_block_is_removed():
    document = docx.Document()
    document.add_paragraph("First.")
    document.add_paragraph("Second.")
    original_bytes = _docx_bytes(document)

    baseline = docx_to_text(original_bytes)
    current = TextModel([baseline.blocks[0]])

    with pytest.raises(UnsupportedEdit):
        apply_edits_to_docx(original_bytes, baseline, current)


# -- when a tracked change was made (D411) ---------------------------------------------------------------------------
def suggestion_text() -> TextModel:
    model = model_with_blocks("The committee rejected the proposal.")
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 14, 22), "rejected", "approved", "tone")
    return model


def dates_in(data: bytes) -> list[str]:
    import re

    xml = docx.Document(BytesIO(data)).paragraphs[0]._p.xml
    return re.findall(r'w:date="([^"]*)"', xml)


def test_a_tracked_change_has_the_time_its_suggestion_was_made():
    data = text_to_docx(suggestion_text(), change_times={"s1": "2026-11-10T09:30:00+01:00"})
    assert dates_in(data) == ["2026-11-10T08:30:00Z"] * 2


def test_a_tracked_change_without_a_known_time_has_no_date():
    assert dates_in(text_to_docx(suggestion_text())) == []


def test_apply_edits_dates_a_tracked_change_too():
    document = docx.Document()
    document.add_paragraph("The committee rejected the proposal.")
    original_bytes = _docx_bytes(document)
    baseline = docx_to_text(original_bytes)
    current = TextModel([Block("b1", baseline.blocks[0].style, baseline.blocks[0].text)])
    current.suggestions["s1"] = suggestion_text().suggestions["s1"]
    out = apply_edits_to_docx(original_bytes, baseline, current, change_times={"s1": "2026-11-10T08:30:00Z"})
    assert dates_in(out) == ["2026-11-10T08:30:00Z"] * 2
