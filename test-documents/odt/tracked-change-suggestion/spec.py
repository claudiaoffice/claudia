"""An open suggestion added in claudia is written as a real OpenDocument tracked change -- a deletion and an
insertion in ``text:tracked-changes`` and their marks in the text -- that a reviewer accepts or rejects in
LibreOffice (checked there by hand, see the implementation note). The paragraph then reads as the replacement; the
deleted word is kept in the change, not in the text."""

from __future__ import annotations

from claudia_composes import Suggestion, TextModel, TextRange
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [("body", "The committee rejected the proposal.")]


def modify(model: TextModel) -> TextModel:
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 14, 22), "rejected", "approved", "tone")
    return model


def after_checks(model: TextModel) -> None:
    assert model.blocks[0].text == "The committee approved the proposal."


def export_checks(edited: bytes) -> None:
    content = read_parts(edited)["content.xml"].decode()
    assert "<text:deletion>" in content and "<text:insertion>" in content
    assert "<dc:creator>Claudia AI</dc:creator>" in content
    assert '<text:p text:style-name="Standard">rejected</text:p>' in content  # the deleted word, inside its change
    assert "<text:change-start " in content and "<text:change-end " in content and "<text:change " in content


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, export_checks=export_checks)
