"""A table that does not hold together says why, in a sentence, before it gets into a document (E9.32, D1201, D1205,
D1207): ids, sizes, columns, merges, the words of the boxes, and the regions of a colleague who is in it."""

from dataclasses import replace

import pytest

from claudia_core import (
    Column,
    ColumnSpec,
    InsertColumns,
    ListItem,
    Merge,
    Paragraph,
    RowSpec,
    TableDef,
    TableLook,
    TableRegion,
    entry_paragraph,
)
from claudia_core.table_commands import DeleteColumns, DeleteRows, ForgetTable


def table(**changes):
    return replace(TableDef.blank("t1", 3, 3), **changes)


def box(row, col, text="x", **more):
    return replace(Paragraph.from_data(entry_paragraph("t1", row, col, text)), **more)


@pytest.mark.parametrize(
    ("column", "why"),
    [
        (Column("C1"), "column id"),
        (Column("c1", kind="date"), "text or number"),
        (Column("c1", total="median"), "sum"),
        (Column("c1", width=5), "width"),
        (Column("c1", width=10_001), "width"),
    ],
)
def test_a_column_that_makes_no_sense_says_so(column, why):
    with pytest.raises(ValueError, match=why):
        column.check()


@pytest.mark.parametrize(
    ("broken", "why"),
    [
        (lambda: table(id="T 1"), "table id"),
        (lambda: table(rows=()), "1 to 100 rows"),
        (lambda: table(rows=tuple(f"r{n}" for n in range(1, 102))), "1 to 100 rows"),
        (lambda: table(columns=()), "1 to 10 columns"),
        (lambda: table(rows=("r1", "r1")), "different ids"),
        (lambda: table(columns=(Column("c1"), Column("c1"))), "different ids"),
        (lambda: table(header_rows=9), "header"),
        (lambda: table(banded="yes"), "banded"),
        (lambda: table(look="Rules!"), "look"),
        (lambda: table(placement="sideways"), "placed"),
        (lambda: table(width=500), "10 %"),
        (lambda: table(merges=(Merge("r9", "c1", 1, 2),)), "starts at a box"),
        (lambda: table(merges=(Merge("r1", "c1", 0, 2),)), "at least one box"),
        (lambda: table(merges=(Merge("r1", "c1", 1, 1),)), "more than one box"),
        (lambda: table(merges=(Merge("r3", "c1", 2, 1),)), "beyond the table"),
        (lambda: table(merges=(Merge("r1", "c1", 1, 2), Merge("r1", "c2", 1, 2))), "share a box"),
        (lambda: table(entries={("r9", "c1"): box("r9", "c1")}), "not in the table"),
        (lambda: table(entries={("r1", "c1"): box("r2", "c1")}), "id of the box"),
        (lambda: table(entries={("r1", "c1"): box("r1", "c1", item=ListItem("l1", 0))}), "plain words"),
        (
            lambda: table(merges=(Merge("r1", "c1", 1, 2),), entries={("r1", "c2"): box("r1", "c2")}),
            "top-left",
        ),
    ],
)
def test_a_table_that_does_not_hold_together_says_why(broken, why):
    with pytest.raises(ValueError, match=why):
        broken().check()


def test_a_look_has_four_roles_and_no_others():
    look = TableLook("l", "L", "h", "b", "band", "t")
    assert [look.style_for(role) for role in ("header", "body", "band", "total")] == ["h", "b", "band", "t"]
    with pytest.raises(ValueError, match="roles"):
        look.style_for("footer")


def test_a_table_is_known_by_its_id_to_whoever_reads_it():
    assert table().source_id == "t1"


def test_a_row_or_column_goes_behind_one_the_table_has_and_a_column_is_not_there_twice():
    with pytest.raises(ValueError, match="no row 'r9' to put a row behind"):
        table().insert_rows([RowSpec("r4", "r9")])
    with pytest.raises(ValueError, match="no column 'c9' to put a column behind"):
        table().insert_columns([ColumnSpec(Column("c4"), "c9")])
    with pytest.raises(ValueError, match="no column 'c9'"):
        table().delete_columns(["c9"])
    with pytest.raises(ValueError, match="starts at a box"):
        table().with_merge("r9", "c1", 1, 2)
    assert InsertColumns("t1", (ColumnSpec(Column("c4")),)).kind == "core.InsertColumns"


# -- the region of a colleague ------------------------------------------------------------------------------------
def test_a_region_loses_the_rows_and_columns_that_were_deleted_and_is_gone_with_the_last_one():
    region = TableRegion("t1", frozenset({"r1", "r2"}), frozenset({"c1"}))
    assert region.transformed(DeleteRows("t1", ("r1",))) == TableRegion("t1", frozenset({"r2"}), frozenset({"c1"}))
    assert region.transformed(DeleteRows("t1", ("r1", "r2"))) is None
    assert region.transformed(DeleteColumns("t1", ("c1",))) is None
    assert region.transformed(DeleteColumns("t1", ("c2",))) == region
    assert region.transformed(ForgetTable("t1")) is None
    assert region.transformed(ForgetTable("t2")) is region
    whole = TableRegion("t1")
    assert whole.transformed(DeleteRows("t1", ("r1",))) is whole, "all rows stay all rows"


@pytest.mark.parametrize(
    "data",
    [
        {"table": 7},
        {"table": "t1", "rows": "r1"},
        {"table": "t1", "cols": [1]},
    ],
)
def test_a_region_a_client_sends_that_is_none_is_refused(data):
    with pytest.raises(ValueError, match="table region"):
        TableRegion.from_data(data)
