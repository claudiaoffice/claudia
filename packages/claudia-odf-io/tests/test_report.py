"""What could not be kept: a list a person can read (D401, E12.6)."""

from __future__ import annotations

from claudia_odf_io import Loss, LossLog


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
