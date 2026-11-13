"""The stream of uniform numbers behind RAND, RANDBETWEEN and RANDOM (D291).

A draw is a pure function of the document's seed, the cell it is for, the document's draw number and the index of the
call inside that cell. Nothing else, so every machine that replays the same log sees the same numbers."""

from __future__ import annotations

from claudia_computes.draws import uniform


def test_a_draw_is_in_the_half_open_unit_interval():
    values = [uniform(7, "s1", row, 0, 0, 0) for row in range(500)]
    assert all(0.0 <= v < 1.0 for v in values)


def test_the_same_inputs_give_the_same_number():
    assert uniform(7, "s1", 2, 3, 5, 0) == uniform(7, "s1", 2, 3, 5, 0)


def test_every_input_changes_the_number():
    base = uniform(7, "s1", 2, 3, 5, 0)
    others = {
        uniform(8, "s1", 2, 3, 5, 0),
        uniform(7, "s2", 2, 3, 5, 0),
        uniform(7, "s1", 3, 3, 5, 0),
        uniform(7, "s1", 2, 4, 5, 0),
        uniform(7, "s1", 2, 3, 6, 0),
        uniform(7, "s1", 2, 3, 5, 1),
    }
    assert base not in others and len(others) == 6


def test_the_numbers_are_spread_evenly():
    values = [uniform(1, "s1", row, 0, 0, 0) for row in range(20_000)]
    assert abs(sum(values) / len(values) - 0.5) < 0.01
    tenths = [sum(1 for v in values if i / 10 <= v < (i + 1) / 10) for i in range(10)]
    assert all(1_800 < count < 2_200 for count in tenths)


def test_the_algorithm_is_pinned_so_that_other_implementations_can_match_it():
    # BLAKE2b with an 8-byte digest of "seed:sheet:row:col:draw:index", top 53 bits, divided by 2**53 (D291).
    assert uniform(0, "s1", 0, 0, 0, 0) == 0.16474191069167177
    assert uniform(42, "s1", 1, 1, 3, 2) == 0.27081632623665597
