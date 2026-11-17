"""An imported document starts with one ``core.Import`` entry that carries the state the import made (D438)."""

from claudia_core import Document, Import, MemoryStore, encode, replay
from claudia_core.testing import Insert, ListModel


def imported(state, **extra):
    return Import("numbers.xlsx", "xlsx", state, sha256="ab" * 32, kept=True, **extra)


def test_an_import_puts_its_state_into_the_document_in_one_entry():
    doc = Document(ListModel(), store=MemoryStore())
    doc.execute(imported(ListModel([4, 5, 6]).serialize()), author="ann")
    assert doc.model.items == [4, 5, 6]
    assert [e.command.kind for e in doc.log.path(doc.revision)] == ["core.Import"]


def test_it_is_nobodys_undo_step_and_work_after_it_is():
    doc = Document(ListModel(), store=MemoryStore())
    doc.execute(imported(ListModel([4]).serialize()), author="ann")
    assert not doc.history_for("ann").can_undo
    doc.execute(Insert(1, 9), author="ann")
    doc.undo("ann")
    assert doc.model.items == [4]


def test_the_log_rebuilds_the_imported_state():
    doc = Document(ListModel(), store=MemoryStore())
    doc.execute(imported(ListModel([1, 2]).serialize()), author="ann")
    doc.execute(Insert(0, 7), author="ann")
    again = replay(ListModel(), doc.log.path(doc.revision))
    assert again.serialize() == doc.model.serialize() == ListModel([7, 1, 2]).serialize()


def test_it_survives_the_trip_through_its_stored_form():
    command = imported(ListModel([3]).serialize())
    back = ListModel.registry.decode(encode(command))
    assert back == command
    assert back.label == "Imported numbers.xlsx"


def test_the_inverse_gives_back_the_state_before():
    doc = Document(ListModel([1]), store=MemoryStore())
    applied = doc.execute(imported(ListModel([2]).serialize()), author="ann")
    assert isinstance(applied.inverse, Import) and applied.inverse.state == ListModel([1]).serialize()


def test_an_import_is_blanked_by_its_app_not_by_itself():
    """Only the model knows what in a state is content (D723): without it nothing is taken away, with it all is."""
    command = imported(ListModel([1]).serialize())
    assert command.redacted() is command
    assert command.redacted_in(ListModel) == Import("", "xlsx", {"items": [0]}, None, False)
