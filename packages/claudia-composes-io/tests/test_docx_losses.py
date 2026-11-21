"""docx_import_losses / docx_export_losses: what the model does not show of a docx, and what a docx cannot hold of
the model (D299, D405)."""

from __future__ import annotations

from io import BytesIO

from claudia_composes_io import docx_export_losses, docx_import_losses, text_to_docx
from docx import Document

from claudia_composes import PageSetup, Paragraph, Suggestion, TextModel, TextRange
from claudia_core import ListBook, ListDef, ListItem
from claudia_odf_io import Loss


def saved(document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def test_a_plain_file_has_nothing_the_model_does_not_show():
    document = Document()
    document.add_paragraph("Title", style="Title")
    document.add_paragraph("words")
    assert docx_import_losses(saved(document)) == ()


def test_what_the_model_does_not_show_is_listed_with_how_many():
    document = Document()
    document.add_paragraph("words", style="List Bullet")  # a style the model does not have, and a list it draws its own
    bold = document.add_paragraph().add_run("bold")
    bold.bold = True
    document.add_table(rows=1, cols=2)  # a regular table: the text holds it (E9.32)
    assert docx_import_losses(saved(document)) == (
        Loss("style", "List Bullet", 1),
        Loss("list-look", "", 1),
        Loss("formatting", "", 1),
    )


def test_a_tracked_change_in_the_file_is_listed():
    suggestion = Suggestion("s1", "ada", TextRange("b1", 0, 5), "Hello", "Howdy", "tone")
    model = TextModel([Paragraph("b1", "body", "Hello")])
    model.suggestions["s1"] = suggestion
    assert Loss("tracked-change", "", 2) in docx_import_losses(text_to_docx(model))


def test_a_model_a_docx_holds_whole_has_no_export_losses():
    assert docx_export_losses(TextModel([Paragraph("b1", "title", "x"), Paragraph("b2", "body", "y")])) == ()


def test_a_style_a_docx_cannot_name_is_written_as_normal():
    assert docx_export_losses(TextModel([Paragraph("b1", "my-style", "x")])) == (Loss("style", "my-style", 1),)


def test_authorship_remarks_and_lost_anchors_are_listed():
    model = TextModel([Paragraph("b1", "body", "Hello").written_by("ada")])
    model.suggestions["s1"] = Suggestion("s1", "bob", TextRange("b1", 0, 2), "He", None, "a remark")  # a remark
    model.suggestions["s2"] = Suggestion("s2", "bob", TextRange("b1", 3, 99), "lo", "x", "tone")  # past the text
    assert docx_export_losses(model) == (
        Loss("authorship", "", 1),
        Loss("remark", "", 1),
        Loss("suggestion-anchor", "", 1),
    )


def test_suggestions_are_a_loss_when_tracking_is_off():
    model = TextModel([Paragraph("b1", "body", "Hello")])
    model.suggestions["s1"] = Suggestion("s1", "bob", TextRange("b1", 0, 5), "Hello", "Howdy", "tone")
    assert docx_export_losses(model, track_suggestions=False) == (Loss("suggestion", "", 1),)


def test_what_the_converter_writes_is_no_loss_for_a_fresh_file():
    items = [Paragraph("b1", "body", "one", item=ListItem("l1", 0))]
    model = TextModel(items, lists=ListBook([ListDef("l1", "bullets")]), page=PageSetup.preset("letter"))
    assert docx_export_losses(model) == ()  # the page and the list are written
