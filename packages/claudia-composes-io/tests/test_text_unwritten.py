"""odt_unwritten_changes / docx_unwritten_changes: what changed in a model that the converters do not write (D299).

The facets a converter writes are not losses; the facets it does not write are, when they differ from the state
the export starts from (the baseline of a patch, or an empty text for a fresh file)."""

from __future__ import annotations

from dataclasses import replace

from claudia_composes_io import docx_unwritten_changes, odt_unwritten_changes
from claudia_composes_io._unwritten import text_unwritten_changes

from claudia_composes import PageSetup, Paragraph, TextModel
from claudia_core import ListBook, ListDef, ListItem
from claudia_odf_io import NOT_WRITTEN, Loss

#: A converter that writes the words and nothing else: every other facet that changes is a loss (the converters of
#: today write all the facets of a text but its floating objects, so these tests stand one in for the others).
TEXT_ONLY = frozenset({"paragraphs", "suggestions"})


def a_text(**changes) -> TextModel:
    paragraphs = changes.pop("paragraphs", None) or [
        Paragraph("b1", "body", "Hello"),
        Paragraph("b2", "heading-1", "World"),
    ]
    return TextModel(paragraphs, **changes)


def test_a_model_that_did_not_change_has_no_unwritten_changes():
    before = a_text()
    assert odt_unwritten_changes(a_text(), before) == ()
    assert docx_unwritten_changes(a_text(), before) == ()


def test_edited_words_and_styles_are_written_so_they_are_no_loss():
    before = a_text()
    after = a_text(paragraphs=[Paragraph("b1", "quote", "Hello again"), Paragraph("b3", "body", "New")])
    assert odt_unwritten_changes(after, before) == ()
    assert docx_unwritten_changes(after, before) == ()


def test_authors_of_runs_are_not_a_change_of_the_paragraphs_facet():
    # authorship has its own loss code (odt_export_losses); a different author alone does not make a "paragraphs" loss
    before = a_text()
    after = a_text(
        paragraphs=[Paragraph("b1", "body", "Hello").written_by("ada"), Paragraph("b2", "heading-1", "World")]
    )
    assert odt_unwritten_changes(after, before) == ()


def test_a_changed_page_is_not_written_by_a_converter_that_does_not_write_it():
    losses = text_unwritten_changes(a_text(page=PageSetup.preset("letter")), a_text(), written=TEXT_ONLY)
    assert losses == (Loss(NOT_WRITTEN, "page", 1),)


def test_a_changed_language_is_not_written_by_a_converter_that_does_not_write_it():
    assert text_unwritten_changes(a_text(language="de"), a_text(), written=TEXT_ONLY) == (
        Loss(NOT_WRITTEN, "language", 1),
    )


def test_page_language_styles_and_palette_are_written_to_both_formats():
    after = a_text(language="de", page=PageSetup.preset("letter"))
    after.palette.replace_all(
        [replace(role, colour="#112233") if role.id == "accent" else role for role in after.palette]
    )
    assert odt_unwritten_changes(after, a_text()) == () and docx_unwritten_changes(after, a_text()) == ()


def test_lists_are_written_to_both_formats():
    items = [
        Paragraph("b1", "body", "one", item=ListItem("l1", 0)),
        Paragraph("b2", "body", "two", item=ListItem("l1", 1)),
    ]
    after = a_text(paragraphs=items, lists=ListBook([ListDef("l1", "bullets")]))
    assert odt_unwritten_changes(after, a_text()) == ()
    assert docx_unwritten_changes(after, a_text()) == ()
    assert Loss(NOT_WRITTEN, "lists", 3) in text_unwritten_changes(after, a_text(), written=TEXT_ONLY)


def test_a_fresh_export_compares_with_an_empty_text():
    # no baseline: what differs from a new document is what the file would have to hold
    assert text_unwritten_changes(a_text(), None, written=TEXT_ONLY) == ()
    assert text_unwritten_changes(a_text(language="fr", page=PageSetup.preset("letter")), None, written=TEXT_ONLY) == (
        Loss(NOT_WRITTEN, "page", 1),
        Loss(NOT_WRITTEN, "language", 1),
    )


def test_facets_come_out_in_a_fixed_order():
    after = a_text(language="de", page=PageSetup.preset("letter"))
    assert [loss.detail for loss in text_unwritten_changes(after, a_text(), written=TEXT_ONLY)] == ["page", "language"]
