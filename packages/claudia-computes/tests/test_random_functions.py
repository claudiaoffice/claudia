"""RAND, RANDBETWEEN and RANDOM in a workbook (E6.22, D291-D293).

What matters: every person sees the same numbers (they come from the log, not from the machine), a number does not
move because something else was edited, ``Resample`` is the one command that draws fresh ones, and it can be undone."""

from __future__ import annotations

import pytest
from conftest import S1, reopen
from test_workbook_formulas import at, error_code, fill, shown, type_in

from claudia_computes import Resample, SetRandomSeed, WorkbookModel
from claudia_computes.distributions import quantile
from claudia_computes.draws import uniform


def draw(doc, address, index=0):
    row, col = at(address)
    return uniform(doc.model.random_seed, S1, row, col, doc.model.random_draw, index)


def test_rand_is_a_draw_of_its_own_cell(doc):
    type_in(doc, "B3", "=RAND()")
    assert shown(doc, "B3") == draw(doc, "B3")
    assert 0 <= shown(doc, "B3") < 1


def test_two_cells_get_different_numbers(doc):
    fill(doc, {"A1": "=RAND()", "A2": "=RAND()"})
    assert shown(doc, "A1") != shown(doc, "A2")


def test_two_calls_in_one_cell_get_different_numbers(doc):
    type_in(doc, "A1", "=RAND()-RAND()")
    assert shown(doc, "A1") == draw(doc, "A1", 0) - draw(doc, "A1", 1)


def test_editing_another_cell_does_not_move_a_number(doc):
    fill(doc, {"A1": "=RAND()", "B1": "=A1*2"})
    before = shown(doc, "A1")
    type_in(doc, "C5", "hello")
    type_in(doc, "D9", "=1+1")
    assert shown(doc, "A1") == before
    assert shown(doc, "B1") == before * 2


def test_retyping_the_same_formula_keeps_the_number(doc):
    type_in(doc, "A1", "=RAND()")
    before = shown(doc, "A1")
    type_in(doc, "A1", "=RAND()")
    assert shown(doc, "A1") == before


def test_resample_draws_fresh_numbers_and_what_depends_on_them_follows(doc):
    fill(doc, {"A1": "=RAND()", "B1": "=A1*2", "C1": "=10"})
    before = shown(doc, "A1")
    doc.execute(Resample(), author="ana")
    assert doc.model.random_draw == 1
    assert shown(doc, "A1") != before
    assert shown(doc, "A1") == draw(doc, "A1")
    assert shown(doc, "B1") == shown(doc, "A1") * 2
    assert shown(doc, "C1") == 10


def test_undoing_a_resample_brings_the_old_numbers_back(doc):
    type_in(doc, "A1", "=RAND()")
    before = shown(doc, "A1")
    doc.execute(Resample(), author="ana")
    doc.undo(author="ana")
    assert doc.model.random_draw == 0
    assert shown(doc, "A1") == before


def test_two_resamples_by_two_people_count_both(doc):
    type_in(doc, "A1", "=RAND()")
    doc.execute(Resample(), author="ana")
    doc.execute(Resample(), author="bob")
    assert doc.model.random_draw == 2


def test_a_different_seed_gives_different_numbers_and_can_be_undone(doc):
    type_in(doc, "A1", "=RAND()")
    before = shown(doc, "A1")
    doc.execute(SetRandomSeed(12345), author="ana")
    assert shown(doc, "A1") != before
    assert shown(doc, "A1") == draw(doc, "A1")
    doc.undo(author="ana")
    assert shown(doc, "A1") == before


def test_a_replayed_log_gives_every_number_again(doc):
    fill(doc, {"A1": "=RAND()", "A2": '=RANDOM("normal",100,15)', "A3": "=RANDBETWEEN(1,6)"})
    doc.execute(SetRandomSeed(99), author="ana")
    doc.execute(Resample(), author="ana")
    again = reopen(doc)
    for address in ("A1", "A2", "A3"):
        assert shown(again, address) == shown(doc, address)


def test_the_seed_and_the_draw_number_survive_a_snapshot(doc):
    type_in(doc, "A1", "=RAND()")
    doc.execute(SetRandomSeed(77), author="ana")
    doc.execute(Resample(), author="ana")
    restored = WorkbookModel.restore(doc.model.serialize())
    assert (restored.random_seed, restored.random_draw) == (77, 1)
    row, col = at("A1")
    assert restored.value(S1, row, col) == shown(doc, "A1")


# ------------------------------------------------------------------ RANDBETWEEN
def test_randbetween_gives_whole_numbers_with_both_ends_possible(doc):
    cells = {f"A{n}": "=RANDBETWEEN(1,3)" for n in range(1, 200)}
    fill(doc, cells)
    seen = {shown(doc, address) for address in cells}
    assert seen == {1, 2, 3}
    assert all(isinstance(v, int) for v in seen)


def test_randbetween_follows_the_draw_of_its_cell(doc):
    type_in(doc, "A1", "=RANDBETWEEN(10,20)")
    assert shown(doc, "A1") == 10 + int(draw(doc, "A1") * 11)


def test_randbetween_with_the_ends_the_wrong_way_round_is_a_number_error(doc):
    type_in(doc, "A1", "=RANDBETWEEN(6,1)")
    assert error_code(doc, "A1") == "#NUM!"


def test_randbetween_wants_numbers(doc):
    type_in(doc, "A1", '=RANDBETWEEN("a",3)')
    assert error_code(doc, "A1") == "#VALUE!"


# ------------------------------------------------------------------ RANDOM
def test_random_without_arguments_is_rand(doc):
    type_in(doc, "A1", "=RAND()")
    rand = shown(doc, "A1")
    type_in(doc, "A1", "=RANDOM()")
    assert shown(doc, "A1") == rand


def test_random_names_its_distribution_and_takes_its_parameters(doc):
    type_in(doc, "B2", '=RANDOM("normal",1000,150)')
    assert shown(doc, "B2") == pytest.approx(quantile("normal", draw(doc, "B2"), (1000, 150)))


def test_random_takes_its_parameters_from_other_cells_and_keeps_the_draw(doc):
    fill(doc, {"A1": 1000, "A2": 150, "B1": '=RANDOM("normal",A1,A2)'})
    first = shown(doc, "B1")
    type_in(doc, "A1", "2000")
    assert shown(doc, "B1") == pytest.approx(first + 1000)  # the same u, a shifted mean


def test_random_limits_cut_the_distribution(doc):
    cells = {f"A{n}": '=RANDOM("normal",1000,150,1000,1200)' for n in range(1, 60)}
    fill(doc, cells)
    values = [shown(doc, address) for address in cells]
    assert min(values) >= 1000 and max(values) <= 1200


def test_random_discrete_picks_from_the_listed_values(doc):
    cells = {f"A{n}": '=RANDOM("discrete",10,1,20,1,30,2)' for n in range(1, 80)}
    fill(doc, cells)
    assert {shown(doc, address) for address in cells} == {10, 20, 30}


def test_random_with_an_unknown_distribution_is_a_value_error_naming_the_choices(doc):
    type_in(doc, "A1", '=RANDOM("cauchy",0,1)')
    assert error_code(doc, "A1") == "#VALUE!"
    assert "normal" in shown(doc, "A1").detail


def test_random_with_the_wrong_number_of_parameters_is_a_value_error(doc):
    type_in(doc, "A1", '=RANDOM("normal",1)')
    assert error_code(doc, "A1") == "#VALUE!"


def test_random_with_impossible_parameters_is_a_number_error(doc):
    type_in(doc, "A1", '=RANDOM("normal",0,-5)')
    assert error_code(doc, "A1") == "#NUM!"


def test_the_distribution_name_may_be_any_case(doc):
    type_in(doc, "A1", '=RANDOM("Normal",0,1)')
    assert isinstance(shown(doc, "A1"), float)


def test_a_random_number_in_a_cell_that_moves_moves_with_it_but_keeps_its_value_until_resampled(doc):
    from claudia_computes import InsertRows, Structure

    type_in(doc, "A5", "=RAND()")
    before = shown(doc, "A5")
    doc.execute(Structure(InsertRows(S1, 0, 2)), author="ana")
    # the formula now sits two rows lower: it is a different cell, so it draws its own number
    assert shown(doc, "A7") == draw(doc, "A7")
    assert shown(doc, "A7") != before
