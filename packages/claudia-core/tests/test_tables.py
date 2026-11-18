"""A table's definition: ids that are never reused, merges as rectangles, numbers read by the document's language,
totals and sorting, the limits, and the plain-data form (D1201–D1207)."""

from decimal import Decimal

import pytest

from claudia_core import (
    MAX_COLUMNS,
    MAX_ROWS,
    Column,
    ColumnSpec,
    Merge,
    Paragraph,
    RowSpec,
    TableDef,
    TableRegion,
    TableSource,
    entry_id,
    format_number,
    parse_entry_id,
    parse_number,
)


def words(table: TableDef, row: str, col: str, text: str, style: str = "") -> Paragraph:
    return Paragraph(entry_id(table.id, row, col), style, text).written_by("ann")


def filled(rows: list[list[str]], **options) -> TableDef:
    """A table whose first row is the header, with these words."""
    table = TableDef.blank("t1", len(rows), len(rows[0]), **options)
    changes = [
        (f"r{r}", f"c{c}", words(table, f"r{r}", f"c{c}", text))
        for r, line in enumerate(rows, 1)
        for c, text in enumerate(line, 1)
        if text
    ]
    return table.with_entries(changes)


HARVEST = [
    ["Site", "Beds", "Harvest"],
    ["Courtyard", "12", "212,5"],
    ["Roof", "8", "96"],
    ["Allotment", "26", "320,5"],
]


# -- ids -------------------------------------------------------------------------------------------------------
def test_a_box_has_the_id_table_row_column_and_it_reads_back():
    assert entry_id("t1", "r4", "c2") == "t1/r4/c2"
    assert parse_entry_id("t1/r4/c2") == ("t1", "r4", "c2")
    assert parse_entry_id("b12") is None
    assert parse_entry_id("t1/r4") is None
    assert parse_entry_id("T1/r4/c2") is None


def test_a_new_table_has_numbered_rows_and_columns_and_a_header_row():
    table = TableDef.blank("t1", 3, 2)
    assert table.rows == ("r1", "r2", "r3")
    assert table.column_ids() == ("c1", "c2")
    assert (table.header_rows, table.look, table.placement, table.banded) == (1, "rules", "flow", False)
    assert (table.next_row, table.next_col) == (3, 2)
    table.check()


def test_the_limits_are_100_rows_and_10_columns():
    assert (MAX_ROWS, MAX_COLUMNS) == (100, 10)
    TableDef.blank("t1", 100, 10).check()
    for rows, cols in ((101, 1), (1, 11), (0, 1), (1, 0)):
        with pytest.raises(ValueError, match="rows and"):
            TableDef.blank("t1", rows, cols)


def test_a_row_cannot_be_added_beyond_the_limit_and_the_message_says_what_to_use():
    table = TableDef.blank("t1", 100, 1)
    with pytest.raises(ValueError, match="linked table"):
        table.insert_rows([RowSpec("r101", "r100")])
    with pytest.raises(ValueError, match="at most 10 columns"):
        TableDef.blank("t1", 1, 10).insert_columns([ColumnSpec(Column("c11"), "c10")])


# -- boxes -----------------------------------------------------------------------------------------------------
def test_a_box_without_words_has_an_empty_paragraph_that_follows_the_look():
    table = TableDef.blank("t1", 2, 2)
    assert table.entry("r1", "c1") is None
    assert table.paragraph("r1", "c1") == Paragraph("t1/r1/c1", "")


def test_setting_a_box_and_taking_it_away_again():
    table = TableDef.blank("t1", 2, 2)
    changed = table.with_entries([("r1", "c2", words(table, "r1", "c2", "Beds"))])
    assert changed.text(0, 1) == "Beds"
    assert changed.with_entries([("r1", "c2", None)]).entries == {}


def test_a_paragraph_must_have_the_id_of_its_box_and_the_box_must_exist():
    table = TableDef.blank("t1", 2, 2)
    with pytest.raises(ValueError, match="id of the box"):
        table.with_entries([("r1", "c1", Paragraph("b1", "", "x"))])
    with pytest.raises(ValueError, match="no box"):
        table.with_entries([("r9", "c1", words(table, "r1", "c1", "x"))])


def test_a_column_is_named_by_its_last_header_box():
    table = filled(HARVEST)
    assert [table.column_name(c) for c in table.column_ids()] == ["Site", "Beds", "Harvest"]
    assert filled(HARVEST, header_rows=0).column_name("c1") == ""


def test_roles_follow_the_header_and_the_band():
    table = filled(HARVEST, banded=True)
    assert [table.role_of(i) for i in range(4)] == ["header", "body", "band", "body"]


def test_a_table_is_a_table_source_whatever_it_is_made_of():
    table = filled(HARVEST)
    assert isinstance(table, TableSource)
    assert (table.column_count(), table.row_count(), table.header_row_count()) == (3, 4, 1)
    assert table.text(2, 0) == "Roof"


# -- rows and columns --------------------------------------------------------------------------------------------
def test_rows_are_put_in_behind_the_row_they_name_and_ids_are_not_reused_after_a_delete():
    table = filled(HARVEST)
    bigger = table.insert_rows([RowSpec("r5", "r1", ((("c1"), words(table, "r5", "c1", "Garden")),))])
    assert bigger.rows == ("r1", "r5", "r2", "r3", "r4")
    assert bigger.text(1, 0) == "Garden"
    smaller = bigger.delete_rows(["r5", "r2"])
    assert smaller.rows == ("r1", "r3", "r4")
    assert smaller.next_row == 5  # r5 is never given again
    assert smaller.entries.get(("r5", "c1")) is None


def test_the_first_row_is_put_in_with_no_row_to_follow_and_the_header_is_kept_by_deleting_nothing():
    table = filled(HARVEST)
    assert table.insert_rows([RowSpec("r9")]).rows[0] == "r9"
    with pytest.raises(ValueError, match="at least one row"):
        table.delete_rows(table.rows)
    with pytest.raises(ValueError, match="no row"):
        table.delete_rows(["r9"])


def test_deleting_header_rows_shortens_the_header():
    table = filled(HARVEST, header_rows=2)
    assert table.delete_rows(["r1"]).header_rows == 1


def test_columns_are_put_in_and_taken_out_with_their_words():
    table = filled(HARVEST)
    wider = table.insert_columns(
        [ColumnSpec(Column("c4", "number"), "c1", (("r1", words(table, "r1", "c4", "Zone")),))]
    )
    assert wider.column_ids() == ("c1", "c4", "c2", "c3")
    assert wider.column_name("c4") == "Zone"
    narrower = wider.delete_columns(["c2"])
    assert narrower.column_ids() == ("c1", "c4", "c3")
    assert not any(k[1] == "c2" for k in narrower.entries)
    with pytest.raises(ValueError, match="at least one column"):
        table.delete_columns(table.column_ids())


def test_a_duplicate_id_is_refused():
    table = filled(HARVEST)
    with pytest.raises(ValueError, match="already"):
        table.insert_rows([RowSpec("r2")])
    with pytest.raises(ValueError, match="already"):
        table.insert_columns([ColumnSpec(Column("c1"))])


def test_moving_rows_keeps_the_header_on_top():
    table = filled(HARVEST)
    assert table.row_order(("r1", "r3", "r2", "r4")).rows == ("r1", "r3", "r2", "r4")
    with pytest.raises(ValueError, match="header stays"):
        table.row_order(("r2", "r1", "r3", "r4"))
    with pytest.raises(ValueError, match="exactly the rows"):
        table.row_order(("r1", "r2"))


def test_moving_columns():
    table = filled(HARVEST)
    assert table.column_order(("c3", "c1", "c2")).column_ids() == ("c3", "c1", "c2")
    with pytest.raises(ValueError, match="exactly the columns"):
        table.column_order(("c1",))


def test_a_column_takes_its_settings_by_id():
    table = filled(HARVEST).with_column(Column("c3", "number", "sum", 3000))
    assert table.column("c3") == Column("c3", "number", "sum", 3000)
    with pytest.raises(ValueError, match="total"):
        filled(HARVEST).with_column(Column("c3", "number", "median"))
    with pytest.raises(KeyError):
        filled(HARVEST).with_column(Column("c9"))


# -- merges ------------------------------------------------------------------------------------------------------
def test_a_merge_is_a_rectangle_and_the_boxes_it_covers_are_empty():
    table = filled([["Harvest", "", ""], ["Site", "Beds", "kg"], ["Roof", "8", "96"]])
    merged = table.with_merge("r1", "c1", 1, 3)
    assert merged.merges == (Merge("r1", "c1", 1, 3),)
    assert merged.covered("r1", "c3") and not merged.covered("r1", "c1")
    assert merged.cover_of("r2", "c1") is None
    merged.check()


def test_a_merge_cannot_cover_words_leave_the_table_or_meet_another_merge():
    table = filled(HARVEST)
    with pytest.raises(ValueError, match="empty"):
        table.with_merge("r1", "c1", 1, 2)
    with pytest.raises(ValueError, match="beyond"):
        table.with_merge("r4", "c3", 2, 1)
    two = filled([["A", "", ""], ["", "", ""], ["", "", ""]]).with_merge("r1", "c1", 2, 2)
    with pytest.raises(ValueError, match="share a box"):
        two.with_merge("r2", "c2", 2, 2)


def test_splitting_a_merge_is_merging_one_by_one():
    table = filled([["A", "", ""], ["", "", ""]]).with_merge("r1", "c1", 2, 2)
    assert table.with_merge("r1", "c1", 1, 1).merges == ()


def test_words_cannot_be_put_in_a_covered_box():
    table = filled([["A", "", ""], ["", "", ""]]).with_merge("r1", "c1", 1, 2)
    with pytest.raises(ValueError, match="top-left"):
        table.with_entries([("r1", "c2", words(table, "r1", "c2", "x"))])


def test_a_row_put_inside_a_merge_makes_it_taller_and_one_put_beside_it_does_not():
    table = filled([["A", "", ""], ["", "", ""], ["x", "y", "z"]]).with_merge("r1", "c1", 2, 2)
    inside = table.insert_rows([RowSpec("r9", "r1")])
    assert inside.merges == (Merge("r1", "c1", 3, 2),)
    behind = table.insert_rows([RowSpec("r9", "r2")])
    assert behind.merges == (Merge("r1", "c1", 2, 2),)
    before = table.insert_rows([RowSpec("r9")])
    assert before.merges == (Merge("r1", "c1", 2, 2),)


def test_a_column_put_inside_a_merge_makes_it_wider():
    table = filled([["A", "", ""], ["", "", ""]]).with_merge("r1", "c1", 1, 3)
    assert table.insert_columns([ColumnSpec(Column("c9"), "c2")]).merges == (Merge("r1", "c1", 1, 4),)


def test_deleting_rows_shrinks_a_merge_and_a_merge_of_one_box_is_gone():
    table = filled([["A", "", ""], ["", "", ""], ["", "", ""], ["", "", ""]]).with_merge("r1", "c1", 3, 1)
    assert table.delete_rows(["r2"]).merges == (Merge("r1", "c1", 2, 1),)
    assert table.delete_rows(["r2", "r3"]).merges == ()
    assert table.delete_rows(["r1"]).merges == (Merge("r2", "c1", 2, 1),)
    assert table.delete_rows(["r1", "r2", "r3"]).merges == ()


def test_deleting_columns_shrinks_a_merge():
    table = filled([["A", "", ""], ["", "", ""]]).with_merge("r1", "c1", 1, 3)
    assert table.delete_columns(["c3"]).merges == (Merge("r1", "c1", 1, 2),)
    assert table.delete_columns(["c2", "c3"]).merges == ()


def test_rows_of_a_merge_stay_together_when_the_rows_are_moved():
    table = filled([["h", "h"], ["A", ""], ["", ""], ["x", "y"]]).with_merge("r2", "c1", 2, 1)
    with pytest.raises(ValueError, match="torn apart"):
        table.row_order(("r1", "r2", "r4", "r3"))
    assert table.row_order(("r1", "r4", "r2", "r3")).rows == ("r1", "r4", "r2", "r3")


def test_columns_of_a_merge_stay_together_when_the_columns_are_moved():
    table = filled([["A", "", "x"], ["", "", "y"]]).with_merge("r1", "c1", 1, 2)
    with pytest.raises(ValueError, match="torn apart"):
        table.column_order(("c1", "c3", "c2"))
    assert table.column_order(("c3", "c1", "c2")).column_ids() == ("c3", "c1", "c2")


def test_restoring_merges_after_an_insert_is_possible_for_an_undo():
    table = filled([["A", "", ""], ["", "", ""], ["x", "y", "z"]]).with_merge("r1", "c1", 2, 2)
    grown = table.insert_rows([RowSpec("r9", "r1")])
    assert grown.delete_rows(["r9"]).merges == table.merges
    assert table.insert_rows([RowSpec("r9", "r1")], merges=table.merges).merges == table.merges


# -- numbers -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "language", "value"),
    [
        ("12", None, "12"),
        ("1.234", "de", "1234"),
        ("1.234", "en", "1.234"),
        ("1.234,5", "de", "1234.5"),
        ("1,234.5", "en", "1234.5"),
        ("1 234,5", "fr", "1234.5"),
        ("212,5", "de-DE", "212.5"),
        ("-3,5", "de", "-3.5"),
        ("−3.5", "en", "-3.5"),
        ("+4", None, "4"),
        (" 7 ", "en", "7"),
        ("0,5", "pt-BR", "0.5"),
        (",5", "de", "0.5"),
    ],
)
def test_words_are_a_number_by_the_conventions_of_the_documents_language(text, language, value):
    assert parse_number(text, language) == Decimal(value)


@pytest.mark.parametrize("text", ["", "x", "12 kg", "1,2,3", "1.2.3", "1,23.4,5", "--1", "1.", ".", "€5", "1,2345,6"])
def test_other_words_are_not_a_number(text):
    assert parse_number(text, "en") is None


def test_a_number_is_written_in_the_language_of_the_text():
    assert format_number(Decimal("1234.50"), "de") == "1234,50"
    assert format_number(Decimal("1234.50"), "en") == "1234.50"
    assert format_number(Decimal("3"), None) == "3"


# -- totals and sorting -------------------------------------------------------------------------------------------
def test_a_total_reads_the_body_rows_by_the_documents_language():
    table = filled(HARVEST).with_column(Column("c2", "number", "sum")).with_column(Column("c3", "number", "sum"))
    assert table.totals("de") == {"c2": "46", "c3": "629,0"}
    assert table.has_total()
    assert filled(HARVEST).totals("de") == {} and not filled(HARVEST).has_total()


def test_every_total_function():
    table = filled([["x", "n"], ["a", "1,5"], ["b", "2,5"], ["c", "skip"], ["d", "6"]])
    out = {}
    for function in ("sum", "mean", "count", "min", "max"):
        out[function] = table.with_column(Column("c2", "number", function)).totals("de")["c2"]
    assert out == {"sum": "10,0", "mean": "3,33", "count": "3", "min": "1,5", "max": "6"}


def test_a_total_of_nothing_is_empty_and_the_header_never_counts():
    table = filled([["1", "2"], ["x", "y"]]).with_column(Column("c1", "number", "sum"))
    assert table.totals("en") == {"c1": ""}


def test_a_total_skips_the_boxes_a_merge_covers():
    table = filled([["h", "h"], ["5", ""], ["", ""], ["7", "1"]]).with_merge("r2", "c1", 2, 1)
    assert table.with_column(Column("c1", "number", "sum")).totals("en") == {"c1": "12"}


def test_sorting_puts_numbers_first_then_words_and_empty_boxes_last_and_keeps_the_header():
    table = filled(
        [["Site", "Kg"], ["Roof", "96"], ["Courtyard", "212,5"], ["Äcker", "x"], ["Garden", ""], ["Hill", "8"]]
    )
    assert table.sort_order("c2", language="de") == ("r1", "r6", "r2", "r3", "r4", "r5")
    assert table.sort_order("c2", descending=True, language="de") == ("r1", "r4", "r3", "r2", "r6", "r5")
    assert table.sort_order("c1") == ("r1", "r4", "r3", "r5", "r6", "r2")  # Äcker sorts under A


def test_sorting_twice_changes_nothing_and_equal_rows_keep_their_order():
    table = filled([["h"], ["b"], ["a"], ["b"]])
    once = table.row_order(table.sort_order("c1"))
    assert once.sort_order("c1") == once.rows
    assert table.sort_order("c1") == ("r1", "r3", "r2", "r4")


def test_sorting_refuses_merged_rows_in_the_body():
    table = filled([["h", "h"], ["A", ""], ["", ""], ["x", "y"]]).with_merge("r2", "c1", 2, 1)
    with pytest.raises(ValueError, match="merged rows"):
        table.sort_order("c1")


# -- checking ----------------------------------------------------------------------------------------------------
def test_a_table_that_holds_together_checks_and_one_that_does_not_says_why():
    table = filled(HARVEST)
    table.check()
    for bad, match in (
        ({"placement": "side"}, "placed flow or float"),
        ({"look": "Rules"}, "look"),
        ({"width": 5}, "line wide"),
        ({"header_rows": 9}, "header"),
        ({"banded": "yes"}, "banded"),
    ):
        with pytest.raises(ValueError, match=match):
            table.with_options(**bad)


def test_a_box_holds_plain_words_only():
    from claudia_core import ListItem

    table = TableDef.blank("t1", 1, 1)
    p = Paragraph("t1/r1/c1", "", "x", ((__import__("claudia_core").Run(1, None)),), item=ListItem("l1"))
    with pytest.raises(ValueError, match="plain words"):
        TableDef(table.id, table.columns, table.rows, {("r1", "c1"): p}).check()


def test_options_are_the_five_a_table_has():
    table = filled(HARVEST).with_options(header_rows=2, banded=True, look="grid", placement="float", width=5000)
    assert (table.header_rows, table.banded, table.look, table.placement, table.width) == (
        2,
        True,
        "grid",
        "float",
        5000,
    )
    with pytest.raises(ValueError, match="no option"):
        table.with_options(colour="red")


# -- the plain-data form -----------------------------------------------------------------------------------------
def test_a_table_round_trips_through_plain_data():
    table = (
        filled([["A", "", ""], ["", "x", "1,5"], ["", "y", "2"]], banded=True, width=7000)
        .with_merge("r1", "c1", 1, 3)
        .with_column(Column("c3", "number", "sum", 2500))
    )
    again = TableDef.from_data(table.to_data())
    assert again == table
    assert again.to_data() == table.to_data()


def test_the_plain_data_names_its_format():
    data = filled(HARVEST).to_data()
    assert data["format"] == 1
    with pytest.raises(ValueError, match="format"):
        TableDef.from_data({**data, "format": 2})


def test_entries_cannot_be_changed_after_the_fact():
    with pytest.raises(TypeError):
        filled(HARVEST).entries[("r1", "c1")] = None  # type: ignore[index]


# -- redaction ---------------------------------------------------------------------------------------------------
def test_blanking_keeps_the_shape_and_loses_the_words():
    table = filled(HARVEST, banded=True)
    emptied = table.blanked()
    assert emptied.rows == table.rows and emptied.columns == table.columns
    assert all(p.text == "" and p.runs == () for p in emptied.all_paragraphs())
    kept = table.blanked(keep_length=True)
    assert kept.paragraph("r2", "c1").text == "█" * len("Courtyard")
    assert kept.paragraph("r2", "c1").runs == table.paragraph("r2", "c1").runs


# -- the region --------------------------------------------------------------------------------------------------
def test_regions_of_a_table_meet_when_they_share_a_row_and_a_column():
    a = TableRegion("t1", frozenset({"r1", "r2"}), frozenset({"c1"}))
    assert a.overlaps(TableRegion("t1", frozenset({"r2"}), frozenset({"c1", "c2"})))
    assert not a.overlaps(TableRegion("t1", frozenset({"r3"}), frozenset({"c1"})))
    assert not a.overlaps(TableRegion("t1", frozenset({"r1"}), frozenset({"c2"})))
    assert not a.overlaps(TableRegion("t2", frozenset({"r1"}), frozenset({"c1"})))
    assert a.overlaps(TableRegion("t1"))  # none means all of it


def test_a_region_round_trips_and_a_bad_one_is_refused():
    region = TableRegion("t1", frozenset({"r1"}), None)
    assert TableRegion.from_data(region.to_data()) == region
    with pytest.raises(ValueError, match="table region"):
        TableRegion.from_data({"table": "t1", "rows": [1], "cols": None})
