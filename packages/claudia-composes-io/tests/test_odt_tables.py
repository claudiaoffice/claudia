"""Tables in odt (E9.32): what a ``table:table`` becomes in the text, and the other way round."""

from __future__ import annotations

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_odt,
    odt_export_losses,
    odt_import_losses,
    odt_to_text,
    text_to_odt,
)
from claudia_composes_io._tables import put_tables
from lxml import etree

from claudia_composes import Block, TextModel
from claudia_core import Column, Merge, Paragraph, TableDef, entry_id
from claudia_odf_io import NS, problems
from claudia_opc_io import read_parts


def table(table_id: str = "t1", **options) -> TableDef:
    """Site / Beds / Harvest, two body rows; the last two columns are number columns."""
    words = [["Site", "Beds", "Harvest"], ["Greenhouse", "12", "184.5"], ["North plot", "20", "231"]]
    blank = TableDef.blank(table_id, 3, 3, header_rows=1)
    entries = [
        (f"r{r}", f"c{c}", Paragraph(entry_id(table_id, f"r{r}", f"c{c}"), "", text).written_by(None))
        for r, line in enumerate(words, 1)
        for c, text in enumerate(line, 1)
    ]
    filled = blank.with_entries(entries)
    return TableDef(
        table_id,
        (Column("c1"), Column("c2", "number"), Column("c3", "number")),
        filled.rows,
        filled.entries,
        header_rows=1,
        **{"look": "rules", **options},
    )


def text_with(*definitions: TableDef) -> TextModel:
    model = TextModel([Block("b1", "body", "Before"), Block("b2", "body", "After")])
    put_tables(model, [("b1", len("Before"), definition) for definition in definitions])
    return model


def content(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["content.xml"])


def q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def words_of(element: etree._Element) -> list[list[str]]:
    return [
        [
            "".join(cell.itertext())
            for cell in row
            if cell.tag in (q("table", "table-cell"), q("table", "covered-table-cell"))
        ]
        for row in element.iter(q("table", "table-row"))
    ]


class TestWriting:
    def test_a_table_is_written_after_the_paragraph_it_hangs_from(self) -> None:
        data = text_to_odt(text_with(table()))
        assert problems(data) == []
        text = content(data).find("office:body/office:text", NS)
        assert [etree.QName(child).localname for child in text] == ["p", "table", "p"]
        assert words_of(text.find("table:table", NS)) == [
            ["Site", "Beds", "Harvest"],
            ["Greenhouse", "12", "184.5"],
            ["North plot", "20", "231"],
        ]

    def test_the_header_rows_are_header_rows(self) -> None:
        element = content(text_to_odt(text_with(table()))).find(".//table:table", NS)
        header = element.find("table:table-header-rows", NS)
        assert header is not None and len(header) == 1
        assert len(element.findall("table:table-row", NS)) == 2

    def test_the_look_is_the_borders_of_the_cells_and_the_words_have_the_style_of_their_role(self) -> None:
        root = content(text_to_odt(text_with(table(look="grid", banded=True))))
        cell = root.find(".//table:table-cell", NS)
        style = next(
            s for s in root.iter(q("style", "style")) if s.get(q("style", "name")) == cell.get(q("table", "style-name"))
        )
        properties = style.find("style:table-cell-properties", NS)
        assert properties.get(q("fo", "border-left")).startswith("0.75pt solid #")
        assert properties.get(q("fo", "background-color")) is not None
        assert cell.find("text:p", NS).get(q("text", "style-name")) == "Table_20_grid_20_header"

    def test_numbers_are_aligned_right_below_the_header(self) -> None:
        root = content(text_to_odt(text_with(table())))
        body = root.find(".//table:table/table:table-row", NS)
        names = [p.get(q("text", "style-name")) for p in body.iterfind("table:table-cell/text:p", NS)]
        automatic = {
            s.get(q("style", "name")): s.find("style:paragraph-properties", NS)
            for s in root.find("office:automatic-styles", NS).iter(q("style", "style"))
        }
        aligned = [
            name in automatic and automatic[name] is not None and automatic[name].get(q("fo", "text-align")) == "end"
            for name in names
        ]
        assert aligned == [False, True, True]

    def test_merged_cells_span_and_cover(self) -> None:
        merged = TableDef.blank("t1", 3, 3, header_rows=0, merges=(Merge("r1", "c1", 2, 2), Merge("r3", "c1", 1, 3)))
        merged = merged.with_entries([("r1", "c1", Paragraph(entry_id("t1", "r1", "c1"), "", "big").written_by(None))])
        element = content(text_to_odt(text_with(merged))).find(".//table:table", NS)
        rows = element.findall("table:table-row", NS)
        first = rows[0].find("table:table-cell", NS)
        assert (first.get(q("table", "number-columns-spanned")), first.get(q("table", "number-rows-spanned"))) == (
            "2",
            "2",
        )
        assert [etree.QName(c).localname for c in rows[0]] == ["table-cell", "covered-table-cell", "table-cell"]
        assert [etree.QName(c).localname for c in rows[1]] == ["covered-table-cell", "covered-table-cell", "table-cell"]
        assert [etree.QName(c).localname for c in rows[2]] == ["table-cell", "covered-table-cell", "covered-table-cell"]

    def test_the_width_of_a_table_is_its_relative_width(self) -> None:
        root = content(text_to_odt(text_with(table(width=5000))))
        element = root.find(".//table:table", NS)
        style = next(
            s
            for s in root.iter(q("style", "style"))
            if s.get(q("style", "name")) == element.get(q("table", "style-name"))
        )
        assert style.find("style:table-properties", NS).get(q("style", "rel-width")) == "50%"

    def test_two_tables_on_one_paragraph_do_not_touch(self) -> None:
        text = content(text_to_odt(text_with(table("t1"), table("t2")))).find("office:body/office:text", NS)
        assert [etree.QName(child).localname for child in text][:5] == ["p", "table", "p", "table", "p"]

    def test_a_table_is_no_loss_of_an_export(self) -> None:
        assert not any(loss.kind == "table" for loss in odt_export_losses(text_with(table())))


class TestReading:
    def test_the_tables_of_a_written_file_come_back_as_they_were(self) -> None:
        back = odt_to_text(text_to_odt(text_with(table(width=6000))))
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
        (found,) = odt_to_text(text_to_odt(text_with(merged))).tables.values()
        assert found.merges == merged.merges
        assert found.paragraph("r1", "c1").text == "big"

    def test_the_column_widths_of_a_file_are_kept(self) -> None:
        wide = TableDef(
            "t1",
            (Column("c1", width=2000), Column("c2", "number", width=3000), Column("c3", "number", width=5000)),
            table().rows,
            table().entries,
            header_rows=1,
        )
        (found,) = odt_to_text(text_to_odt(text_with(wide))).tables.values()
        assert [c.width for c in found.columns] == [2000, 3000, 5000]

    def test_no_loss_when_the_text_holds_the_table(self) -> None:
        assert not any(loss.kind == "table" for loss in odt_import_losses(text_to_odt(text_with(table()))))


class TestWhatStaysInTheFile:
    def odt(self, mutate) -> bytes:
        """A file written from the text, with its table changed by ``mutate(root)``."""
        data = text_to_odt(text_with(table()))
        parts = read_parts(data)
        root = etree.fromstring(parts["content.xml"])
        mutate(root)
        parts["content.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
        from claudia_opc_io import write_parts

        return write_parts(parts)

    def lost(self, data: bytes) -> int:
        return sum(loss.count for loss in odt_import_losses(data) if loss.kind == "table")

    def test_a_table_in_a_cell_is_not_a_table_of_the_text(self) -> None:
        def mutate(root) -> None:
            cell = root.find(".//table:table-cell", NS)
            inner = etree.SubElement(cell, q("table", "table"))
            etree.SubElement(inner, q("table", "table-column"))

        data = self.odt(mutate)
        assert odt_to_text(data).tables == {} and self.lost(data) == 2

    def test_a_cell_of_two_paragraphs_is_not_a_table_of_the_text(self) -> None:
        def mutate(root) -> None:
            cell = root.find(".//table:table-cell", NS)
            etree.SubElement(cell, q("text", "p")).text = "second"

        data = self.odt(mutate)
        assert odt_to_text(data).tables == {} and self.lost(data) == 1

    def test_a_cell_with_a_formula_is_not_a_table_of_the_text(self) -> None:
        def mutate(root) -> None:
            root.find(".//table:table-cell", NS).set(q("table", "formula"), "of:=1+1")

        assert odt_to_text(self.odt(mutate)).tables == {}

    def test_a_row_group_is_not_a_table_of_the_text(self) -> None:
        def mutate(root) -> None:
            element = root.find(".//table:table", NS)
            group = etree.Element(q("table", "table-row-group"))
            for row in element.findall("table:table-row", NS):
                group.append(row)
            element.append(group)

        assert odt_to_text(self.odt(mutate)).tables == {}

    def test_repeated_rows_and_columns_are_expanded(self) -> None:
        def mutate(root) -> None:
            element = root.find(".//table:table", NS)
            rows = element.findall("table:table-row", NS)
            rows[1].set(q("table", "number-rows-repeated"), "2")
            element.remove(rows[0])

        (found,) = odt_to_text(self.odt(mutate)).tables.values()
        assert len(found.rows) == 3  # the header and the one body row that is repeated twice

    def test_a_table_before_the_first_paragraph_is_not_a_table_of_the_text(self) -> None:
        def mutate(root) -> None:
            text = root.find("office:body/office:text", NS)
            element = text.find("table:table", NS)
            text.remove(element)
            text.insert(0, element)

        data = self.odt(mutate)
        assert odt_to_text(data).tables == {} and self.lost(data) == 1


class TestEditsToAKeptFile:
    def original(self) -> bytes:
        return text_to_odt(text_with(table()))

    def test_a_table_nobody_changed_stays_as_it_is(self) -> None:
        data = self.original()
        baseline, current = odt_to_text(data), odt_to_text(data)
        assert apply_edits_to_odt(data, baseline, current) == data

    def test_a_paragraph_edit_keeps_the_table_of_the_file(self) -> None:
        data = self.original()
        baseline = odt_to_text(data)
        current = odt_to_text(data)
        first = current.blocks[0]
        current.blocks[0] = Block(first.id, first.style, "Edited")
        patched = apply_edits_to_odt(data, baseline, current)
        text = content(patched).find("office:body/office:text", NS)
        assert [etree.QName(child).localname for child in text] == ["p", "table", "p"]
        assert text.find("text:p", NS).text == "Edited"

    def test_a_table_that_changed_makes_the_file_be_written_anew(self) -> None:
        data = self.original()
        baseline, current = odt_to_text(data), odt_to_text(data)
        (definition,) = current.tables.values()
        current.tables.put(
            definition.with_entries(
                [("r2", "c1", Paragraph(entry_id(definition.id, "r2", "c1"), "", "Cold frame").written_by(None))]
            )
        )
        with pytest.raises(UnsupportedEdit):
            apply_edits_to_odt(data, baseline, current)


class TestOddFiles:
    """Tables as other programs write them, and tables that are more than the text holds."""

    def odt(self, mutate) -> bytes:
        return TestWhatStaysInTheFile().odt(mutate)

    def table_of(self, root):
        return root.find(".//table:table", NS)

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda t: t.append(etree.Element(q("table", "table-row-group"))),
            lambda t: t.find("table:table-header-rows", NS).clear(),
            lambda t: t.find("table:table-header-rows", NS).append(etree.Element(q("text", "p"))),
            lambda t: t.findall("table:table-row", NS)[0].remove(t.find("table:table-row/table:table-cell", NS)),
            lambda t: t.findall("table:table-row", NS)[0].append(etree.Element(q("text", "p"))),
            lambda t: t.findall("table:table-row", NS)[0].append(etree.Element(q("table", "table-cell"))),
            lambda t: t.find(".//table:table-cell", NS).append(etree.Element(q("text", "h"))),
            lambda t: [t.remove(each) for each in t.findall("table:table-column", NS)],
            lambda t: t.findall("table:table-row", NS)[0].set(q("table", "number-rows-repeated"), "5000"),
            lambda t: t.find("table:table-column", NS).set(q("table", "number-columns-repeated"), "5000"),
            lambda t: t.find(".//table:table-cell", NS).set(q("table", "number-columns-repeated"), "5000"),
        ],
        ids=[
            "a row group",
            "an empty header",
            "a header that holds no rows",
            "a short row",
            "something else in a row",
            "a long row",
            "a heading in a cell",
            "no columns",
            "a million rows",
            "a million columns",
            "a million cells",
        ],
    )
    def test_what_is_more_than_the_text_holds_stays_in_the_file(self, mutate) -> None:
        data = self.odt(lambda root: mutate(self.table_of(root)))
        assert odt_to_text(data).tables == {}
        assert sum(loss.count for loss in odt_import_losses(data) if loss.kind == "table") == 1

    def test_a_note_or_a_reference_in_a_cell_is_more_than_words(self) -> None:
        def note(root) -> None:
            cell = root.find(".//table:table-cell/text:p", NS)
            etree.SubElement(etree.SubElement(cell, q("text", "note")), q("text", "note-body"))

        def reference(root) -> None:
            cell = root.find(".//table:table-cell/text:p", NS)
            etree.SubElement(cell, q("text", "bookmark-ref")).set(q("text", "ref-name"), "x")

        assert odt_to_text(self.odt(note)).tables == {}
        assert odt_to_text(self.odt(reference)).tables == {}

    def test_what_a_program_writes_for_itself_is_no_matter(self) -> None:
        def mutate(root) -> None:
            element = self.table_of(root)
            element.insert(0, etree.Comment("a comment"))
            element.insert(0, etree.Element(q("office", "forms")))
            etree.SubElement(element.find(".//table:table-cell", NS), q("text", "p")).text = "  "
            element.find(".//table:table-cell", NS).insert(0, etree.Comment("again"))
            element.findall("table:table-row", NS)[0].set(q("table", "number-rows-repeated"), "x")
            element.findall("table:table-row", NS)[1].find("table:table-cell", NS).set(
                q("table", "number-columns-spanned"), "x"
            )

        (found,) = odt_to_text(self.odt(mutate)).tables.values()
        assert found.merges == () and len(found.rows) == 3

    def test_the_widths_a_file_gives_are_read_as_it_gives_them(self) -> None:
        def absolute_only(root) -> None:
            for properties in root.iter(q("style", "table-column-properties")):
                del properties.attrib[q("style", "rel-column-width")]
            properties = next(root.iter(q("style", "table-properties")))
            del properties.attrib[q("style", "rel-width")]
            properties.set(q("style", "width"), "8cm")

        (found,) = odt_to_text(self.odt(absolute_only)).tables.values()
        assert [c.width for c in found.columns] == [3333, 3333, 3334]
        assert found.width is not None and 4000 < found.width < 6000  # (8 cm of an A4 page's text)

        def none(root) -> None:
            for properties in root.iter(q("style", "table-column-properties")):
                properties.attrib.clear()
            properties = next(root.iter(q("style", "table-properties")))
            properties.attrib.clear()
            properties.set(q("style", "rel-width"), "x%")

        (found,) = odt_to_text(self.odt(none)).tables.values()
        assert all(c.width is None for c in found.columns) or len({c.width for c in found.columns}) == 1
        assert found.width is None

        def unstyled(root) -> None:
            self.table_of(root).attrib.pop(q("table", "style-name"))

        (found,) = odt_to_text(self.odt(unstyled)).tables.values()
        assert found.width is None
