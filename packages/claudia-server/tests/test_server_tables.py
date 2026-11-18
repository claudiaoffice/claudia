"""Tables over the wire (E9.32, D1201–D1212): what a client or the AI asks of a table, by ids.

The kernel's commands carry the exact inverse and the locks; these tests are about what the wire adds: the words a
request is made of, ids that nobody gave twice, the totals in the language of the text, and that every refusal says what
is wrong and leaves the table as it was."""

import pytest

from claudia_composes import SetLanguage, TextModel
from claudia_core import Document, MemoryStore, SetEntries, TableRegion, entry_id, entry_paragraph
from claudia_server.apps import MODEL_METHODS
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")
AI = Account.assistant(MODEL_METHODS["composes"])

HARVEST = [["Site", "Beds", "Harvest"], ["Courtyard", "12", "212,5"], ["Roof", "8", "96"], ["Allotment", "26", "320,5"]]


@pytest.fixture
def paper():
    d = Document(TextModel(), store=MemoryStore())
    call(d, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "The gardens\nOur beds."})
    return d


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params or {})


def add(doc, cells=None, **more):
    given = {"block": "b1", "offset": 3, **({"cells": cells} if cells else {"rows": 3, "cols": 2}), **more}
    return call(doc, "add_table", given)


def tid(doc):
    """The id of the one table of the document: tables get ids like objects do, random, never counted."""
    (only,) = doc.model.tables
    return only


def table_of(doc):
    return doc.model.tables[tid(doc)]


def box(doc, row, col):
    return entry_id(tid(doc), row, col)


def words(doc, row, col):
    return table_of(doc).paragraph(row, col).text


@pytest.fixture
def harvest(paper):
    add(paper, HARVEST)
    return paper


def test_composes_has_the_methods_that_change_a_table():
    expected = {
        "tables",
        "add_table",
        "remove_table",
        "set_entries",
        "insert_rows",
        "delete_rows",
        "insert_columns",
        "delete_columns",
        "sort_rows",
        "move_rows",
        "move_columns",
        "set_column",
        "set_table_options",
        "merge_cells",
        "split_cell",
    }
    assert expected <= composes_methods.names()


# -- a table comes in ------------------------------------------------------------------------------------------
def test_a_table_is_put_where_the_person_points_and_gets_a_name_and_ids_from_one(paper):
    made = add(paper)
    assert set(made) == {"object", "table", "revision"}
    shown = paper.model.get_object(made["object"])
    assert (shown.anchor.block, shown.anchor.offset) == ("b1", 3)
    assert shown.body.kind == "table" and shown.body.table == made["table"]
    assert shown.body.name == "Table 1"
    definition = paper.model.tables[made["table"]]
    assert definition.rows == ("r1", "r2", "r3") and definition.column_ids() == ("c1", "c2")
    assert definition.header_rows == 1 and definition.look == "rules" and definition.placement == "flow"


def test_a_table_may_come_with_its_words_which_are_the_authors(paper):
    add(paper, HARVEST)
    assert words(paper, "r1", "c1") == "Site" and words(paper, "r4", "c3") == "320,5"
    assert table_of(paper).paragraph("r2", "c1").runs[0].author == "ann"
    assert table_of(paper).column_ids() == ("c1", "c2", "c3")


def test_the_words_may_be_fewer_than_the_boxes_but_not_more(paper):
    add(paper, [["a"]], rows=3, cols=2)
    assert table_of(paper).rows == ("r1", "r2", "r3") and words(paper, "r1", "c1") == "a"
    with pytest.raises(RequestError) as refused:
        add(paper, [["a", "b", "c"]], rows=2, cols=2)
    assert refused.value.code == "bad_request" and "cells" in refused.value.message


def test_the_limits_are_refused_with_a_sentence_and_the_text_is_unchanged(paper):
    before = paper.revision
    for rows, cols in ((101, 2), (2, 11), (0, 2)):
        with pytest.raises(RequestError) as refused:
            call(paper, "add_table", {"block": "b1", "offset": 0, "rows": rows, "cols": cols})
        assert refused.value.code in ("bad_request", "command_error") and "100 rows" in refused.value.message
    assert paper.revision == before and not paper.model.tables


def test_a_table_cannot_hang_from_a_place_that_is_not_there(paper):
    with pytest.raises(RequestError) as refused:
        call(paper, "add_table", {"block": "b9", "offset": 0, "rows": 2, "cols": 2})
    assert refused.value.code == "command_error"
    with pytest.raises(RequestError):
        call(paper, "add_table", {"block": "b1", "offset": 999, "rows": 2, "cols": 2})


def test_a_viewer_may_read_the_tables_but_not_change_them(harvest):
    (shown,) = call(harvest, "tables", account=VERA)
    assert shown["id"] == tid(harvest)
    with pytest.raises(RequestError) as refused:
        call(harvest, "insert_rows", {"table": tid(harvest), "count": 1}, account=VERA)
    assert refused.value.code == "forbidden"


# -- reading ---------------------------------------------------------------------------------------------------
def test_the_tables_are_listed_with_the_objects_that_show_them_and_the_derived_totals(harvest):
    harvest.execute(SetLanguage("de"), author="ann")
    call(harvest, "set_column", {"table": tid(harvest), "column": "c3", "changes": {"kind": "number", "total": "sum"}})
    (shown,) = call(harvest, "tables")
    assert shown["id"] == tid(harvest) and shown["rows"] == ["r1", "r2", "r3", "r4"]
    assert [c["id"] for c in shown["columns"]] == ["c1", "c2", "c3"]
    assert shown["used_by"] == harvest.model.users_of_table(tid(harvest))
    assert shown["totals"] == {"c3": "629,0"}, "a total is read, never stored (D1203)"
    assert "totals" not in table_of(harvest).to_data()


def test_the_totals_follow_the_language_of_the_text(harvest):
    call(harvest, "set_column", {"table": tid(harvest), "column": "c3", "changes": {"kind": "number", "total": "sum"}})
    (shown,) = call(harvest, "tables")
    assert shown["totals"] == {"c3": "96"}, "without a language 212,5 is not a number"
    harvest.execute(SetLanguage("de"), author="ann")
    (shown,) = call(harvest, "tables")
    assert shown["totals"] == {"c3": "629,0"}
    call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r3", "c3", "96,5"]]})
    (shown,) = call(harvest, "tables")
    assert shown["totals"] == {"c3": "629,5"}, "212,5 + 96,5 + 320,5 with a decimal comma"


# -- boxes -----------------------------------------------------------------------------------------------------
def test_boxes_are_set_and_cleared_by_their_row_and_column_in_one_step(harvest):
    before = harvest.revision
    call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r2", "c2", "13"], ["r3", "c1", None]]})
    assert words(harvest, "r2", "c2") == "13" and words(harvest, "r3", "c1") == ""
    harvest.undo("ann")
    assert words(harvest, "r2", "c2") == "12" and words(harvest, "r3", "c1") == "Roof"
    assert harvest.revision != before


def test_a_box_keeps_its_own_style_when_its_words_are_set(harvest):
    harvest.execute(
        SetEntries(tid(harvest), (("r1", "c1", entry_paragraph(tid(harvest), "r1", "c1", "Site", "body")),)),
        author="ann",
    )
    call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r1", "c1", "Place"]]})
    assert table_of(harvest).paragraph("r1", "c1").style == "body" and words(harvest, "r1", "c1") == "Place"


def test_words_with_a_line_break_are_one_line_in_a_box_and_make_no_field(harvest):
    call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r2", "c1", "Court\nyard￼"]]})
    assert words(harvest, "r2", "c1") == "Court yard"


def test_a_box_that_is_not_there_or_is_covered_is_refused_and_nothing_changes(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r1", "col": "c1", "rows": 1, "cols": 2})
    before = harvest.revision
    for changes, why in (([["r9", "c1", "x"]], "r9"), ([["r1", "c2", "x"]], "merged"), ([["r2", "c9", "x"]], "c9")):
        with pytest.raises(RequestError) as refused:
            call(harvest, "set_entries", {"table": tid(harvest), "changes": changes})
        assert refused.value.code == "command_error" and why in refused.value.message
    with pytest.raises(RequestError) as unknown:
        call(harvest, "set_entries", {"table": "t9", "changes": [["r1", "c1", "x"]]})
    assert unknown.value.code == "command_error" and "t9" in unknown.value.message
    assert harvest.revision == before


def test_a_box_a_colleague_holds_is_locked_and_the_rest_of_the_table_is_not(harvest):
    harvest.lock("ben", [TableRegion(tid(harvest), frozenset({"r2"}), frozenset({"c1"}))], ttl=5)
    with pytest.raises(RequestError) as refused:
        call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r2", "c1", "x"]]})
    assert refused.value.code == "locked"
    call(harvest, "set_entries", {"table": tid(harvest), "changes": [["r2", "c2", "13"]]})


# -- rows and columns --------------------------------------------------------------------------------------------
def test_rows_come_in_behind_a_row_in_front_of_one_or_at_the_end_with_ids_nobody_had(harvest):
    behind = call(harvest, "insert_rows", {"table": tid(harvest), "count": 2, "after": "r2"})["rows"]
    assert table_of(harvest).rows == ("r1", "r2", *behind, "r3", "r4")
    front = call(harvest, "insert_rows", {"table": tid(harvest), "count": 1, "before": "r1"})["rows"]
    assert table_of(harvest).rows[0] == front[0]
    end = call(harvest, "insert_rows", {"table": tid(harvest), "count": 1})["rows"]
    assert table_of(harvest).rows[-1] == end[0]
    ids = table_of(harvest).rows
    assert len(set(ids)) == len(ids) == 8


def test_a_deleted_rows_id_does_not_come_back_for_a_new_row(harvest):
    call(harvest, "delete_rows", {"table": tid(harvest), "ids": ["r4"]})
    (new,) = call(harvest, "insert_rows", {"table": tid(harvest), "count": 1})["rows"]
    assert new not in ("r1", "r2", "r3", "r4")
    harvest.undo("ann")
    harvest.undo("ann")
    assert table_of(harvest).rows == ("r1", "r2", "r3", "r4") and words(harvest, "r4", "c1") == "Allotment"


def test_rows_and_columns_come_and_go_within_the_limits_and_one_request_is_one_step(harvest):
    call(harvest, "insert_rows", {"table": tid(harvest), "count": 96})
    assert len(table_of(harvest).rows) == 100
    revision = harvest.revision
    with pytest.raises(RequestError) as refused:
        call(harvest, "insert_rows", {"table": tid(harvest), "count": 1})
    assert refused.value.code == "command_error" and "100 rows" in refused.value.message
    assert harvest.revision == revision
    new = call(harvest, "insert_columns", {"table": tid(harvest), "count": 2, "after": "c1"})["columns"]
    assert table_of(harvest).column_ids() == ("c1", *new, "c2", "c3")
    call(harvest, "delete_columns", {"table": tid(harvest), "ids": new})
    assert table_of(harvest).column_ids() == ("c1", "c2", "c3")
    with pytest.raises(RequestError):
        call(harvest, "insert_columns", {"table": tid(harvest), "count": 8})


def test_both_after_and_before_make_no_sense_and_neither_does_a_row_that_is_not_there(harvest):
    for given in ({"after": "r1", "before": "r2"}, {"after": "r9"}, {"before": "r9"}, {"count": 0}, {"count": 101}):
        with pytest.raises(RequestError) as refused:
            call(harvest, "insert_rows", {"table": tid(harvest), "count": 1, **given})
        assert refused.value.code in ("bad_request", "command_error")


def test_rows_that_are_not_there_cannot_be_deleted(harvest):
    with pytest.raises(RequestError) as refused:
        call(harvest, "delete_rows", {"table": tid(harvest), "ids": ["r2", "r9"]})
    assert refused.value.code == "command_error" and "r9" in refused.value.message
    assert len(table_of(harvest).rows) == 4


# -- sorting and moving --------------------------------------------------------------------------------------------
def test_sorting_keeps_the_header_and_the_ids_and_undoes_in_one_step(harvest):
    call(harvest, "set_column", {"table": tid(harvest), "column": "c2", "changes": {"kind": "number"}})
    call(harvest, "sort_rows", {"table": tid(harvest), "column": "c2"})
    assert table_of(harvest).rows == ("r1", "r3", "r2", "r4")
    call(harvest, "sort_rows", {"table": tid(harvest), "column": "c2", "descending": True})
    assert table_of(harvest).rows == ("r1", "r4", "r2", "r3")
    harvest.undo("ann")
    assert table_of(harvest).rows == ("r1", "r3", "r2", "r4")


def test_sorting_reads_numbers_in_the_language_of_the_text(harvest):
    harvest.execute(SetLanguage("de"), author="ann")
    call(harvest, "sort_rows", {"table": tid(harvest), "column": "c3"})
    assert table_of(harvest).rows == ("r1", "r3", "r2", "r4"), "96, 212,5, 320,5"


def test_a_table_with_merged_rows_is_not_sorted(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r2", "col": "c1", "rows": 2, "cols": 1})
    with pytest.raises(RequestError) as refused:
        call(harvest, "sort_rows", {"table": tid(harvest), "column": "c2"})
    assert refused.value.code == "command_error" and "split" in refused.value.message


def test_rows_and_columns_are_moved_in_front_of_another_or_to_the_end(harvest):
    call(harvest, "move_rows", {"table": tid(harvest), "ids": ["r4"], "before": "r2"})
    assert table_of(harvest).rows == ("r1", "r4", "r2", "r3")
    call(harvest, "move_rows", {"table": tid(harvest), "ids": ["r2", "r3"]})
    assert table_of(harvest).rows == ("r1", "r4", "r2", "r3")
    call(harvest, "move_columns", {"table": tid(harvest), "ids": ["c3"], "before": "c1"})
    assert table_of(harvest).column_ids() == ("c3", "c1", "c2")
    assert words(harvest, "r2", "c3") == "212,5", "the words travel with their column"


def test_the_header_stays_at_the_top_and_a_row_is_not_moved_in_front_of_itself(harvest):
    with pytest.raises(RequestError) as refused:
        call(harvest, "move_rows", {"table": tid(harvest), "ids": ["r1"]})
    assert refused.value.code == "command_error" and "header" in refused.value.message
    assert table_of(harvest).rows == ("r1", "r2", "r3", "r4")


def test_moving_something_that_is_not_there_is_refused(harvest):
    with pytest.raises(RequestError):
        call(harvest, "move_rows", {"table": tid(harvest), "ids": ["r9"]})
    with pytest.raises(RequestError):
        call(harvest, "move_rows", {"table": tid(harvest), "ids": ["r1"], "before": "r1"})


# -- the settings --------------------------------------------------------------------------------------------------
def test_a_column_is_a_number_or_words_and_may_total(harvest):
    call(harvest, "set_column", {"table": tid(harvest), "column": "c2", "changes": {"kind": "number", "total": "mean"}})
    column = table_of(harvest).column("c2")
    assert (column.kind, column.total) == ("number", "mean")
    call(harvest, "set_column", {"table": tid(harvest), "column": "c2", "changes": {"total": None, "width": 2500}})
    column = table_of(harvest).column("c2")
    assert (column.kind, column.total, column.width) == ("number", None, 2500), "what is not said stays"
    with pytest.raises(RequestError) as refused:
        call(harvest, "set_column", {"table": tid(harvest), "column": "c2", "changes": {"total": "median"}})
    assert refused.value.code == "command_error" and "sum" in refused.value.message
    with pytest.raises(RequestError):
        call(harvest, "set_column", {"table": tid(harvest), "column": "c2", "changes": {"colour": "red"}})


def test_the_options_of_a_table_are_the_few_it_has(harvest):
    call(
        harvest,
        "set_table_options",
        {"table": tid(harvest), "options": {"banded": True, "look": "grid", "header_rows": 2}},
    )
    table = table_of(harvest)
    assert (table.banded, table.look, table.header_rows) == (True, "grid", 2)
    call(harvest, "set_table_options", {"table": tid(harvest), "options": {"placement": "float", "width": 5000}})
    assert (table_of(harvest).placement, table_of(harvest).width) == ("float", 5000)
    harvest.undo("ann")
    assert table_of(harvest).placement == "flow"


def test_an_option_that_is_not_one_or_a_look_the_text_does_not_have_is_refused(harvest):
    for options in ({"colour": "red"}, {"look": "neon"}, {"header_rows": 9}, {"placement": "sideways"}):
        with pytest.raises(RequestError) as refused:
            call(harvest, "set_table_options", {"table": tid(harvest), "options": options})
        assert refused.value.code == "command_error"
    assert table_of(harvest).look == "rules"


# -- merging ---------------------------------------------------------------------------------------------------------
def test_merging_joins_the_words_of_the_boxes_it_covers_into_the_first_one(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r2", "col": "c1", "rows": 1, "cols": 2})
    assert words(harvest, "r2", "c1") == "Courtyard 12" and words(harvest, "r2", "c2") == ""
    assert [(m.row, m.col, m.rows, m.cols) for m in table_of(harvest).merges] == [("r2", "c1", 1, 2)]
    harvest.undo("ann")
    assert words(harvest, "r2", "c1") == "Courtyard" and words(harvest, "r2", "c2") == "12"
    assert not table_of(harvest).merges, "one request is one step"


def test_splitting_gives_the_boxes_back_and_the_words_stay_in_the_first(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r2", "col": "c1", "rows": 2, "cols": 1})
    call(harvest, "split_cell", {"table": tid(harvest), "row": "r2", "col": "c1"})
    assert not table_of(harvest).merges and words(harvest, "r2", "c1") == "Courtyard Roof"


def test_a_merge_that_does_not_fit_is_refused_and_nothing_changes(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r1", "col": "c1", "rows": 1, "cols": 2})
    before = harvest.revision
    for given in (
        {"row": "r1", "col": "c2", "rows": 2, "cols": 1},  # meets the merge
        {"row": "r4", "col": "c3", "rows": 2, "cols": 1},  # leaves the table
        {"row": "r2", "col": "c1", "rows": 1, "cols": 1},  # one box is no merge
    ):
        with pytest.raises(RequestError) as refused:
            call(harvest, "merge_cells", {"table": tid(harvest), **given})
        assert refused.value.code in ("command_error", "bad_request")
    assert harvest.revision == before


def test_splitting_a_box_that_is_no_merge_says_so(harvest):
    with pytest.raises(RequestError) as refused:
        call(harvest, "split_cell", {"table": tid(harvest), "row": "r2", "col": "c1"})
    assert refused.value.code == "command_error" and "merged" in refused.value.message


# -- taking a table away -----------------------------------------------------------------------------------------
def test_a_table_goes_with_its_object_and_comes_back_with_both_in_one_undo(harvest):
    table = tid(harvest)
    objects = harvest.model.users_of_table(table)
    call(harvest, "remove_table", {"id": table})
    assert not harvest.model.tables and not any(o in harvest.model.objects for o in objects)
    harvest.undo("ann")
    assert table_of(harvest).paragraph("r2", "c1").text == "Courtyard"
    assert harvest.model.users_of_table(table) == objects


def test_a_table_that_is_not_there_cannot_be_taken_away(harvest):
    with pytest.raises(RequestError) as refused:
        call(harvest, "remove_table", {"id": "t9"})
    assert refused.value.code == "command_error" and "t9" in refused.value.message


# -- typing in a box (D1210, D1212) ----------------------------------------------------------------------------------
def test_typing_in_a_box_is_replace_text_on_the_boxs_id(harvest):
    answer = call(
        harvest,
        "replace_text",
        {
            "block": box(harvest, "r2", "c1"),
            "start": 0,
            "end_block": box(harvest, "r2", "c1"),
            "end": 5,
            "text": "Yard",
        },
    )
    assert (
        words(harvest, "r2", "c1") == "Yardyard"
        and answer["block"] == box(harvest, "r2", "c1")
        and answer["offset"] == 4
    )
    assert table_of(harvest).paragraph("r2", "c1").runs[0].author in ("ann",)


def test_a_line_break_typed_in_a_box_is_a_space_because_a_box_is_one_paragraph(harvest):
    call(
        harvest,
        "replace_text",
        {
            "block": box(harvest, "r3", "c1"),
            "start": 4,
            "end_block": box(harvest, "r3", "c1"),
            "end": 4,
            "text": "\ntop",
        },
    )
    assert words(harvest, "r3", "c1") == "Roof top"
    assert len(harvest.model.blocks) == 2


def test_a_typing_that_leaves_its_box_or_misses_it_is_refused(harvest):
    with pytest.raises(RequestError) as spans:
        call(
            harvest,
            "replace_text",
            {
                "block": box(harvest, "r2", "c1"),
                "start": 0,
                "end_block": box(harvest, "r2", "c2"),
                "end": 1,
                "text": "",
            },
        )
    assert spans.value.code == "command_error" and "box" in spans.value.message
    with pytest.raises(RequestError) as mixed:
        call(
            harvest,
            "replace_text",
            {"block": "b1", "start": 0, "end_block": box(harvest, "r2", "c1"), "end": 1, "text": ""},
        )
    assert mixed.value.code == "command_error"
    with pytest.raises(RequestError) as beyond:
        call(
            harvest,
            "replace_text",
            {
                "block": box(harvest, "r2", "c1"),
                "start": 0,
                "end_block": box(harvest, "r2", "c1"),
                "end": 99,
                "text": "",
            },
        )
    assert beyond.value.code == "command_error"
    with pytest.raises(RequestError):
        call(
            harvest,
            "replace_text",
            {"block": f"{tid(harvest)}/r9/c1", "start": 0, "end_block": f"{tid(harvest)}/r9/c1", "end": 0, "text": "x"},
        )


def test_a_covered_box_takes_no_typing_and_the_sentence_says_where_the_words_go(harvest):
    call(harvest, "merge_cells", {"table": tid(harvest), "row": "r1", "col": "c1", "rows": 1, "cols": 2})
    with pytest.raises(RequestError) as refused:
        call(
            harvest,
            "replace_text",
            {
                "block": box(harvest, "r1", "c2"),
                "start": 0,
                "end_block": box(harvest, "r1", "c2"),
                "end": 0,
                "text": "x",
            },
        )
    assert refused.value.code == "command_error" and "top-left" in refused.value.message


def test_the_ai_quotes_the_words_of_a_box_by_its_id_like_those_of_a_paragraph(harvest):
    call(harvest, "replace_words", {"block": box(harvest, "r2", "c3"), "find": "212,5", "text": "230"}, account=AI)
    assert words(harvest, "r2", "c3") == "230"
    assert table_of(harvest).paragraph("r2", "c3").runs[0].author == AI.user
    with pytest.raises(RequestError) as missing:
        call(harvest, "replace_words", {"block": box(harvest, "r2", "c3"), "find": "zzz", "text": "1"}, account=AI)
    assert "not in paragraph" in missing.value.message


# -- what the clients are told -------------------------------------------------------------------------------------
def test_a_change_of_the_table_is_one_event_with_the_whole_table_and_typing_is_a_text_event(harvest):
    seen = []
    stop = harvest.subscribe(lambda event: seen.append(event.to_data()))
    call(harvest, "insert_rows", {"table": tid(harvest), "count": 1})
    tables = [e for e in seen if e["type"] == "table"]
    assert len(tables) == 1 and tables[0]["id"] == tid(harvest) and len(tables[0]["definition"]["rows"]) == 5
    seen.clear()
    call(
        harvest,
        "replace_text",
        {"block": box(harvest, "r2", "c1"), "start": 0, "end_block": box(harvest, "r2", "c1"), "end": 0, "text": "x"},
    )
    assert any(e["type"] == "text" and e["block"] == box(harvest, "r2", "c1") for e in seen)
    stop()


def test_a_table_the_ai_makes_is_the_ais_and_a_name_is_free_for_the_next(paper):
    first = add(paper)
    second = add(paper, block="b1", offset=1)
    names = {paper.model.get_object(first["object"]).body.name, paper.model.get_object(second["object"]).body.name}
    assert names == {"Table 1", "Table 2"}
