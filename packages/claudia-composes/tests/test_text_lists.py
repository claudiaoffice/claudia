"""Lists in a text (E9.21): items are paragraphs with a list and a level, markers are derived and told to clients."""

import pytest
from composes_helpers import texts

from claudia_composes import (
    InsertText,
    ItemChanged,
    JoinBlocks,
    LabelsChanged,
    SetListItem,
    SplitBlock,
    TextModel,
)
from claudia_composes.region import TextRange
from claudia_core import (
    Batch,
    CreateList,
    Document,
    ListDef,
    ListItem,
    ListsChanged,
    MemoryStore,
    RegionHeld,
    UndoConflict,
)

NUMBERS = ListDef("l1", "numbers")
BULLETS = ListDef("l2", "bullets")


@pytest.fixture
def listed(clock):
    """Three paragraphs, b1..b3, and the two lists ``l1`` (numbers) and ``l2`` (bullets) in the book."""
    d = Document(TextModel(), store=MemoryStore(), clock=clock.time, lock_clock=clock.lock_time)
    d.execute(InsertText("b1", 0, "one"), author="ann")
    d.execute(SplitBlock("b1", 3, "b2", "body"), author="ann")
    d.execute(InsertText("b2", 0, "two"), author="ann")
    d.execute(SplitBlock("b2", 3, "b3", "body"), author="ann")
    d.execute(InsertText("b3", 0, "three"), author="ann")
    d.execute(CreateList(NUMBERS), author="ann")
    d.execute(CreateList(BULLETS), author="ann")
    return d


def collect(doc, *types):
    events: list = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, types) else None)
    return events


def markers(doc):
    return {b: label.marker for b, label in doc.model.labels().items()}


# ----------------------------------------------------------------------------- the command
def test_making_a_paragraph_an_item_tells_the_clients_the_item_and_its_label(listed):
    events = collect(listed, ItemChanged, LabelsChanged)
    listed.execute(SetListItem("b1", ListItem("l1", 0)), author="ann")
    assert listed.model.block("b1").item == ListItem("l1", 0)
    item, labels = events
    assert item.to_data() == {"type": "item", "block": "b1", "item": {"list": "l1", "level": 0}}
    assert labels.to_data() == {"type": "labels", "labels": {"b1": {"marker": "1.", "path": [1]}}}


def test_undo_gives_the_paragraph_its_old_item_back_and_the_label_goes(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    events = collect(listed, ItemChanged, LabelsChanged)
    listed.undo("ann")
    assert listed.model.block("b1").item is None
    assert [e.to_data() for e in events] == [
        {"type": "item", "block": "b1", "item": None},
        {"type": "labels", "labels": {"b1": None}},
    ]
    listed.redo("ann")
    assert listed.model.block("b1").item == ListItem("l1")


def test_an_item_needs_a_list_the_document_has_and_a_level_that_exists(listed):
    for bad, match in ((ListItem("ghost"), "no list"), (ListItem("l1", 9), "level")):
        with pytest.raises(ValueError, match=match):
            listed.execute(SetListItem("b1", bad), author="ann")
    with pytest.raises(KeyError):
        listed.execute(SetListItem("b9", ListItem("l1")), author="ann")
    assert listed.model.block("b1").item is None


def test_the_history_says_what_happened():
    assert SetListItem("b1", ListItem("l1", 1)).summary == "list item, level 2"
    assert SetListItem("b1", None).summary == "no longer a list item"


def test_the_command_survives_a_trip_through_the_log():
    from claudia_core import encode

    for command in (SetListItem("b1", ListItem("l1", 3)), SetListItem("b1", None)):
        assert TextModel.registry.decode(encode(command)) == command


# ----------------------------------------------------------------------------- counting is told, not guessed
def test_only_the_labels_that_changed_are_told(listed):
    for block in ("b1", "b2", "b3"):
        listed.execute(SetListItem(block, ListItem("l1")), author="ann")
    assert markers(listed) == {"b1": "1.", "b2": "2.", "b3": "3."}
    events = collect(listed, LabelsChanged)
    listed.execute(SetListItem("b1", None), author="ann")  # the others count one less
    (event,) = events
    assert event.to_data()["labels"] == {
        "b1": None,
        "b2": {"marker": "1.", "path": [1]},
        "b3": {"marker": "2.", "path": [2]},
    }


def test_typing_changes_no_label_and_so_tells_nothing(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    events = collect(listed, LabelsChanged)
    listed.execute(InsertText("b1", 0, "x"), author="ann")
    assert events == []


def test_changing_a_list_renumbers_its_items(listed):
    from claudia_core import ChangeList

    for block in ("b1", "b2"):
        listed.execute(SetListItem(block, ListItem("l1")), author="ann")
    listed.execute(ChangeList(ListDef("l1", "numbers", 5, "Steps")), author="ann")
    assert markers(listed) == {"b1": "5.", "b2": "6."}
    listed.execute(ChangeList(ListDef("l1", "bullets")), author="ann")
    assert markers(listed) == {"b1": "•", "b2": "•"}


def test_a_failed_command_tells_nothing_and_changes_nothing(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    events = collect(listed, ItemChanged, LabelsChanged)
    with pytest.raises(ValueError, match="no list"):
        listed.execute(Batch((SetListItem("b2", ListItem("l1")), SetListItem("b3", ListItem("ghost")))), author="ann")
    assert events == [] and listed.model.block("b2").item is None
    assert markers(listed) == {"b1": "1."}


# ----------------------------------------------------------------------------- split and join
def test_enter_in_an_item_makes_another_item_of_the_same_list_and_level(listed):
    listed.execute(SetListItem("b1", ListItem("l1", 1)), author="ann")
    listed.execute(SplitBlock("b1", 1, "b4", "body"), author="ann")
    assert listed.model.block("b4").item == ListItem("l1", 1)
    assert texts(listed)[:2] == ["o", "ne"]
    assert markers(listed) == {"b1": "a.", "b4": "b."}  # no level-0 item above them: the missing parent counts as one


def test_undoing_a_split_takes_the_new_item_and_its_label_away(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SplitBlock("b1", 1, "b4", "body"), author="ann")
    listed.undo("ann")
    assert "b4" not in [b.id for b in listed.model.blocks]
    assert markers(listed) == {"b1": "1."}


def test_a_join_keeps_the_item_of_the_first_paragraph(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SetListItem("b2", ListItem("l2")), author="ann")
    listed.execute(JoinBlocks("b2", "b1", 3), author="ann")
    assert listed.model.block("b1").item == ListItem("l1")
    assert markers(listed) == {"b1": "1."}


def test_undoing_a_join_brings_the_removed_paragraphs_own_item_back(listed):
    listed.execute(SetListItem("b2", ListItem("l2", 2)), author="ann")  # b1 is no item, b2 is
    listed.execute(JoinBlocks("b2", "b1", 3), author="ann")
    assert listed.model.block("b1").item is None
    listed.undo("ann")
    assert [b.item for b in listed.model.blocks[:2]] == [None, ListItem("l2", 2)]
    assert markers(listed) == {"b2": "▪"}


def test_a_join_that_changes_nothing_about_the_item_has_the_plain_inverse(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SetListItem("b2", ListItem("l1")), author="ann")
    applied = listed.execute(JoinBlocks("b2", "b1", 3), author="ann")
    assert isinstance(applied.inverse, SplitBlock)


def test_undoing_a_change_of_an_item_that_was_joined_away_is_refused(listed):
    listed.execute(SetListItem("b2", ListItem("l1")), author="ann")
    listed.execute(JoinBlocks("b2", "b1", 3), author="ben")
    with pytest.raises(UndoConflict):
        listed.undo("ann")


def test_undoing_the_creation_of_a_list_is_refused_while_an_item_uses_it(listed):
    listed.execute(SetListItem("b1", ListItem("l2")), author="ben")  # ann's last step made the list l2
    with pytest.raises(UndoConflict, match="in use"):
        listed.undo("ann")
    assert "l2" in listed.model.lists


def test_a_list_in_use_is_known_to_the_model(listed):
    assert not listed.model.list_in_use("l1")
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    assert listed.model.list_in_use("l1") and not listed.model.list_in_use("l2")


# ----------------------------------------------------------------------------- colleagues
def test_a_colleagues_zone_keeps_an_item_change_out(listed):
    listed.lock("ben", [TextRange("b1", 0, 2)], ttl=5)
    with pytest.raises(RegionHeld):
        listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SetListItem("b2", ListItem("l1")), author="ann")  # elsewhere is free


# ----------------------------------------------------------------------------- state
def test_items_and_lists_are_part_of_the_state_and_come_back(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SetListItem("b2", ListItem("l1", 1)), author="ann")
    state = listed.model.serialize()
    assert state["lists"] == [NUMBERS.to_data(), BULLETS.to_data()]
    again = TextModel.restore(state)
    assert again.serialize() == state
    assert {b: label.marker for b, label in again.labels().items()} == {"b1": "1.", "b2": "a."}


def test_replaying_the_log_gives_the_same_items_and_lists(listed):
    listed.execute(SetListItem("b1", ListItem("l1")), author="ann")
    listed.execute(SplitBlock("b1", 1, "b4", "body"), author="ann")
    listed.execute(JoinBlocks("b4", "b1", 1), author="ben")
    listed.undo("ben")
    rebuilt = listed.materialize(listed.revision)
    assert rebuilt.serialize() == listed.model.serialize()


def test_the_clients_hear_of_the_lists_too(listed):
    events = collect(listed, ListsChanged)
    listed.execute(CreateList(ListDef("l3", "numbers", 1, "Steps")), author="ann")
    assert events[-1].to_data()["lists"][-1] == {"id": "l3", "scheme": "numbers", "start": 1, "name": "Steps"}
