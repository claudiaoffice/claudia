"""Running a search over a document's texts, and planning a replacement, for any app (CODE-18).

The places are made up on purpose: a paragraph and an offset, a slide and an object. Nothing here may depend on
sheets, rows and columns.
"""

import time

import pytest

from claudia_search import Query, SearchError, Text, location_key, plan, scan
from claudia_search.testing import STOPPED_IN_TIME


def search(text, replace=None, **options):
    data = {"mode": "text", "text": text, **options}
    if replace is not None:
        data["replace"] = [{"text": replace}]
    return Query.from_data(data).compile()


def texts(*items):
    return [Text({"paragraph": n, "object": None}, kind, text) for n, (kind, text) in enumerate(items)]


# ------------------------------------------------------------------------------------------------------ the places
def test_a_place_has_one_key_whatever_the_order_of_its_fields():
    assert location_key({"slide": 2, "object": "a"}) == location_key({"object": "a", "slide": 2})
    assert location_key({"slide": 2}) != location_key({"slide": 3})


def test_every_answer_names_its_place_by_the_apps_own_at():
    found = scan(texts(("body", "red fox"), ("title", "a red hen")), search("red"))
    assert [m.at for m in found.matches] == [{"paragraph": 0, "object": None}, {"paragraph": 1, "object": None}]
    assert found.matches[1].to_data() == {
        "at": {"paragraph": 1, "object": None},
        "kind": "title",
        "number": 0,
        "start": 2,
        "end": 5,
        "parts": [],
        "after": None,
        "text": "a red hen",
        "excerpt": [2, 5],
        "clipped": [False, False],
    }


# --------------------------------------------------------------------------------------------------------- looking
def test_counts_are_of_texts_by_their_kind_and_the_total_is_of_matches():
    found = scan(texts(("body", "a a"), ("body", "a"), ("title", "a"), ("title", "b")), search("a"))
    assert found.counts == {"body": 2, "title": 1}
    assert found.total == 4


def test_a_kind_that_is_never_replaced_has_no_after():
    found = scan(texts(("body", "red"), ("shown", "red")), search("red", "blue"), replaceable={"body"})
    assert [m.after for m in found.matches] == ["blue", None]


def test_the_list_is_cut_but_the_counts_are_not():
    found = scan(texts(*[("body", "x x")] * 5), search("x"), max_listed=3)
    assert len(found.matches) == 3 and found.truncated
    assert found.total == 10 and found.counts == {"body": 5}


def test_a_long_text_is_shown_as_an_excerpt_around_the_match():
    long = "a" * 200 + "needle" + "b" * 200
    hit = scan(texts(("body", long)), search("needle")).matches[0]
    assert hit.text[hit.excerpt_start : hit.excerpt_end] == "needle"
    assert hit.clipped_before and hit.clipped_after
    assert len(hit.text) == 60 + 6 + 60


def test_a_text_the_conditions_keep_out_is_listed_with_the_reason():
    query = Query.from_data(
        {"mode": "builder", "parts": [{"what": "digit"}], "conditions": [{"kind": "not_contains", "text": "draft"}]}
    ).compile()
    found = scan(texts(("body", "page 4"), ("body", "draft 2")), query)
    assert [m.at["paragraph"] for m in found.matches] == [0]
    assert [(o.at["paragraph"], o.why) for o in found.left_out] == [(1, {"kind": "not_contains", "text": "draft"})]


def test_a_search_that_runs_out_of_time_says_so_and_keeps_what_it_found():
    slow = Query.from_data({"mode": "pattern", "find": "(?:a|aa)+!"}).compile()
    items = [Text({"n": 0}, "body", "x!"), Text({"n": 1}, "body", "a" * 80), Text({"n": 2}, "body", "a!")]
    started = time.monotonic()
    found = scan(items, slow, deadline=started + 0.2)
    assert found.timed_out
    assert time.monotonic() - started < STOPPED_IN_TIME
    assert [m.at for m in found.matches] == []  # (the first text had no match, the second ran out of time)


def test_a_deadline_already_gone_finds_nothing_and_says_why():
    found = scan(texts(("body", "a")), search("a"), deadline=time.monotonic() - 1)
    assert found.timed_out and found.matches == []


# ------------------------------------------------------------------------------------------------------- replacing
def test_a_plan_lists_what_changes_from_what_to_what():
    made = plan(texts(("body", "red fox"), ("body", "grey"), ("title", "red")), search("red", "blue"))
    assert [c.to_data() for c in made.changes] == [
        {"at": {"paragraph": 0, "object": None}, "kind": "body", "before": "red fox", "after": "blue fox"},
        {"at": {"paragraph": 2, "object": None}, "kind": "title", "before": "red", "after": "blue"},
    ]
    assert not made.timed_out


def test_matches_a_person_leaves_are_kept_one_by_one_or_by_place():
    items = texts(("body", "red red"), ("body", "red"))
    made = plan(items, search("red", "blue"), leave=[(items[0].at, 1), ({"object": None, "paragraph": 1}, None)])
    assert [(c.at["paragraph"], c.after) for c in made.changes] == [(0, "blue red")]


def test_leaving_a_whole_place_wins_over_leaving_one_of_its_matches():
    items = texts(("body", "red red"))
    made = plan(items, search("red", "blue"), leave=[(items[0].at, None), (items[0].at, 0)])
    assert made.changes == []


def test_the_app_may_refuse_a_change_and_say_who_or_why():
    def refuse(item, after):
        return ("locked", "ben") if item.kind == "title" else ("too_long", None) if len(after) > 6 else None

    made = plan(texts(("body", "red"), ("title", "red"), ("body", "red red")), search("red", "blue"), refuse=refuse)
    assert [c.at["paragraph"] for c in made.changes] == [0]
    assert [s.to_data() for s in made.skipped] == [
        {"at": {"paragraph": 1, "object": None}, "kind": "title", "reason": "locked", "by": "ben"},
        {"at": {"paragraph": 2, "object": None}, "kind": "body", "reason": "too_long", "by": None},
    ]


def test_a_plan_that_ran_out_of_time_says_so():
    slow = Query.from_data({"mode": "pattern", "find": "(?:a|aa)+!", "replace": "b"}).compile()
    made = plan([Text({"n": 0}, "body", "a!"), Text({"n": 1}, "body", "a" * 80)], slow, deadline=time.monotonic() + 0.2)
    assert made.timed_out
    assert [c.after for c in made.changes] == ["b"]


def test_a_search_without_a_replacement_cannot_be_planned():
    with pytest.raises(SearchError):
        plan(texts(("body", "red")), search("red"))


# ------------------------------------------------------------------------------------- what a change is made of
def test_a_change_says_which_stretches_are_replaced_so_an_app_can_keep_the_rest_as_it_is():
    made = plan(texts(("body", "red fox, red hen")), search("red", "blue"))
    (change,) = made.changes
    assert [(e.number, e.start, e.end, e.before, e.after) for e in change.edits] == [
        (0, 0, 3, "red", "blue"),
        (1, 9, 12, "red", "blue"),
    ]
    assert change.after == "blue fox, blue hen"


def test_a_match_that_is_left_is_not_one_of_the_edits():
    items = texts(("body", "red, red, red"))
    made = plan(items, search("red", "blue"), leave=[(items[0].at, 1)])
    assert [e.number for e in made.changes[0].edits] == [0, 2]
    assert made.changes[0].after == "blue, red, blue"


def test_the_edits_use_what_the_kept_parts_matched():
    made = plan(
        texts(("body", "€12")), Query.from_data({"mode": "pattern", "find": "€(\\d+)", "replace": "\\1 EUR"}).compile()
    )
    assert [(e.before, e.after) for e in made.changes[0].edits] == [("€12", "12 EUR")]


# ------------------------------------------------------------------------- a match a person saw and that changed
def test_a_match_left_alone_by_what_it_said_is_still_left_alone_when_the_text_is_as_it_was():
    items = texts(("body", "red and red"))
    made = plan(items, search("red", "blue"), leave=[(items[0].at, 1, "red")])
    assert made.changes[0].after == "blue and red"
    assert made.skipped == []


def test_a_text_whose_matches_are_no_longer_what_a_person_saw_is_skipped_and_not_guessed_at():
    """She left match 1 alone, which said "red". A colleague has typed since, so match 1 now says "hen": replacing
    the others on the strength of numbers that moved would change what she did not mean to."""
    items = texts(("body", "red, red hen"))
    made = plan(items, search("red|hen", "x"), leave=[(items[0].at, 1, "red")])
    assert made.changes == []
    assert [(s.at, s.reason) for s in made.skipped] == [(items[0].at, "changed")]


def test_a_match_that_is_not_there_any_more_counts_as_changed():
    items = texts(("body", "red"))
    made = plan(items, search("red", "blue"), leave=[(items[0].at, 3, "red")])
    assert [s.reason for s in made.skipped] == ["changed"]
