"""A sheet and a named range can be described (D1317, D1318): a plain string beside the name, by id."""

import pytest
from names_helpers import name

from claudia_computes import AddSheet, DefineName, NamedRange, WorkbookModel
from claudia_core import DescribeThing, Document, MemoryStore, ThingDescribed


@pytest.fixture
def book():
    doc = Document(WorkbookModel(), store=MemoryStore())
    doc.execute(AddSheet("s1", "Budget"), author="ann")
    return doc


def test_a_sheet_is_described_told_and_undone(book):
    events: list = []
    book.subscribe(lambda e: events.append(e) if isinstance(e, ThingDescribed) else None)
    book.execute(DescribeThing("s1", "Q4 plan"), author="ann")
    assert book.model.thing_description("s1") == "Q4 plan"
    assert events == [ThingDescribed("s1", "Q4 plan")]
    book.undo("ann")
    assert book.model.thing_description("s1") == ""


def test_a_description_survives_a_snapshot_and_a_state_from_before_descriptions(book):
    book.execute(DescribeThing("s1", "kept"), author="ann")
    state = book.model.serialize()
    assert WorkbookModel.restore(state).thing_description("s1") == "kept"
    del state["descriptions"]
    assert WorkbookModel.restore(state).thing_description("s1") == ""


def test_a_named_range_is_described_by_its_id_and_keeps_the_words_through_a_rename(book):
    named = NamedRange("Rates", None, name("Rates", "A1:A3").range, id="rrates001")
    book.execute(DefineName(named), author="ann")
    book.execute(DescribeThing("rrates001", "the tax rates"), author="ann")
    book.execute(book.model.rename_command("rrates001", "TaxRates"), author="ann")
    assert book.model.thing_name("rrates001") == "TaxRates"
    assert book.model.thing_description("rrates001") == "the tax rates"


def test_a_sheet_is_renamed_by_rename_thing_and_a_range_by_rename_name(book):
    from claudia_core import RenameThing

    assert book.model.rename_command("s1", "Plan") == RenameThing("s1", "Plan")


def test_nothing_is_described_that_is_not_there(book):
    with pytest.raises(ValueError, match="nothing with the id"):
        book.execute(DescribeThing("nope", "x"), author="ann")
