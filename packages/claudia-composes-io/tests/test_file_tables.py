"""The part of the table converters that knows no format (E9.32): what a regular table is, and the grid to write."""

from __future__ import annotations

from claudia_composes_io._tables import (
    FileCell,
    FileTable,
    cell_look,
    column_shares,
    read_table,
    table_styles,
    write_grid,
)

from claudia_composes import TextModel
from claudia_core import Column, Merge, Paragraph, TableDef, entry_id


def cells(*lines: str, header: int = 0, **options) -> FileTable:
    return FileTable(tuple(tuple(FileCell(word) for word in line.split("|")) for line in lines), header, **options)


def words(definition: TableDef) -> list[list[str]]:
    return [[definition.paragraph(r, c).text for c in definition.column_ids()] for r in definition.rows]


class TestReading:
    def test_a_grid_of_words_is_a_table_with_ids_and_a_header(self) -> None:
        found = read_table(cells("Site|Beds", "Greenhouse|12", "North plot|20", header=1), "t1")
        assert found is not None
        assert (found.rows, found.column_ids(), found.header_rows) == (("r1", "r2", "r3"), ("c1", "c2"), 1)
        assert words(found) == [["Site", "Beds"], ["Greenhouse", "12"], ["North plot", "20"]]
        assert found.paragraph("r2", "c1").id == entry_id("t1", "r2", "c1")

    def test_a_column_of_numbers_in_the_documents_language_is_a_number_column(self) -> None:
        english = read_table(cells("a|n", "x|1,234.5", "y|7", header=1), "t1", "en")
        german = read_table(cells("a|n", "x|1.234,5", "y|7", header=1), "t1", "de")
        assert [c.kind for c in english.columns] == ["text", "number"]  # type: ignore[union-attr]
        assert [c.kind for c in german.columns] == ["text", "number"]  # type: ignore[union-attr]
        wrong = read_table(cells("a|n", "x|1.234,5", "y|7", header=1), "t1", "en")
        assert [c.kind for c in wrong.columns] == ["text", "text"]  # type: ignore[union-attr]

    def test_a_column_with_a_word_in_it_or_with_nothing_is_text(self) -> None:
        found = read_table(cells("n|m", "1|", "x|", header=0), "t1")
        assert [c.kind for c in found.columns] == ["text", "text"]  # type: ignore[union-attr]

    def test_the_words_of_a_cell_are_one_line_without_fields(self) -> None:
        found = read_table(cells("one \n two  three￼|x"), "t1")
        assert found is not None and found.paragraph("r1", "c1").text == "one two three"

    def test_widths_are_shares_of_the_table_and_add_up(self) -> None:
        found = read_table(cells("a|b|c", widths=(1000, 1000, 2000), width=6000), "t1")
        assert found is not None
        assert [c.width for c in found.columns] == [2500, 2500, 5000]
        assert found.width == 6000
        thirds = read_table(cells("a|b|c", widths=(1, 1, 1)), "t1")
        assert thirds is not None and sum(c.width or 0 for c in thirds.columns) == 10_000

    def test_a_width_that_makes_no_sense_is_left_to_the_text(self) -> None:
        found = read_table(cells("a|b", widths=(0, 5), width=50), "t1")
        assert found is not None and found.width is None and [c.width for c in found.columns] == [None, None]

    def test_merges_are_rectangles_and_the_words_of_the_covered_boxes_join_the_first(self) -> None:
        grid = FileTable(
            (
                (FileCell("A", cols=2), FileCell("", covered=True), FileCell("c")),
                (FileCell("d", rows=2), FileCell("e"), FileCell("f")),
                (FileCell("", covered=True), FileCell("g"), FileCell("h")),
            )
        )
        found = read_table(grid, "t1")
        assert found is not None
        assert found.merges == (Merge("r1", "c1", 1, 2), Merge("r2", "c1", 2, 1))
        joined = FileTable(((FileCell("A", cols=2), FileCell("B", covered=True)),))
        merged = read_table(joined, "t1")
        assert merged is not None and merged.paragraph("r1", "c1").text == "A B"

    def test_a_merge_that_does_not_fit_is_not_a_regular_table(self) -> None:
        outside = FileTable(((FileCell("a"), FileCell("b", cols=2)),))
        unmarked = FileTable(((FileCell("a", cols=2), FileCell("b")),))
        crossing = FileTable(
            (
                (FileCell("a", cols=2), FileCell("", covered=True)),
                (FileCell("b", rows=2, cols=2), FileCell("", covered=True)),
            )
        )
        assert [read_table(each, "t1") for each in (outside, unmarked, crossing)] == [None, None, None]

    def test_the_limits_of_a_table_of_a_text_are_kept(self) -> None:
        assert read_table(FileTable(()), "t1") is None
        assert read_table(cells(*(["x"] * 101)), "t1") is None
        assert read_table(cells("|".join(["x"] * 11)), "t1") is None
        assert read_table(cells(*(["x"] * 100)), "t1") is not None
        assert read_table(cells("|".join(["x"] * 10)), "t1") is not None
        ragged = FileTable(((FileCell("a"), FileCell("b")), (FileCell("c"),)))
        assert read_table(ragged, "t1") is None
        assert read_table(cells("a", header=2), "t1") is None


class TestWriting:
    def definition(self) -> TableDef:
        blank = TableDef.blank("t1", 3, 2, header_rows=1, look="grid", banded=True)
        words_ = {
            ("r1", "c1"): "Site",
            ("r1", "c2"): "Beds",
            ("r2", "c1"): "North",
            ("r2", "c2"): "12",
            ("r3", "c2"): "8",
        }
        entries = [
            (r, c, Paragraph(entry_id("t1", r, c), "", text).written_by(None)) for (r, c), text in words_.items()
        ]
        return blank.with_entries(entries)

    def test_every_cell_has_the_style_of_its_role_in_the_look(self) -> None:
        grid = write_grid(self.definition())
        assert [[cell.style for cell in line] for line in grid] == [
            ["table-grid-header"] * 2,
            ["table-grid-body"] * 2,
            ["table-grid-band"] * 2,
        ]
        assert grid[1][0].text == "North"

    def test_a_box_with_a_style_of_its_own_keeps_it(self) -> None:
        own = self.definition().with_entries(
            [("r2", "c1", Paragraph(entry_id("t1", "r2", "c1"), "quote", "North").written_by(None))]
        )
        assert write_grid(own)[1][0].style == "quote"

    def test_the_total_row_is_written_as_the_words_the_total_is(self) -> None:
        columns = (Column("c1"), Column("c2", "number", "sum"))
        total = TableDef("t1", columns, ("r1", "r2", "r3"), self.definition().entries, header_rows=1, look="rules")
        grid = write_grid(total, "en")
        assert [cell.text for cell in grid[-1]] == ["", "20"]
        assert grid[-1][1].role == "total" and grid[-1][1].number

    def test_a_merge_is_the_first_box_with_a_span_and_the_rest_covered(self) -> None:
        merged = TableDef.blank("t1", 2, 2, header_rows=0, merges=(Merge("r1", "c1", 2, 2),))
        grid = write_grid(merged)
        assert (grid[0][0].cols, grid[0][0].rows, grid[0][0].covered) == (2, 2, False)
        assert [cell.covered for line in grid for cell in line] == [False, True, True, True]

    def test_number_columns_are_aligned_right_except_in_the_header(self) -> None:
        number = TableDef("t1", (Column("c1", "number"),), ("r1", "r2"), {}, header_rows=1)
        assert [line[0].number for line in write_grid(number)] == [False, True]

    def test_unset_widths_share_what_the_set_ones_leave(self) -> None:
        definition = TableDef("t1", (Column("c1", width=4000), Column("c2"), Column("c3")), ("r1",), {})
        assert column_shares(definition) == [4000, 3000, 3000]


def test_a_look_gives_the_fill_and_the_lines_of_a_cell() -> None:
    model = TextModel(None)
    header, body, band = (cell_look(model, f"table-rules-{role}") for role in ("header", "body", "band"))
    assert header.fill is None and header.sides[0] is not None and header.sides[2] is not None
    assert header.sides[1] is None and header.sides[3] is None
    assert header.sides[0][1] > header.sides[2][1]  # the heavy rule above, the thin one under
    assert body.sides == (None, None, None, None)
    assert band.fill is not None
    assert cell_look(model, "table-grid-body").sides.count(None) == 0
    assert cell_look(model, "no-such-style").fill is None


class TestWhatTheStylesAre:
    def test_the_styles_a_table_is_written_with_are_those_of_its_roles_and_its_boxes(self) -> None:
        found = read_table(cells("a|b", "1|2", header=1), "t1")
        assert table_styles(found) == {"table-rules-header", "table-rules-body"}  # type: ignore[arg-type]
        own = found.with_entries([("r2", "c1", Paragraph(entry_id("t1", "r2", "c1"), "mine", "x").written_by(None))])  # type: ignore[union-attr]
        assert "mine" in table_styles(own)

    def test_a_column_with_a_total_adds_the_style_of_the_total(self) -> None:
        found = read_table(cells("a|b", "1|2", header=1), "t1")
        total = TableDef(
            "t1",
            (found.columns[0], Column("c2", "number", "sum")),  # type: ignore[union-attr]
            found.rows,  # type: ignore[union-attr]
            found.entries,  # type: ignore[union-attr]
            header_rows=1,
        )
        assert "table-rules-total" in table_styles(total)
