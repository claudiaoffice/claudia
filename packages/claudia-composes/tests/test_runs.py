"""Authorship runs: who wrote which stretch of a paragraph, and how that survives editing."""

from claudia_composes.runs import Run, delete_runs, insert_runs, runs_from_data, runs_to_data, slice_runs, total


def runs(*items):
    return [Run(n, who, via) for n, who, via in items]


def test_adjacent_runs_by_the_same_person_are_one_run():
    merged = insert_runs(runs((3, "ann", None)), 3, runs((2, "ann", None)))
    assert merged == runs((5, "ann", None))


def test_the_same_person_through_a_suggestion_is_another_run():
    merged = insert_runs(runs((3, "ann", None)), 3, runs((2, "ann", "ai")))
    assert merged == runs((3, "ann", None), (2, "ann", "ai"))


def test_inserting_inside_a_run_splits_it():
    result = insert_runs(runs((6, "ann", None)), 2, runs((3, "ben", None)))
    assert result == runs((2, "ann", None), (3, "ben", None), (4, "ann", None))


def test_inserting_at_the_ends():
    assert insert_runs(runs((2, "ann", None)), 0, runs((1, "ben", None))) == runs((1, "ben", None), (2, "ann", None))
    assert insert_runs([], 0, runs((4, "ben", None))) == runs((4, "ben", None))


def test_deleting_removes_exactly_that_part():
    original = runs((3, "ann", None), (3, "ben", None), (3, "ann", None))
    result = delete_runs(original, 2, 7)
    assert total(result) == 4
    assert result == runs((4, "ann", None))  # ann's two pieces meet and merge


def test_a_slice_keeps_who_wrote_what():
    original = runs((3, "ann", None), (3, "ben", None))
    assert slice_runs(original, 2, 5) == runs((1, "ann", None), (2, "ben", None))
    assert slice_runs(original, 0, 0) == []


def test_runs_survive_a_round_trip_through_data():
    original = runs((3, "ann", None), (2, "ben", "ai"))
    assert runs_to_data(original) == [[3, "ann", None], [2, "ben", "ai"]]
    assert runs_from_data(runs_to_data(original)) == original
