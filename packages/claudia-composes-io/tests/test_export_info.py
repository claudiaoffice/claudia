"""export_info: what the command log says about when a document was made and changed (D411)."""

from __future__ import annotations

from claudia_composes_io import export_info

from claudia_composes import InsertText, ProposeSuggestion, TextModel
from claudia_core import Batch, Document, MemoryStore


def a_document() -> Document:
    return Document(TextModel(), store=MemoryStore())


def type_text(document: Document, text: str, author: str, time: str) -> None:
    document.execute(InsertText("b1", len(document.model.blocks[0].text), text), author=author, time=time)


def propose(document: Document, suggestion_id: str, author: str, time: str) -> ProposeSuggestion:
    command = ProposeSuggestion(suggestion_id, "b1", 0, 3, "one", "1", "")
    document.execute(command, author=author, time=time)
    return command


def test_an_empty_log_knows_nothing():
    info, times = export_info(a_document().log)
    assert (info.created, info.modified, info.creator, info.modifier) == (None, None, None, None)
    assert times == {}


def test_a_document_was_made_with_its_first_change_and_last_changed_with_its_last():
    document = a_document()
    type_text(document, "one two", "Ann", "2026-01-02T03:04:05Z")
    type_text(document, " three", "Bob", "2026-11-11T17:13:05Z")
    info, _ = export_info(document.log)
    assert (info.created, info.creator) == ("2026-01-02T03:04:05Z", "Ann")
    assert (info.modified, info.modifier) == ("2026-11-11T17:13:05Z", "Bob")


def test_a_suggestion_was_made_when_it_was_proposed():
    document = a_document()
    type_text(document, "one two", "Ann", "2026-01-02T03:04:05Z")
    propose(document, "s1", "Claudia AI", "2026-03-04T05:06:07Z")
    type_text(document, "!", "Ann", "2026-04-05T06:07:08Z")
    assert export_info(document.log)[1] == {"s1": "2026-03-04T05:06:07Z"}


def test_a_suggestion_proposed_inside_a_batch_is_found_too():
    document = a_document()
    type_text(document, "one two", "Ann", "2026-01-02T03:04:05Z")
    inner = ProposeSuggestion("s9", "b1", 0, 3, "one", "1", "")
    document.execute(Batch((inner,)), author="Claudia AI", time="2026-05-06T07:08:09Z")
    assert export_info(document.log)[1] == {"s9": "2026-05-06T07:08:09Z"}


def test_the_line_in_use_decides_not_the_other_branches():
    document = a_document()
    type_text(document, "one two", "Ann", "2026-01-02T03:04:05Z")
    first = document.log.head(document.branch)
    propose(document, "s1", "Claudia AI", "2026-03-04T05:06:07Z")
    document.log.fork("other", first)
    document.log.activate("other")
    assert export_info(document.log, "other")[1] == {}
