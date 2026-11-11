"""One style API for all three apps: `style_model`, `apply_style`, `deviate` and `style_uses` (styling-suite plan,
step 1.5; D304, D309, D311, D315, D316)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import ClassVar, Self

import pytest

from claudia_composes import TextModel
from claudia_core import (
    BOX_FACET,
    SLOTS,
    Command,
    CommandRegistry,
    Document,
    DocumentModel,
    MemoryStore,
    Slot,
    StyleBook,
    StyleDef,
    new_registry,
)
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.computes import computes_methods
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError, core_methods
from claudia_server.style_targets import add_target_methods
from claudia_server.styles import own_css

ANN = Account("ann", "owner")
AI = Account.assistant()


def call(doc, name, params=None, methods=creates_methods, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return methods.dispatch(ctx, name, params)


@pytest.fixture
def deck():
    return Document(SlideModel.empty(), store=MemoryStore())


@pytest.fixture
def paper():
    return Document(TextModel(), store=MemoryStore())


def add(doc, kind, text="", shape="rectangle"):
    given = {"slide": "s1", "kind": kind, "x": 10, "y": 10, "w": 300, "h": 200, "text": text}
    if kind == "shape":
        given["shape"] = shape
    return call(doc, "add_object", given)["object"]


def body(doc, object_id):
    return doc.model.get(object_id).body


# ----------------------------------------------------------------------------- the model
def test_every_app_sends_the_slot_table_and_the_targets_it_takes(deck, paper):
    model = call(deck, "style_model")
    assert model["facets"]["outline"] == ["fill", "stroke", "stroke-width"]
    assert model["kinds"]["paragraph"] == ["text", "paragraph", "box"]
    assert [s["name"] for s in model["slots"]["text"]] == ["box", "words"]
    assert model["targets"] == ["object"]
    assert call(paper, "style_model", methods=composes_methods)["targets"] == ["block", "object"]
    assert (
        "object"
        in call(Document(SlideModel.empty(), store=MemoryStore()), "style_model", methods=computes_methods)["targets"]
    )


# ----------------------------------------------------------------------------- applying
def test_a_bundle_fills_every_slot_of_a_text_box_it_fits(deck):
    """D309, D316: Body text is a paragraph style; a text box's box reads its box part, its words the rest."""
    box = add(deck, "text", "hello")
    call(deck, "apply_style", {"targets": [{"object": box}], "style": "body-text"})
    assert (body(deck, box).style, body(deck, box).paragraph.style) == ("body-text", "body-text")
    call(deck, "undo")
    assert (body(deck, box).style, body(deck, box).paragraph.style) == ("plain-box", "body-text")


def test_a_style_goes_only_where_it_fits_on_a_shape(deck):
    shape = add(deck, "shape", "label")
    call(deck, "apply_style", {"targets": [{"object": shape}], "style": "body-text"})
    assert (body(deck, shape).style, body(deck, shape).paragraph.style) == ("plain-shape", "body-text")
    with pytest.raises(RequestError, match="does not fit the outline of a shape"):
        call(deck, "apply_style", {"targets": [{"object": shape}], "style": "body-text", "slot": "outline"})


def test_one_slot_only(deck):
    box = add(deck, "text", "hello")
    call(deck, "apply_style", {"targets": [{"object": box}], "style": "body-text", "slot": "box"})
    assert body(deck, box).style == "body-text"
    with pytest.raises(RequestError, match="has no slot “label”"):
        call(deck, "apply_style", {"targets": [{"object": box}], "style": "body-text", "slot": "label"})


def test_a_paragraph_of_a_text_is_a_target_like_any_other(paper):
    call(paper, "apply_style", {"targets": [{"block": "b1"}], "style": "quote"}, methods=composes_methods)
    assert paper.model.block("b1").style == "quote"
    with pytest.raises(RequestError, match="outline style and does not fit"):
        call(paper, "apply_style", {"targets": [{"block": "b1"}], "style": "plain-shape"}, methods=composes_methods)


def test_many_targets_change_in_one_step(deck):
    a, b = add(deck, "text", "a"), add(deck, "text", "b")
    call(deck, "apply_style", {"targets": [{"object": a}, {"object": b}], "style": "body-text", "slot": "box"})
    assert body(deck, a).style == body(deck, b).style == "body-text"
    call(deck, "undo")
    assert body(deck, a).style == body(deck, b).style == "plain-box"


@pytest.mark.parametrize(
    ("targets", "error"),
    [
        ([], "bad_request"),
        ([{"slide": "s1"}], "bad_request"),
        (["o1"], "bad_request"),
        ([{"object": 3}], "bad_request"),
        ([{"object": "nope"}], "command_error"),
    ],
)
def test_targets_that_are_not_there_or_not_targets_are_refused(deck, targets, error):
    with pytest.raises(RequestError) as caught:
        call(deck, "apply_style", {"targets": targets, "style": "body-text"})
    assert caught.value.code == error
    assert deck.revision is None


def test_an_unknown_style_is_refused(deck):
    box = add(deck, "text")
    with pytest.raises(RequestError, match="no style"):
        call(deck, "apply_style", {"targets": [{"object": box}], "style": "sparkly"})


def test_the_assistant_does_not_restyle_a_text(paper):
    """composes keeps its guard: the assistant suggests, it does not write (D63)."""
    with pytest.raises(RequestError) as caught:
        call(
            paper, "apply_style", {"targets": [{"block": "b1"}], "style": "quote"}, methods=composes_methods, account=AI
        )
    assert caught.value.code == "forbidden"


# ----------------------------------------------------------------------------- deviating
def test_changing_the_words_of_one_text_box_only(deck):
    """ "These only", and only one slot (D75, D309): a provisional paragraph style in the words, the box untouched."""
    box, other = add(deck, "text", "mine"), add(deck, "text", "theirs")
    made = call(
        deck,
        "deviate",
        {"parent": "body-text", "targets": [{"object": box}], "slot": "words", "set": {"font-weight": "bold"}},
    )
    style = deck.model.styles.get(made["style"])
    assert (style.kind, style.based_on, style.to_name, made["name"]) == (
        "paragraph",
        "body-text",
        True,
        "Body text (changed)",
    )
    assert (body(deck, box).style, body(deck, box).paragraph.style) == ("plain-box", made["style"])
    assert body(deck, other).paragraph.style == "body-text"


def test_without_a_slot_a_deviation_replaces_the_parent_wherever_it_was(deck):
    box = add(deck, "text", "hello")
    call(deck, "apply_style", {"targets": [{"object": box}], "style": "body-text"})
    made = call(deck, "deviate", {"parent": "body-text", "targets": [{"object": box}], "set": {"color": "#C0392B"}})
    assert (body(deck, box).style, body(deck, box).paragraph.style) == (made["style"], made["style"])


def test_a_deviation_stays_inside_its_parents_kind(deck):
    shape = add(deck, "shape")
    with pytest.raises(RequestError, match="font-size"):
        call(deck, "deviate", {"parent": "plain-shape", "targets": [{"object": shape}], "set": {"font-size": "40px"}})
    made = call(
        deck, "deviate", {"parent": "plain-shape", "targets": [{"object": shape}], "set": {"stroke-width": "9px"}}
    )
    assert body(deck, shape).style == made["style"] and deck.model.styles.get(made["style"]).kind == "outline"


def test_a_deviation_that_changes_nothing_is_refused(deck):
    box = add(deck, "text")
    with pytest.raises(RequestError, match="would look just like"):
        call(deck, "deviate", {"parent": "body-text", "targets": [{"object": box}], "slot": "words", "set": {}})


def test_counting_uses_counts_every_slot(deck, paper):
    add(deck, "text", "a")
    add(deck, "shape", "b")
    uses = call(deck, "style_uses")["uses"]
    assert (uses["plain-box"], uses["body-text"], uses["plain-shape"], uses["shape-label"]) == (1, 1, 1, 1)
    assert call(paper, "style_uses", methods=composes_methods)["uses"] == {"body": 1}


# ----------------------------------------------------------------------------- a later thing (D315)
@dataclass(frozen=True)
class SetBackground(Command):
    """A test-only command: put a style into a slide's background slot."""

    kind: ClassVar[str] = "test.SetBackground"
    slide: str
    style: str

    @property
    def label(self) -> str:
        return "Background"

    @property
    def summary(self) -> str:
        return f"background {self.style}"

    def apply(self, ctx) -> Command:
        old = ctx.model.backgrounds[self.slide]
        ctx.model.backgrounds[self.slide] = self.style
        return SetBackground(self.slide, old)

    def to_data(self) -> dict:
        return {"slide": self.slide, "style": self.style}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetBackground:
        return cls(data["slide"], data["style"])


_REGISTRY = new_registry()
_REGISTRY.register(SetBackground)


class Backgrounds(DocumentModel):
    """A made-up app whose slides have one styled thing, a background — the kind of row D315 says comes later."""

    app: ClassVar[str] = "test-backgrounds"
    registry: ClassVar[CommandRegistry] = _REGISTRY

    def __init__(self):
        self.styles = StyleBook(
            [StyleDef("calm", "Calm", "a quiet slide", None, {"background-color": "#EEE"}, kind="box")]
        )
        self.backgrounds = {"s1": "calm"}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self) -> dict:
        return {"styles": self.styles.to_data(), "backgrounds": dict(self.backgrounds)}

    @classmethod
    def restore(cls, state: dict) -> Self:
        model = cls()
        model.styles = StyleBook.from_data(state["styles"])
        model.backgrounds = dict(state["backgrounds"])
        return model


class SlideBackgrounds:
    key = "slide"

    def thing(self, model, target):
        if target["slide"] not in model.backgrounds:
            raise KeyError(f"no slide {target['slide']!r}")
        return "slide"

    def style_in(self, model, target, slot):
        return model.backgrounds[target["slide"]]

    def command(self, model, target, slot, style):
        return SetBackground(target["slide"], style)

    def uses(self, model):
        return Counter(model.backgrounds.values())


def test_a_later_kind_of_thing_is_a_row_and_an_adapter_and_nothing_else():
    """D315: a slide background comes later as one more row of the slot table and one adapter; the shared methods
    serve it unchanged — fitting, applying, deviating and counting."""
    table = core_methods.extended()
    slots = SLOTS.with_row("slide", (Slot("background", (BOX_FACET,), "box"),))
    add_target_methods(table, lambda ctx: None, (SlideBackgrounds(),), own_css=own_css, slots=slots)
    doc = Document(Backgrounds(), store=MemoryStore())
    doc.model.styles.add(StyleDef("loud", "Loud", "", None, {"background-color": "#F00"}, kind="box"))

    assert call(doc, "style_model", methods=table)["slots"]["slide"][0]["takes"] == ["paragraph", "box"]
    call(doc, "apply_style", {"targets": [{"slide": "s1"}], "style": "loud"}, methods=table)
    assert doc.model.backgrounds["s1"] == "loud"
    made = call(
        doc, "deviate", {"parent": "loud", "targets": [{"slide": "s1"}], "set": {"padding-top": "4px"}}, methods=table
    )
    assert doc.model.backgrounds["s1"] == made["style"]
    assert call(doc, "style_uses", methods=table)["uses"] == {made["style"]: 1}


# ----------------------------------------------------------------------------- cells (step 1.6; D307, D311, D313)
@pytest.fixture
def book():
    from claudia_computes import WorkbookModel

    doc = Document(WorkbookModel(), store=MemoryStore())
    call(doc, "add_sheet", {"name": "Sheet1"}, methods=computes_methods)
    return doc


def sheet_id(doc):
    return next(iter(doc.model.sheets))


def cells(doc, area):
    return {"sheet": sheet_id(doc), "range": list(area)}


def look_at(doc, row, col):
    return call(doc, "cell_style_at", {"sheet": sheet_id(doc), "row": row, "col": col}, methods=computes_methods)


def test_a_workbook_takes_cells_and_objects_as_targets(book):
    assert call(book, "style_model", methods=computes_methods)["targets"] == ["object", "sheet"]


def test_applying_a_style_to_cells_fills_both_slots_as_on_a_paragraph(book):
    """D311: a cell takes a style the way a composes paragraph does — one name, both slots."""
    call(book, "apply_style", {"targets": [cells(book, (0, 0, 0, 3))], "style": "header"}, methods=computes_methods)
    assert look_at(book, 0, 2) == {
        "box": {"style": "header", "layer": "range"},
        "words": {"style": "header", "layer": "range"},
    }
    assert look_at(book, 1, 2)["words"] == {"style": "body-text", "layer": "default"}
    call(book, "undo", methods=computes_methods)
    assert look_at(book, 0, 2)["box"]["style"] == "body-text"


def test_a_box_style_goes_only_into_the_box_of_a_cell(book):
    call(book, "apply_style", {"targets": [cells(book, (2, 2, 2, 2))], "style": "plain-box"}, methods=computes_methods)
    assert look_at(book, 2, 2)["box"]["style"] == "plain-box" and look_at(book, 2, 2)["words"]["style"] == "body-text"
    with pytest.raises(RequestError, match="does not fit any slot of a cell"):
        call(
            book,
            "apply_style",
            {"targets": [cells(book, (2, 2, 2, 2))], "style": "plain-shape"},
            methods=computes_methods,
        )


def test_a_whole_column_is_a_target_too(book):
    from claudia_computes.limits import MAX_ROWS

    call(
        book,
        "apply_style",
        {"targets": [cells(book, (0, 1, MAX_ROWS - 1, 1))], "style": "input", "slot": "words"},
        methods=computes_methods,
    )
    assert look_at(book, 500_000, 1)["words"] == {"style": "input", "layer": "column"}


def test_changing_only_the_box_of_some_cells(book):
    """D309: "only the box" deviates one slot; the words keep the bundle."""
    call(book, "apply_style", {"targets": [cells(book, (0, 0, 1, 1))], "style": "header"}, methods=computes_methods)
    made = call(
        book,
        "deviate",
        {
            "parent": "header",
            "targets": [cells(book, (0, 0, 0, 1))],
            "slot": "box",
            "set": {"background-color": "@attention/14"},
        },
        methods=computes_methods,
    )
    assert book.model.styles.get(made["style"]).kind == "paragraph"
    assert look_at(book, 0, 0)["box"]["style"] == made["style"] and look_at(book, 0, 0)["words"]["style"] == "header"
    assert look_at(book, 1, 0)["box"]["style"] == "header"


def test_the_grid_reads_the_ranges_of_a_window(book):
    call(
        book,
        "apply_style",
        {"targets": [cells(book, (0, 0, 9, 9))], "style": "note", "slot": "words"},
        methods=computes_methods,
    )
    answer = call(
        book,
        "cell_styles",
        {"sheet": sheet_id(book), "row0": 5, "row1": 20, "col0": 0, "col1": 3},
        methods=computes_methods,
    )
    assert answer["ranges"] == [{"slot": "words", "layer": "range", "area": [5, 0, 9, 3], "style": "note"}]
    with pytest.raises(RequestError):
        call(
            book,
            "cell_styles",
            {"sheet": sheet_id(book), "row0": 5, "row1": 1, "col0": 0, "col1": 3},
            methods=computes_methods,
        )


def test_cell_targets_that_do_not_hold_together_are_refused(book):
    for target in (
        {"sheet": sheet_id(book), "range": [3, 3, 1, 1]},
        {"sheet": sheet_id(book), "range": "A1"},
        {"sheet": 4, "range": [0, 0, 0, 0]},
    ):
        with pytest.raises(RequestError) as caught:
            call(book, "apply_style", {"targets": [target], "style": "note"}, methods=computes_methods)
        assert caught.value.code == "bad_request"
    with pytest.raises(RequestError) as caught:
        call(
            book,
            "apply_style",
            {"targets": [{"sheet": "nope", "range": [0, 0, 0, 0]}], "style": "note"},
            methods=computes_methods,
        )
    assert caught.value.code == "command_error"


def test_uses_count_each_range_once(book):
    call(book, "apply_style", {"targets": [cells(book, (0, 0, 99, 9))], "style": "input"}, methods=computes_methods)
    assert call(book, "style_uses", methods=computes_methods)["uses"]["input"] == 2  # one range, two slots
