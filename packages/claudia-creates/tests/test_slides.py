"""The slide model: typed objects (text boxes and shapes), their commands, undo, locks and redaction (E10.1, E10.6)."""

import random

import pytest
from conftest import SLIDE, define, put, reopen, shape_object, text_box

import claudia_creates.model as model_module
from claudia_core import Batch, Document, MemoryStore, RegionHeld, Revision, UndoConflict, UndoRefused, encode
from claudia_creates import (
    AddObject,
    AddSlide,
    ForgetShape,
    MoveObject,
    ObjectSet,
    RemoveObject,
    RemoveSlide,
    ResizeObject,
    SetText,
    SlideModel,
    SlideObject,
)
from claudia_creates.events import ObjectsChanged, ShapesChanged, SlidesChanged


def ids(doc, slide=SLIDE):
    return [o.id for o in doc.model.objects_on(slide)]


# -- the first draft's whole story: add, move, resize, edit, remove, undo ------------------------------------
def test_a_text_box_is_added_moved_resized_edited_and_removed_and_every_step_can_be_undone(doc):
    put(doc, text_box(text="Hello"))
    assert doc.model.get("t1").text == "Hello"

    doc.execute(MoveObject("t1", 300, 250), author="ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").y) == (300, 250)

    doc.execute(ResizeObject("t1", 290, 240, 500, 200), author="ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").y, doc.model.get("t1").w, doc.model.get("t1").h) == (
        290,
        240,
        500,
        200,
    )

    doc.execute(SetText("t1", "Hello, world"), author="ana")
    assert doc.model.get("t1").text == "Hello, world"

    doc.execute(RemoveObject("t1"), author="ana")
    assert ids(doc) == []

    for expected in (
        lambda o: o.text == "Hello, world",  # undo the removal
        lambda o: o.text == "Hello",  # undo the new text
        lambda o: (o.w, o.h) == (400, 120) and (o.x, o.y) == (300, 250),  # undo the resize
        lambda o: (o.x, o.y) == (100, 100),  # undo the move
    ):
        doc.undo("ana")
        assert expected(doc.model.get("t1"))
    doc.undo("ana")
    assert ids(doc) == [], "the last undo takes the box away again"


def test_redo_brings_a_step_back(doc):
    put(doc, text_box())
    doc.execute(MoveObject("t1", 50, 60), author="ana")
    doc.undo("ana")
    doc.redo("ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").y) == (50, 60)


def test_objects_keep_their_stacking_order_even_through_remove_and_undo(doc):
    for name in ("a", "b", "c"):
        put(doc, text_box(name, y=100 + 10 * (ord(name) - ord("a"))))
    assert ids(doc) == ["a", "b", "c"], "the one added last is on top"
    doc.execute(RemoveObject("b"), author="ana")
    assert ids(doc) == ["a", "c"]
    doc.undo("ana")
    assert ids(doc) == ["a", "b", "c"], "undo puts it back where it was, not on top"


def test_a_shape_is_added_with_its_definition_and_undo_takes_both_away(doc):
    put(doc, shape_object())
    assert doc.model.get("r1").shape == "rectangle"
    assert "rectangle" in doc.model.shapes, "the document keeps its own copy of the outline"
    doc.undo("ana")
    assert ids(doc) == [] and doc.model.shapes == {}


def test_the_document_keeps_working_without_the_library_because_it_holds_the_outline(doc):
    put(doc, shape_object(shape="circle", w=200, h=200))
    again = reopen(doc)
    assert again.model.shapes["circle"].path.startswith("M50 0 A50 50")
    assert again.model.serialize() == doc.model.serialize()


# -- what a model refuses ------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "changes",
    [
        {"slide": "nowhere"},
        {"style": "fancy"},
        {"kind": "picture"},
        {"shape": "rectangle"},  # a text box has no outline
        {"id": "Bad Id"},
        {"id": ""},
        {"x": -1},
        {"y": -1},
        {"x": 1300},  # 1300 + 400 is wider than the slide
        {"y": 800},  # 800 + 120 is taller than the slide
        {"w": 19},
        {"h": 19},
        {"w": 2000, "x": 0},
        {"x": 1.5},
        {"x": True},
        {"w": "400"},
        {"text": "x" * 20_001},
        {"text": 5},
    ],
)
def test_an_object_that_is_not_right_is_refused_and_changes_nothing(doc, changes):
    before = doc.model.serialize()
    with pytest.raises((ValueError, TypeError)):
        doc.execute(AddObject(text_box(**changes)), author="ana")
    assert doc.model.serialize() == before
    assert doc.log.next_revision("main") == Revision("main", 1), "nothing was written to the history"


@pytest.mark.parametrize(
    "changes",
    [{"kind": "shape", "shape": None}, {"kind": "shape", "shape": "hexagon"}, {"kind": "shape", "shape": "Rect"}],
)
def test_a_shape_object_needs_a_shape_the_document_has(doc, changes):
    with pytest.raises(ValueError, match="shape"):
        doc.execute(AddObject(text_box(**changes)), author="ana")


def test_an_id_can_only_be_used_once(doc):
    put(doc, text_box())
    with pytest.raises(ValueError, match="exists"):
        put(doc, text_box())


def test_there_is_a_limit_to_the_objects_on_a_slide(doc, monkeypatch):
    monkeypatch.setattr(model_module, "MAX_OBJECTS_PER_SLIDE", 2)
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    with pytest.raises(ValueError, match="at most 2"):
        put(doc, text_box("c"))


def test_commands_on_an_object_that_is_not_there_are_refused(doc):
    for command in (
        MoveObject("ghost", 1, 1),
        ResizeObject("ghost", 1, 1, 50, 50),
        SetText("ghost", "x"),
        RemoveObject("ghost"),
    ):
        with pytest.raises(ValueError, match="ghost"):
            doc.execute(command, author="ana")


def test_an_object_cannot_be_moved_or_resized_off_the_slide(doc):
    put(doc, text_box())
    for command in (
        MoveObject("t1", -1, 0),
        MoveObject("t1", 1300, 100),
        MoveObject("t1", 100, 800),
        ResizeObject("t1", 100, 100, 10, 120),
        ResizeObject("t1", 100, 100, 1600, 120),
    ):
        with pytest.raises(ValueError, match=r"slide|size"):
            doc.execute(command, author="ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").w) == (100, 400)


def test_a_circle_stays_a_circle(doc):
    put(doc, shape_object("c1", "circle", w=200, h=200))
    with pytest.raises(ValueError, match="proportions"):
        doc.execute(ResizeObject("c1", 200, 200, 300, 200), author="ana")
    doc.execute(ResizeObject("c1", 200, 200, 300, 301), author="ana")  # one unit of rounding is fine
    with pytest.raises(ValueError, match="proportions"):
        put(doc, shape_object("c2", "circle", w=200, h=100))


def test_a_shape_that_is_in_use_cannot_be_forgotten_and_one_that_exists_cannot_be_defined_again(doc):
    put(doc, shape_object())
    with pytest.raises(ValueError, match="in use"):
        doc.execute(ForgetShape("rectangle"), author="ana")
    with pytest.raises(ValueError, match="already"):
        doc.execute(define(), author="ana")
    doc.execute(RemoveObject("r1"), author="ana")
    doc.execute(ForgetShape("rectangle"), author="ana")
    assert doc.model.shapes == {}


def test_slides_are_added_and_only_empty_ones_removed(doc):
    doc.execute(AddSlide("s2"), author="ana")
    assert doc.model.slides == [SLIDE, "s2"]
    with pytest.raises(ValueError, match="exists"):
        doc.execute(AddSlide("s2"), author="ana")
    put(doc, text_box())
    with pytest.raises(ValueError, match="objects"):
        doc.execute(RemoveSlide(SLIDE), author="ana")
    doc.execute(RemoveSlide("s2"), author="ana")
    doc.undo("ana")
    assert doc.model.slides == [SLIDE, "s2"]


def test_a_new_presentation_starts_with_one_empty_slide():
    model = SlideModel.empty()
    assert model.slides == [SLIDE] and model.objects_on(SLIDE) == []
    assert SlideModel.restore(model.serialize()).slides == [SLIDE]
    doc = Document(SlideModel.empty(), store=MemoryStore())
    assert reopen(doc).model.slides == [SLIDE], "a replay starts from the same empty presentation"


# -- working together (D46, D47) -----------------------------------------------------------------------------
def test_a_removed_slide_comes_back_where_it_was(doc):
    for name in ("s2", "s3"):
        doc.execute(AddSlide(name), author="ana")
    doc.execute(RemoveSlide("s2"), author="ana")
    assert doc.model.slides == [SLIDE, "s3"]
    doc.undo("ana")
    assert doc.model.slides == [SLIDE, "s2", "s3"]


def test_undo_of_a_removal_is_refused_when_a_colleague_took_the_shape_away_meanwhile(doc):
    put(doc, shape_object())
    doc.execute(RemoveObject("r1"), author="ana")
    doc.execute(ForgetShape("rectangle"), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")


def test_undo_never_overwrites_a_colleagues_move_of_the_same_object(doc):
    put(doc, text_box())
    doc.execute(MoveObject("t1", 150, 150), author="ana")
    doc.execute(MoveObject("t1", 600, 300), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").y) == (600, 300)


def test_a_move_and_a_new_text_by_two_people_do_not_get_in_each_others_way(doc):
    put(doc, text_box())
    doc.execute(MoveObject("t1", 150, 150), author="ana")
    doc.execute(SetText("t1", "ben was here"), author="ben")
    doc.undo("ana")
    assert (doc.model.get("t1").x, doc.model.get("t1").y) == (100, 100)
    assert doc.model.get("t1").text == "ben was here", "ben's words stay"


def test_undo_of_a_resize_is_refused_when_a_colleague_moved_the_object(doc):
    put(doc, text_box())
    doc.execute(ResizeObject("t1", 100, 100, 500, 150), author="ana")
    doc.execute(MoveObject("t1", 300, 300), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")


def test_undo_of_text_is_refused_when_a_colleague_wrote_after_me(doc):
    put(doc, text_box())
    doc.execute(SetText("t1", "mine"), author="ana")
    doc.execute(SetText("t1", "theirs"), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")


def test_taking_back_my_new_box_is_refused_when_a_colleague_worked_on_it(doc):
    put(doc, text_box())
    doc.execute(SetText("t1", "ben's idea"), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert doc.model.get("t1").text == "ben's idea"


def test_taking_back_my_new_shape_is_refused_while_a_colleague_uses_the_same_outline(doc):
    put(doc, shape_object("r1"))
    put(doc, shape_object("r2", y=500), author="ben")
    with pytest.raises(UndoConflict):
        doc.undo("ana")
    assert ids(doc) == ["r1", "r2"]


def test_undo_of_a_removal_comes_back_even_if_a_colleague_worked_elsewhere(doc):
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    doc.execute(RemoveObject("a"), author="ana")
    doc.execute(MoveObject("b", 700, 400), author="ben")
    doc.undo("ana")
    assert ids(doc) == ["a", "b"]


def test_a_colleagues_lock_stops_an_edit_of_that_object_only(doc):
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    doc.lock("ben", [ObjectSet(SLIDE, frozenset({"a"}))], ttl=5)
    with pytest.raises(RegionHeld):
        doc.execute(MoveObject("a", 10, 10), author="ana")
    with pytest.raises(RegionHeld):
        doc.execute(SetText("a", "x"), author="ana")
    with pytest.raises(RegionHeld):
        doc.execute(RemoveObject("a"), author="ana")
    doc.execute(MoveObject("b", 10, 10), author="ana")
    put(doc, text_box("c"))  # a new object is nobody's lock


def test_a_lock_blocks_an_undo_that_would_touch_it(doc):
    put(doc, text_box())
    doc.execute(MoveObject("t1", 10, 10), author="ana")
    doc.lock("ben", [ObjectSet(SLIDE, frozenset({"t1"}))], ttl=5)
    with pytest.raises(UndoRefused):
        doc.undo("ana")


def test_the_holder_can_still_change_what_they_hold(doc):
    put(doc, text_box())
    doc.lock("ben", [ObjectSet(SLIDE, frozenset({"t1"}))], ttl=5)
    doc.execute(SetText("t1", "ben types"), author="ben")
    assert doc.model.get("t1").text == "ben types"


# -- regions -------------------------------------------------------------------------------------------------
def test_object_sets_overlap_when_they_share_an_object_on_the_same_slide():
    a = ObjectSet("s1", frozenset({"x", "y"}))
    assert a.overlaps(ObjectSet("s1", frozenset({"y"})))
    assert not a.overlaps(ObjectSet("s1", frozenset({"z"})))
    assert not a.overlaps(ObjectSet("s2", frozenset({"x"})))


def test_a_colleagues_selection_follows_removals_until_nothing_is_left(doc):
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    doc.show_presence("ben", [ObjectSet(SLIDE, frozenset({"a", "b"}))])
    doc.execute(RemoveObject("a"), author="ana")
    assert doc.presence.of("ben").regions == (ObjectSet(SLIDE, frozenset({"b"})),)
    doc.execute(RemoveObject("b"), author="ana")
    assert doc.presence.of("ben") is None


def test_regions_travel_as_data_and_bad_data_is_refused(doc):
    region = ObjectSet(SLIDE, frozenset({"a", "b"}))
    assert doc.model.region_from_data(region.to_data()) == region
    for bad in (
        {},
        {"slide": 1, "ids": []},
        {"slide": SLIDE, "ids": "a"},
        {"slide": SLIDE, "ids": [1]},
        {"slide": SLIDE},
    ):
        with pytest.raises(ValueError, match="selection"):
            doc.model.region_from_data(bad)
    with pytest.raises(ValueError, match="selection"):
        doc.model.region_from_data({"slide": SLIDE, "ids": [f"o{i}" for i in range(100)]})


# -- what views are told -------------------------------------------------------------------------------------
def collect(doc):
    seen = []
    doc.subscribe(seen.append)
    return seen


def test_views_are_told_what_changed_and_the_new_stacking_order(doc):
    seen = collect(doc)
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    doc.execute(MoveObject("a", 20, 30), author="ana")
    doc.execute(RemoveObject("b"), author="ana")
    told = [e for e in seen if isinstance(e, ObjectsChanged)]
    assert [(e.slide, [o.id for o in e.changed], list(e.removed), list(e.order)) for e in told] == [
        (SLIDE, ["a"], [], ["a"]),
        (SLIDE, ["b"], [], ["a", "b"]),
        (SLIDE, ["a"], [], ["a", "b"]),
        (SLIDE, [], ["b"], ["a"]),
    ]
    data = told[2].to_data()
    assert data["type"] == "objects" and data["slide"] == SLIDE and data["order"] == ["a", "b"]
    assert data["changed"][0]["x"] == 20 and data["removed"] == []


def test_views_hear_about_shapes_and_slides(doc):
    seen = collect(doc)
    doc.execute(define(), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    shapes = [e for e in seen if isinstance(e, ShapesChanged)]
    assert shapes[0].to_data()["type"] == "shape" and shapes[0].to_data()["definition"]["id"] == "rectangle"
    assert any(isinstance(e, SlidesChanged) for e in seen)
    doc.execute(ForgetShape("rectangle"), author="ana")
    assert [e for e in seen if isinstance(e, ShapesChanged)][-1].to_data() == {
        "type": "shape",
        "id": "rectangle",
        "definition": None,
    }


# -- the history reads like sentences ------------------------------------------------------------------------
def test_the_history_has_labels_and_sentences_people_can_read():
    box = text_box(text="Quarterly results")
    assert AddObject(box).label == "Add text box" and "Quarterly results" in AddObject(box).summary
    assert AddObject(shape_object()).label == "Add shape" and "rectangle" in AddObject(shape_object()).summary
    assert (AddSlide("s2").summary, RemoveSlide("s2").summary) == ("Added a slide", "Removed a slide")
    assert MoveObject("t1", 1, 2).label == "Move object"
    assert ResizeObject("t1", 1, 2, 30, 40).label == "Resize object"
    assert SetText("t1", "x").label == "Edit text"
    assert RemoveObject("t1").label == "Remove object"
    for command in (AddObject(box), MoveObject("t1", 1, 2), SetText("t1", "x"), RemoveObject("t1")):
        assert command.summary.strip()


# -- documents are forever -----------------------------------------------------------------------------------
def test_every_command_survives_the_log_and_a_model_survives_its_snapshot(doc):
    put(doc, text_box("a", text="words"))
    put(doc, shape_object("b", "circle", w=200, h=200))
    doc.execute(MoveObject("a", 5, 6), author="ana")
    doc.execute(ResizeObject("b", 10, 10, 250, 250), author="ana")
    doc.execute(SetText("b", "inside"), author="ana")
    doc.execute(RemoveObject("a"), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    assert reopen(doc).model.serialize() == doc.model.serialize()
    assert SlideModel.restore(doc.model.serialize()).serialize() == doc.model.serialize()


def test_command_data_round_trips_and_kinds_are_namespaced():
    registry = SlideModel.registry
    commands = [
        AddSlide("s1"),
        RemoveSlide("s1"),
        AddObject(text_box(), at=0),
        AddObject(shape_object()),
        RemoveObject("t1"),
        MoveObject("t1", 1, 2),
        ResizeObject("t1", 1, 2, 30, 40),
        SetText("t1", "x"),
        define(),
        ForgetShape("rectangle"),
    ]
    for command in commands:
        assert command.kind.startswith("creates.")
        assert registry.decode(encode(command)) == command


def test_equal_states_serialize_equally_whatever_order_they_were_reached_in(doc):
    put(doc, text_box("a"))
    put(doc, text_box("b"))
    other = Document(SlideModel.empty(), store=MemoryStore())
    other.execute(AddObject(text_box("a")), author="x")
    other.execute(AddObject(text_box("b")), author="x")
    assert other.model.serialize() == doc.model.serialize()


# -- redaction (E1.8) ----------------------------------------------------------------------------------------
def test_redacting_a_secret_text_keeps_the_object_where_it_is(doc):
    put(doc, text_box())
    secret = doc.execute(SetText("t1", "confidential figures"), author="ben")
    doc.redact([secret.revision])
    assert doc.model.get("t1").text == ""
    assert (doc.model.get("t1").x, doc.model.get("t1").w) == (100, 400)
    assert reopen(doc).model.serialize() == doc.model.serialize()


def test_redacting_an_object_added_with_words_keeps_its_place_and_shape(doc):
    added = put(doc, shape_object(text="secret plan"))
    doc.execute(MoveObject("r1", 500, 400), author="ana")
    doc.redact([added.revision])
    assert doc.model.get("r1").text == "" and doc.model.get("r1").shape == "rectangle"
    assert (doc.model.get("r1").x, doc.model.get("r1").y) == (500, 400), "the later move still has its object"
    assert reopen(doc).model.serialize() == doc.model.serialize()


# -- random sessions replay identically ----------------------------------------------------------------------
def random_step(rng, doc, serial):
    author = rng.choice(["ana", "ben"])
    objects = doc.model.objects_on(SLIDE)
    choice = rng.choice(["add", "add", "move", "resize", "text", "remove", "undo", "redo"])
    if choice == "add" or not objects:
        shape = rng.choice([None, "rectangle", "circle", "triangle"])
        size = rng.randrange(40, 300)
        base = {
            "x": rng.randrange(0, 1000),
            "y": rng.randrange(0, 500),
            "w": size,
            "h": size if shape == "circle" else 80,
        }
        obj = text_box(f"o{serial}", **base) if shape is None else shape_object(f"o{serial}", shape, **base)
        return author, [
            Batch((define(shape), AddObject(obj))) if shape and shape not in doc.model.shapes else AddObject(obj)
        ]
    target = rng.choice(objects)
    if choice == "move":
        return author, [MoveObject(target.id, rng.randrange(0, 1000), rng.randrange(0, 500))]
    if choice == "resize":
        size = rng.randrange(40, 300)
        side = size if target.shape == "circle" else 90
        return author, [ResizeObject(target.id, rng.randrange(0, 1000), rng.randrange(0, 500), size, side)]
    if choice == "text":
        return author, [SetText(target.id, f"text {rng.randrange(1000)}")]
    if choice == "remove":
        return author, [RemoveObject(target.id)]
    return author, [choice]


@pytest.mark.parametrize("seed", range(8))
def test_random_sessions_replay_identically_with_the_same_undo_stacks(doc, seed):
    rng = random.Random(seed)
    for serial in range(60):
        author, steps = random_step(rng, doc, serial)
        try:
            for step in steps:
                if step == "undo":
                    doc.undo(author)
                elif step == "redo":
                    doc.redo(author)
                else:
                    doc.execute(step, author=author)
        except ValueError, UndoConflict, UndoRefused:
            continue
    again = reopen(doc)
    assert again.model.serialize() == doc.model.serialize()
    for who in ("ana", "ben"):
        a, b = doc.history_for(who), again.history_for(who)
        assert (a.undo_label, a.redo_label, a.can_undo, a.can_redo) == (
            b.undo_label,
            b.redo_label,
            b.can_undo,
            b.can_redo,
        )
    assert doc.materialize(doc.revision).serialize() == doc.model.serialize()


def test_a_slide_object_knows_what_it_is_made_of():
    box = text_box(text="hi")
    assert SlideObject.from_data(box.to_data()) == box
    assert set(box.to_data()) == {"id", "slide", "kind", "x", "y", "w", "h", "style", "text", "shape"}
    assert define().to_data()["shape"]["id"] == "rectangle"
