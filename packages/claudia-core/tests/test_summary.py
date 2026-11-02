"""Commands describe themselves in a sentence for the history panel (``Command.summary``)."""

from claudia_core import Batch, CommandApplied
from claudia_core.testing import Insert, Remove


def test_the_default_summary_is_the_label():
    assert Insert(0, 5).summary == Insert(0, 5).label == "Insert 5"


def test_a_batch_names_its_parts_up_to_three_and_counts_the_rest():
    assert Batch((Insert(0, 1),)).summary == "Insert 1"
    assert Batch((Insert(0, 1), Insert(0, 2))).summary == "Insert 1; Insert 2"
    many = Batch(tuple(Insert(0, i) for i in range(5)))
    assert many.summary == "Insert 0; Insert 1; Insert 2; and 2 more"


def test_a_named_batch_keeps_its_name_and_the_parts_are_not_listed():
    assert Batch((Insert(0, 1), Remove(0)), name="Swap").summary == "Swap"


def test_the_applied_event_carries_the_summary(doc):
    seen = []
    doc.subscribe(lambda event: seen.append(event) if isinstance(event, CommandApplied) else None)
    doc.execute(Insert(0, 7), author="ann")
    assert seen[-1].to_data()["summary"] == "Insert 7"
