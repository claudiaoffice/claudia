"""Search in a workbook (E6.20): what is looked at (text, formulas, values), where, what a replacement changes."""

import pytest
from conftest import S1

from claudia_computes import AddSheet, CellRegion, SetCells, WorkbookModel, parse_input
from claudia_computes.search import (
    EXTRA_PARTS,
    KINDS,
    cell_at,
    cell_of,
    plan_replacement,
    replace_command,
    scan_workbook,
)
from claudia_core import Document, MemoryStore
from claudia_core.commands import encode
from claudia_search import MAX_LISTED, Query, Scan, SearchError


def typed(doc, cells, sheet=S1):
    doc.execute(SetCells(sheet, tuple((r, c, parse_input(t)) for r, c, t in cells)), author="ana")


@pytest.fixture
def budget(doc):
    """The mock-up's budget: amounts as text with a currency sign, and formulas that take the sign away again."""
    typed(
        doc,
        [
            (0, 0, "Travel"),
            (0, 1, "€12,50"),
            (1, 0, "Hotel"),
            (1, 1, "€80"),
            (2, 0, "Lunch"),
            (2, 1, "$9.90 EUR"),
            (3, 0, "Total"),
            (3, 1, '=VALUE(SUBSTITUTE(B1,"€",""))+1'),
            (4, 1, "42"),
            (5, 1, "=B5*2"),
            (6, 1, '=SUBSTITUTE(A1,"Tr","X")'),
        ],
    )
    return doc.model


def query(**data):
    return Query.from_data(data).compile(EXTRA_PARTS)


def find(text, **more):
    return query(mode="text", text=text, **more)


def places(result: Scan):
    return [(m.at["row"], m.at["col"], m.kind) for m in result.matches]


# --- what is looked at
def test_the_kinds_a_search_can_look_in():
    assert KINDS == ("text", "formulas", "values")


def test_text_is_the_text_constants_only(budget):
    result = scan_workbook(budget, find("tra"), kinds=("text",))
    assert places(result) == [(0, 0, "text")]


def test_formulas_are_looked_at_as_typed(budget):
    result = scan_workbook(budget, find("SUBSTITUTE"), kinds=("formulas",))
    assert places(result) == [(3, 1, "formula"), (6, 1, "formula")]
    assert result.matches[0].start == 7  # a span in the formula's own text, `=VALUE(` first


def test_a_formula_shows_its_text_with_the_equals_sign(budget):
    hit = scan_workbook(budget, find("=B5"), kinds=("formulas",)).matches[0]
    assert (hit.start, hit.end) == (0, 3)


def test_values_are_what_the_cells_show(budget):
    result = scan_workbook(budget, find("85"), kinds=("values",))
    assert places(result) == []  # nothing shows 85
    result = scan_workbook(budget, find("84"), kinds=("values",))
    assert places(result) == [(5, 1, "value")]  # B6 = B5 * 2 shows 84


def test_a_number_is_a_value_not_text(budget):
    assert places(scan_workbook(budget, find("42"), kinds=("text",))) == []
    assert places(scan_workbook(budget, find("42"), kinds=("values",))) == [(4, 1, "value")]


def test_text_in_values_is_not_reported_twice(budget):
    # "Travel" is text; with all three kinds it is found once, as text
    result = scan_workbook(budget, find("travel"), kinds=KINDS)
    assert places(result) == [(0, 0, "text")]


def test_values_include_formula_text_results(doc):
    typed(doc, [(0, 0, '="Hello "&"World"')])
    result = scan_workbook(doc.model, find("world"), kinds=("values",))
    assert places(result) == [(0, 0, "value")]
    assert result.matches[0].text == "Hello World"


def test_an_error_value_can_be_found_by_its_code(doc):
    typed(doc, [(0, 0, "=1/0")])
    assert places(scan_workbook(doc.model, find("#DIV/0!"), kinds=("values",))) == [(0, 0, "value")]


def test_counts_say_how_many_cells_hold_a_match_per_kind(budget):
    result = scan_workbook(budget, find("€"), kinds=KINDS)
    assert result.counts == {"text": 2, "formulas": 1, "values": 0}
    assert result.total == 3


def test_counts_are_of_all_matches_even_when_the_list_is_cut(doc):
    typed(doc, [(r, 0, "x") for r in range(MAX_LISTED + 5)])
    result = scan_workbook(doc.model, find("x"), kinds=("text",))
    assert len(result.matches) == MAX_LISTED
    assert result.total == MAX_LISTED + 5
    assert result.truncated


def test_more_matches_in_one_cell_are_listed_in_order(doc):
    typed(doc, [(0, 0, "a-b-c")])
    result = scan_workbook(doc.model, find("-"), kinds=("text",))
    assert [(m.start, m.end, m.number) for m in result.matches] == [(1, 2, 0), (3, 4, 1)]


def test_a_match_carries_what_its_kept_parts_matched_and_what_it_would_become(budget):
    q = query(
        mode="builder",
        parts=[{"what": "any_of", "chars": "€$£"}, {"what": "number", "keep": "amount"}],
        replace=[{"keep": "amount"}, {"text": " EUR"}],
    )
    first = scan_workbook(budget, q, kinds=("text",)).matches[0]
    assert first.kept == ("12,50",)
    assert first.after == "12,50 EUR"


def test_the_excerpt_is_bounded_and_the_span_inside_it(doc):
    typed(doc, [(0, 0, "a" * 500 + "NEEDLE" + "b" * 500)])
    hit = scan_workbook(doc.model, find("needle"), kinds=("text",)).matches[0]
    assert (hit.start, hit.end) == (500, 506)
    assert len(hit.text) <= 130
    assert hit.text[hit.excerpt_start : hit.excerpt_end] == "NEEDLE"
    assert (hit.clipped_before, hit.clipped_after) == (True, True)


# --- where
def test_one_sheet_and_all_sheets(doc):
    doc.execute(AddSheet("s2", "Other"), author="ana")
    typed(doc, [(0, 0, "needle")])
    typed(doc, [(4, 4, "needle")], sheet="s2")
    assert [
        (m.at["sheet"], m.at["row"]) for m in scan_workbook(doc.model, find("needle"), kinds=("text",)).matches
    ] == [
        ("s1", 0),
        ("s2", 4),
    ]
    only = scan_workbook(doc.model, find("needle"), kinds=("text",), sheets=["s2"])
    assert [(m.at["sheet"], m.at["row"]) for m in only.matches] == [("s2", 4)]


def test_a_selection_limits_the_search_to_its_cells(budget):
    result = scan_workbook(budget, find("€"), kinds=("text",), sheets=[S1], area=(1, 1, 2, 1))
    assert places(result) == [(1, 1, "text")]


def test_an_unknown_sheet_is_an_error(doc):
    with pytest.raises(ValueError, match="unknown sheet"):
        scan_workbook(doc.model, find("x"), kinds=("text",), sheets=["nope"])


def test_the_order_is_by_sheet_then_row_then_column(doc):
    typed(doc, [(2, 0, "x"), (0, 3, "x"), (0, 1, "x")])
    assert [(m.at["row"], m.at["col"]) for m in scan_workbook(doc.model, find("x"), kinds=("text",)).matches] == [
        (0, 1),
        (0, 3),
        (2, 0),
    ]


# --- the extra parts
def test_a_cell_reference_is_a_part_of_computes(budget):
    q = query(mode="builder", parts=[{"what": "cellref"}])
    found = [
        (m.at["row"], m.at["col"], m.text[m.excerpt_start : m.excerpt_end])
        for m in scan_workbook(budget, q, kinds=("formulas",)).matches
    ]
    assert found == [(3, 1, "B1"), (5, 1, "B5"), (6, 1, "A1")]


def test_a_cell_reference_does_not_match_inside_a_name_or_a_function(doc):
    typed(doc, [(0, 0, "=LOG10(5)+X1Y")])
    q = query(mode="builder", parts=[{"what": "cellref"}])
    assert scan_workbook(doc.model, q, kinds=("formulas",)).matches == []


def test_a_cell_reference_can_be_absolute(doc):
    typed(doc, [(0, 0, "=$A$2+B$3")])
    q = query(mode="builder", parts=[{"what": "cellref"}])
    assert [
        m.text[m.excerpt_start : m.excerpt_end] for m in scan_workbook(doc.model, q, kinds=("formulas",)).matches
    ] == [
        "$A$2",
        "B$3",
    ]


# --- left out
def test_a_cell_that_looks_like_a_match_is_left_out_with_the_reason(budget):
    q = query(
        mode="builder",
        parts=[{"what": "any_of", "chars": "€$£"}, {"what": "number"}],
        conditions=[{"kind": "not_contains", "text": "EUR"}],
    )
    result = scan_workbook(budget, q, kinds=("text",))
    assert places(result) == [(0, 1, "text"), (1, 1, "text")]
    assert [(o.at["row"], o.at["col"], o.kind, o.why) for o in result.left_out] == [
        (2, 1, "text", {"kind": "not_contains", "text": "EUR"})
    ]


def test_left_out_counts_do_not_change_the_counts_of_matches(budget):
    q = query(
        mode="builder",
        parts=[{"what": "any_of", "chars": "€$£"}],
        conditions=[{"kind": "not_contains", "text": "EUR"}],
    )
    assert scan_workbook(budget, q, kinds=("text",)).counts["text"] == 2


# --- the time budget
def test_a_search_that_runs_out_of_time_says_so(doc):
    import time

    typed(doc, [(0, 0, "a!"), (1, 0, "a" * 80), (2, 0, "a!")])
    slow = Query.from_data({"mode": "pattern", "find": "(?:a|aa)+!"}).compile()
    started = time.monotonic()
    result = scan_workbook(doc.model, slow, kinds=("text",), deadline=started + 0.2)
    assert result.timed_out and time.monotonic() - started < 0.6
    assert [m.at for m in result.matches] == [cell_at(S1, 0, 0)]


def test_a_place_is_a_cell_and_only_a_cell_comes_back():
    assert cell_of(cell_at(S1, 3, 4)) == (S1, 3, 4)
    for bad in (
        {"sheet": S1, "row": 1},
        {"sheet": S1, "row": -1, "col": 0},
        {"sheet": 1, "row": 0, "col": 0},
        {"sheet": S1, "row": True, "col": 0},
        {"sheet": S1, "row": 0, "col": 0, "x": 1},
        "A1",
    ):
        with pytest.raises(ValueError):
            cell_of(bad)


# --- replace
def test_replace_in_text_makes_one_change_per_cell(budget):
    q = query(mode="text", text="€", replace=[{"text": "EUR "}])
    plan = plan_replacement(budget, q, kinds=("text",))
    assert [(c.at["row"], c.at["col"], c.before, c.after) for c in plan.changes] == [
        (0, 1, "€12,50", "EUR 12,50"),
        (1, 1, "€80", "EUR 80"),
    ]
    assert plan.skipped == []


def test_a_replacement_never_touches_formulas_unless_asked(budget):
    q = query(mode="text", text="€", replace=[{"text": ""}])
    assert {(c.at["row"], c.at["col"]) for c in plan_replacement(budget, q, kinds=("text",)).changes} == {
        (0, 1),
        (1, 1),
    }
    both = plan_replacement(budget, q, kinds=("text", "formulas"))
    assert {(c.at["row"], c.at["col"]) for c in both.changes} == {(0, 1), (1, 1), (3, 1)}


def test_values_are_found_but_never_replaced(budget):
    q = query(mode="text", text="84", replace=[{"text": "85"}])
    assert plan_replacement(budget, q, kinds=("values",)).changes == []


def test_a_number_is_not_replaced_through_its_shown_value(budget):
    q = query(mode="text", text="42", replace=[{"text": "43"}])
    assert plan_replacement(budget, q, kinds=("text", "formulas", "values")).changes == []


def test_replace_with_kept_parts(budget):
    q = query(
        mode="builder",
        parts=[{"what": "any_of", "chars": "€$£"}, {"what": "number", "keep": "amount"}],
        conditions=[{"kind": "not_contains", "text": "EUR"}],
        replace=[{"keep": "amount"}, {"text": " EUR"}],
    )
    assert [(c.at["row"], c.after) for c in plan_replacement(budget, q, kinds=("text",)).changes] == [
        (0, "12,50 EUR"),
        (1, "80 EUR"),
    ]


def test_a_match_can_be_left_alone(doc):
    typed(doc, [(0, 0, "a-b-c")])
    q = query(mode="text", text="-", replace=[{"text": "+"}])
    plan = plan_replacement(doc.model, q, kinds=("text",), leave=[(cell_at(S1, 0, 0), 0)])
    assert plan.changes[0].after == "a-b+c"


def test_a_whole_cell_can_be_left_alone(budget):
    q = query(mode="text", text="€", replace=[{"text": ""}])
    plan = plan_replacement(budget, q, kinds=("text",), leave=[(cell_at(S1, 0, 1), None)])
    assert [(c.at["row"], c.at["col"]) for c in plan.changes] == [(1, 1)]


def test_a_replacement_that_changes_nothing_is_no_change(doc):
    typed(doc, [(0, 0, "same")])
    q = query(mode="text", text="same", replace=[{"text": "same"}])
    assert plan_replacement(doc.model, q, kinds=("text",)).changes == []


def test_replacing_a_whole_text_by_nothing_empties_the_cell(doc):
    typed(doc, [(0, 0, "gone")])
    q = query(mode="text", text="gone", replace=[{"text": ""}])
    command = replace_command(plan_replacement(doc.model, q, kinds=("text",)))
    doc.execute(command, author="ana")
    assert doc.model.get(S1, 0, 0) is None


def test_the_new_text_stays_text_even_if_it_looks_like_a_number(doc):
    typed(doc, [(0, 0, "x12")])
    q = query(mode="text", text="x", replace=[{"text": ""}])
    doc.execute(replace_command(plan_replacement(doc.model, q, kinds=("text",))), author="ana")
    assert doc.model.get(S1, 0, 0) == {"t": "text", "v": "12"}


def test_a_formula_that_would_no_longer_read_is_skipped_and_named(budget):
    q = query(mode="text", text="SUBSTITUTE(", replace=[{"text": "SUBSTITUTE"}])
    plan = plan_replacement(budget, q, kinds=("formulas",))
    assert plan.changes == []
    assert [(s.at["row"], s.at["col"], s.reason) for s in plan.skipped] == [(3, 1, "formula"), (6, 1, "formula")]


def test_a_formula_that_stops_being_one_is_skipped(doc):
    typed(doc, [(0, 0, "=A2")])
    q = query(mode="text", text="=", replace=[{"text": ""}])
    plan = plan_replacement(doc.model, q, kinds=("formulas",))
    assert [(s.at["row"], s.reason) for s in plan.skipped] == [(0, "formula")]


def test_a_formula_replacement_is_stored_as_a_formula(doc):
    typed(doc, [(0, 0, "=B1+B2")])
    q = query(mode="text", text="B1", replace=[{"text": "C9"}])
    doc.execute(replace_command(plan_replacement(doc.model, q, kinds=("formulas",))), author="ana")
    assert doc.model.get(S1, 0, 0) == {"t": "formula", "v": "=C9+B2"}


def test_a_cell_held_by_somebody_else_is_skipped_and_named(budget, doc):
    q = query(mode="text", text="€", replace=[{"text": ""}])
    held = {(S1, 1, 1): "anna"}
    plan = plan_replacement(budget, q, kinds=("text",), held=lambda sheet, r, c: held.get((sheet, r, c)))
    assert [(c.at["row"], c.at["col"]) for c in plan.changes] == [(0, 1)]
    assert [(s.at["row"], s.at["col"], s.reason, s.by) for s in plan.skipped] == [(1, 1, "locked", "anna")]


def test_a_search_without_a_replacement_cannot_be_planned(budget):
    with pytest.raises(SearchError):
        plan_replacement(budget, find("x"), kinds=("text",))


def test_the_command_is_one_undo_step_that_restores_everything(doc):
    typed(doc, [(0, 0, "€1"), (0, 1, "€2"), (3, 0, "€3")])
    q = query(mode="text", text="€", replace=[{"text": "$"}])
    command = replace_command(plan_replacement(doc.model, q, kinds=("text",)))
    doc.execute(command, author="ana")
    assert [doc.model.get(S1, r, c)["v"] for r, c in ((0, 0), (0, 1), (3, 0))] == ["$1", "$2", "$3"]
    doc.undo("ana")
    assert [doc.model.get(S1, r, c)["v"] for r, c in ((0, 0), (0, 1), (3, 0))] == ["€1", "€2", "€3"]


def test_the_command_holds_only_the_cells_it_changes(doc):
    typed(doc, [(0, 0, "x"), (5, 5, "x")])
    q = query(mode="text", text="x", replace=[{"text": "y"}])
    command = replace_command(plan_replacement(doc.model, q, kinds=("text",)))
    regions = command.regions(doc.model)
    assert all(isinstance(r, CellRegion) for r in regions)
    assert not any(r.overlaps(CellRegion.of(S1, 3, 3, 3, 3)) for r in regions)  # (the box between them is not touched)


def test_the_command_says_what_it_did(doc):
    typed(doc, [(0, 0, "x"), (1, 0, "x")])
    q = query(mode="text", text="x", replace=[{"text": "y"}])
    command = replace_command(plan_replacement(doc.model, q, kinds=("text",)))
    assert command.label == "Replace in 2 cells"
    assert command.summary == "Replace in 2 cells"


def test_no_change_gives_no_command(doc):
    typed(doc, [(0, 0, "x")])
    q = query(mode="text", text="zzz", replace=[{"text": "y"}])
    assert replace_command(plan_replacement(doc.model, q, kinds=("text",))) is None


def test_replay_never_depends_on_the_engine(doc):
    """The command stores the cells it changed, so a log replays to the same document without any pattern."""
    typed(doc, [(0, 0, "a1"), (1, 0, "a2")])
    q = query(
        mode="builder",
        parts=[{"what": "text", "value": "a"}, {"what": "digit", "keep": "n"}],
        replace=[{"keep": "n"}],
    )
    command = replace_command(plan_replacement(doc.model, q, kinds=("text",)))
    again = Document(WorkbookModel(), store=MemoryStore())
    again.execute(AddSheet(S1, "Sheet1"), author="ana")
    typed(again, [(0, 0, "a1"), (1, 0, "a2")])
    again.execute(WorkbookModel.registry.decode(encode(command)), author="ana")
    assert [again.model.get(S1, r, 0)["v"] for r in (0, 1)] == ["1", "2"]


def test_a_part_of_a_query_result_is_a_value_that_is_found_but_not_stored(doc):
    typed(doc, [(0, 0, '=SQL("SELECT 1 AS one UNION ALL SELECT 2 * 2121 AS one")')])
    sheet = doc.model.sheet(S1)
    assert any(sheet.spilled), "the query should fill cells below its formula"
    (position,) = [p for p in sheet.spilled if "4242" in str(sheet.grid.get(p))]
    found = scan_workbook(doc.model, find("4242"), kinds=("values",))
    assert [(m.at["row"], m.at["col"], m.kind) for m in found.matches] == [(*position, "value")]
    assert scan_workbook(doc.model, find("4242"), kinds=("text", "formulas")).matches == []
    q = query(mode="text", text="4242", replace=[{"text": "1"}])
    assert plan_replacement(doc.model, q, kinds=KINDS).changes == []


def test_a_kind_nobody_knows_is_an_error(doc):
    with pytest.raises(ValueError, match="cannot look in 'words'"):
        scan_workbook(doc.model, find("x"), kinds=("words",))
    with pytest.raises(ValueError, match="cannot look in"):
        plan_replacement(doc.model, query(mode="text", text="x", replace=[{"text": "y"}]), kinds=("everything",))


def test_a_text_that_would_get_too_long_is_skipped_and_named(doc):
    typed(doc, [(0, 0, "ab"), (1, 0, "a")])
    q = query(mode="text", text="a", replace=[{"text": "xxxx"}])
    plan = plan_replacement(doc.model, q, kinds=("text",), max_length=4)
    assert [(c.at["row"], c.after) for c in plan.changes] == [(1, "xxxx")]
    assert [(s.at["row"], s.reason) for s in plan.skipped] == [(0, "too_long")]
