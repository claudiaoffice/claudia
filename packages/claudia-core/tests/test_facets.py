"""Facets, kinds and slots: what every style property means, and where a style can be put (D303-D305, D312, D315).

A *facet* is a named set of properties (Text, Paragraph, Box, Outline); every property a style may set belongs to
exactly one. A style's *kind* says which facets it may hold. A *slot* is a place in a thing that reads a style —
the box of a text box, the words of a cell — and the slot table says which slots each kind of thing has.
"""

import pytest

from claudia_core import (
    ALLOWED_CSS,
    BOX_FACET,
    FACETS,
    KINDS,
    OUTLINE_FACET,
    PARAGRAPH_FACET,
    SLOTS,
    TEXT_FACET,
    Slot,
    SlotTable,
    check_kind,
    facet_of,
    fits,
)


# ----------------------------------------------------------------------------- facets
def test_every_property_a_style_may_set_belongs_to_exactly_one_facet():
    seen: list[str] = [prop for facet in FACETS for prop in facet.properties]
    assert len(seen) == len(set(seen)), "a property in two facets"
    assert set(seen) == ALLOWED_CSS, "a facet without a check, or an allowed property in no facet"


def test_the_four_facets_and_what_they_hold():
    assert [facet.name for facet in FACETS] == ["text", "paragraph", "box", "outline"]
    assert {"font-family", "font-size", "font-weight", "font-style", "text-decoration", "color"} <= set(
        TEXT_FACET.properties
    )
    assert {"text-align", "line-height", "margin-top", "margin-left"} <= set(PARAGRAPH_FACET.properties)
    assert {"background-color", "border-top", "border-left", "padding-top"} <= set(BOX_FACET.properties)
    assert {"vertical-align", "white-space"} <= set(BOX_FACET.properties)  # CSS_VERSION 3, a cell's box (D307)
    assert set(OUTLINE_FACET.properties) == {"fill", "stroke", "stroke-width"}


def test_a_property_knows_its_facet():
    assert facet_of("fill") is OUTLINE_FACET
    assert facet_of("background-color") is BOX_FACET
    assert facet_of("text-align") is PARAGRAPH_FACET
    assert facet_of("color") is TEXT_FACET
    with pytest.raises(KeyError, match="position"):
        facet_of("position")


# ----------------------------------------------------------------------------- kinds
def test_there_are_three_kinds_and_each_says_which_facets_it_may_hold():
    """D312: `paragraph`, `box` and `outline`. A paragraph style may carry a box as well (composes' Definition has a
    background and a left border), because a composes paragraph reads all three facets."""
    assert {name: [f.name for f in facets] for name, facets in KINDS.items()} == {
        "paragraph": ["text", "paragraph", "box"],
        "box": ["box"],
        "outline": ["outline"],
    }


def test_a_kind_accepts_its_own_properties():
    check_kind("paragraph", {"font-size": "12pt", "text-align": "center", "background-color": "@accent/8"})
    check_kind("box", {"background-color": "white", "border-top": "1px solid black", "padding-left": "4px"})
    check_kind("outline", {"fill": "@accent/14", "stroke": "@accent", "stroke-width": "2px"})
    check_kind("box", {})


@pytest.mark.parametrize(
    ("kind", "css", "named"),
    [
        ("paragraph", {"fill": "red"}, "fill"),
        ("box", {"font-size": "12pt"}, "font-size"),
        ("box", {"stroke": "red"}, "stroke"),
        ("outline", {"background-color": "red"}, "background-color"),
        ("outline", {"text-align": "center"}, "text-align"),
    ],
)
def test_a_kind_refuses_a_property_of_another_facet_and_says_which(kind, css, named):
    with pytest.raises(ValueError, match=f"“{named}”.*{kind} style"):
        check_kind(kind, css)


def test_every_refused_property_is_named_at_once():
    with pytest.raises(ValueError) as caught:
        check_kind("outline", {"fill": "red", "font-size": "9pt", "color": "blue"})
    assert "“font-size”" in str(caught.value) and "“color”" in str(caught.value)
    assert "“fill”" not in str(caught.value)


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValueError, match="kind"):
        check_kind("character", {})


# ----------------------------------------------------------------------------- slots
def test_every_thing_that_can_be_styled_has_its_slots():
    """D304: a container has a box or an outline, its content a paragraph. The table is the one source of truth;
    the server sends it to the clients, which keep no copy."""
    table = {
        thing: [(s.name, [f.name for f in s.reads], s.kind) for s in SLOTS.slots_of(thing)] for thing in SLOTS.things()
    }
    assert table == {
        "paragraph": [("paragraph", ["text", "paragraph", "box"], "paragraph")],
        "text": [("box", ["box"], "box"), ("words", ["text", "paragraph"], "paragraph")],
        "shape": [("outline", ["outline"], "outline"), ("label", ["text", "paragraph"], "paragraph")],
        "image": [("box", [], "box")],
        "diagram": [("box", ["box"], "box")],
        "cell": [("box", ["box"], "box"), ("words", ["text", "paragraph"], "paragraph")],
    }


def test_a_slot_never_reads_a_facet_its_kind_cannot_hold():
    for thing in SLOTS.things():
        for slot in SLOTS.slots_of(thing):
            assert set(slot.reads) <= set(KINDS[slot.kind]), f"{thing}.{slot.name}"


def test_a_style_fits_a_slot_when_its_kind_holds_everything_the_slot_reads():
    """D316: a box slot reads only the box, so it takes a box style and a paragraph style (which may hold a box) —
    that is how one bundle fills both slots of a cell or a text box (D309, D311)."""
    words = SLOTS.slot("text", "words")
    box = SLOTS.slot("text", "box")
    assert fits("paragraph", words) and not fits("box", words) and not fits("outline", words)
    assert fits("box", box) and fits("paragraph", box) and not fits("outline", box)
    assert fits("outline", SLOTS.slot("shape", "outline")) and not fits("paragraph", SLOTS.slot("shape", "outline"))
    assert fits("paragraph", SLOTS.slot("paragraph", "paragraph"))
    assert not fits("box", SLOTS.slot("paragraph", "paragraph"))


def test_a_slot_that_reads_nothing_takes_only_its_own_kind():
    picture = SLOTS.slot("image", "box")
    assert fits("box", picture) and not fits("paragraph", picture) and not fits("outline", picture)
    assert not fits("character", picture)


def test_asking_for_a_thing_or_slot_that_does_not_exist_says_so():
    with pytest.raises(KeyError, match="slide"):
        SLOTS.slots_of("slide")
    with pytest.raises(KeyError, match="label"):
        SLOTS.slot("text", "label")


# ----------------------------------------------------------------------------- the table is open (D315)
def test_a_later_thing_is_one_more_row_and_changes_nothing_else():
    """D315: a slide background, a page, the parts of a diagram — each comes later as a row of the table, without
    touching the facets, the kinds, or anything that reads the table."""
    later = SLOTS.with_row("slide", (Slot("background", (BOX_FACET,), "box"),))
    assert later.slots_of("slide")[0].name == "background"
    assert fits("box", later.slot("slide", "background"))
    assert later.slots_of("cell") == SLOTS.slots_of("cell")
    with pytest.raises(KeyError):
        SLOTS.slots_of("slide")  # the table it came from is unchanged


def test_a_row_that_breaks_the_rules_is_refused():
    with pytest.raises(ValueError, match="already"):
        SLOTS.with_row("cell", (Slot("box", (BOX_FACET,), "box"),))
    with pytest.raises(ValueError, match="kind"):
        SLOTS.with_row("slide", (Slot("background", (BOX_FACET,), "page"),))
    with pytest.raises(ValueError, match="outline.*cannot hold"):
        SLOTS.with_row("slide", (Slot("background", (OUTLINE_FACET,), "box"),))
    with pytest.raises(ValueError, match="twice"):
        SLOTS.with_row("slide", (Slot("a", (BOX_FACET,), "box"), Slot("a", (BOX_FACET,), "box")))
    with pytest.raises(ValueError, match="no slots"):
        SlotTable({"slide": ()})


def test_the_table_travels_as_plain_data():
    """What the server's `style_model` will answer (plan, step 1.5): facets, kinds and slots by name."""
    data = SLOTS.to_data()
    assert data["facets"]["outline"] == ["fill", "stroke", "stroke-width"]
    assert data["kinds"]["box"] == ["box"]
    assert data["slots"]["shape"] == [
        {"name": "outline", "reads": ["outline"], "kind": "outline", "takes": ["outline"]},
        {"name": "label", "reads": ["text", "paragraph"], "kind": "paragraph", "takes": ["paragraph"]},
    ]
    assert data["slots"]["cell"][0]["takes"] == ["paragraph", "box"]  # a bundle fills a cell's box (D311, D316)
