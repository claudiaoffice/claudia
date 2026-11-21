"""Tables in docx (E9.32): what a docx table becomes in the text, and the other way round."""

from __future__ import annotations

from io import BytesIO

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_docx,
    docx_export_losses,
    docx_import_losses,
    docx_to_text,
    docx_unwritten_changes,
    odt_unwritten_changes,
    text_to_docx,
)
from claudia_composes_io._tables import put_tables
from docx import Document
from docx.oxml.ns import qn

from claudia_composes import Block, TextModel
from claudia_core import Column, Merge, Paragraph, TableDef, entry_id


def table(table_id: str = "t1", **options) -> TableDef:
    """Site / Beds / Harvest, two body rows, the last column a number column with a sum."""
    words = [["Site", "Beds", "Harvest"], ["Greenhouse", "12", "184.5"], ["North plot", "20", "231"]]
    blank = TableDef.blank(table_id, 3, 3, header_rows=1, **options)
    entries = [
        (f"r{r}", f"c{c}", Paragraph(entry_id(table_id, f"r{r}", f"c{c}"), "", text).written_by(None))
        for r, line in enumerate(words, 1)
        for c, text in enumerate(line, 1)
    ]
    definition = blank.with_entries(entries)
    columns = (Column("c1"), Column("c2", "number"), Column("c3", "number"))
    return TableDef(
        table_id,
        columns,
        definition.rows,
        definition.entries,
        header_rows=1,
        **{"look": "rules", **options},
    )


def text_with(*definitions: TableDef, language: str = "en") -> TextModel:
    model = TextModel([Block("b1", "body", "Before"), Block("b2", "body", "After")], language=language)
    put_tables(model, [("b1", len("Before"), definition) for definition in definitions])
    return model


def words_of(element) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in element.rows]


def tables_of(docx: bytes):
    return Document(BytesIO(docx)).tables


class TestWriting:
    def test_a_table_is_written_after_the_paragraph_it_hangs_from(self) -> None:
        docx = text_to_docx(text_with(table()))
        document = Document(BytesIO(docx))
        order = [child.tag.split("}")[1] for child in document.element.body.iterchildren()]
        assert order[:3] == ["p", "tbl", "p"]
        assert words_of(document.tables[0]) == [
            ["Site", "Beds", "Harvest"],
            ["Greenhouse", "12", "184.5"],
            ["North plot", "20", "231"],
        ]

    def test_the_header_row_repeats_and_the_cells_have_the_style_of_their_role(self) -> None:
        element = tables_of(text_to_docx(text_with(table())))[0]._tbl
        rows = list(element.iterchildren(qn("w:tr")))
        assert [row.find(qn("w:trPr") + "/" + qn("w:tblHeader")) is not None for row in rows] == [True, False, False]
        styles = [row.find(".//" + qn("w:pStyle")).get(qn("w:val")) for row in rows]
        assert styles[0] != styles[1]

    def test_the_rules_of_a_look_are_the_borders_of_its_cells(self) -> None:
        header = tables_of(text_to_docx(text_with(table())))[0].rows[0]._tr.find(".//" + qn("w:tcBorders"))
        assert header.find(qn("w:top")).get(qn("w:val")) == "single"
        assert header.find(qn("w:left")).get(qn("w:val")) == "nil"
        grid = tables_of(text_to_docx(text_with(table(look="grid"))))[0].rows[1]._tr.find(".//" + qn("w:tcBorders"))
        assert grid.find(qn("w:left")).get(qn("w:val")) == "single"

    def test_a_banded_row_is_shaded(self) -> None:
        element = tables_of(text_to_docx(text_with(table(banded=True))))[0]
        shaded = [row._tr.find(".//" + qn("w:shd")) is not None for row in element.rows]
        assert shaded == [False, False, True]

    def test_numbers_are_aligned_right_below_the_header(self) -> None:
        rows = tables_of(text_to_docx(text_with(table())))[0].rows
        aligned = [[cell.paragraphs[0].alignment is not None for cell in row.cells] for row in rows]
        assert aligned == [[False] * 3, [False, True, True], [False, True, True]]

    def test_a_total_is_written_as_the_words_it_is(self) -> None:
        withtotal = TableDef(
            "t1",
            (Column("c1"), Column("c2", "number", "sum"), Column("c3", "number")),
            table().rows,
            table().entries,
            header_rows=1,
        )
        rows = words_of(tables_of(text_to_docx(text_with(withtotal)))[0])
        assert rows[-1] == ["", "32", ""]

    def test_merged_cells_are_one_cell_that_spans(self) -> None:
        merged = TableDef.blank("t1", 3, 3, header_rows=0, merges=(Merge("r1", "c1", 2, 2), Merge("r3", "c1", 1, 3)))
        merged = merged.with_entries([("r1", "c1", Paragraph(entry_id("t1", "r1", "c1"), "", "big").written_by(None))])
        element = tables_of(text_to_docx(text_with(merged)))[0]._tbl
        rows = list(element.iterchildren(qn("w:tr")))
        assert [len(list(row.iterchildren(qn("w:tc")))) for row in rows] == [2, 2, 1]
        first = rows[0].find(qn("w:tc") + "/" + qn("w:tcPr"))
        assert first.find(qn("w:gridSpan")).get(qn("w:val")) == "2"
        assert first.find(qn("w:vMerge")).get(qn("w:val")) == "restart"
        below = rows[1].find(qn("w:tc") + "/" + qn("w:tcPr"))
        assert below.find(qn("w:vMerge")) is not None and below.find(qn("w:vMerge")).get(qn("w:val")) is None

    def test_a_width_the_text_set_is_the_tables_width(self) -> None:
        element = tables_of(text_to_docx(text_with(table(width=5000))))[0]._tbl
        size = element.find(qn("w:tblPr") + "/" + qn("w:tblW"))
        assert (size.get(qn("w:type")), size.get(qn("w:w"))) == ("pct", "2500")

    def test_two_tables_on_one_paragraph_do_not_become_one(self) -> None:
        document = Document(BytesIO(text_to_docx(text_with(table("t1"), table("t2")))))
        order = [child.tag.split("}")[1] for child in document.element.body.iterchildren()]
        assert order[:5] == ["p", "tbl", "p", "tbl", "p"]

    def test_a_table_is_no_loss_of_an_export(self) -> None:
        assert not any(loss.kind == "table" for loss in docx_export_losses(text_with(table())))


class TestReading:
    def test_the_tables_of_a_written_file_come_back_as_they_were(self) -> None:
        back = docx_to_text(text_to_docx(text_with(table(banded=True, look="grid", width=6000))))
        (found,) = back.tables.values()
        original = table()
        assert [[found.paragraph(r, c).text for c in found.column_ids()] for r in found.rows] == [
            [original.paragraph(r, c).text for c in original.column_ids()] for r in original.rows
        ]
        assert found.header_rows == 1
        assert [column.kind for column in found.columns] == ["text", "number", "number"]
        assert found.width == 6000
        (obj,) = [o for o in back.objects.values() if o.body.kind == "table"]
        assert (obj.anchor.block, obj.body.ref) == ("b1", found.id)

    def test_the_merges_of_a_written_file_come_back(self) -> None:
        merged = TableDef.blank("t1", 3, 3, header_rows=0, merges=(Merge("r1", "c1", 2, 2), Merge("r3", "c1", 1, 3)))
        merged = merged.with_entries([("r1", "c1", Paragraph(entry_id("t1", "r1", "c1"), "", "big").written_by(None))])
        (found,) = docx_to_text(text_to_docx(text_with(merged))).tables.values()
        assert found.merges == merged.merges
        assert found.paragraph("r1", "c1").text == "big"

    def test_a_table_of_word_is_read(self) -> None:
        document = Document()
        document.add_paragraph("Intro")
        word = document.add_table(rows=3, cols=2)
        for r, line in enumerate([["Name", "Qty"], ["Nails", "1,200"], ["Screws", "300"]]):
            for c, text in enumerate(line):
                word.cell(r, c).text = text
        word.cell(1, 0).merge(word.cell(2, 0)).text = "Nails"
        word.rows[0]._tr.get_or_add_trPr().append(word.rows[0]._tr.makeelement(qn("w:tblHeader"), {}))
        out = BytesIO()
        document.save(out)
        model = docx_to_text(out.getvalue())
        (found,) = model.tables.values()
        assert found.header_rows == 1 and found.merges == (Merge("r2", "c1", 2, 1),)
        assert found.paragraph("r2", "c1").text == "Nails"
        assert [c.kind for c in found.columns] == ["text", "number"]
        assert not any(loss.kind == "table" for loss in docx_import_losses(out.getvalue()))


class TestWhatStaysInTheFile:
    def build(self, fill) -> bytes:
        document = Document()
        document.add_paragraph("Intro")
        fill(document)
        out = BytesIO()
        document.save(out)
        return out.getvalue()

    def lost(self, data: bytes) -> int:
        return sum(loss.count for loss in docx_import_losses(data) if loss.kind == "table")

    def test_a_table_in_a_cell_is_not_a_table_of_the_text(self) -> None:
        def fill(document) -> None:
            outer = document.add_table(rows=1, cols=1)
            outer.cell(0, 0).add_table(rows=1, cols=1)

        data = self.build(fill)
        assert docx_to_text(data).tables == {} and self.lost(data) == 2

    def test_a_cell_of_two_paragraphs_is_not_a_table_of_the_text(self) -> None:
        def fill(document) -> None:
            two = document.add_table(rows=1, cols=2)
            two.cell(0, 0).text = "a"
            two.cell(0, 0).add_paragraph("b")

        data = self.build(fill)
        assert docx_to_text(data).tables == {} and self.lost(data) == 1

    def test_a_table_before_the_first_paragraph_is_not_a_table_of_the_text(self) -> None:
        document = Document()
        document.add_table(rows=1, cols=1).cell(0, 0).text = "x"
        document.add_paragraph("after")
        out = BytesIO()
        document.save(out)
        assert docx_to_text(out.getvalue()).tables == {} and self.lost(out.getvalue()) == 1

    def test_a_table_of_eleven_columns_is_not_a_table_of_the_text(self) -> None:
        data = self.build(lambda document: document.add_table(rows=1, cols=11))
        assert docx_to_text(data).tables == {} and self.lost(data) == 1

    def test_a_cell_with_a_picture_is_not_a_table_of_the_text(self) -> None:
        def fill(document) -> None:
            cell = document.add_table(rows=1, cols=1).cell(0, 0)
            run = cell.paragraphs[0].add_run()
            run._r.append(run._r.makeelement(qn("w:drawing"), {}))

        assert docx_to_text(self.build(fill)).tables == {}


class TestEditsToAKeptFile:
    def original(self) -> bytes:
        return text_to_docx(text_with(table()))

    def test_a_table_nobody_changed_stays_as_it_is(self) -> None:
        data = self.original()
        baseline, current = docx_to_text(data), docx_to_text(data)
        assert apply_edits_to_docx(data, baseline, current) == data

    def test_a_table_whose_words_changed_is_written_in_place_and_the_rest_stays(self) -> None:
        data = self.original()
        baseline, current = docx_to_text(data), docx_to_text(data)
        (definition,) = current.tables.values()
        current.tables.put(
            definition.with_entries(
                [("r2", "c1", Paragraph(entry_id(definition.id, "r2", "c1"), "", "Cold frame").written_by(None))]
            )
        )
        patched = apply_edits_to_docx(data, baseline, current)
        (found,) = Document(BytesIO(patched)).tables
        assert words_of(found)[1] == ["Cold frame", "12", "184.5"]
        assert [p.text for p in Document(BytesIO(patched)).paragraphs] == ["Before", "After"]

    def test_a_table_that_was_removed_goes_out_of_the_file(self) -> None:
        data = self.original()
        baseline, current = docx_to_text(data), docx_to_text(data)
        (obj,) = [o for o in current.objects.values() if o.body.kind == "table"]
        current.delete_object(obj.id)
        current.tables.forget(obj.body.ref)
        assert Document(BytesIO(apply_edits_to_docx(data, baseline, current))).tables == []

    def test_a_table_that_was_added_is_put_after_its_paragraph(self) -> None:
        document = Document()
        document.add_paragraph("one")
        document.add_paragraph("two")
        out = BytesIO()
        document.save(out)
        data = out.getvalue()
        baseline, current = docx_to_text(data), docx_to_text(data)
        put_tables(current, [("b1", 3, table("tnew"))])
        patched = Document(BytesIO(apply_edits_to_docx(data, baseline, current)))
        order = [child.tag.split("}")[1] for child in patched.element.body.iterchildren()]
        assert order[:3] == ["p", "tbl", "p"]
        assert words_of(patched.tables[0])[0] == ["Site", "Beds", "Harvest"]
        names = {style.style_id for style in patched.styles}
        used = {p.get(qn("w:val")) for p in patched.element.body.iter(qn("w:pStyle"))}
        assert used <= names


class TestWhatIsWritten:
    def test_a_table_is_not_among_the_changes_a_file_cannot_hold(self) -> None:
        model = text_with(table())
        for changes in (docx_unwritten_changes(model), odt_unwritten_changes(model)):
            assert [loss.detail for loss in changes] == []

    def test_a_table_that_changed_after_the_import_is_not_one_either(self) -> None:
        baseline = docx_to_text(text_to_docx(text_with(table())))
        current = docx_to_text(text_to_docx(text_with(table())))
        (definition,) = current.tables.values()
        current.tables.put(
            definition.with_entries(
                [("r2", "c1", Paragraph(entry_id(definition.id, "r2", "c1"), "", "Cold frame").written_by(None))]
            )
        )
        assert docx_unwritten_changes(current, baseline) == ()
        assert odt_unwritten_changes(current, baseline) == ()


def raw(mutate) -> bytes:
    """A file with a table of 2 rows and 3 columns that ``mutate(w:tbl)`` changes."""
    document = Document()
    document.add_paragraph("Intro")
    word = document.add_table(rows=2, cols=3)
    for r in range(2):
        for c in range(3):
            word.cell(r, c).text = f"{r}{c}"
    mutate(word._tbl)
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def tc(table, row: int, column: int):
    return list(list(table.iterchildren(qn("w:tr")))[row].iterchildren(qn("w:tc")))[column]


def properties(cell):
    found = cell.find(qn("w:tcPr"))
    return found if found is not None else cell.insert(0, cell.makeelement(qn("w:tcPr"), {})) or cell.find(qn("w:tcPr"))


class TestOddFiles:
    """Tables as other programs write them, and tables that are more than the text holds."""

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda t: t.find(qn("w:tblPr")).append(t.makeelement(qn("w:tblCellSpacing"), {})),
            lambda t: list(t.iterchildren(qn("w:tr")))[0].insert(0, t.makeelement(qn("w:trPr"), {}))
            or list(t.iterchildren(qn("w:tr")))[0].find(qn("w:trPr")).append(t.makeelement(qn("w:gridAfter"), {})),
            lambda t: [t.remove(row) for row in list(t.iterchildren(qn("w:tr")))],
            lambda t: list(t.iterchildren(qn("w:tr")))[1].remove(tc(t, 1, 2)),
            lambda t: properties(tc(t, 0, 0)).append(t.makeelement(qn("w:vMerge"), {})),
            lambda t: properties(tc(t, 0, 0)).append(
                t.makeelement(qn("w:gridSpan"), {qn("w:val"): "x"}),
            ),
        ],
        ids=["cell spacing", "a short row", "no rows", "a ragged row", "a continuation of nothing", "a span of x"],
    )
    def test_what_is_more_than_the_text_holds_stays_in_the_file(self, mutate) -> None:
        data = raw(mutate)
        assert docx_to_text(data).tables == {}
        assert sum(loss.count for loss in docx_import_losses(data) if loss.kind == "table") == 1

    def test_a_continuation_of_another_width_is_not_regular(self) -> None:
        def mutate(t) -> None:
            first = properties(tc(t, 0, 0))
            first.append(first.makeelement(qn("w:vMerge"), {qn("w:val"): "restart"}))
            second = properties(tc(t, 1, 0))
            second.append(second.makeelement(qn("w:gridSpan"), {qn("w:val"): "2"}))
            second.append(second.makeelement(qn("w:vMerge"), {}))
            t.findall(qn("w:tr"))[1].remove(tc(t, 1, 1))

        assert docx_to_text(raw(mutate)).tables == {}

    def test_tabs_breaks_and_links_are_words_as_spaces(self) -> None:
        def mutate(t) -> None:
            cell = tc(t, 0, 0)
            paragraph = cell.find(qn("w:p"))
            for run in list(paragraph):
                paragraph.remove(run)
            run = paragraph.makeelement(qn("w:r"), {})
            paragraph.append(run)
            for tag, text in (("w:t", "a"), ("w:tab", None), ("w:t", "b"), ("w:br", None)):
                part = run.makeelement(qn(tag), {})
                part.text = text
                run.append(part)
            link = paragraph.makeelement(qn("w:hyperlink"), {})
            inner = link.makeelement(qn("w:r"), {})
            word = inner.makeelement(qn("w:t"), {})
            word.text = "c"
            inner.append(word)
            link.append(inner)
            paragraph.append(link)

        (found,) = docx_to_text(raw(mutate)).tables.values()
        assert found.paragraph("r1", "c1").text == "a b c"

    def test_the_widths_a_file_gives_are_read_as_it_gives_them(self) -> None:
        def gridless(t) -> None:
            t.remove(t.find(qn("w:tblGrid")))

        def broken(t) -> None:
            t.find(qn("w:tblGrid")).find(qn("w:gridCol")).set(qn("w:w"), "x")
            t.find(qn("w:tblPr")).append(t.makeelement(qn("w:tblW"), {qn("w:w"): "x", qn("w:type"): "dxa"}))

        def absolute(t) -> None:
            for column, width in zip(t.find(qn("w:tblGrid")), (1000, 2000, 3000), strict=True):
                column.set(qn("w:w"), str(width))
            size = t.find(qn("w:tblPr")).find(qn("w:tblW"))
            if size is None:
                size = t.makeelement(qn("w:tblW"), {})
                t.find(qn("w:tblPr")).append(size)
            size.set(qn("w:w"), "4536")
            size.set(qn("w:type"), "dxa")

        (found,) = docx_to_text(raw(gridless)).tables.values()
        assert all(column.width is None for column in found.columns) and found.width is None
        (found,) = docx_to_text(raw(broken)).tables.values()
        assert all(column.width is None for column in found.columns) and found.width is None
        (found,) = docx_to_text(raw(absolute)).tables.values()
        assert [column.width for column in found.columns] == [1667, 3333, 5000]
        assert found.width is not None and abs(found.width - 5000) <= 1  # (half the text of an A4 page)

    def test_a_table_that_is_not_regular_stays_with_its_paragraph_when_the_others_change(self) -> None:
        document = Document()
        document.add_paragraph("one")
        document.add_table(rows=1, cols=1).cell(0, 0).add_table(rows=1, cols=1)
        document.add_paragraph("two")
        out = BytesIO()
        document.save(out)
        data = out.getvalue()
        baseline, current = docx_to_text(data), docx_to_text(data)
        put_tables(current, [("b2", 3, table("tnew"))])
        patched = Document(BytesIO(apply_edits_to_docx(data, baseline, current)))
        order = [child.tag.split("}")[1] for child in patched.element.body.iterchildren()]
        assert order[:4] == ["p", "tbl", "p", "tbl"]

    def test_edits_measured_from_another_text_are_refused(self) -> None:
        data = text_to_docx(text_with(table()))
        baseline, current = docx_to_text(data), docx_to_text(data)
        baseline.tables.put(
            baseline.tables["t1"].with_entries(
                [("r2", "c1", Paragraph(entry_id("t1", "r2", "c1"), "", "other").written_by(None))]
            )
        )
        with pytest.raises(UnsupportedEdit):
            apply_edits_to_docx(data, baseline, current)

    def test_two_tables_added_to_one_paragraph_are_kept_apart(self) -> None:
        document = Document()
        document.add_paragraph("one")
        out = BytesIO()
        document.save(out)
        data = out.getvalue()
        baseline, current = docx_to_text(data), docx_to_text(data)
        put_tables(current, [("b1", 3, table("ta")), ("b1", 3, table("tb"))])
        patched = Document(BytesIO(apply_edits_to_docx(data, baseline, current)))
        order = [child.tag.split("}")[1] for child in patched.element.body.iterchildren()]
        assert order[:4] == ["p", "tbl", "p", "tbl"]
