"""E1.7: File > Save makes a named checkpoint. (Restoring one forks: see test_restore_fork.py.)"""

from claudia_core import CheckpointSaved, Revision
from claudia_core.testing import Insert


def test_save_labels_the_current_state(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Insert(0, 2), author="ana")
    info = doc.save_checkpoint("ana", "first draft")
    assert (info.number, info.label, info.author) == (1, "first draft", "ana")
    assert info.marks == Revision("main", 2) and info.entry == Revision("main", 3)
    assert doc.checkpoints == (info,)
    assert doc.log.get(info.entry).command.kind == "core.Checkpoint"


def test_default_label_is_numbered(doc):
    doc.execute(Insert(0, 1))
    assert doc.save_checkpoint().label == "Checkpoint 1"
    doc.execute(Insert(0, 1))
    assert doc.save_checkpoint().label == "Checkpoint 2"


def test_an_unchanged_document_makes_no_empty_checkpoint(doc):
    assert doc.save_checkpoint() is None  # nothing ever happened
    doc.execute(Insert(0, 1))
    assert doc.save_checkpoint() is not None
    assert doc.save_checkpoint() is None  # nothing since
    assert len(doc.checkpoints) == 1
    assert doc.revision == Revision("main", 2)  # and no entry was written for the refused ones


def test_a_checkpoint_is_nobodys_undo_step(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.save_checkpoint("ana")
    doc.undo("ana")
    assert doc.model.items == []  # undo went past the checkpoint to ana's edit


def test_event(doc):
    got = []
    doc.subscribe(lambda e: got.append(e) if isinstance(e, CheckpointSaved) else None)
    doc.execute(Insert(0, 1))
    doc.save_checkpoint("ana", "x")
    assert got[0].label == "x" and got[0].number == 1


def test_a_checkpoint_does_not_move_the_state_revision(doc):
    doc.execute(Insert(0, 1), author="ana")
    doc.save_checkpoint("ana")
    assert doc.state_revision == Revision("main", 1) and doc.revision == Revision("main", 2)
