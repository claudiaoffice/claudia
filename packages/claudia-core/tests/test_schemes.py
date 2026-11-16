"""Numbering schemes as document data (E9.22, step D): levels, the built-ins, the book and its commands; numbered
heading styles; list items on any paragraph."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar, Self

import pytest

from claudia_core import (
    NO_NUMBERING,
    ChangeScheme,
    CommandRegistry,
    CreateList,
    CreateScheme,
    Document,
    DocumentModel,
    LevelFormat,
    ListBook,
    ListDef,
    ListItem,
    MemoryStore,
    RemoveList,
    RemoveScheme,
    Scheme,
    SchemeBook,
    SchemesChanged,
    SetListItem,
    SetStyleNumbering,
    StyleBook,
    StyleDef,
    UndoConflict,
    builtin_scheme,
    builtin_schemes,
    encode,
    new_registry,
)


def chapters() -> Scheme:
    scheme = builtin_scheme("chapters")
    assert scheme is not None
    return scheme


# ----------------------------------------------------------------------------- a level and a scheme
def test_the_built_in_schemes_draw_what_lists_have_always_drawn_and_chapters_draws_the_whole_trail():
    numbers, bullets = builtin_scheme("numbers"), builtin_scheme("bullets")
    assert numbers is not None and bullets is not None
    assert [numbers.marker((2,)), numbers.marker((2, 1)), numbers.marker((2, 1, 4))] == ["2.", "a.", "iv."]
    assert [bullets.marker((1,)), bullets.marker((1, 1)), bullets.marker((1, 1, 1))] == ["•", "◦", "▪"]
    assert [chapters().marker((2,)), chapters().marker((2, 3)), chapters().marker((2, 3, 1))] == ["2", "2.3", "2.3.1"]


def test_the_number_a_reference_prints_is_the_whole_trail_without_the_text_around_it():
    numbers = builtin_scheme("numbers")
    assert numbers is not None
    assert numbers.number((2, 2)) == "2.b"
    titled = replace(chapters(), levels=(LevelFormat("upper-roman", before="Part ", after=":"), *chapters().levels[1:]))
    assert (titled.marker((4,)), titled.number((4, 2))) == ("Part IV:", "IV.2")


@pytest.mark.parametrize(
    ("level", "path", "marker"),
    [
        (LevelFormat("upper-alpha", after=")"), (28,), "AB)"),
        (LevelFormat("lower-roman", from_level=1), (3, 9), "ix"),
        (LevelFormat("decimal", before="§ ", from_level=0), (3, 9), "§ 3.9"),
        (LevelFormat("bullet", "–"), (5,), "–"),
        (LevelFormat("none", after=" "), (5,), " "),
    ],
)
def test_a_level_writes_its_counters_its_bullet_or_nothing_between_its_text(level, path, marker):
    levels = list(chapters().levels)
    levels[len(path) - 1] = level
    assert replace(chapters(), levels=tuple(levels)).marker(path) == marker


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"id": "Big Scheme"}, "id"),
        ({"name": " "}, "name"),
        ({"kind": "stars"}, "bullet or a number"),
        ({"levels": chapters().levels[:3]}, "9 levels"),
        ({"indent": 11}, "indent"),
        ({"gap": -1}, "gap"),
        ({"levels": (LevelFormat("cuneiform"), *chapters().levels[1:])}, "format"),
        ({"levels": (LevelFormat("bullet", ""), *chapters().levels[1:])}, "bullet"),
        ({"levels": (LevelFormat(before="x" * 21), *chapters().levels[1:])}, "before and after"),
        ({"levels": (LevelFormat(from_level=1), *chapters().levels[1:])}, "shows the levels"),
    ],
)
def test_a_scheme_that_makes_no_sense_is_refused_with_a_sentence(change, message):
    with pytest.raises(ValueError, match=message):
        replace(chapters(), **change).check()


def test_schemes_round_trip_through_plain_data():
    for scheme in builtin_schemes():
        assert Scheme.from_data(scheme.to_data()) == scheme
    book = SchemeBook()
    assert SchemeBook.from_data(book.to_data()).to_data() == book.to_data()


def test_a_new_book_and_a_document_from_before_schemes_have_the_built_in_ones():
    assert SchemeBook().ids() == ["bullets", "numbers", "chapters"]
    assert SchemeBook.from_data(None).ids() == ["bullets", "numbers", "chapters"]
    assert SchemeBook.from_data([]).ids() == []


def test_the_book_counts_its_changes_and_finds_a_free_id():
    book = SchemeBook()
    version = book.version
    book.add(replace(chapters(), id=book.unique_id(), name="Mine"))
    assert book.ids()[-1] == "scheme-1" and book.unique_id() == "scheme-2"
    book.replace(replace(book.get("scheme-1"), gap=1))
    book.remove("scheme-1")
    assert book.version == version + 3
    with pytest.raises(KeyError, match="no list scheme"):
        book.get("scheme-1")


# ----------------------------------------------------------------------------- the commands
class Numbered(DocumentModel):
    """A model with the books a numbered text has, and paragraphs by id."""

    app: ClassVar[str] = "test-numbered"
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.lists = ListBook()
        self.schemes = SchemeBook()
        self.styles = StyleBook([StyleDef("body", "Body", "", None, {}), StyleDef("h1", "Heading 1", "", "body", {})])
        self.items: dict[str, ListItem | None] = {"p1": None, "p2": None}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {
            "lists": self.lists.to_data(),
            "schemes": self.schemes.to_data(),
            "styles": self.styles.to_data(),
            "items": {k: None if v is None else v.to_data() for k, v in self.items.items()},
        }

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.lists = ListBook.from_data(state["lists"])
        model.schemes = SchemeBook.from_data(state["schemes"])
        model.styles = StyleBook.from_data(state["styles"])
        model.items = {k: None if v is None else ListItem.from_data(v) for k, v in state["items"].items()}
        return model

    def item_of(self, paragraph_id: str) -> ListItem | None:
        return self.items[paragraph_id]

    def put_item(self, paragraph_id: str, item: ListItem | None) -> object:
        self.items[paragraph_id] = item
        return ("item", paragraph_id)

    def list_in_use(self, list_id: str) -> bool:
        return any(item is not None and item.list == list_id for item in self.items.values())


@pytest.fixture
def doc():
    return Document(Numbered(), store=MemoryStore())


def test_a_new_scheme_is_told_to_the_clients_and_undo_takes_it_back(doc):
    events = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, SchemesChanged) else None)
    mine = replace(chapters(), id="appendix", name="Appendix")
    doc.execute(CreateScheme(mine), author="ann")
    assert doc.model.schemes.get("appendix") == mine
    assert events[-1].to_data()["type"] == "schemes" and events[-1].to_data()["schemes"][-1]["id"] == "appendix"
    doc.undo("ann")
    assert "appendix" not in doc.model.schemes


def test_changing_a_scheme_and_undoing_it_puts_the_old_one_back(doc):
    doc.execute(ChangeScheme(replace(chapters(), gap=1.0)), author="ann")
    assert doc.model.schemes.get("chapters").gap == 1.0
    doc.undo("ann")
    assert doc.model.schemes.get("chapters") == chapters()


def test_a_scheme_a_list_uses_cannot_be_removed(doc):
    doc.execute(CreateList(ListDef("l1", "chapters")), author="ann")
    with pytest.raises(ValueError, match="used by the list"):
        doc.execute(RemoveScheme("chapters"), author="ann")


def test_a_list_needs_a_scheme_the_document_has(doc):
    with pytest.raises(ValueError, match="no list scheme"):
        doc.execute(CreateList(ListDef("l1", "spirals")), author="ann")


def test_a_style_numbered_in_a_list_and_undo(doc):
    doc.execute(CreateList(ListDef("outline", "chapters")), author="ann")
    doc.execute(SetStyleNumbering("h1", "outline"), author="ann")
    assert doc.model.styles.numbering("h1") == "outline"
    doc.undo("ann")
    assert doc.model.styles.numbering("h1") is None


def test_a_style_can_only_be_numbered_in_a_list_that_exists_and_a_list_that_numbers_a_style_stays(doc):
    with pytest.raises(ValueError, match="no list"):
        doc.execute(SetStyleNumbering("h1", "outline"), author="ann")
    doc.execute(CreateList(ListDef("outline", "chapters")), author="ann")
    doc.execute(SetStyleNumbering("h1", "outline"), author="ben")
    with pytest.raises(UndoConflict, match="numbers the style"):
        doc.undo("ann")
    with pytest.raises(ValueError, match="numbers the style"):
        doc.execute(RemoveList("outline"), author="ann")


def test_numbering_is_inherited_and_none_says_not_numbered_whatever_the_parent_says():
    book = StyleBook(
        [
            StyleDef("body", "Body", "", None, {}),
            StyleDef("h1", "Heading 1", "", "body", {}, numbering="outline"),
            StyleDef("h2", "Heading 2", "", "h1", {}),
            StyleDef("quiet", "Quiet", "", "h1", {}, numbering=NO_NUMBERING),
        ]
    )
    assert [book.numbering(s) for s in ("body", "h1", "h2", "quiet")] == [None, "outline", "outline", None]
    assert {v["id"]: v["numbered"] for v in book.views()}["h2"] == "outline"
    assert StyleDef.from_data(book.get("h1").to_data()) == book.get("h1")
    assert "numbering" not in book.get("body").to_data()


def test_only_a_paragraph_style_can_be_numbered():
    with pytest.raises(ValueError, match="paragraph style"):
        StyleBook([StyleDef("box", "Box", "", None, {}, kind="box", numbering="outline")])


def test_any_paragraph_can_be_made_an_item_and_undo_gives_its_old_item_back(doc):
    doc.execute(CreateList(ListDef("l1", "numbers")), author="ann")
    doc.execute(SetListItem("p2", ListItem("l1", 1)), author="ann")
    assert doc.model.items["p2"] == ListItem("l1", 1)
    doc.undo("ann")
    assert doc.model.items["p2"] is None
    with pytest.raises(ValueError, match="no list"):
        doc.execute(SetListItem("p1", ListItem("ghost")), author="ann")


def test_the_new_commands_survive_a_trip_through_the_log():
    registry = new_registry()
    for command in (
        CreateScheme(chapters()),
        ChangeScheme(chapters()),
        RemoveScheme("chapters"),
        SetStyleNumbering("h1", "outline"),
        SetStyleNumbering("h1", None),
        SetListItem("o7", ListItem("l1", 2)),
        SetListItem("o7", None),
    ):
        assert registry.decode(encode(command)) == command


def test_replaying_the_log_gives_the_same_document(doc):
    doc.execute(CreateScheme(replace(chapters(), id="appendix", name="Appendix")), author="ann")
    doc.execute(CreateList(ListDef("outline", "appendix")), author="ann")
    doc.execute(SetStyleNumbering("h1", "outline"), author="ben")
    doc.execute(SetListItem("p1", ListItem("outline")), author="ann")
    assert doc.materialize(doc.revision).serialize() == doc.model.serialize()


def test_the_book_finds_the_scheme_that_draws_some_levels_or_makes_one():
    book = SchemeBook()
    numbers = builtin_scheme("numbers")
    assert numbers is not None
    assert book.drawing({0: numbers.levels[0], 1: numbers.levels[1]}, True) == "numbers"
    made = book.drawing({0: LevelFormat("upper-roman", after=")")}, True, "Articles")
    assert made == "scheme-1" and book.get(made).name == "Articles" and book.get(made).marker((3,)) == "III)"
    assert book.drawing({0: LevelFormat("upper-roman", after=")")}, True, "Articles") == made, "found, not made twice"
    assert book.drawing({0: LevelFormat("bullet", "")}, False) is None
