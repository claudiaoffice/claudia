"""Lists (E9.21): the counting rules, the book of lists, and the commands that change it."""

from __future__ import annotations

from typing import ClassVar, Self

import pytest

from claudia_core import (
    SCHEMES,
    ChangeList,
    CommandRegistry,
    CreateList,
    Document,
    DocumentModel,
    Label,
    ListBook,
    ListDef,
    ListItem,
    ListsChanged,
    MemoryStore,
    Paragraph,
    RemoveList,
    UndoConflict,
    encode,
    new_registry,
    numbering_labels,
)

BULLETS = ListDef("l1", "bullets")
NUMBERS = ListDef("l2", "numbers")


def book(*lists: ListDef) -> ListBook:
    return ListBook(lists or (BULLETS, NUMBERS))


def item(list_id: str, level: int = 0) -> ListItem:
    return ListItem(list_id, level)


def counted(entries: list[tuple[str, ListItem | None]], lists: ListBook | None = None) -> dict[str, str]:
    """Just the markers, by paragraph id."""
    return {k: v.marker for k, v in numbering_labels(entries, lists or book()).items()}


# ----------------------------------------------------------------------------- the item
def test_an_item_round_trips_through_plain_data():
    assert ListItem.from_data(ListItem("l1", 3).to_data()) == ListItem("l1", 3)


@pytest.mark.parametrize("level", [-1, 9, 100])
def test_an_item_has_a_level_from_0_to_8(level):
    with pytest.raises(ValueError, match="level"):
        ListItem("l1", level).check()


def test_a_paragraph_without_an_item_serialises_as_it_always_did():
    """Documents are forever, and creates must not notice lists exist: ``item`` is written only when set."""
    p = Paragraph("b1", "body", "hi")
    assert "item" not in p.to_data()
    assert Paragraph.from_data(p.to_data()) == p


def test_a_paragraph_keeps_its_item_through_plain_data():
    p = Paragraph("b1", "body", "hi", item=ListItem("l1", 2))
    assert p.to_data()["item"] == {"list": "l1", "level": 2}
    assert Paragraph.from_data(p.to_data()) == p


def test_a_paragraph_can_take_an_item_and_give_it_back():
    p = Paragraph("b1", "body", "hi")
    assert p.with_item(ListItem("l1")).item == ListItem("l1")
    assert p.with_item(ListItem("l1")).with_item(None) == p


# ----------------------------------------------------------------------------- the book
def test_a_list_has_a_scheme_a_start_and_may_have_a_name():
    d = ListDef("l1", "numbers", 4, "Steps")
    assert ListDef.from_data(d.to_data()) == d
    assert ListDef("l1", "bullets").name is None
    assert ListDef("l1", "bullets").start == 1


def test_the_book_refuses_what_makes_no_sense():
    b = ListBook()
    with pytest.raises(ValueError, match="scheme"):
        b.add(ListDef("l1", "roman-spirals"))
    with pytest.raises(ValueError, match="id"):
        b.add(ListDef("L 1!", "bullets"))
    with pytest.raises(ValueError, match="start"):
        b.add(ListDef("l1", "numbers", 0))
    with pytest.raises(ValueError, match="name"):
        b.add(ListDef("l1", "numbers", 1, "two\nlines"))
    b.add(BULLETS)
    with pytest.raises(ValueError, match="exists"):
        b.add(BULLETS)


def test_the_book_answers_for_a_list_it_does_not_have_with_a_sentence():
    with pytest.raises(KeyError, match="no list"):
        book().get("nope")


def test_the_book_round_trips_through_plain_data_and_keeps_its_order():
    b = book(NUMBERS, BULLETS)
    assert ListBook.from_data(b.to_data()).ids() == ["l2", "l1"]


def test_the_built_in_schemes_are_bullets_and_numbers():
    assert set(SCHEMES) == {"bullets", "numbers"}
    assert [SCHEMES["bullets"].marker(level, 1) for level in range(4)] == ["•", "◦", "▪", "•"]


# ----------------------------------------------------------------------------- counting
def test_bullets_are_drawn_by_level_and_start_over_after_three():
    entries = [(f"b{n}", item("l1", n)) for n in range(5)]
    assert list(counted(entries).values()) == ["•", "◦", "▪", "•", "◦"]


def test_numbers_count_per_level_and_a_new_parent_starts_its_children_over():
    entries = [
        ("a", item("l2", 0)),
        ("b", item("l2", 1)),
        ("c", item("l2", 1)),
        ("d", item("l2", 0)),
        ("e", item("l2", 1)),
    ]
    assert counted(entries) == {"a": "1.", "b": "a.", "c": "b.", "d": "2.", "e": "a."}


def test_the_label_carries_the_number_trail_for_references_to_come():
    entries = [("a", item("l2", 0)), ("b", item("l2", 1)), ("c", item("l2", 2))]
    labels = numbering_labels(entries, book())
    assert labels["c"] == Label("i.", (1, 1, 1))
    assert numbering_labels([("x", item("l1"))], book())["x"].path is None


def test_an_item_of_another_list_does_not_count_and_does_not_break_the_count():
    entries = [("a", item("l2")), ("x", item("l1")), ("b", item("l2"))]
    assert counted(entries)["b"] == "2."


def test_a_paragraph_between_two_items_of_one_list_does_not_interrupt_it():
    entries = [("a", item("l2")), ("note", None), ("b", item("l2"))]
    assert counted(entries) == {"a": "1.", "b": "2."}


def test_two_neighbouring_lists_never_count_together():
    two = ListDef("l3", "numbers")
    entries = [("a", item("l2")), ("b", item("l2")), ("c", item("l3")), ("d", item("l3"))]
    assert counted(entries, book(NUMBERS, two)) == {"a": "1.", "b": "2.", "c": "1.", "d": "2."}


def test_the_first_level_starts_at_the_lists_start_value():
    entries = [("a", item("l2")), ("b", item("l2", 1)), ("c", item("l2"))]
    started = ListDef("l2", "numbers", 5)
    assert counted(entries, book(started)) == {"a": "5.", "b": "a.", "c": "6."}


def test_a_level_without_a_parent_above_it_starts_at_one_so_nothing_can_fail():
    entries = [("a", item("l2", 2)), ("b", item("l2", 2))]
    labels = numbering_labels(entries, book())
    assert [labels["a"].marker, labels["b"].marker] == ["i.", "ii."]
    assert labels["b"].path == (1, 1, 2)  # the missing parents count as one each


def test_letters_go_on_after_z_and_romans_fall_back_to_digits_after_3999():
    many = [(f"b{n}", item("l2", 1)) for n in range(1, 28)]
    parent = [("p", item("l2", 0))]
    markers = counted(parent + many)
    assert markers["b1"] == "a." and markers["b26"] == "z." and markers["b27"] == "aa."
    deep = [("p", item("l2", 0)), ("q", item("l2", 1))] + [(f"b{n}", item("l2", 2)) for n in range(1, 4)]
    assert counted(deep)["b3"] == "iii."
    big = ListDef("l2", "numbers", 4000)
    assert counted([("a", item("l2", 2))], book(big))["a"] == "i."  # level 2 restarts at one, not at `start`
    assert SCHEMES["numbers"].marker(2, 4000) == "4000."


def test_an_item_of_a_list_the_book_does_not_have_is_left_without_a_label():
    assert numbering_labels([("a", item("ghost"))], book()) == {}


# ----------------------------------------------------------------------------- commands
class Listed(DocumentModel):
    """A model that is only a book of lists, plus the one question the commands ask of an app."""

    app: ClassVar[str] = "test-listed"
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.lists = ListBook()
        self.in_use: set[str] = set()

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"lists": self.lists.to_data()}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.lists = ListBook.from_data(state["lists"])
        return model

    def list_in_use(self, list_id: str) -> bool:
        return list_id in self.in_use


@pytest.fixture
def paper():
    return Document(Listed(), store=MemoryStore())


def seen(doc):
    events = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, ListsChanged) else None)
    return events


def test_creating_a_list_tells_the_clients_all_lists_and_undo_takes_it_back(paper):
    events = seen(paper)
    paper.execute(CreateList(NUMBERS), author="ann")
    assert paper.model.lists.get("l2") == NUMBERS
    (event,) = events
    assert event.to_data() == {"type": "lists", "lists": [NUMBERS.to_data()]}
    paper.undo("ann")
    assert "l2" not in paper.model.lists
    assert events[-1].to_data()["lists"] == []
    paper.redo("ann")
    assert "l2" in paper.model.lists


def test_a_list_cannot_be_taken_back_while_an_item_uses_it(paper):
    paper.execute(CreateList(NUMBERS), author="ann")
    paper.model.in_use.add("l2")  # a colleague made an item in the meantime
    with pytest.raises(UndoConflict, match="in use"):
        paper.undo("ann")
    assert "l2" in paper.model.lists


def test_changing_a_list_swaps_its_definition_and_undo_restores_the_old_one(paper):
    paper.execute(CreateList(NUMBERS), author="ann")
    paper.execute(ChangeList(ListDef("l2", "numbers", 3, "Steps")), author="ann")
    assert paper.model.lists.get("l2") == ListDef("l2", "numbers", 3, "Steps")
    paper.undo("ann")
    assert paper.model.lists.get("l2") == NUMBERS


def test_a_change_with_an_unknown_list_or_a_bad_value_changes_nothing(paper):
    before = paper.model.serialize()
    with pytest.raises(ValueError, match="no list"):
        paper.execute(ChangeList(ListDef("ghost", "numbers")), author="ann")
    paper.execute(CreateList(NUMBERS), author="ann")
    with pytest.raises(ValueError, match="scheme"):
        paper.execute(ChangeList(ListDef("l2", "wavy")), author="ann")
    assert paper.model.lists.get("l2") == NUMBERS and before == {"lists": []}


def test_undo_never_overwrites_a_colleagues_change_of_the_same_list(paper):
    paper.execute(CreateList(NUMBERS), author="ann")
    paper.execute(ChangeList(ListDef("l2", "numbers", 3)), author="ann")
    paper.execute(ChangeList(ListDef("l2", "numbers", 7)), author="ben")
    with pytest.raises(UndoConflict):
        paper.undo("ann")
    assert paper.model.lists.get("l2").start == 7


def test_undo_goes_through_when_a_colleague_changed_another_list(paper):
    paper.execute(CreateList(NUMBERS), author="ann")
    paper.execute(CreateList(BULLETS), author="ann")
    paper.execute(ChangeList(ListDef("l2", "numbers", 3)), author="ann")
    paper.execute(ChangeList(ListDef("l1", "bullets", 1, "Dots")), author="ben")
    paper.undo("ann")
    assert paper.model.lists.get("l2") == NUMBERS and paper.model.lists.get("l1").name == "Dots"


def test_the_history_says_what_happened():
    assert CreateList(ListDef("l2", "numbers")).summary == "started a numbered list"
    assert CreateList(ListDef("l1", "bullets")).summary == "started a bulleted list"
    assert ChangeList(ListDef("l2", "numbers", 3)).summary == "changed the list l2"
    assert RemoveList("l2").summary == "took back the list l2"


def test_the_commands_survive_a_trip_through_the_log(paper):
    registry = new_registry()
    for command in (CreateList(NUMBERS), RemoveList("l2"), ChangeList(ListDef("l2", "numbers", 3, "Steps"))):
        assert registry.decode(encode(command)) == command


def test_replaying_the_log_gives_the_same_book(paper):
    paper.execute(CreateList(NUMBERS), author="ann")
    paper.execute(ChangeList(ListDef("l2", "numbers", 3, "Steps")), author="ben")
    paper.execute(CreateList(BULLETS), author="ann")
    paper.undo("ann")
    rebuilt = paper.materialize(paper.revision)
    assert rebuilt.serialize() == paper.model.serialize()


def test_the_models_requirement_is_clear_when_it_has_no_book_of_lists():
    from claudia_core.testing import ListModel

    doc = Document(ListModel(), store=MemoryStore())
    with pytest.raises(TypeError, match="book of lists"):
        doc.execute(CreateList(NUMBERS), author="ann")


def test_the_book_counts_its_changes_so_that_what_is_derived_from_it_knows_when_to_derive_again():
    b = ListBook()
    seen = [b.version]
    b.add(NUMBERS)
    seen.append(b.version)
    b.replace(ListDef("l2", "numbers", 3))
    seen.append(b.version)
    b.remove("l2")
    seen.append(b.version)
    assert seen == [0, 1, 2, 3]
