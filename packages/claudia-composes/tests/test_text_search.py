"""Search and replace in a text (E9.28, D281-D289): which texts a document offers, where they are, what a replacement
changes, and what it must leave alone. The engine is claudia-search's; this is composes' part of it."""

import pytest

from claudia_composes import BlockAnchor, InsertText, SetStyle, SplitBlock, TextModel, TextRange
from claudia_composes.search import (
    EXTRA_PARTS,
    KINDS,
    block_at,
    object_at,
    plan_replacement,
    replace_command,
    scan_text,
    text_texts,
)
from claudia_core import (
    DefineShape,
    Document,
    MemoryStore,
    ObjectBody,
    ObjectSet,
    ShapeDefinition,
    VisualObject,
    paragraph_for,
)
from claudia_search import Query


def search(text, replace=None, **options):
    data = {"mode": "text", "text": text, **options}
    if replace is not None:
        data["replace"] = [{"text": replace}]
    return Query.from_data(data).compile(EXTRA_PARTS)


def document(*paragraphs):
    """A document of paragraphs ``(style, text)``, all written by ann."""
    d = Document(TextModel(), store=MemoryStore())
    for number, (style, text) in enumerate(paragraphs):
        if number:
            d.execute(
                SplitBlock(f"b{number}", len(d.model.block(f"b{number}").text), f"b{number + 1}", style), author="ann"
            )
        elif style != "body":
            d.execute(SetStyle("b1", style), author="ann")
        d.execute(InsertText(f"b{number + 1}", 0, text), author="ann")
    return d


def add_box(d, block="b1", offset=0, words="a red note", description="", kind="text", object_id="o1"):
    style, words_style = ("plain-box", "body") if kind == "text" else ("plain-shape", "shape-label")
    shape = None
    if kind == "shape":
        shape = "rectangle"
        d.execute(DefineShape(ShapeDefinition("rectangle", "Rectangle", "M0 0H100V100H0Z")), author="ann")
    body = ObjectBody(
        object_id,
        kind,
        200,
        80,
        style,
        paragraph_for(object_id, words_style, words),
        ref=shape,
        description=description,
    )
    d.model.insert_object(VisualObject(body, BlockAnchor(block, offset)))


def places(found):
    return [(m.at, m.kind) for m in found.matches]


# ---------------------------------------------------------------------------------------------- what is offered
def test_a_paragraph_is_text_a_heading_or_a_remark_by_its_style_and_the_styles_it_is_based_on():
    d = document(("title", "red title"), ("heading-1", "red section"), ("body", "red body"), ("remark", "red remark"))
    assert [(t.at, t.kind) for t in text_texts(d.model, KINDS)] == [
        (block_at("b1"), "heading"),
        (block_at("b2"), "heading"),
        (block_at("b3"), "text"),
        (block_at("b4"), "remark"),
    ]


def test_a_style_made_from_a_heading_is_a_heading_too():
    d = document(("body", "red"))
    d.model.styles = d.model.styles  # (the built-in book)
    from claudia_core import CreateStyle, StyleDef

    d.execute(
        CreateStyle(StyleDef("chapter", "Chapter", "a chapter", "heading-1", {"font-size": "22pt"})), author="ann"
    )
    d.execute(SetStyle("b1", "chapter"), author="ann")
    assert [t.kind for t in text_texts(d.model, KINDS)] == ["heading"]


def test_only_the_kinds_asked_for_are_offered():
    d = document(("heading-1", "red"), ("body", "red"), ("remark", "red"))
    assert [t.kind for t in text_texts(d.model, ["text", "remark"])] == ["text", "remark"]


def test_an_empty_paragraph_offers_nothing():
    d = document(("body", ""), ("body", "red"))
    assert [t.at for t in text_texts(d.model, KINDS)] == [block_at("b2")]


def test_the_words_and_the_description_of_an_object_are_texts_of_their_own():
    d = document(("body", "red"))
    add_box(d, words="a red box", description="a red box on a desk")
    items = [(t.at, t.kind, t.text) for t in text_texts(d.model, KINDS)]
    assert items == [
        (block_at("b1"), "text", "red"),
        (object_at("b1", "o1", "box"), "object", "a red box"),
        (object_at("b1", "o1", "description"), "description", "a red box on a desk"),
    ]


def test_the_label_of_a_shape_is_an_object_text_as_well():
    d = document(("body", "x"))
    add_box(d, words="red label", kind="shape")
    assert (object_at("b1", "o1", "label"), "object") in [(t.at, t.kind) for t in text_texts(d.model, KINDS)]


def test_a_kind_that_does_not_exist_is_refused():
    with pytest.raises(ValueError, match="cannot look in 'notes'"):
        list(text_texts(document(("body", "x")).model, ["notes"]))


# ------------------------------------------------------------------------------------------------------ where
def test_a_section_runs_from_its_heading_to_the_next_heading_of_the_same_or_a_higher_level():
    d = document(
        ("title", "red title"),
        ("heading-1", "red one"),
        ("body", "red body one"),
        ("heading-2", "red sub"),
        ("body", "red body sub"),
        ("heading-1", "red two"),
        ("body", "red body two"),
    )
    found = scan_text(d.model, search("red"), kinds=KINDS, scope={"section": "b4"})
    assert [m.at["block"] for m in found.matches] == ["b4", "b5"]  # the subsection only
    found = scan_text(d.model, search("red"), kinds=KINDS, scope={"section": "b3"})
    assert [m.at["block"] for m in found.matches] == ["b2", "b3", "b4", "b5"]  # one, with its subsection


def test_text_before_the_first_section_heading_is_a_section_of_its_own():
    d = document(("title", "red title"), ("body", "red intro"), ("heading-1", "red one"))
    found = scan_text(d.model, search("red"), kinds=KINDS, scope={"section": "b2"})
    assert [m.at["block"] for m in found.matches] == ["b1", "b2"]


def test_a_selection_searches_only_what_is_selected_and_says_where_in_the_paragraph_that_starts():
    d = document(("body", "red one red"), ("body", "red two"), ("body", "red three"))
    scope = {"range": {"from": {"block": "b1", "offset": 4}, "to": {"block": "b3", "offset": 3}}}
    found = scan_text(d.model, search("red"), kinds=KINDS, scope=scope)
    assert places(found) == [
        ({"block": "b1", "offset": 4}, "text"),
        ({"block": "b2"}, "text"),
        ({"block": "b3", "offset": 0}, "text"),
    ]
    assert [(m.start, m.end) for m in found.matches] == [(4, 7), (0, 3), (0, 3)]


def test_a_scope_that_names_nothing_that_exists_is_refused():
    d = document(("body", "x"))
    with pytest.raises(ValueError, match="no such paragraph"):
        scan_text(d.model, search("x"), kinds=KINDS, scope={"section": "b9"})
    with pytest.raises(ValueError, match="a scope is"):
        scan_text(d.model, search("x"), kinds=KINDS, scope={"page": 3})


# ------------------------------------------------------------------------------------------------------ the parts
def test_a_word_is_a_part_of_the_builder():
    query = Query.from_data({"mode": "builder", "parts": [{"what": "word", "count": "once"}]})
    d = document(("body", "red fox"))
    found = scan_text(d.model, query.compile(EXTRA_PARTS), kinds=KINDS)
    assert [(m.start, m.end) for m in found.matches] == [(0, 3), (4, 7)]


def test_a_word_is_not_part_of_a_longer_one():
    query = Query.from_data({"mode": "builder", "parts": [{"what": "word"}, {"what": "text", "value": "s"}]})
    assert scan_text(document(("body", "reds s")).model, query.compile(EXTRA_PARTS), kinds=KINDS).total == 0


# ------------------------------------------------------------------------------------------------- the counting
def test_counts_say_how_many_texts_of_each_kind_hold_a_match():
    d = document(("heading-1", "red"), ("body", "red red"), ("body", "blue"))
    add_box(d, words="red", description="red")
    found = scan_text(d.model, search("red"), kinds=KINDS)
    assert found.counts == {"text": 1, "heading": 1, "remark": 0, "object": 1, "description": 1}
    assert found.total == 5


# ------------------------------------------------------------------------------------------------- replacing
def no_conflicts(regions):
    return []


def replaced(d, query, author="ben", **options):
    made = plan_replacement(d.model, query, kinds=options.pop("kinds", KINDS), conflicts=no_conflicts, **options)
    command = replace_command(d.model, made, author)
    if command is not None:
        d.execute(command, author=author)
    return made


def test_a_replacement_is_one_step_that_undo_takes_back_whole():
    d = document(("body", "red fox"), ("body", "a red hen, a red cow"))
    made = replaced(d, search("red", "blue"))
    assert [b.text for b in d.model.blocks] == ["blue fox", "a blue hen, a blue cow"]
    assert len(made.changes) == 2
    d.undo("ben")
    assert [b.text for b in d.model.blocks] == ["red fox", "a red hen, a red cow"]


def test_the_history_names_the_step_by_its_size():
    d = document(("body", "red"), ("body", "red"))
    made = plan_replacement(d.model, search("red", "blue"), kinds=KINDS, conflicts=no_conflicts)
    assert replace_command(d.model, made, "ben").label == "Replace in 2 texts"


def test_the_words_around_a_replacement_keep_their_author_and_the_new_words_are_the_replacers():
    d = document(("body", "the red fox"))
    replaced(d, search("red", "grey"), author="ben")
    block = d.model.block("b1")
    assert block.text == "the grey fox"
    assert [(r.length, r.author) for r in block.runs] == [(4, "ann"), (4, "ben"), (4, "ann")]


def test_a_paragraph_keeps_its_style_and_an_object_hanging_in_it_stays_with_its_word():
    d = document(("heading-1", "the red fox"))
    add_box(d, offset=8, words="note")
    replaced(d, search("red", "grey"), kinds=["heading"])
    assert d.model.block("b1").style == "heading-1"
    assert d.model.objects["o1"].anchor.block == "b1"


def test_only_the_kinds_chosen_are_replaced():
    d = document(("heading-1", "red"), ("body", "red"))
    replaced(d, search("red", "blue"), kinds=["text"])
    assert [b.text for b in d.model.blocks] == ["red", "blue"]


def test_the_words_of_an_object_are_rewritten_in_place_and_keep_their_authors():
    d = document(("body", "x"))
    add_box(d, words="a red note")
    replaced(d, search("red", "blue"), kinds=["object"], author="ben")
    words = d.model.objects["o1"].body.paragraph
    assert words.text == "a blue note"
    assert [(r.length, r.author) for r in words.runs][1] == (4, "ben")


def test_a_description_is_replaced_and_stays_a_description():
    d = document(("body", "x"))
    add_box(d, words="note", description="a red box")
    replaced(d, search("red", "blue"), kinds=["description"])
    assert d.model.objects["o1"].body.description == "a blue box"


def test_a_pattern_with_kept_parts_is_stored_as_text_not_as_a_pattern():
    d = document(("body", "€12 and €30"))
    query = Query.from_data({"mode": "pattern", "find": "€(\\d+)", "replace": "\\1 EUR"}).compile()
    replaced(d, query)
    assert d.model.block("b1").text == "12 EUR and 30 EUR"


def test_nothing_to_change_makes_no_command():
    d = document(("body", "blue"))
    made = plan_replacement(d.model, search("red", "x"), kinds=KINDS, conflicts=no_conflicts)
    assert made.changes == [] and replace_command(d.model, made, "ben") is None


def test_matches_a_person_left_alone_stay():
    d = document(("body", "red, red"))
    made = replaced(d, search("red", "blue"), leave=[(block_at("b1"), 0)])
    assert d.model.block("b1").text == "red, blue"
    assert made.skipped == []


def test_a_paragraph_typed_into_since_the_person_looked_is_skipped_not_guessed_at():
    d = document(("body", "red hen"))
    made = replaced(d, search("red|hen", "x"), leave=[(block_at("b1"), 1, "red")])
    assert d.model.block("b1").text == "red hen"
    assert [(s.at, s.reason) for s in made.skipped] == [(block_at("b1"), "changed")]


# -------------------------------------------------------------------------------------------------- the locks
def test_a_match_inside_the_zone_somebody_else_holds_is_skipped_and_named():
    d = document(("body", "red fox and red hen"), ("body", "red cow"))
    d.lock("ann", [TextRange("b1", 14, 19)], ttl=5)  # round "hen", beyond the second "red" at 12-15? it overlaps
    made = plan_replacement(
        d.model, search("red", "blue"), kinds=KINDS, conflicts=lambda regions: d.presence.conflicts("ben", regions)
    )
    assert [(s.at, s.reason, s.by) for s in made.skipped] == [(block_at("b1"), "locked", "ann")]
    assert [c.at for c in made.changes] == [block_at("b2")]


def test_a_zone_held_elsewhere_in_the_paragraph_does_not_stop_the_replacement():
    d = document(("body", "red fox and a lazy dog"))
    d.lock("ann", [TextRange("b1", 14, 22)], ttl=5)
    made = plan_replacement(
        d.model, search("red", "blue"), kinds=KINDS, conflicts=lambda regions: d.presence.conflicts("ben", regions)
    )
    assert made.skipped == [] and len(made.changes) == 1


def test_an_object_somebody_holds_is_skipped_and_named():
    d = document(("body", "x"))
    add_box(d, words="a red note")
    d.lock("ann", [ObjectSet("b1", frozenset({"o1"}))], ttl=5)
    made = plan_replacement(
        d.model, search("red", "blue"), kinds=KINDS, conflicts=lambda regions: d.presence.conflicts("ben", regions)
    )
    assert [(s.at, s.reason, s.by) for s in made.skipped] == [(object_at("b1", "o1", "box"), "locked", "ann")]


def test_a_result_that_is_too_long_is_skipped():
    d = document(("body", "red"))
    made = plan_replacement(d.model, search("red", "x" * 30), kinds=KINDS, conflicts=no_conflicts, max_length=10)
    assert [s.reason for s in made.skipped] == ["too_long"]


def test_a_section_starts_at_any_heading_by_its_level_and_the_title_starts_none():
    d = document(("title", "red title"), ("heading-3", "red three"), ("body", "red body"), ("heading-4", "red four"))
    found = scan_text(d.model, search("red"), kinds=KINDS, scope={"section": "b4"})
    assert [m.at["block"] for m in found.matches] == ["b4"]
    found = scan_text(d.model, search("red"), kinds=KINDS, scope={"section": "b3"})
    assert [m.at["block"] for m in found.matches] == ["b2", "b3", "b4"]
    assert [t.kind for t in text_texts(d.model, KINDS)][:2] == ["heading", "heading"]
