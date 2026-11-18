"""What a table command says of itself: its words in the history, the rows and columns it touches, needs and
overwrites, and what a colleague's work does to it when it is undone later (E9.32, D1201, D1210)."""

import pytest

from claudia_core import (
    Column,
    ColumnSpec,
    DefineTable,
    DeleteColumns,
    DeleteRows,
    ForgetTable,
    InsertColumns,
    InsertRows,
    Merge,
    Paragraph,
    RowSpec,
    SetColumn,
    SetColumnOrder,
    SetEntries,
    SetMerge,
    SetRowOrder,
    SetTableOptions,
    TableDef,
    entry_paragraph,
)
from claudia_core.commands import core_commands

TABLE = TableDef.blank("t1", 3, 2)
WORDS = entry_paragraph("t1", "r1", "c1", "Site")


def rebuilt(command):
    """The command read back from its plain data, as the log does."""
    return type(command).from_data(command.to_data(), core_commands)


COMMANDS = {
    "define": DefineTable(TABLE.to_data()),
    "forget": ForgetTable("t1"),
    "entries": SetEntries("t1", (("r1", "c1", WORDS),)),
    "insert_rows": InsertRows("t1", (RowSpec("r4", "r3", (("c1", Paragraph("t1/r4/c1", "", "x")),)),)),
    "delete_rows": DeleteRows("t1", ("r2",)),
    "row_order": SetRowOrder("t1", ("r1", "r3", "r2")),
    "sorted": SetRowOrder("t1", ("r1", "r3", "r2"), "c1"),
    "insert_columns": InsertColumns("t1", (ColumnSpec(Column("c3"), "c2", (("r1", Paragraph("t1/r1/c3", "", "x")),)),)),
    "delete_columns": DeleteColumns("t1", ("c2",)),
    "column_order": SetColumnOrder("t1", ("c2", "c1")),
    "column": SetColumn("t1", Column("c1", "number", "sum")),
    "options": SetTableOptions("t1", (("banded", True),)),
    "merge": SetMerge("t1", "r1", "c1", 1, 2),
    "split": SetMerge("t1", "r1", "c1", 1, 1),
}


@pytest.mark.parametrize("name", COMMANDS)
def test_every_table_command_has_words_for_the_history_and_survives_its_plain_data(name):
    command = COMMANDS[name]
    assert command.label and command.summary
    assert rebuilt(command) == command


def test_the_words_say_what_was_done():
    assert COMMANDS["merge"].label == "Merge cells" and COMMANDS["split"].label == "Split cell"
    assert "Sorted" in COMMANDS["sorted"].summary and "Moved rows" in COMMANDS["row_order"].summary
    assert COMMANDS["sorted"].label == "Sort rows" and COMMANDS["row_order"].label == "Move rows"
    assert (
        "Deleted 1 row" in COMMANDS["delete_rows"].summary and "Deleted 1 column" in COMMANDS["delete_columns"].summary
    )
    assert "Inserted 1 column" in COMMANDS["insert_columns"].summary
    assert "Moved columns" in COMMANDS["column_order"].summary
    assert "settings of a column" in COMMANDS["column"].summary and "options" in COMMANDS["options"].summary
    assert "takes a table" in COMMANDS["define"].summary and "lets go of the table t1" in COMMANDS["forget"].summary
    assert "Split a merged box" in COMMANDS["split"].summary and "Merged boxes" in COMMANDS["merge"].summary


def test_a_command_says_which_rows_and_columns_it_touches_needs_and_overwrites():
    assert COMMANDS["column"].touched() == (None, frozenset({"c1"}))
    assert COMMANDS["column"].needs()[1] == {"c1"}
    assert COMMANDS["delete_columns"].touched() == (None, frozenset({"c2"}))
    assert COMMANDS["delete_columns"].needs() == (frozenset(), frozenset({"c2"}))
    assert COMMANDS["delete_columns"].overwrites() == (None, frozenset({"c2"}))
    assert COMMANDS["delete_rows"].needs() == (frozenset({"r2"}), frozenset())
    assert COMMANDS["entries"].overwrites() == (frozenset({"r1"}), frozenset({"c1"}))
    assert COMMANDS["merge"].touched() == (frozenset({"r1"}), frozenset({"c1"}))
    assert COMMANDS["insert_columns"].needs() == (frozenset(), frozenset({"c2"}))
    assert COMMANDS["row_order"].touched() == (None, None) == COMMANDS["column_order"].touched()


def test_what_a_command_would_lose_is_what_it_redacts_and_a_structure_has_nothing_to_redact():
    for name in ("row_order", "column_order", "column", "options", "forget", "split"):
        assert COMMANDS[name].redacted() == COMMANDS[name]
    blank = COMMANDS["insert_columns"].redacted()
    assert blank.columns[0].entries[0][1].text == ""
    assert COMMANDS["insert_rows"].redacted().rows[0].entries[0][1].text == ""


def test_the_merges_an_undo_hands_back_are_in_the_plain_data_of_a_row_or_column_command():
    merges = (Merge("r1", "c1", 1, 2),)
    rows, cols = (
        InsertRows("t1", (RowSpec("r4", "r3"),), merges),
        InsertColumns(
            "t1",
            (
                ColumnSpec(
                    Column("c3"),
                ),
            ),
            merges,
        ),
    )
    assert rows.to_data()["merges"] == [m.to_data() for m in merges] == cols.to_data()["merges"]
    assert type(rows).from_data(rows.to_data(), core_commands) == rows
    assert type(cols).from_data(cols.to_data(), core_commands) == cols
    deleting = DeleteColumns("t1", ("c2",), merges)
    assert type(deleting).from_data(deleting.to_data(), core_commands) == deleting


# -- what a colleague's work does to an old command ------------------------------------------------------------------
def test_an_old_order_means_nothing_once_a_colleague_changed_the_rows_or_the_columns():
    order, columns = COMMANDS["row_order"], COMMANDS["column_order"]
    assert order.shifted_by(DeleteRows("t1", ("r1",))) is None
    assert order.shifted_by(InsertRows("t1", (RowSpec("r9", "r1"),))) is None
    assert order.shifted_by(COMMANDS["sorted"]) is None
    assert order.shifted_by(ForgetTable("t1")) is None
    assert order.shifted_by(DeleteRows("t2", ("r1",))) is order, "another table is no business of it"
    assert order.shifted_by(DeleteColumns("t1", ("c1",))) is order
    assert columns.shifted_by(DeleteColumns("t1", ("c1",))) is None
    assert (
        columns.shifted_by(
            InsertColumns(
                "t1",
                (
                    ColumnSpec(
                        Column("c9"),
                    ),
                ),
            )
        )
        is None
    )
    assert columns.shifted_by(ForgetTable("t1")) is None
    assert columns.shifted_by(DeleteRows("t1", ("r1",))) is columns


def test_a_merge_is_somewhere_else_once_a_colleague_inserted_or_moved_rows_or_columns():
    merge = COMMANDS["merge"]
    for other in (InsertRows("t1", (RowSpec("r9"),)), COMMANDS["column_order"], COMMANDS["row_order"]):
        assert merge.shifted_by(other) is None
    assert merge.shifted_by(DeleteRows("t1", ("r3",))) is merge
    assert merge.shifted_by(DeleteRows("t1", ("r1",))) is None, "its first row is gone"
    assert merge.redacted() is merge


def test_a_colleagues_typing_in_a_box_an_old_command_would_overwrite_makes_it_refuse_and_elsewhere_it_does_not():
    class Typed:
        kind = "text.InsertText"

        def __init__(self, paragraph):
            self.paragraph = paragraph

    assert COMMANDS["entries"].shifted_by(Typed("t1/r1/c1")) is None
    assert COMMANDS["entries"].shifted_by(Typed("t1/r3/c2")) is COMMANDS["entries"]
    assert COMMANDS["delete_columns"].shifted_by(Typed("t1/r3/c2")) is None
    assert COMMANDS["delete_columns"].shifted_by(Typed("t1/r3/c1")) is COMMANDS["delete_columns"]
    assert COMMANDS["define"].shifted_by(COMMANDS["define"]) is None
    assert COMMANDS["define"].shifted_by(ForgetTable("t1")) is COMMANDS["define"]
