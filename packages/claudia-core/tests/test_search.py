"""The search engine: a person's description of what to find, compiled to a pattern and run on texts (E1.12, D283-D284).

The builder's vocabulary is a table in ``claudiaoffice-log/notes/search-and-replace.md``; each row of it is a test here
that states the pattern it compiles to. The quick field is plain text, a typed pattern is checked with the position of
its first mistake, and a pattern that could backtrack without end is refused (Python's ``re`` cannot be interrupted).
"""

import pytest

from claudia_core import Query, SearchError


def builder(parts=(), conditions=(), *, combine="all", match_case=False, whole="none", replace=None):
    return Query.from_data(
        {
            "mode": "builder",
            "parts": list(parts),
            "conditions": list(conditions),
            "combine": combine,
            "match_case": match_case,
            "whole": whole,
            "replace": replace,
        }
    )


def text_query(text, **options):
    return Query.from_data({"mode": "text", "text": text, **options})


def pattern_query(find, filter="", replace="", *, match_case=False):
    return Query.from_data(
        {"mode": "pattern", "find": find, "filter": filter, "replace": replace, "match_case": match_case}
    )


def spans(compiled, text):
    return [(m.start, m.end) for m in compiled.matches(text)]


# --- the quick field: plain text ------------------------------------------------------------------------------------


def test_plain_text_is_found_as_typed_even_when_it_looks_like_a_pattern():
    found = text_query("Rates (2027)").compile()
    assert spans(found, "see Rates (2027) here") == [(4, 16)]
    assert spans(text_query("a.b").compile(), "a.b axb") == [(0, 3)]


def test_plain_text_ignores_capitals_unless_asked_not_to():
    assert spans(text_query("rates").compile(), "Rates RATES") == [(0, 5), (6, 11)]
    assert spans(text_query("rates", match_case=True).compile(), "Rates rates") == [(6, 11)]


def test_empty_text_finds_nothing():
    assert spans(text_query("").compile(), "anything") == []


def test_whole_text_and_whole_word_options():
    assert spans(text_query("EUR", whole="entire").compile(), "EUR") == [(0, 3)]
    assert spans(text_query("EUR", whole="entire").compile(), "150 EUR") == []
    assert spans(text_query("EUR", whole="word").compile(), "150 EUR, EURO") == [(4, 7)]
    assert spans(text_query("€", whole="word").compile(), "a € b") == [(2, 3)]  # a symbol is a word of its own


def test_plain_text_replacement_is_literal_and_never_a_template():
    query = Query.from_data({"mode": "text", "text": "a", "replace": [{"text": r"\1 & \g<0>"}]})
    assert query.compile().replaced("banana") == r"b\1 & \g<0>n\1 & \g<0>n\1 & \g<0>"


# --- the builder: parts (what x how many) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("part", "source"),
    [
        ({"what": "text", "value": "a.b"}, r"a\.b"),
        ({"what": "any_of", "chars": "€$£"}, "[€$£]"),
        ({"what": "none_of", "chars": "ab"}, "[^ab]"),
        ({"what": "letter"}, r"[^\W\d_]"),
        ({"what": "digit"}, r"\d"),
        ({"what": "space"}, r"\s"),
        ({"what": "any"}, "."),
        ({"what": "number"}, r"\d+(?:[.,]\d+)*"),
        ({"what": "start"}, "^"),
        ({"what": "end"}, r"\Z"),
    ],
)
def test_every_part_compiles_to_the_pattern_the_note_states(part, source):
    assert builder([part]).compile().pattern_text()["find"] == source


@pytest.mark.parametrize(
    ("count", "suffix"),
    [
        ({}, ""),
        ({"count": "once"}, ""),
        ({"count": "optional"}, "?"),
        ({"count": "one_or_more"}, "+"),
        ({"count": "any"}, "*"),
        ({"count": "exactly", "n": 3}, "{3}"),
        ({"count": "between", "n": 2, "m": 4}, "{2,4}"),
    ],
)
def test_every_count_compiles_to_its_quantifier(count, suffix):
    part = {"what": "digit", **count}
    assert builder([part]).compile().pattern_text()["find"] == r"\d" + suffix


def test_a_quantified_text_part_is_grouped_so_the_count_applies_to_all_of_it():
    part = {"what": "text", "value": "ab", "count": "one_or_more"}
    assert builder([part]).compile().pattern_text()["find"] == "(?:ab)+"


def test_parts_are_found_in_order():
    parts = [
        {"what": "text", "value": "€"},
        {"what": "space", "count": "optional"},
        {"what": "number", "keep": "amount"},
    ]
    found = builder(parts).compile()
    assert spans(found, "Flights € 1.240 booked") == [(8, 15)]
    assert spans(found, "€45") == [(0, 3)]
    assert spans(found, "45 €") == []


def test_a_kept_part_is_a_capture_group_and_is_reported_with_the_match():
    parts = [{"what": "text", "value": "€"}, {"what": "number", "keep": "amount"}]
    found = builder(parts).compile()
    assert found.pattern_text()["find"] == r"€(\d+(?:[.,]\d+)*)"
    (match,) = found.matches("€1.240")
    assert match.kept == ("1.240",)


def test_a_number_covers_both_decimal_marks():
    found = builder([{"what": "number"}]).compile()
    assert [text for text in ("12", "3.5", "1.234,50") if spans(found, text) == [(0, len(text))]] == [
        "12",
        "3.5",
        "1.234,50",
    ]


def test_a_letter_is_a_unicode_letter_and_not_a_digit_or_underscore():
    found = builder([{"what": "letter", "count": "one_or_more"}]).compile()
    assert spans(found, "ä1_é") == [(0, 1), (3, 4)]


def test_the_builder_ignores_capitals_unless_asked_not_to():
    parts = [{"what": "text", "value": "eur"}]
    assert spans(builder(parts).compile(), "150 EUR") == [(4, 7)]
    assert spans(builder(parts, match_case=True).compile(), "150 EUR") == []


def test_a_part_an_app_adds_is_looked_up_and_an_unknown_one_is_refused():
    query = builder([{"what": "cell_ref"}])
    assert spans(query.compile(extra_parts={"cell_ref": r"\$?[A-Z]{1,3}\$?\d+"}), "=B4*Rates!$B$3") == [
        (1, 3),
        (10, 14),
    ]
    with pytest.raises(SearchError, match="cell_ref"):
        query.compile()


def test_a_part_needs_what_it_needs():
    for bad in (
        {"what": "text"},
        {"what": "text", "value": ""},
        {"what": "any_of", "chars": ""},
        {"what": "digit", "count": "exactly"},
        {"what": "digit", "count": "between", "n": 5, "m": 2},
        {"what": "digit", "count": "sometimes"},
        {"what": "digit", "count": "exactly", "n": 100_000},
    ):
        with pytest.raises(SearchError):
            builder([bad])


def test_no_parts_and_no_conditions_is_an_empty_search_that_finds_nothing():
    assert spans(builder().compile(), "anything") == []


# --- the builder: conditions on the whole cell ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("condition", "source"),
    [
        ({"kind": "contains", "text": "EUR"}, "^(?=.*EUR)"),
        ({"kind": "not_contains", "text": "EUR"}, "^(?!.*EUR)"),
        ({"kind": "starts_with", "text": "€"}, "^(?=€)"),
        ({"kind": "ends_with", "text": "EUR"}, r"^(?=.*EUR\Z)"),
        ({"kind": "is", "text": "EUR"}, r"^(?=EUR\Z)"),
        ({"kind": "contains_any_of", "chars": "€$"}, "^(?=.*[€$])"),
        ({"kind": "not_contains_any_of", "chars": "€$"}, "^(?!.*[€$])"),
    ],
)
def test_every_condition_compiles_to_its_cell_filter(condition, source):
    assert builder([{"what": "any"}], [condition]).compile().pattern_text()["filter"] == source


def test_the_owners_example_not_this_string_but_at_least_one_of_these_characters():
    found = builder([{"what": "any_of", "chars": "€$£"}], [{"kind": "not_contains", "text": "EUR"}]).compile()
    assert spans(found, "€ 1.240") == [(0, 1)]
    assert spans(found, "$ 310") == [(0, 1)]
    assert spans(found, "€ 980 (EUR)") == []
    assert spans(found, "150 EUR") == []


def test_all_of_means_every_condition_and_any_of_means_one():
    conditions = [{"kind": "contains", "text": "a"}, {"kind": "contains", "text": "b"}]
    assert builder([], conditions).compile().admits("ab") and not builder([], conditions).compile().admits("a")
    anyof = builder([], conditions, combine="any").compile()
    assert anyof.admits("a") and anyof.admits("b") and not anyof.admits("c")


def test_a_condition_looks_at_a_cell_that_holds_line_breaks():
    found = builder([{"what": "digit"}], [{"kind": "contains", "text": "end"}]).compile()
    assert spans(found, "1\nthe end") == [(0, 1)]


def test_with_no_parts_the_whole_cell_is_the_match():
    found = builder([], [{"kind": "contains", "text": "x"}]).compile()
    assert spans(found, "a x b") == [(0, 5)]
    assert spans(found, "a b") == []


def test_a_condition_says_what_it_needs():
    for bad in (
        {"kind": "contains"},
        {"kind": "contains", "text": ""},
        {"kind": "near", "text": "a"},
        {"kind": "is", "chars": "a"},
    ):
        with pytest.raises(SearchError):
            builder([], [bad])


def test_a_cell_is_left_out_with_the_reason_when_the_find_matches_but_a_condition_fails():
    found = builder([{"what": "any_of", "chars": "€"}], [{"kind": "not_contains", "text": "EUR"}]).compile()
    assert found.left_out("€ 980 (EUR)") == {"kind": "not_contains", "text": "EUR"}
    assert found.left_out("€ 1.240") is None  # it matched: it was not left out
    assert found.left_out("980 EUR") is None  # nothing similar in it at all


def test_whole_text_wraps_the_find_in_anchors():
    found = builder([{"what": "digit", "count": "one_or_more"}], whole="entire").compile()
    assert spans(found, "123") == [(0, 3)] and spans(found, "12a") == []


# --- replacing ------------------------------------------------------------------------------------------------------


def test_a_kept_part_can_be_put_into_the_replacement_and_the_rest_is_literal():
    parts = [
        {"what": "text", "value": "€"},
        {"what": "space", "count": "optional"},
        {"what": "number", "keep": "amount"},
    ]
    found = builder(parts, replace=[{"keep": "amount"}, {"text": " EUR"}]).compile()
    assert found.replaced("€ 1.240") == "1.240 EUR"
    assert found.replaced("€45 and € 64,50") == "45 EUR and 64,50 EUR"
    (match,) = found.matches("€45")
    assert match.after == "45 EUR"


def test_a_backslash_in_a_literal_replacement_stays_a_backslash():
    found = builder([{"what": "digit"}], replace=[{"text": "\\"}]).compile()
    assert found.replaced("a1") == "a\\"


def test_a_replacement_names_only_parts_that_are_kept():
    with pytest.raises(SearchError, match="amount"):
        builder([{"what": "digit"}], replace=[{"keep": "amount"}])


def test_kept_names_are_unique():
    parts = [{"what": "digit", "keep": "x"}, {"what": "letter", "keep": "x"}]
    with pytest.raises(SearchError, match="x"):
        builder(parts)


def test_replaced_can_leave_some_matches_alone():
    found = text_query("a", replace=[{"text": "o"}]).compile()
    assert found.replaced("banana", leave={1}) == "bonano"
    assert found.replaced("banana", leave={0, 2}) == "banona"


def test_replacing_with_nothing_removes_the_match():
    assert text_query("x", replace=[]).compile().replaced("axb") == "ab"


# --- a typed pattern ------------------------------------------------------------------------------------------------


def test_a_typed_pattern_finds_and_replaces_with_group_references():
    found = pattern_query(r"€\s?(\d+(?:[.,]\d+)*)", r"^(?!.*EUR)", r"\1 EUR").compile()
    assert spans(found, "€ 1.240") == [(0, 7)]
    assert found.replaced("€ 1.240") == "1.240 EUR"
    assert spans(found, "€ 980 (EUR)") == []
    assert found.left_out("€ 980 (EUR)") == {"kind": "filter"}


def test_a_typed_pattern_ignores_capitals_unless_asked_not_to():
    assert spans(pattern_query("eur").compile(), "EUR") == [(0, 3)]
    assert spans(pattern_query("eur", match_case=True).compile(), "EUR") == []


def test_a_mistake_in_a_typed_pattern_is_reported_with_its_position():
    with pytest.raises(SearchError) as caught:
        pattern_query(r"€\s?(\d+(?:[.,]\d+*").compile()
    assert caught.value.field == "find" and caught.value.position == 18
    assert caught.value.message == "multiple repeat"
    with pytest.raises(SearchError) as open_group:
        pattern_query("a(bc").compile()
    assert open_group.value.position == 1 and "missing )" in open_group.value.message


def test_a_mistake_in_the_cell_pattern_or_the_replacement_names_its_field():
    with pytest.raises(SearchError) as cell:
        pattern_query("a", "(").compile()
    assert cell.value.field == "filter"
    with pytest.raises(SearchError) as replace:
        pattern_query("a", "", r"\1").compile()
    assert replace.value.field == "replace"


def test_an_empty_typed_pattern_finds_nothing():
    assert spans(pattern_query("").compile(), "abc") == []


def test_what_the_builder_made_can_be_read_back_as_the_three_fields():
    parts = [
        {"what": "text", "value": "€"},
        {"what": "space", "count": "optional"},
        {"what": "number", "keep": "amount"},
    ]
    made = builder(
        parts, [{"kind": "not_contains", "text": "EUR"}], replace=[{"keep": "amount"}, {"text": " EUR"}]
    ).compile()
    assert made.pattern_text() == {"find": r"€\s?(\d+(?:[.,]\d+)*)", "filter": "^(?!.*EUR)", "replace": r"\g<1> EUR"}
    again = pattern_query(**made.pattern_text()).compile()
    assert again.replaced("€ 1.240") == made.replaced("€ 1.240") == "1.240 EUR"


# --- patterns that could freeze the server --------------------------------------------------------------------------


@pytest.mark.parametrize("pattern", ["(a+)+$", "(a*)*b", "(a|aa)+$", r"(\w+\s?)*$", "((ab)*)+", "(?:a{2,})+"])
def test_a_pattern_that_backtracks_without_end_is_refused(pattern):
    with pytest.raises(SearchError, match="(?i)backtrack|repeat"):
        pattern_query(pattern).compile()


# SEC-18: the static guard is a heuristic, and these shapes pass it. Measured at cfa2d91 on 24 characters:
# `(a|a?)+!` 12.5 s, `(x\w*)*!` 1.2 s, both doubling with every further character, on the event loop. The fix is a
# search that can be stopped (D284's worker budget, or the `regex` package's timeout, D287), not a longer guard.
@pytest.mark.xfail(strict=True, reason="SEC-18: exponential patterns pass the guard")
@pytest.mark.parametrize(("pattern", "text"), [("(a|a?)+!", "a" * 19), (r"(x\w*)*!", "x" * 21)])
def test_a_pattern_the_guard_lets_through_still_cannot_hold_the_server(pattern, text):
    import time

    try:
        compiled = pattern_query(pattern).compile()
    except SearchError:
        return
    started = time.perf_counter()
    compiled.matches(text)
    assert time.perf_counter() - started < 0.02  # an ordinary pattern takes microseconds here; these take 0.15-0.35 s


@pytest.mark.parametrize("pattern", ["a+b*", r"(\d+)(?:,\d+)?", "(ab)?c", "(?:a{2})+", r"\d+(?:[.,]\d+)*", ".*x.*"])
def test_ordinary_repeats_are_allowed(pattern):
    pattern_query(pattern).compile()


def test_the_refusal_covers_the_cell_pattern_too():
    with pytest.raises(SearchError) as caught:
        pattern_query("a", "(a+)+$").compile()
    assert caught.value.field == "filter"


def test_a_pattern_that_is_too_long_or_too_deep_is_refused():
    with pytest.raises(SearchError):
        pattern_query("a" * 5000).compile()
    with pytest.raises(SearchError):
        builder([{"what": "digit"}] * 100)


def test_a_cell_filter_rejects_a_long_text_before_the_parts_run():
    found = builder([{"what": "any"}, {"what": "digit"}], [{"kind": "contains", "text": "z"}]).compile()
    assert spans(found, "a" * 50_000 + "1") == []  # no "z": rejected by the cell filter before the parts run


# --- reading the data a client sent ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"mode": "magic"},
        {"mode": "text"},
        {"mode": "text", "text": 5},
        {"mode": "text", "text": "a", "whole": "sentence"},
        {"mode": "text", "text": "a", "match_case": "yes"},
        {"mode": "builder", "parts": "x"},
        {"mode": "builder", "parts": [5]},
        {"mode": "builder", "conditions": [], "combine": "some"},
        {"mode": "pattern", "find": 1},
        {"mode": "text", "text": "a", "replace": [{"text": 5}]},
        {"mode": "text", "text": "a", "replace": [{"text": "x", "keep": "y"}]},
        {"mode": "text", "text": "a", "extra": 1},
    ],
)
def test_data_that_is_not_a_search_is_refused_with_search_error(bad):
    with pytest.raises(SearchError):
        Query.from_data(bad)


def test_a_query_gives_back_the_data_it_was_made_from():
    data = {
        "mode": "builder",
        "parts": [{"what": "digit", "count": "exactly", "n": 2, "keep": "d"}],
        "conditions": [{"kind": "contains", "text": "x"}],
        "combine": "any",
        "match_case": True,
        "whole": "entire",
        "replace": [{"keep": "d"}],
    }
    assert Query.from_data(data).to_data() == data


# --- more shapes that are refused, and more mistakes in what a client sends ------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    ["((a+)+)?", "(x(a+)+)", "x|(a+)+", "(?=(a+)+b)", "(?:a+|b)+$", "((a|a)|c)+"],
)
def test_a_repeat_hidden_in_a_group_a_branch_or_a_look_ahead_is_found_too(pattern):
    with pytest.raises(SearchError, match="backtrack"):
        pattern_query(pattern).compile()


def test_a_repeat_of_nothing_is_harmless():
    assert spans(pattern_query("(?:)*x").compile(), "ax") == [(1, 2)]


def test_a_pattern_nested_beyond_what_python_can_read_is_refused_in_words():
    with pytest.raises(SearchError, match="nested too deeply") as caught:
        pattern_query("(" * 990 + "a" + ")" * 990).compile()
    assert caught.value.field == "find"


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"mode": "builder", "parts": [{"what": "any_of"}]}, "needs its characters"),
        ({"mode": "builder", "parts": [{"what": "text", "value": "a", "keep": ""}]}, "kept under"),
        ({"mode": "builder", "parts": [{"what": "text", "value": "a", "keep": "x" * 61}]}, "kept under"),
        ({"mode": "builder", "parts": [{"what": "text", "value": "a", "n": 2}]}, "belong to a count"),
        ({"mode": "builder", "parts": [{"what": "start", "count": "any"}]}, "is a place"),
        ({"mode": "builder", "parts": [{"what": "digit", "count": "any", "n": 3}]}, "belong to a count"),
        ({"mode": "builder", "conditions": [{"kind": "contains_any_of", "text": "a"}]}, "takes characters"),
        ({"mode": "text", "text": "a", "replace": [{"text": "x"}] * 51}, "at most 50"),
        ({"mode": "pattern", "find": "a", "replace": 5}, "replace must be text"),
    ],
)
def test_a_client_that_sends_something_else_is_told_what_is_wrong(data, message):
    with pytest.raises(SearchError, match=message):
        Query.from_data(data)


@pytest.mark.parametrize(
    "data",
    [
        {"mode": "text", "text": "a.b", "replace": [{"text": "x"}], "match_case": True, "whole": "word"},
        {"mode": "pattern", "find": "a+", "filter": "^b", "replace": "x", "match_case": True},
    ],
)
def test_what_a_query_says_about_itself_makes_the_same_query(data):
    query = Query.from_data(data)
    assert Query.from_data(query.to_data()) == query
