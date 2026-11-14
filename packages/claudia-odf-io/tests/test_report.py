"""What could not be kept: a list a person can read (D401, E12.6)."""

from __future__ import annotations

from claudia_odf_io import Loss, LossLog, unwritten_changes


def test_a_loss_names_what_and_how_many():
    assert Loss("table", "", 2).count == 2 and Loss("style", "Salutation").detail == "Salutation"


def test_the_same_thing_lost_twice_is_one_line_with_a_count():
    log = LossLog()
    log.add("table")
    log.add("table")
    log.add("table", count=3)
    assert log.result() == (Loss("table", "", 5),)


def test_the_same_kind_with_another_detail_is_another_line():
    log = LossLog()
    log.add("style", "Salutation")
    log.add("style", "Signature")
    log.add("style", "Salutation")
    assert log.result() == (Loss("style", "Salutation", 2), Loss("style", "Signature", 1))


def test_the_lines_come_in_the_order_things_were_first_lost():
    log = LossLog()
    for kind in ("frame", "table", "frame", "list"):
        log.add(kind)
    assert [loss.kind for loss in log.result()] == ["frame", "table", "list"]


def test_an_empty_log_is_an_empty_result():
    assert LossLog().result() == ()


# -- changes the writer cannot write (D450) -----------------------------------------------------------------------
def test_a_change_to_a_facet_that_is_written_is_not_a_loss():
    assert unwritten_changes({"blocks": [1]}, {"blocks": [1, 2]}, written={"blocks"}) == ()


def test_a_change_to_a_facet_that_is_not_written_is_a_loss_named_after_it():
    assert unwritten_changes({"page": {"paper": "a4"}}, {"page": {"paper": "letter"}}, written=set()) == (
        Loss("not-written", "page", 1),
    )


def test_a_facet_that_did_not_change_is_not_a_loss_even_when_it_is_not_written():
    assert unwritten_changes({"page": 1, "lists": []}, {"page": 1, "lists": []}, written=set()) == ()


def test_a_facet_with_a_code_of_its_own_is_lost_under_that_code():
    losses = unwritten_changes({"charts": {}}, {"charts": {"c1": 1}}, written=set(), kinds={"charts": "chart"})
    assert losses == (Loss("chart", "", 1),)


def test_the_count_is_how_many_entries_differ():
    before = {"objects": [{"id": "o1"}, {"id": "o2"}]}
    after = {"objects": [{"id": "o1"}, {"id": "o2x"}, {"id": "o3"}]}
    assert unwritten_changes(before, after, written=set()) == (Loss("not-written", "objects", 2),)
    assert unwritten_changes({"names": {"a": 1}}, {"names": {"a": 2, "b": 1}}, written=set()) == (
        Loss("not-written", "names", 2),
    )


def test_a_facet_that_came_or_went_is_a_difference():
    assert unwritten_changes({}, {"language": "de"}, written=set()) == (Loss("not-written", "language", 1),)
    assert unwritten_changes({"language": "de"}, {}, written=set()) == (Loss("not-written", "language", 1),)


def test_the_losses_come_in_the_order_of_the_new_state_then_the_removed_ones():
    before = {"a": 1, "z": 1}
    after = {"b": 2, "a": 2}
    assert [loss.detail for loss in unwritten_changes(before, after, written=set())] == ["b", "a", "z"]
