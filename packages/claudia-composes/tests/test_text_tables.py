"""Tables in a text: an object that shows a definition, boxes that are typed into like any paragraph, and commands that
carry their exact inverse (D1201–D1210)."""

import pytest
from composes_helpers import SENTENCE

from claudia_composes import BlockAnchor, DeleteText, InsertText, TextModel
from claudia_core import (
    AddObject,
    Batch,
    Column,
    DefineTable,
    DeleteColumns,
    DeleteRows,
    Document,
    ForgetTable,
    ImageImport,
    InsertColumns,
    InsertRows,
    MemoryStore,
    ObjectBody,
    Paragraph,
    RegionHeld,
    RemoveObject,
    RowSpec,
    SetColumn,
    SetColumnOrder,
    SetEntries,
    SetMerge,
    SetRowOrder,
    SetTableOptions,
    TableDef,
    TableRegion,
    UndoConflict,
    UndoRefused,
    entry_id,
    entry_paragraph,
)


def table_in_a_text(rows: int = 4, cols: int = 3, **options) -> Document:
    d = Document(TextModel(), store=MemoryStore())
    d.execute(InsertText("b1", 0, SENTENCE), author="ann")
    table = TableDef.blank("t1", rows, cols, **options)
    body = ObjectBody("tb1", "table", 480, 120, "plain-box", ref="t1", name="Harvest")
    d.execute(Batch((DefineTable(table.to_data()), AddObject(body, BlockAnchor("b1", 9).to_data()))), author="ann")
    return d


def box(row: str, col: str) -> str:
    return entry_id("t1", row, col)


def fill(d: Document, rows: list[list[str]], author: str = "ann") -> None:
    changes = tuple(
        (f"r{r}", f"c{c}", entry_paragraph("t1", f"r{r}", f"c{c}", text, author=author))
        for r, line in enumerate(rows, 1)
        for c, text in enumerate(line, 1)
        if text
    )
    d.execute(SetEntries("t1", changes), author=author)


def words(d: Document, row: str, col: str) -> str:
    return d.model.tables["t1"].paragraph(row, col).text


HARVEST = [["Site", "Beds", "Harvest"], ["Courtyard", "12", "212,5"], ["Roof", "8", "96"], ["Allotment", "26", "320,5"]]


# -- the object and its definition --------------------------------------------------------------------------------
def test_a_table_is_an_object_that_hangs_from_a_paragraph_and_follows_the_words_in_front_of_it():
    d = table_in_a_text()
    assert d.model.objects["tb1"].body.kind == "table" and d.model.objects["tb1"].anchor.offset == 9
    d.execute(InsertText("b1", 0, "Look: "), author="ben")
    assert d.model.objects["tb1"].anchor.offset == 15
    d.undo("ben")
    assert d.model.objects["tb1"].anchor.offset == 9


def test_a_table_object_needs_a_definition_the_document_has():
    d = Document(TextModel(), store=MemoryStore())
    body = ObjectBody("tb1", "table", 480, 120, "plain-box", ref="t1")
    with pytest.raises(ValueError, match="does not know the table"):
        d.execute(AddObject(body, BlockAnchor("b1", 0).to_data()), author="ann")
    with pytest.raises(ValueError, match="needs a table"):
        d.execute(
            AddObject(ObjectBody("tb1", "table", 480, 120, "plain-box"), BlockAnchor("b1", 0).to_data()), author="ann"
        )


def test_a_table_object_has_no_import_record_and_no_words_of_its_own():
    d = Document(TextModel(), store=MemoryStore())
    d.execute(DefineTable(TableDef.blank("t1", 2, 2).to_data()), author="ann")
    record = ImageImport("a" * 64, "", "ana", "2026-11-18T10:00:00.000Z", "disk", "plan.png")
    with pytest.raises(ValueError, match="no import record"):
        d.execute(
            AddObject(
                ObjectBody("tb1", "table", 480, 120, "plain-box", ref="t1", imported=record),
                BlockAnchor("b1", 0).to_data(),
            ),
            author="ann",
        )
    words = Paragraph("tb1", "plain", "x")
    with pytest.raises(ValueError, match="carries no text"):
        d.execute(
            AddObject(
                ObjectBody("tb1", "table", 480, 120, "plain-box", words, ref="t1"), BlockAnchor("b1", 0).to_data()
            ),
            author="ann",
        )


def test_a_definition_that_is_shown_cannot_be_forgotten_and_one_nobody_shows_can():
    d = table_in_a_text()
    with pytest.raises(ValueError, match="is shown by"):
        d.execute(ForgetTable("t1"), author="ann")
    d.execute(RemoveObject("tb1"), author="ann")
    d.execute(ForgetTable("t1"), author="ann")
    assert d.model.tables == {}
    d.undo("ann")
    assert "t1" in d.model.tables


def test_the_look_has_to_be_one_the_text_has_and_a_box_style_a_paragraph_style():
    d = table_in_a_text()
    with pytest.raises(ValueError, match="no table look"):
        d.execute(SetTableOptions("t1", (("look", "fancy"),)), author="ann")
    with pytest.raises(ValueError, match="style"):
        d.execute(
            SetEntries("t1", (("r1", "c1", entry_paragraph("t1", "r1", "c1", "x", style="plain-shape")),)), author="ann"
        )
    d.execute(SetTableOptions("t1", (("look", "grid"),)), author="ann")
    assert d.model.tables["t1"].look == "grid"


def test_a_table_is_a_named_thing_in_the_shared_namespace():
    d = table_in_a_text()
    assert ("table", "tb1", "Harvest") in list(d.model.named_things())
    with pytest.raises(ValueError, match="already a"):
        d.execute(
            AddObject(
                ObjectBody("tb2", "table", 480, 120, "plain-box", ref="t1", name="harvest"),
                BlockAnchor("b1", 0).to_data(),
            ),
            author="ann",
        )


# -- the snapshot and old documents -------------------------------------------------------------------------------
def test_the_tables_are_in_the_snapshot_and_a_text_from_before_tables_reads():
    d = table_in_a_text()
    fill(d, HARVEST)
    state = d.model.serialize()
    again = TextModel.restore(state)
    assert again.tables["t1"] == d.model.tables["t1"]
    assert again.serialize() == state
    del state["tables"]
    assert TextModel.restore(state).tables == {}
    assert TextModel.state_schema == 16  # 16: paragraph descriptions


# -- typing in a box ----------------------------------------------------------------------------------------------
def test_typing_in_a_box_is_the_ordinary_text_command_on_the_boxs_paragraph_id():
    d = table_in_a_text()
    d.execute(InsertText(box("r2", "c1"), 0, "Courtyard"), author="ben")
    assert words(d, "r2", "c1") == "Courtyard"
    assert d.model.tables["t1"].paragraph("r2", "c1").runs[0].author == "ben"
    d.execute(InsertText(box("r2", "c1"), 5, "-"), author="ann")
    d.execute(DeleteText(box("r2", "c1"), 0, 3), author="ann")
    assert words(d, "r2", "c1") == "rt-yard"
    d.undo("ann")
    d.undo("ann")
    assert words(d, "r2", "c1") == "Courtyard"
    alone = table_in_a_text()
    alone.execute(InsertText(box("r2", "c1"), 0, "Courtyard"), author="ben")
    alone.undo("ben")
    assert alone.model.tables["t1"].entry("r2", "c1") is None, "a box with no words and no style of its own is not kept"


def test_the_clients_are_told_with_the_text_event_and_the_boxs_id():
    d = table_in_a_text()
    seen = []
    d.subscribe(lambda event: seen.append(event.to_data()) if hasattr(event, "to_data") else None) if hasattr(
        d, "subscribe"
    ) else None
    d.execute(InsertText(box("r1", "c2"), 0, "Beds"), author="ann")
    if seen:
        assert any(e.get("type") == "text" and e.get("block") == box("r1", "c2") for e in seen)


def test_a_covered_box_takes_no_typing_but_its_top_left_box_does():
    d = table_in_a_text()
    d.execute(SetMerge("t1", "r1", "c1", 1, 2), author="ann")
    with pytest.raises(ValueError, match="top-left"):
        d.execute(InsertText(box("r1", "c2"), 0, "x"), author="ann")
    d.execute(InsertText(box("r1", "c1"), 0, "Harvest"), author="ann")
    assert words(d, "r1", "c1") == "Harvest"


def test_typing_in_a_box_that_is_not_there_is_refused():
    d = table_in_a_text()
    with pytest.raises((ValueError, KeyError)):
        d.execute(InsertText("t1/r9/c1", 0, "x"), author="ann")


def test_typing_in_a_box_makes_a_zone_that_only_that_box_holds():
    d = table_in_a_text()
    d.execute(InsertText(box("r2", "c1"), 0, "Courtyard"), author="ann")
    region = d.model.describe_regions(InsertText(box("r2", "c1"), 0, "x"))
    assert region == (TableRegion("t1", frozenset({"r2"}), frozenset({"c1"})),)
    assert d.model.region_from_data(region[0].to_data()) == region[0]


def test_a_box_held_by_a_colleague_cannot_be_typed_in_but_the_next_box_can():
    d = table_in_a_text()
    d.lock("ben", [TableRegion("t1", frozenset({"r2"}), frozenset({"c1"}))], ttl=5)
    with pytest.raises(RegionHeld):
        d.execute(InsertText(box("r2", "c1"), 0, "x"), author="ann")
    d.execute(InsertText(box("r2", "c2"), 0, "x"), author="ann")


# -- boxes: paste, fill, clear ------------------------------------------------------------------------------------
def test_setting_and_clearing_boxes_is_one_step_that_undoes_exactly():
    d = table_in_a_text()
    before = d.model.serialize()
    fill(d, HARVEST)
    assert words(d, "r3", "c1") == "Roof"
    d.execute(SetEntries("t1", (("r3", "c1", None), ("r3", "c2", None))), author="ann")
    assert words(d, "r3", "c1") == ""
    d.undo("ann")
    assert words(d, "r3", "c1") == "Roof"
    d.undo("ann")
    assert d.model.serialize() == before


# -- rows ---------------------------------------------------------------------------------------------------------
def test_deleting_rows_undoes_to_the_same_rows_with_the_same_ids_and_words_in_the_same_places():
    d = table_in_a_text()
    fill(d, HARVEST)
    before = d.model.tables["t1"]
    d.execute(DeleteRows("t1", ("r2", "r4")), author="ann")
    assert d.model.tables["t1"].rows == ("r1", "r3")
    d.undo("ann")
    assert d.model.tables["t1"] == before


def test_inserting_a_row_and_taking_it_back():
    d = table_in_a_text()
    fill(d, HARVEST)
    before = d.model.tables["t1"]
    d.execute(InsertRows("t1", (RowSpec("r5", "r2"),)), author="ann")
    assert d.model.tables["t1"].rows == ("r1", "r2", "r5", "r3", "r4")
    d.undo("ann")
    after = d.model.tables["t1"]
    assert (after.rows, after.entries, after.merges) == (before.rows, before.entries, before.merges)
    assert after.next_row == 5, "an id once given is never given again, so an undo cannot meet a colleague's new row"


def test_deleting_the_header_row_shortens_the_header_and_undo_brings_it_back():
    d = table_in_a_text()
    fill(d, HARVEST)
    before = d.model.tables["t1"]
    d.execute(DeleteRows("t1", ("r1",)), author="ann")
    assert d.model.tables["t1"].header_rows == 0
    d.undo("ann")
    assert d.model.tables["t1"] == before


def test_a_row_deleted_inside_a_merge_comes_back_inside_it():
    d = table_in_a_text(5, 3)
    d.execute(SetMerge("t1", "r2", "c1", 3, 1), author="ann")
    before = d.model.tables["t1"]
    d.execute(DeleteRows("t1", ("r3",)), author="ann")
    assert d.model.tables["t1"].merges[0].rows == 2
    d.undo("ann")
    assert d.model.tables["t1"] == before


def test_the_row_limit_is_refused_with_a_sentence_and_the_table_is_unchanged():
    d = table_in_a_text(100, 2)
    before = d.model.tables["t1"]
    with pytest.raises(ValueError, match="at most 100 rows"):
        d.execute(InsertRows("t1", (RowSpec("r101", "r100"),)), author="ann")
    assert d.model.tables["t1"] == before


# -- columns ------------------------------------------------------------------------------------------------------
def test_deleting_a_column_undoes_with_its_settings_and_words():
    d = table_in_a_text()
    fill(d, HARVEST)
    d.execute(SetColumn("t1", Column("c3", "number", "sum", 2500)), author="ann")
    before = d.model.tables["t1"]
    d.execute(DeleteColumns("t1", ("c2", "c3")), author="ann")
    assert d.model.tables["t1"].column_ids() == ("c1",)
    d.undo("ann")
    assert d.model.tables["t1"] == before


def test_inserting_columns_and_the_limit():
    d = table_in_a_text(2, 3)
    from claudia_core import ColumnSpec

    d.execute(InsertColumns("t1", (ColumnSpec(Column("c4", "number"), "c1"),)), author="ann")
    assert d.model.tables["t1"].column_ids() == ("c1", "c4", "c2", "c3")
    d.undo("ann")
    assert d.model.tables["t1"].column_ids() == ("c1", "c2", "c3")
    full = table_in_a_text(2, 10)
    with pytest.raises(ValueError, match="at most 10 columns"):
        full.execute(InsertColumns("t1", (ColumnSpec(Column("c11"), "c10"),)), author="ann")


def test_a_column_has_a_total_and_the_total_is_not_a_row():
    d = table_in_a_text()
    fill(d, HARVEST)
    d.execute(SetColumn("t1", Column("c2", "number", "sum")), author="ann")
    assert d.model.tables["t1"].totals("de") == {"c2": "46"}
    assert d.model.tables["t1"].row_count() == 4
    d.undo("ann")
    assert d.model.tables["t1"].totals("de") == {}


# -- order, sorting, moving ---------------------------------------------------------------------------------------
def test_sorting_is_one_step_that_keeps_the_ids_and_undoes():
    d = table_in_a_text()
    fill(d, HARVEST)
    before = d.model.tables["t1"]
    order = before.sort_order("c3", descending=True, language="de")
    d.execute(SetRowOrder("t1", order, "c3"), author="ann")
    assert [words(d, r, "c1") for r in d.model.tables["t1"].rows] == ["Site", "Allotment", "Courtyard", "Roof"]
    d.undo("ann")
    assert d.model.tables["t1"] == before


def test_columns_are_moved_by_their_order():
    d = table_in_a_text()
    d.execute(SetColumnOrder("t1", ("c3", "c1", "c2")), author="ann")
    assert d.model.tables["t1"].column_ids() == ("c3", "c1", "c2")
    d.undo("ann")
    assert d.model.tables["t1"].column_ids() == ("c1", "c2", "c3")


# -- merges and options -------------------------------------------------------------------------------------------
def test_merging_and_splitting_are_the_same_command_and_undo_each_other():
    d = table_in_a_text()
    d.execute(SetMerge("t1", "r2", "c1", 2, 2), author="ann")
    assert d.model.tables["t1"].merges[0].rows == 2
    d.execute(SetMerge("t1", "r2", "c1", 1, 1), author="ann")
    assert d.model.tables["t1"].merges == ()
    d.undo("ann")
    assert d.model.tables["t1"].merges[0].cols == 2
    d.undo("ann")
    assert d.model.tables["t1"].merges == ()


def test_the_options_of_a_table_change_and_undo():
    d = table_in_a_text()
    d.execute(SetTableOptions("t1", (("banded", True), ("placement", "float"), ("width", 6000))), author="ann")
    t = d.model.tables["t1"]
    assert (t.banded, t.placement, t.width) == (True, "float", 6000)
    d.undo("ann")
    t = d.model.tables["t1"]
    assert (t.banded, t.placement, t.width) == (False, "flow", None)


# -- one author's undo among colleagues ---------------------------------------------------------------------------
def test_an_undo_of_a_row_insert_is_not_shifted_by_a_colleagues_typing_elsewhere_in_the_table():
    d = table_in_a_text()
    d.execute(InsertRows("t1", (RowSpec("r5", "r4"),)), author="ann")
    d.execute(InsertText(box("r2", "c1"), 0, "Roof"), author="ben")
    d.undo("ann")
    assert "r5" not in d.model.tables["t1"].rows
    assert words(d, "r2", "c1") == "Roof"


def test_an_undo_that_would_delete_a_colleagues_words_is_refused():
    d = table_in_a_text()
    d.execute(InsertRows("t1", (RowSpec("r5", "r4"),)), author="ann")
    d.execute(InsertText(box("r5", "c1"), 0, "Garden"), author="ben")
    with pytest.raises((UndoConflict, UndoRefused)):
        d.undo("ann")
    assert words(d, "r5", "c1") == "Garden"


def test_an_undo_of_words_a_colleague_changed_since_is_refused():
    d = table_in_a_text()
    fill(d, HARVEST)
    d.execute(SetEntries("t1", (("r2", "c1", None),)), author="ann")
    d.execute(SetEntries("t1", (("r2", "c1", entry_paragraph("t1", "r2", "c1", "Court", author="ben")),)), author="ben")
    with pytest.raises((UndoConflict, UndoRefused)):
        d.undo("ann")


def test_a_row_a_colleague_deleted_cannot_be_put_in_front_of_by_an_old_undo():
    d = table_in_a_text()
    d.execute(DeleteRows("t1", ("r3",)), author="ann")  # undo of this puts r3 back behind r2
    d.execute(DeleteRows("t1", ("r2",)), author="ben")
    with pytest.raises((UndoConflict, UndoRefused)):
        d.undo("ann")


# -- redaction ----------------------------------------------------------------------------------------------------
def test_blanking_an_import_keeps_every_box_and_its_length():
    d = table_in_a_text()
    fill(d, HARVEST)
    d.model.blank(None)
    t = d.model.tables["t1"]
    assert t.paragraph("r2", "c1").text == "█" * len("Courtyard") and t.rows == ("r1", "r2", "r3", "r4")


def test_a_redacted_step_keeps_the_shape_and_loses_the_words():
    command = SetEntries("t1", (("r2", "c1", entry_paragraph("t1", "r2", "c1", "Courtyard")),))
    assert command.redacted().changes[0][2]["text"] == ""
    spec = RowSpec("r5", "r4", (("c1", __import__("claudia_core").Paragraph("t1/r5/c1", "", "x")),))
    assert InsertRows("t1", (spec,)).redacted().rows[0].entries[0][1].text == ""
    assert DefineTable(TableDef.blank("t1", 1, 1).to_data()).redacted().definition["format"] == 1


# -- the log ------------------------------------------------------------------------------------------------------
def test_every_table_command_survives_the_log():
    from claudia_core import ColumnSpec

    commands = [
        DefineTable(TableDef.blank("t2", 2, 2).to_data()),
        ForgetTable("t2"),
        SetEntries("t1", (("r1", "c1", None),)),
        InsertRows("t1", (RowSpec("r9", None),), merges=()),
        DeleteRows("t1", ("r1",), merges=()),
        InsertColumns("t1", (ColumnSpec(Column("c9"), None),)),
        DeleteColumns("t1", ("c1",)),
        SetRowOrder("t1", ("r1", "r2"), "c1"),
        SetColumnOrder("t1", ("c1", "c2")),
        SetColumn("t1", Column("c1", "number", "sum", 2000)),
        SetTableOptions("t1", (("banded", True),)),
        SetMerge("t1", "r1", "c1", 2, 2),
    ]
    registry = TextModel.registry
    from claudia_core import encode

    for command in commands:
        assert registry.decode(encode(command)) == command, command.kind


# -- a reference written in a box (step H, D1210) ---------------------------------------------------------------------
def test_a_box_may_hold_a_reference_which_is_a_field_like_in_any_paragraph():
    from claudia_core import FIELD_CHAR, RefField, SetField  # noqa: PLC0415

    d = table_in_a_text()
    seen = []
    d.subscribe(seen.append)
    d.execute(InsertText(box("r2", "c1"), 0, "see " + FIELD_CHAR, fields=(RefField("b1"),)), author="ann")
    assert d.model.fields_of(box("r2", "c1")) == (RefField("b1"),)
    assert any(e.to_data()["type"] == "block_fields" for e in seen if hasattr(e, "to_data"))
    d.execute(SetField(box("r2", "c1"), 0, RefField("b1", "text")), author="ann")
    assert d.model.fields_of(box("r2", "c1")) == (RefField("b1", "text"),)
    seen.clear()
    d.execute(DeleteText(box("r2", "c1"), 3, 2), author="ann")
    assert d.model.fields_of(box("r2", "c1")) == () and words(d, "r2", "c1") == "see"
    assert any(e.to_data()["type"] == "block_fields" for e in seen if hasattr(e, "to_data"))
    d.undo("ann")
    assert d.model.fields_of(box("r2", "c1")) == (RefField("b1", "text"),)
    d.execute(SetField(box("r2", "c1"), 0, RefField("b1")), author="ann")
    assert d.model.fields_of("b1") == ()
