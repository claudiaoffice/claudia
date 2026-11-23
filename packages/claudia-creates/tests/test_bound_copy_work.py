"""Keeping the bound copies equal to their placeholders looks only at what a command touched (PERF-12, D1531)."""

import pytest
from conftest import add, frame, resize, text_box

import claudia_creates.model as model_module
from claudia_core import InsertText
from claudia_creates import AddSlide, DefineLayout, SetSlideLayout
from claudia_creates.layout_plans import update_layout

SLIDES = 30


@pytest.fixture
def deck(doc):
    """A layout with a title placeholder, and ``SLIDES`` slides on it, each with a heading bound to the title."""
    doc.execute(DefineLayout("list", "List"), author="ana")
    doc.execute(add(text_box("title", slide="list", purpose="Title", x=100, y=50, w=800, h=100)), author="ana")
    for number in range(1, SLIDES + 1):
        slide = f"s{number}"
        if slide != "s1":
            doc.execute(AddSlide(slide), author="ana")
        doc.execute(SetSlideLayout(slide, "list"), author="ana")
        doc.execute(
            add(text_box(f"h{number}", slide=slide, x=100, y=50, w=800, h=100, bound_to_placeholder="title")),
            author="ana",
        )
    return doc


@pytest.fixture
def looked_at(monkeypatch):
    """The ids of the objects whose copy was compared with its placeholder."""
    seen: list[str] = []
    original = model_module._bound_to

    def counting(obj, placeholder):
        seen.append(obj.id)
        return original(obj, placeholder)

    monkeypatch.setattr(model_module, "_bound_to", counting)
    return seen


def test_a_command_on_a_free_object_leaves_the_bound_ones_alone(deck, looked_at):
    deck.execute(add(text_box("note", slide="s7", x=1, y=1, w=50, h=20)), author="ana")
    assert looked_at == []


def test_typing_in_a_bound_object_looks_at_that_object_only(deck, looked_at):
    deck.execute(InsertText("h3", 0, "Hello"), author="ana")
    assert looked_at == ["h3"]


def test_changing_the_placeholder_repairs_every_slide_that_follows_it(deck, looked_at):
    deck.execute(update_layout(deck.model, "s1", resize("h1", 120, 60, 700, 90)), author="ana")
    assert sorted(looked_at) == sorted(f"h{n}" for n in range(1, SLIDES + 1))
    assert all(frame(deck, f"h{n}") == (120, 60, 700, 90) for n in range(1, SLIDES + 1))


def test_putting_a_slide_on_another_layout_looks_at_the_objects_of_that_slide_only(deck, looked_at):
    deck.execute(DefineLayout("wide", "Wide"), author="ana")
    looked_at.clear()
    deck.execute(SetSlideLayout("s2", "wide"), author="ana")
    assert looked_at == []  # nothing on "wide" to follow: the binding is inert
    deck.execute(SetSlideLayout("s2", "list"), author="ana")
    assert looked_at == ["h2"]


def test_undo_repairs_what_the_undone_command_had_changed(deck, looked_at):
    deck.execute(update_layout(deck.model, "s1", resize("h1", 120, 60, 700, 90)), author="ana")
    deck.undo("ana")
    assert all(frame(deck, f"h{n}") == (100, 50, 800, 100) for n in range(1, SLIDES + 1))
