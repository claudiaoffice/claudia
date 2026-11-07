"""``peek_line``: a read-only look at any line, active or hidden, without switching to it (E3.8).

The preview a person sees before asking to make a line current: it must show exactly what ``switch_to`` would
bring back, and it must touch nothing.
"""

import pytest

from claudia_core import KernelError
from claudia_core.testing import Insert, Remove


@pytest.fixture
def worked(doc):
    doc.execute(Insert(0, 1), author="ana")  # main:1
    doc.execute(Insert(1, 2), author="ben")  # main:2
    doc.save_checkpoint("ana", "good")  # main:3 labels main:2
    doc.execute(Insert(0, 3), author="ben")  # main:4
    doc.execute(Remove(1), author="ana")  # main:5
    return doc


@pytest.fixture
def restored(worked):
    worked.restore_checkpoint(1, author="ana")  # forks restore-1, main becomes hidden
    return worked


def test_peeking_the_active_line_matches_the_live_model(restored):
    assert restored.peek_line("restore-1").serialize() == restored.model.serialize()


def test_peeking_a_hidden_line_shows_its_own_state_undisturbed(restored):
    peeked = restored.peek_line("main")
    assert peeked.items == [3, 2]


def test_peeking_does_not_touch_the_live_model_or_branch(restored):
    before_model, before_branch = restored.model.serialize(), restored.branch
    restored.peek_line("main")
    assert restored.model.serialize() == before_model and restored.branch == before_branch


def test_peeking_does_not_touch_undo_or_checkpoints(restored):
    before_checkpoints = [c.label for c in restored.checkpoints]
    before_can_undo = restored.history_for("ana").can_undo
    restored.peek_line("main")
    assert [c.label for c in restored.checkpoints] == before_checkpoints
    assert restored.history_for("ana").can_undo == before_can_undo


def test_peeking_matches_what_switching_would_bring_back(restored):
    peeked = restored.peek_line("main").serialize()
    restored.switch_to("main", author="ana")
    assert restored.model.serialize() == peeked


def test_an_unknown_line_is_an_error(restored):
    with pytest.raises(KernelError):
        restored.peek_line("nowhere")


def test_peeking_a_line_with_nothing_on_it_gives_the_empty_model(doc):
    assert doc.peek_line("main").serialize() == doc.model.serialize()
