"""The style book every app shares (E1.10): named styles made of CSS, based on each other, changed by commands."""

from __future__ import annotations

from typing import ClassVar, Self

import pytest

from claudia_core import (
    ChangeStyle,
    CommandRegistry,
    CreateStyle,
    CssError,
    Document,
    DocumentModel,
    MemoryStore,
    RemoveStyle,
    RenameStyle,
    StyleBook,
    StyleDef,
    StylesChanged,
    UndoConflict,
    new_registry,
)

BODY = StyleDef("body", "Body text", "running text", None, {"font-size": "11pt", "color": "#1F1A33"})
HEADING = StyleDef("heading", "Heading", "a section", "body", {"font-size": "18pt", "font-weight": "bold"})


def book() -> StyleBook:
    return StyleBook([BODY, HEADING])


# ----------------------------------------------------------------------------- the book
def test_a_style_has_only_its_own_differences_and_the_computed_look_resolves_the_parents():
    s = book()
    assert s.get("heading").css == {"font-size": "18pt", "font-weight": "bold"}
    assert s.computed("heading") == {"font-size": "18pt", "font-weight": "bold", "color": "#1F1A33"}
    assert s.computed("body") == {"font-size": "11pt", "color": "#1F1A33"}


def test_changing_a_parent_changes_the_child_where_it_has_not_overridden_the_property():
    s = book()
    s.set_css("body", {"font-size": "12pt", "color": "#000000"})
    assert s.computed("heading")["color"] == "#000000"
    assert s.computed("heading")["font-size"] == "18pt"  # overridden by the child


def test_a_chain_of_three():
    s = book()
    s.add(StyleDef("heading-changed", "Heading (changed)", "", "heading", {"color": "red"}, to_name=True))
    assert s.computed("heading-changed") == {
        "font-size": "18pt",
        "font-weight": "bold",
        "color": "red",
    }
    assert [c.id for c in s.chain("heading-changed")] == ["body", "heading", "heading-changed"]
    assert s.children("body") == ["heading"]


def test_unknown_parent_duplicate_id_and_duplicate_name_are_refused():
    s = book()
    with pytest.raises(ValueError, match="no style"):
        s.add(StyleDef("x", "X", "", "nope", {}))
    with pytest.raises(ValueError, match="exists already"):
        s.add(StyleDef("body", "Another", "", None, {}))
    with pytest.raises(ValueError, match="already a style named"):
        s.add(StyleDef("x", "  body TEXT ", "", None, {}))


@pytest.mark.parametrize("name", ["", "   ", "x" * 61, "two\nlines"])
def test_names_must_be_short_one_line_and_not_empty(name):
    with pytest.raises(ValueError, match="name"):
        book().add(StyleDef("x", name, "", None, {}))


@pytest.mark.parametrize("ident", ["", "Has Space", "UPPER", "-lead", "x" * 70])
def test_ids_are_lower_case_words_with_hyphens(ident):
    with pytest.raises(ValueError, match="id"):
        book().add(StyleDef(ident, "Fine", "", None, {}))


def test_css_in_a_style_is_validated_and_cleaned():
    s = book()
    s.add(StyleDef("loud", "Loud", "", "body", {"font-weight": "BOLD"}))
    assert s.get("loud").css == {"font-weight": "bold"}
    with pytest.raises(CssError):
        s.add(StyleDef("evil", "Evil", "", "body", {"color": "url(http://example.com)"}))
    assert "evil" not in s


def test_rename_keeps_names_unique_and_marks_the_style_as_named():
    s = book()
    s.add(StyleDef("x", "Heading (changed)", "", "heading", {}, to_name=True))
    s.rename("x", "Chapter title")
    assert (s.get("x").name, s.get("x").to_name) == ("Chapter title", False)
    with pytest.raises(ValueError, match="already a style named"):
        s.rename("x", "body text")
    s.rename("x", "CHAPTER TITLE")  # the same name in other letters is still this style's own name


def test_remove_refuses_while_other_styles_are_based_on_it():
    s = book()
    with pytest.raises(ValueError, match="based on it"):
        s.remove("body")
    s.remove("heading")
    assert "heading" not in s


def test_helpers_make_ids_and_provisional_names_that_are_free():
    s = book()
    assert s.unique_id("Heading (changed)") == "heading-changed"
    s.add(StyleDef("heading-changed", "Heading (changed)", "", "heading", {}, to_name=True))
    assert s.unique_id("Heading (changed)") == "heading-changed-2"
    assert s.provisional_name("heading") == "Heading (changed 2)"
    assert s.provisional_name("body") == "Body text (changed)"
    assert s.unique_id("Überschrift & Co.") == "uberschrift-co"
    assert s.unique_id("***") == "style"


def test_the_book_round_trips_as_plain_data_and_keeps_its_order():
    s = book()
    s.add(StyleDef("x", "X", "purpose", "heading", {"color": "red"}, to_name=True))
    again = StyleBook.from_data(s.to_data())
    assert [d.id for d in again] == ["body", "heading", "x"]
    assert again.to_data() == s.to_data()
    assert s.views()[2]["computed"]["font-size"] == "18pt"


def test_a_style_that_looks_like_itself_is_not_changed_by_computing():
    s = book()
    s.computed("heading")["color"] = "red"  # the answer is a copy
    assert s.computed("heading")["color"] == "#1F1A33"


# ----------------------------------------------------------------------------- the commands
class Styled(DocumentModel):
    """A model that is only a style book, plus the one question the commands ask of an app."""

    app: ClassVar[str] = "test-styled"
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.styles = book()
        self.in_use: set[str] = set()

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"styles": self.styles.to_data()}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.styles = StyleBook.from_data(state["styles"])
        return model

    def style_in_use(self, style_id: str) -> bool:
        return style_id in self.in_use


@pytest.fixture
def paper():
    return Document(Styled(), store=MemoryStore())


def seen(doc):
    events = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, StylesChanged) else None)
    return events


def test_creating_a_style_tells_the_clients_the_whole_book_and_can_be_undone(paper):
    events = seen(paper)
    new = StyleDef("quote", "Quote", "someone else's words", "body", {"font-style": "italic"})
    paper.execute(CreateStyle(new), author="ann")
    assert paper.model.styles.get("quote").css == {"font-style": "italic"}
    (event,) = events
    data = event.to_data()
    assert data["type"] == "styles" and [s["id"] for s in data["styles"]] == ["body", "heading", "quote"]
    assert data["styles"][2]["computed"]["color"] == "#1F1A33"
    paper.undo("ann")
    assert "quote" not in paper.model.styles
    assert [s["id"] for s in events[-1].to_data()["styles"]] == ["body", "heading"]
    paper.redo("ann")
    assert "quote" in paper.model.styles


def test_the_history_says_what_happened():
    assert CreateStyle(StyleDef("q", "Quote", "", "body", {})).summary == "created the style “Quote”"
    assert ChangeStyle("q", {"color": "red"}, ()).summary == "changed the style q: color"
    assert ChangeStyle("q", {"color": "red", "font-size": "9pt"}, ("font-style",)).summary.endswith(
        "color, font-size, font-style"
    )
    assert RenameStyle("q", "Quote", False).summary == "named the style “Quote”"


def test_changing_a_style_sets_and_unsets_and_the_inverse_restores_exactly(paper):
    paper.execute(ChangeStyle("heading", {"color": "#5B4BC4", "font-size": "20pt"}, ("font-weight",)), author="ann")
    assert paper.model.styles.get("heading").css == {"font-size": "20pt", "color": "#5B4BC4"}
    paper.undo("ann")
    assert paper.model.styles.get("heading").css == {"font-size": "18pt", "font-weight": "bold"}


def test_a_change_with_an_unknown_style_or_bad_css_changes_nothing(paper):
    before = paper.model.serialize()
    with pytest.raises(ValueError, match="no style"):
        paper.execute(ChangeStyle("nope", {"color": "red"}, ()), author="ann")
    with pytest.raises(CssError):
        paper.execute(ChangeStyle("heading", {"color": "red", "position": "absolute"}, ()), author="ann")
    assert paper.model.serialize() == before and paper.revision is None


def test_naming_a_style_ends_the_invitation_and_undo_brings_it_back(paper):
    paper.execute(CreateStyle(StyleDef("h2", "Heading (changed)", "", "heading", {}, to_name=True)), author="ann")
    paper.execute(RenameStyle("h2", "Chapter", False), author="ann")
    assert (paper.model.styles.get("h2").name, paper.model.styles.get("h2").to_name) == ("Chapter", False)
    paper.undo("ann")
    assert (paper.model.styles.get("h2").name, paper.model.styles.get("h2").to_name) == ("Heading (changed)", True)


def test_a_style_cannot_be_taken_back_while_something_uses_it(paper):
    paper.execute(CreateStyle(StyleDef("quote", "Quote", "", "body", {})), author="ann")
    paper.model.in_use.add("quote")  # a colleague applied it in the meantime
    with pytest.raises(UndoConflict, match="in use"):
        paper.undo("ann")
    assert "quote" in paper.model.styles


def test_undo_never_overwrites_a_colleagues_change_of_the_same_property(paper):
    paper.execute(ChangeStyle("body", {"color": "#111111"}, ()), author="ann")
    paper.execute(ChangeStyle("body", {"color": "#222222"}, ()), author="ben")
    with pytest.raises(UndoConflict):
        paper.undo("ann")
    assert paper.model.styles.get("body").css["color"] == "#222222"


def test_undo_goes_through_when_a_colleague_changed_something_else(paper):
    paper.execute(ChangeStyle("body", {"color": "#111111"}, ()), author="ann")
    paper.execute(ChangeStyle("body", {"font-size": "13pt"}, ()), author="ben")
    paper.undo("ann")
    assert paper.model.styles.get("body").css == {"font-size": "13pt", "color": "#1F1A33"}


def test_undo_of_a_creation_is_refused_when_a_colleague_changed_or_named_the_style(paper):
    paper.execute(CreateStyle(StyleDef("quote", "Quote (changed)", "", "body", {}, to_name=True)), author="ann")
    paper.execute(RenameStyle("quote", "Quote", False), author="ben")
    with pytest.raises(UndoConflict):
        paper.undo("ann")


def test_replaying_the_log_gives_the_same_book(paper):
    paper.execute(
        CreateStyle(StyleDef("quote", "Quote (changed)", "", "body", {"font-style": "italic"}, to_name=True)),
        author="ann",
    )
    paper.execute(ChangeStyle("quote", {"color": "#444444"}, ()), author="ben")
    paper.execute(RenameStyle("quote", "Quote", False), author="ann")
    paper.undo("ann")
    rebuilt = paper.materialize(paper.revision)
    assert rebuilt.serialize() == paper.model.serialize()


def test_the_models_requirement_is_clear_when_it_has_no_style_book():
    from claudia_core.testing import ListModel

    doc = Document(ListModel(), store=MemoryStore())
    with pytest.raises(TypeError, match="style book"):
        doc.execute(ChangeStyle("body", {"color": "red"}, ()), author="ann")


def test_remove_is_an_ordinary_command_with_a_sentence():
    assert RemoveStyle("quote").summary == "took back the style quote"
