"""Deleting and hiding styles (E1.10, D226, D785): a deletion never leaves a dangling reference; the person chooses
to assign another style (looks change) or to re-base on another style (looks held); built-in, root and template
styles can only be hidden."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Self

import pytest

from claudia_core import (
    DELETE_HOWS,
    INITIAL_CSS,
    Batch,
    Command,
    CommandRegistry,
    CreateStyle,
    Document,
    DocumentModel,
    MemoryStore,
    RebaseStyle,
    SetHeadingLevel,
    SetStyleHidden,
    StyleBook,
    StyleDef,
    assign_changes_look,
    held_look,
    new_registry,
    plan_delete_style,
    validate_css,
)
from claudia_core.facets import FACET_PROPERTIES

BODY = StyleDef("body", "Body text", "running text", None, {"font-size": "11pt", "color": "#1F1A33"}, origin="builtin")
QUOTE = StyleDef("quote", "Quote", "the words of others", "body", {"font-style": "italic", "margin-left": "2em"})
SMALL = StyleDef("small-quote", "Small quote", "a short quote", "quote", {"font-size": "9pt"})
PLAIN = StyleDef("plain", "Plain", "no frills", "body", {"font-weight": "bold"})


class Used(DocumentModel):
    """A model that is a style book and a few things that use a style."""

    app: ClassVar[str] = "test-used"
    registry: ClassVar[CommandRegistry] = new_registry()

    def __init__(self):
        self.styles = StyleBook([BODY, QUOTE, SMALL, PLAIN])
        self.uses: dict[str, str] = {}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"styles": self.styles.to_data(), "uses": dict(self.uses)}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.styles = StyleBook.from_data(state["styles"])
        model.uses = dict(state["uses"])
        return model

    def style_in_use(self, style_id: str) -> bool:
        return style_id in self.uses.values()

    def restyle_users(self, old: str, new: str) -> list[Command]:
        return [Use(item, new) for item, style in sorted(self.uses.items()) if style == old]


@Used.registry.register
@dataclass(frozen=True)
class Use(Command):
    kind: ClassVar[str] = "test.Use"
    item: str
    style: str

    @property
    def label(self) -> str:
        return "Use"

    @property
    def summary(self) -> str:
        return f"{self.item} uses {self.style}"

    def apply(self, ctx):
        if self.style not in ctx.model.styles:
            raise ValueError(f"no style {self.style!r}")
        old = ctx.model.uses.get(self.item)
        ctx.model.uses[self.item] = self.style
        return Use(self.item, old)

    def to_data(self) -> dict:
        return {"item": self.item, "style": self.style}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Use:
        return cls(data["item"], data["style"])


@pytest.fixture
def doc():
    d = Document(Used(), store=MemoryStore())
    d.model.uses.update({"a": "quote", "b": "quote", "c": "plain"})
    return d


def looks(model: Used) -> dict[str, dict[str, str]]:
    """What every user of a style looks like, by item."""
    return {item: model.styles.computed(style) for item, style in model.uses.items()}


def child_looks(model: Used) -> dict[str, dict[str, str]]:
    return {s.id: model.styles.computed(s.id) for s in model.styles}


# ------------------------------------------------------------------------------------ initial values
def test_every_initial_value_is_one_the_allow_list_accepts_and_belongs_to_a_property():
    assert set(INITIAL_CSS) <= FACET_PROPERTIES
    assert validate_css(dict(INITIAL_CSS)) == dict(INITIAL_CSS)


def test_properties_that_depend_on_the_app_have_no_initial_value():
    # font, size and colour are what an app's body style says, and text-align is by content in a cell (D318)
    assert not {"font-family", "font-size", "color", "text-align"} & set(INITIAL_CSS)


# ------------------------------------------------------------------------------------ holding a look
def test_held_look_writes_only_what_differs_from_the_new_base():
    old = {"font-style": "italic", "margin-left": "2em", "font-size": "11pt"}
    base = {"font-size": "11pt", "margin-left": "2em"}
    assert held_look(old, base) == {"font-style": "italic"}


def test_held_look_overrides_what_the_new_base_sets_and_the_old_look_did_not():
    old = {"font-size": "11pt"}
    base = {"font-size": "11pt", "font-style": "italic"}
    assert held_look(old, base) == {"font-style": "normal"}


def test_held_look_refuses_what_it_cannot_hold_and_names_the_property():
    with pytest.raises(ValueError, match="“color”"):
        held_look({}, {"color": "red"})


# ------------------------------------------------------------------------------------ holding the look
def test_deleting_a_style_nothing_uses_just_removes_it_and_undo_brings_it_back(doc):
    before = doc.model.styles.to_data()
    doc.model.uses.clear()
    plan = plan_delete_style(doc.model, "small-quote")
    doc.execute(plan, author="ann")
    assert "small-quote" not in doc.model.styles
    doc.undo("ann")
    assert doc.model.styles.to_data() == before


def test_children_of_a_deleted_style_keep_their_look_when_it_is_rebased_on_its_own_parent(doc):
    before = child_looks(doc.model)
    doc.model.uses.clear()
    doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="body"), author="ann")
    assert "quote" not in doc.model.styles
    assert doc.model.styles.get("small-quote").based_on == "body"
    assert doc.model.styles.computed("small-quote") == before["small-quote"]
    assert not any(s.to_name for s in doc.model.styles)  # nothing needed a stand-in


def test_things_that_use_a_rebased_style_keep_their_look_through_a_stand_in_style_to_be_named(doc):
    before = looks(doc.model)
    doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="body"), author="ann")
    assert "quote" not in doc.model.styles
    stand_in = doc.model.uses["a"]
    assert doc.model.uses["b"] == stand_in != "quote"
    made = doc.model.styles.get(stand_in)
    assert (made.name, made.to_name, made.purpose, made.origin) == (
        "Quote (kept)",
        True,
        "the words of others",
        "document",
    )
    assert looks(doc.model) == before
    assert doc.model.uses["c"] == "plain"  # what did not use it is left alone


def test_the_whole_deletion_is_one_undo_step_that_puts_everything_back(doc):
    before_book, before_uses = doc.model.styles.to_data(), dict(doc.model.uses)
    revision = doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="body"), author="ann")
    assert revision is not None
    doc.undo("ann")
    assert (doc.model.styles.to_data(), doc.model.uses) == (before_book, before_uses)


def test_the_deletion_is_a_batch_the_history_names_in_words(doc):
    plan = plan_delete_style(doc.model, "quote", how="assign", target="plain")
    assert isinstance(plan, Batch)
    assert plan.label.startswith("Delete style")
    assert "Quote" in plan.summary


# ------------------------------------------------------------------------------------ re-basing
def test_rebasing_holds_the_look_of_children_and_users_and_moves_them_under_the_new_style(doc):
    before_children, before_users = child_looks(doc.model), looks(doc.model)
    doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="plain"), author="ann")
    small = doc.model.styles.get("small-quote")
    assert small.based_on == "plain"
    # "plain" is bold and the old chain never said so: the child says "normal" to keep what it looked like
    assert small.css["font-weight"] == "normal"
    assert doc.model.styles.computed("small-quote") == {**before_children["small-quote"], "font-weight": "normal"}
    stand_in = doc.model.styles.get(doc.model.uses["a"])
    assert stand_in.based_on == "plain"
    # the look, in the properties the old look had, is the same; the rest is spelled out to stay neutral
    for item in ("a", "b"):
        now = doc.model.styles.computed(doc.model.uses[item])
        assert {k: now[k] for k in before_users[item]} == before_users[item]


def test_rebasing_on_a_style_that_does_not_exist_is_refused(doc):
    with pytest.raises(ValueError, match="no style"):
        plan_delete_style(doc.model, "quote", how="rebase", target="nope")


def test_a_look_that_cannot_be_held_refuses_the_deletion_and_changes_nothing(doc):
    # "naked" and its child say nothing about colour, "loud" does: what colour would the child have under "loud"?
    doc.model.styles.add(StyleDef("naked", "Naked", "", None, {"font-style": "italic"}))
    doc.model.styles.add(StyleDef("naked-child", "Naked child", "", "naked", {}))
    doc.model.styles.add(StyleDef("loud", "Loud", "", None, {"color": "red"}))
    before = doc.model.styles.to_data()
    with pytest.raises(ValueError, match="“color”"):
        plan_delete_style(doc.model, "naked", how="rebase", target="loud")
    assert doc.model.styles.to_data() == before


def test_a_style_cannot_be_rebased_on_itself_on_one_of_its_descendants_or_on_another_kind(doc):
    for target in ("quote", "small-quote"):
        with pytest.raises(ValueError, match="based on it|itself"):
            plan_delete_style(doc.model, "quote", how="rebase", target=target)
    doc.model.styles.add(StyleDef("frame", "Frame", "a box", None, {"padding-top": "4px"}, kind="box"))
    with pytest.raises(ValueError, match="same kind"):
        plan_delete_style(doc.model, "quote", how="rebase", target="frame")


def test_heading_level_and_numbering_are_held_too(doc):
    doc.model.styles.set_heading_level("quote", 1)  # the children are headings of level 1 by inheritance
    assert doc.model.styles.heading_level("small-quote") == 1
    doc.model.uses.clear()
    doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="body"), author="ann")
    assert doc.model.styles.heading_level("small-quote") == 1
    assert doc.model.styles.get("small-quote").heading_level == 1  # now its own


def test_rebasing_a_heading_onto_body_text_says_body_to_stay_one_if_it_was_not(doc):
    doc.model.styles.set_heading_level("plain", 2)
    doc.model.uses.clear()
    doc.execute(plan_delete_style(doc.model, "quote", how="rebase", target="plain"), author="ann")
    assert doc.model.styles.heading_level("small-quote") is None
    assert doc.model.styles.get("small-quote").heading_level == "body"


# ------------------------------------------------------------------------------------ what may not be deleted
def test_a_built_in_style_can_only_be_hidden(doc):
    with pytest.raises(ValueError, match="built-in.*hidden"):
        plan_delete_style(doc.model, "body")


def test_a_template_style_can_only_be_hidden(doc):
    doc.model.styles.add(StyleDef("brand", "Brand", "from the template", "body", {}, origin="template"))
    with pytest.raises(ValueError, match="template.*hidden"):
        plan_delete_style(doc.model, "brand")


def test_an_unknown_style_is_refused(doc):
    with pytest.raises(ValueError, match="no style"):
        plan_delete_style(doc.model, "nope")


def test_a_model_that_cannot_repoint_its_users_cannot_delete_a_style_in_use(doc):
    class Mute(Used):
        restyle_users = None  # type: ignore[assignment]

    model = Mute()
    model.uses["a"] = "quote"
    with pytest.raises(ValueError, match="cannot move"):
        plan_delete_style(model, "quote")


# ------------------------------------------------------------------------------------ two authors
def test_somebody_using_the_style_while_it_is_deleted_refuses_the_deletion_and_changes_nothing(doc):
    plan = plan_delete_style(doc.model, "plain", how="rebase", target="body")
    doc.execute(Use("late", "plain"), author="bob")  # arrives between the plan and the deletion
    before_book, before_uses = doc.model.styles.to_data(), dict(doc.model.uses)
    with pytest.raises(ValueError, match="in use"):
        doc.execute(plan, author="ann")
    assert (doc.model.styles.to_data(), doc.model.uses) == (before_book, before_uses)


def test_a_change_to_the_style_by_somebody_else_drops_the_deletion_rather_than_applying_a_stale_one():
    plan = RebaseStyle("small-quote", "body", {}, None, None, None)
    from claudia_core import ChangeStyle

    assert plan.shifted_by(ChangeStyle("small-quote", {"color": "red"})) is None
    assert plan.shifted_by(ChangeStyle("plain", {"color": "red"})) is plan


# ------------------------------------------------------------------------------------ hiding
def test_hiding_a_style_is_one_undoable_command_and_changes_no_look(doc):
    before = child_looks(doc.model)
    doc.execute(SetStyleHidden("body", True), author="ann")
    assert doc.model.styles.get("body").hidden is True
    assert child_looks(doc.model) == before
    assert doc.model.styles.views()[0]["hidden"] is True
    doc.undo("ann")
    assert doc.model.styles.get("body").hidden is False


def test_a_style_is_not_hidden_unless_it_says_so_and_the_flags_round_trip_as_data():
    assert "hidden" not in QUOTE.to_data()
    assert "origin" not in QUOTE.to_data()
    odd = StyleDef("odd", "Odd", "", None, {}, origin="template", hidden=True)
    assert StyleDef.from_data(odd.to_data()) == odd


def test_only_the_known_origins_are_taken():
    with pytest.raises(ValueError, match="origin"):
        StyleBook().add(StyleDef("odd", "Odd", "", None, {}, origin="alien"))


def test_hiding_a_style_that_is_not_there_is_refused(doc):
    with pytest.raises(ValueError, match="no style"):
        doc.execute(SetStyleHidden("nope", True), author="ann")


# ------------------------------------------------------------------------------------ the pieces
def test_create_and_rebase_keep_the_look_of_a_style_with_its_own_flags(doc):
    doc.execute(CreateStyle(StyleDef("big", "Big", "", "plain", {"font-size": "20pt"})), author="ann")
    doc.execute(
        RebaseStyle("big", "quote", {"font-size": "20pt", "font-weight": "bold"}, None, None, None), author="ann"
    )
    assert doc.model.styles.get("big").based_on == "quote"
    assert doc.model.styles.computed("big")["font-style"] == "italic"
    doc.undo("ann")
    assert doc.model.styles.get("big").based_on == "plain"


def test_rebasing_cannot_make_a_cycle_or_cross_kinds(doc):
    with pytest.raises(ValueError, match="itself|based on it"):
        doc.execute(RebaseStyle("quote", "small-quote", {}, None, None, None), author="ann")
    with pytest.raises(ValueError, match="itself"):
        doc.execute(RebaseStyle("quote", "quote", {}, None, None, None), author="ann")


def test_set_heading_level_is_untouched_by_all_of_this(doc):
    doc.execute(SetHeadingLevel("plain", 3), author="ann")
    assert doc.model.styles.heading_level("plain") == 3


# ------------------------------------------------------------------------------------ assigning (D785)
def test_the_two_ways_come_in_the_order_a_dialog_offers_them():
    assert DELETE_HOWS == ("assign", "rebase")


def test_assigning_puts_what_has_the_style_and_what_is_based_on_it_under_the_other_style(doc):
    doc.execute(plan_delete_style(doc.model, "quote", how="assign", target="plain"), author="ann")
    assert "quote" not in doc.model.styles
    assert doc.model.uses == {"a": "plain", "b": "plain", "c": "plain"}
    small = doc.model.styles.get("small-quote")
    assert small.based_on == "plain" and small.css == {"font-size": "9pt"}  # as it was: it just lost what Quote said
    assert "font-style" not in doc.model.styles.computed("small-quote")
    assert doc.model.styles.computed("small-quote")["font-weight"] == "bold"  # and took on what Plain says
    assert not any(s.to_name for s in doc.model.styles)  # no stand-in: nothing needs a name


def test_the_plain_style_of_the_kind_is_a_style_like_any_other_to_assign(doc):
    doc.execute(plan_delete_style(doc.model, "quote", how="assign", target="body"), author="ann")
    assert doc.model.uses == {"a": "body", "b": "body", "c": "plain"}
    assert doc.model.styles.get("small-quote").based_on == "body"


def test_assigning_is_one_undo_step_that_puts_everything_back(doc):
    before_book, before_uses = doc.model.styles.to_data(), dict(doc.model.uses)
    doc.execute(plan_delete_style(doc.model, "quote", how="assign", target="plain"), author="ann")
    doc.undo("ann")
    assert (doc.model.styles.to_data(), doc.model.uses) == (before_book, before_uses)


def test_a_style_has_to_say_which_style_takes_its_place_unless_nothing_needs_one(doc):
    with pytest.raises(ValueError, match="say which style"):
        plan_delete_style(doc.model, "quote")  # users and a child
    doc.model.uses.clear()
    with pytest.raises(ValueError, match="say which style"):
        plan_delete_style(doc.model, "quote", how="rebase")  # still a child
    doc.execute(plan_delete_style(doc.model, "small-quote"), author="ann")
    assert "small-quote" not in doc.model.styles


def test_a_style_cannot_be_replaced_by_itself_by_a_descendant_by_one_that_is_not_there_or_of_another_kind(doc):
    for target, message in (("quote", "itself"), ("small-quote", "based on it"), ("nope", "no style")):
        with pytest.raises(ValueError, match=message):
            plan_delete_style(doc.model, "quote", how="assign", target=target)
    doc.model.styles.add(StyleDef("frame", "Frame", "a box", None, {"padding-top": "4px"}, kind="box"))
    with pytest.raises(ValueError, match="same kind"):
        plan_delete_style(doc.model, "quote", how="assign", target="frame")


def test_assigning_says_whether_a_look_changes(doc):
    assert assign_changes_look(doc.model, "quote", "plain") is True  # it has users, and Quote is italic
    doc.model.uses.clear()
    assert assign_changes_look(doc.model, "quote", "body") is True  # Small quote loses the italic
    assert assign_changes_look(doc.model, "small-quote", "body") is False  # nothing has it, nothing is based on it
    doc.model.styles.add(StyleDef("same", "Same", "", "body", {}))
    doc.model.uses["x"] = "same"
    assert assign_changes_look(doc.model, "same", "body") is False  # it said nothing of its own
    assert assign_changes_look(doc.model, "same", "plain") is True  # but Plain does


def test_a_box_style_has_a_plain_style_of_its_own_chain_to_go_back_to():
    class Boxes(Used):
        pass

    model = Boxes()
    model.styles.add(StyleDef("plain-box", "Plain box", "", None, {"padding-top": "0"}, kind="box", origin="builtin"))
    model.styles.add(StyleDef("plain-image", "Plain image", "", None, {}, kind="box", origin="builtin"))
    model.styles.add(StyleDef("framed", "Framed", "", "plain-image", {"border-top": "1px solid #000000"}, kind="box"))
    model.styles.add(StyleDef("loose", "Loose", "", None, {}, kind="box"))
    assert model.styles.fallback("framed").id == "plain-image"
    assert model.styles.fallback("loose").id == "plain-box"  # the first built-in root of its kind
    assert model.styles.fallback("quote").id == "body"


def test_a_book_without_a_built_in_root_of_the_kind_suggests_nothing():
    model = Used()
    model.styles.add(StyleDef("loose", "Loose", "", None, {}, kind="box"))
    assert model.styles.fallback("loose") is None


def test_a_built_in_style_cannot_be_deleted_by_assigning_either(doc):
    with pytest.raises(ValueError, match="built-in.*hidden"):
        plan_delete_style(doc.model, "body", how="assign", target="plain")


def test_the_way_has_to_be_one_of_the_two(doc):
    for how in ("sideways", "keep", "fall_back"):
        with pytest.raises(ValueError, match="one of"):
            plan_delete_style(doc.model, "quote", how=how, target="plain")


def test_somebody_using_the_style_meanwhile_refuses_an_assignment_too(doc):
    plan = plan_delete_style(doc.model, "plain", how="assign", target="body")
    doc.execute(Use("late", "plain"), author="bob")
    with pytest.raises(ValueError, match="in use"):
        doc.execute(plan, author="ann")
    assert "plain" in doc.model.styles
