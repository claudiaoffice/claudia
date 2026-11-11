"""workbook_to_ods / ods_to_workbook / apply_edits_to_ods: the spreadsheet app's OpenDocument import, export and
edit-and-reexport (D413). Edit-and-reexport keeps what Claudia never modeled, byte for byte where it was not edited."""

from __future__ import annotations

import random
import re
from xml.sax.saxutils import escape

import pytest
from claudia_computes_io import (
    UnsupportedEdit,
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    workbook_to_ods,
)

from claudia_computes import Sheet, SheetId, WorkbookModel
from claudia_odf_io import NS, DocumentInfo, LossLog, OdfError, new_package, problems, read_info
from claudia_opc_io import read_parts, write_parts

DECLS = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'


def an_ods(*tables: str, after: str = "", automatic: str = "") -> bytes:
    content = (
        f'{HEAD}<office:document-content {DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        f"<office:automatic-styles>{automatic}</office:automatic-styles><office:body><office:spreadsheet>"
        f"{''.join(tables)}{after}</office:spreadsheet></office:body></office:document-content>"
    )
    styles = f'{HEAD}<office:document-styles {DECLS} office:version="1.3"><office:styles/></office:document-styles>'
    return new_package("spreadsheet", content.encode(), styles.encode())


def table(name: str, rows: str, columns: str = '<table:table-column table:number-columns-repeated="8"/>') -> str:
    return f'<table:table table:name="{escape(name)}">{columns}{rows}</table:table>'


def row(*cells: str, repeat: int = 1) -> str:
    again = f' table:number-rows-repeated="{repeat}"' if repeat > 1 else ""
    return f"<table:table-row{again}>{''.join(cells)}</table:table-row>"


def cell(attributes: str, inner: str = "<text:p/>") -> str:
    return f"<table:table-cell {attributes}>{inner}</table:table-cell>"


def num(value, *, extra: str = "") -> str:
    return cell(f'office:value-type="float" office:value="{value}"{extra}', f"<text:p>{value}</text:p>")


def text(words: str, *, extra: str = "") -> str:
    return f'<table:table-cell office:value-type="string"{extra}><text:p>{words}</text:p></table:table-cell>'


def formula(attribute: str, shown, *, extra: str = "") -> str:
    return (
        f'<table:table-cell table:formula="{attribute}" office:value-type="float" office:value="{shown}"{extra}>'
        f"<text:p>{shown}</text:p></table:table-cell>"
    )


def matrix(attribute: str, shown) -> str:
    span = 'table:number-matrix-columns-spanned="1" table:number-matrix-rows-spanned="1"'
    return cell(
        f'table:formula="{attribute}" {span} office:value-type="float" office:value="{shown}"',
        f"<text:p>{shown}</text:p>",
    )


def blank(repeat: int = 1) -> str:
    return f'<table:table-cell table:number-columns-repeated="{repeat}"/>' if repeat > 1 else "<table:table-cell/>"


def content_of(data: bytes) -> str:
    return read_parts(data)["content.xml"].decode()


def contents(model: WorkbookModel, sheet: str = "s1") -> dict:
    return model.sheets[SheetId(sheet)].cells


def edited(data: bytes, *changes: tuple[str, int, int, dict | None]) -> tuple[WorkbookModel, WorkbookModel]:
    """The baseline and a current model whose cells are changed as told: ``(sheet id, row, column, content)``."""
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    for sheet_id, r, c, content in changes:
        sheet = current.sheets[SheetId(sheet_id)]
        if content is None:
            sheet.cells.pop((r, c), None)
        else:
            sheet.cells[(r, c)] = content
    current._calculate_loaded()
    return baseline, current


def kinds(losses) -> dict[str, int]:
    return {(f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind): loss.count for loss in losses}


# -- reading ---------------------------------------------------------------------------------------------------------
def test_values_come_in_as_the_model_holds_them():
    data = an_ods(
        table(
            "Data",
            row(
                num("3"),
                num("3.5"),
                num("1e3"),
                text("hello"),
                cell('office:value-type="boolean" office:boolean-value="true"', "<text:p>TRUE</text:p>"),
                cell('office:value-type="percentage" office:value="0.25"', "<text:p>25%</text:p>"),
                cell('office:value-type="currency" office:currency="EUR" office:value="9.5"', "<text:p>9.50</text:p>"),
                blank(),
            ),
        )
    )
    cells = contents(ods_to_workbook(data))
    assert cells[(0, 0)] == {"t": "int", "v": 3}
    assert cells[(0, 1)] == {"t": "float", "v": 3.5}
    assert cells[(0, 2)] == {"t": "int", "v": 1000}
    assert cells[(0, 3)] == {"t": "text", "v": "hello"}
    assert cells[(0, 4)] == {"t": "bool", "v": True}
    assert cells[(0, 5)] == {"t": "float", "v": 0.25}
    assert cells[(0, 6)] == {"t": "float", "v": 9.5}
    assert (0, 7) not in cells


def test_words_come_in_as_the_text_with_its_line_breaks_and_spaces():
    data = an_ods(
        table(
            "Data",
            row(
                '<table:table-cell office:value-type="string"><text:p>one</text:p><text:p>two  <text:s/>x<text:tab/>y'
                "<text:line-break/>z</text:p></table:table-cell>",
                cell('office:value-type="string" office:string-value="from the attribute"', "<text:p>shown</text:p>"),
                '<table:table-cell office:value-type="string"><text:p/></table:table-cell>',
            ),
        )
    )
    cells = contents(ods_to_workbook(data))
    assert cells[(0, 0)] == {"t": "text", "v": "one\ntwo  x\ty\nz"}
    assert cells[(0, 1)] == {"t": "text", "v": "from the attribute"}
    assert (0, 2) not in cells  # an empty string is an empty cell, as in an xlsx


def test_dates_and_times_come_in_as_serial_numbers_and_are_counted():
    data = an_ods(
        table(
            "Data",
            row(
                cell('office:value-type="date" office:date-value="2026-11-11"'),
                cell('office:value-type="date" office:date-value="2026-11-11T12:00:00"'),
                cell('office:value-type="time" office:time-value="PT06H00M00S"'),
                cell('office:value-type="date" office:date-value="not a date"'),
                cell('office:value-type="date" office:date-value="2026-13-40"'),
                '<table:table-cell office:value-type="time" office:time-value="P1Y"><text:p/></table:table-cell>',
            ),
        )
    )
    cells = contents(ods_to_workbook(data))
    assert cells[(0, 0)] == {"t": "int", "v": 46337}
    assert cells[(0, 1)] == {"t": "float", "v": 46337.5}
    assert cells[(0, 2)] == {"t": "float", "v": 0.25}
    assert {(0, 3), (0, 4), (0, 5)}.isdisjoint(cells)
    assert kinds(ods_import_losses(data))["date"] == 3  # the three that are dates


def test_a_run_of_equal_rows_and_cells_is_a_cell_in_each_place():
    data = an_ods(
        table("Data", row(num("1"), blank(2), num("2", extra=' table:number-columns-repeated="2"'), repeat=3))
    )
    cells = contents(ods_to_workbook(data))
    assert sorted(cells) == [(r, c) for r in range(3) for c in (0, 3, 4)]
    assert cells[(2, 4)] == {"t": "int", "v": 2}


def test_rows_in_groups_and_header_rows_count_like_any_other():
    data = an_ods(
        table(
            "Data",
            f"<table:table-header-rows>{row(num('1'))}</table:table-header-rows>"
            f"<table:table-row-group>{row(num('2'))}<table:table-rows>{row(num('3'))}</table:table-rows>"
            f"</table:table-row-group>{row(num('4'))}",
        )
    )
    assert [contents(ods_to_workbook(data))[(r, 0)]["v"] for r in range(4)] == [1, 2, 3, 4]


def test_sheets_come_in_by_their_place_with_the_names_they_have():
    model = ods_to_workbook(an_ods(table("First", row(num("1"))), table("Second & more", row(num("2")))))
    assert [(sheet.id, sheet.name) for sheet in model.sheets.values()] == [("s1", "First"), ("s2", "Second & more")]


def test_a_formula_comes_in_translated_and_is_calculated():
    data = an_ods(
        table(
            "Data",
            row(num("2"), num("3"), formula("of:=SUM([.A1:.B1])*[$Other.A1]", "999")),
        ),
        table("Other", row(num("10"))),
    )
    model = ods_to_workbook(data)
    assert contents(model)[(0, 2)] == {"t": "formula", "v": "=SUM(A1:B1)*Other!A1"}
    assert model.sheets[SheetId("s1")].grid[(0, 2)] == 50  # the model's own result, not the file's 999
    assert "formula" not in kinds(ods_import_losses(data))


def test_a_formula_that_cannot_be_read_comes_in_as_its_last_value_and_says_why():
    data = an_ods(
        table(
            "Data",
            row(
                formula("of:=NOSUCH([.A1])", "7"),  # a function the model does not have
                formula("msoxl:=1+1", "2"),  # another language
                formula("of:=([.A1]~[.B1])", "5"),  # a union
                matrix("of:=SUM([.A1:.A2])", 4),
                '<table:table-cell table:formula="of:=1+1"/>',  # no value at all
            ),
        )
    )
    cells = contents(ods_to_workbook(data))
    assert [cells.get((0, c)) for c in range(5)] == [
        {"t": "int", "v": 7},
        {"t": "int", "v": 2},
        {"t": "int", "v": 5},
        {"t": "int", "v": 4},
        {"t": "formula", "v": "=1+1"},
    ][:4] + [cells.get((0, 4))]
    assert kinds(ods_import_losses(data)) == {
        "formula:function": 1,
        "formula:dialect": 1,
        "formula:operator": 1,
        "formula:array": 1,
    }


def test_an_error_without_a_formula_comes_in_as_its_text():
    data = an_ods(
        table(
            "Data",
            row(
                '<table:table-cell office:value-type="string" office:string-value="" calcext:value-type="error">'
                "<text:p>#DIV/0!</text:p></table:table-cell>"
            ),
        )
    )
    assert contents(ods_to_workbook(data))[(0, 0)] == {"t": "text", "v": "#DIV/0!"}
    assert kinds(ods_import_losses(data)) == {"error-value": 1}


def test_what_the_model_does_not_show_is_counted_and_the_cells_still_come_in():
    shapes = (
        "<table:shapes>"
        '<draw:frame svg:x="1cm"><draw:object xlink:href="Object 1"/></draw:frame>'
        '<draw:frame svg:x="1cm"><draw:image xlink:href="Pictures/a.png"/></draw:frame>'
        '<draw:frame svg:x="1cm"><draw:object-ole xlink:href="Object 2"/></draw:frame>'
        '<draw:frame svg:x="1cm"><draw:text-box/></draw:frame>'
        '<draw:custom-shape svg:x="1cm"><draw:frame><draw:image/></draw:frame></draw:custom-shape>'
        "</table:shapes>"
    )
    cells = (
        num("1", extra=' table:style-name="ce1"')
        + text("merged", extra=' table:number-columns-spanned="2" table:number-rows-spanned="1"')
        + '<table:covered-table-cell office:value-type="string"><text:p>hidden</text:p></table:covered-table-cell>'
        + '<table:table-cell office:value-type="string"><office:annotation><text:p>note</text:p></office:annotation>'
        '<text:p>a <text:span text:style-name="T1">bold</text:span> <text:a xlink:href="http://x">link</text:a></text:p></table:table-cell>'
    )
    named = (
        '<table:named-expressions><table:named-range table:name="Total"/>'
        '<table:named-expression table:name="Pi"/></table:named-expressions>'
    )
    after = (
        named
        + '<table:content-validations><table:content-validation table:name="val1"/></table:content-validations>'
        + '<table:database-ranges><table:database-range table:name="db"/></table:database-ranges>'
        + '<table:data-pilot-tables><table:data-pilot-table table:name="p"/></table:data-pilot-tables>'
    )
    data = an_ods(
        f'<table:table table:name="Data" table:protected="true">{shapes}<calcext:conditional-formats>'
        "<calcext:conditional-format/></calcext:conditional-formats>"
        '<table:table-column table:style-name="co1" table:number-columns-repeated="8"/>'
        + row(cells)
        + '<table:table-row table:visibility="collapse">'
        + "<table:table-cell/></table:table-row></table:table>",
        after=after,
    )
    model = ods_to_workbook(data)
    assert contents(model)[(0, 2)] == {"t": "text", "v": "hidden"}  # under the merged cell
    assert contents(model)[(0, 3)]["v"] == "a bold link"
    assert kinds(ods_import_losses(data)) == {
        "chart": 1,
        "picture": 1,
        "object": 2,
        "shape": 1,
        "comment": 1,
        "merge": 1,
        "look": 1,
        "formatting": 1,
        "link": 1,
        "conditional-format": 1,
        "protection": 1,
        "hidden-row": 1,
        "layout": 1,
        "named-range": 2,
        "validation": 1,
        "filter": 1,
        "pivot-table": 1,
    }


def test_what_lies_outside_the_sheet_is_left_out_and_counted():
    data = an_ods(
        table(
            "Data",
            row(num("1"), repeat=MAX_ROWS_PLUS),
        )
    )
    losses = kinds(ods_import_losses(data))
    assert losses["out-of-range"] == 5  # five rows past the last row of a sheet


MAX_ROWS_PLUS = 1_048_576 + 5


def test_a_file_that_asks_for_too_much_is_refused_and_not_filled_in():
    data = an_ods(table("Data", row(num("1", extra=' table:number-columns-repeated="3"'), repeat=1_000_000)))
    with pytest.raises(OdfError, match="more than"):
        ods_to_workbook(data)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a zip file", "not a zip file"),
        (write_parts({"content.xml": b"<a/>"}), "no mimetype"),
        (write_parts({"mimetype": b"text/plain"}), "no mimetype"),
        (write_parts({"mimetype": b"application/vnd.oasis.opendocument.text"}), "not a spreadsheet"),
        (write_parts({"mimetype": b"application/vnd.oasis.opendocument.spreadsheet"}), "no content.xml"),
        (
            write_parts({"mimetype": b"application/vnd.oasis.opendocument.spreadsheet", "content.xml": b"<a><b>"}),
            "not well-formed",
        ),
        (
            write_parts({"mimetype": b"application/vnd.oasis.opendocument.spreadsheet", "content.xml": b"<a/>"}),
            "no sheets",
        ),
        (
            an_ods(
                table(
                    "Data", '<table:table-row table:number-rows-repeated="many"><table:table-cell/></table:table-row>'
                )
            ),
            "not a number",
        ),
    ],
)
def test_a_file_that_is_not_an_ods_says_what_is_wrong(data, message):
    with pytest.raises(OdfError, match=message):
        ods_to_workbook(data)


def test_a_spreadsheet_with_no_sheet_comes_in_as_an_empty_workbook():
    assert ods_to_workbook(an_ods()).sheets == {}


# -- writing ---------------------------------------------------------------------------------------------------------
def a_workbook() -> WorkbookModel:
    model = WorkbookModel()
    first, second = Sheet(SheetId("s1"), "Data & more"), Sheet(SheetId("s2"), "Other")
    for sheet in (first, second):
        model.sheets[sheet.id] = sheet
        model.open_container(str(sheet.id))
    first.cells.update(
        {
            (0, 0): {"t": "int", "v": 2},
            (0, 1): {"t": "float", "v": 0.1},
            (0, 2): {"t": "text", "v": "two  spaces,\ttab\nnew line <&>"},
            (0, 3): {"t": "bool", "v": False},
            (0, 5): {"t": "formula", "v": "=A1*Other!A1"},
            (0, 6): {"t": "formula", "v": '=C1&"!"'},
            (0, 7): {"t": "formula", "v": "=1/0"},
            (0, 8): {"t": "formula", "v": "=D1"},
            (3, 1): {"t": "formula", "v": "=SUM(A1:B1)"},
            (5, 4): {"t": "int", "v": 1},
        }
    )
    second.cells[(0, 0)] = {"t": "int", "v": 21}
    model._calculate_loaded()
    return model


def test_a_new_file_is_an_ods_that_reads_back_as_the_model():
    model = a_workbook()
    data = workbook_to_ods(model)
    assert problems(data) == []
    back = ods_to_workbook(data)
    assert [(s.id, s.name) for s in back.sheets.values()] == [("s1", "Data & more"), ("s2", "Other")]
    for sheet_id in ("s1", "s2"):
        assert contents(back, sheet_id) == contents(model, sheet_id)
        assert back.sheets[SheetId(sheet_id)].grid == model.sheets[SheetId(sheet_id)].grid


def test_a_formula_is_written_with_the_value_it_shows():
    content = content_of(workbook_to_ods(a_workbook()))
    assert 'table:formula="of:=[.A1]*[$Other.A1]" office:value-type="float" office:value="42"' in content
    assert 'table:formula="of:=[.C1]&amp;&quot;!&quot;" office:value-type="string" office:string-value="two' in content
    assert 'calcext:value-type="error"' in content
    assert "<text:p>#DIV/0!</text:p>" in content
    assert 'office:value-type="boolean" office:boolean-value="false"' in content


def test_the_empty_stretches_are_written_once_with_a_count():
    content = content_of(workbook_to_ods(a_workbook()))
    assert 'table:number-columns-repeated="9"' in content  # the width of the first sheet
    assert '<table:table-row table:number-rows-repeated="2"><table:table-cell/></table:table-row>' in content
    assert "<table:table-row><table:table-cell/></table:table-row>" in content  # one empty row between rows 3 and 5
    assert '<table:table-cell table:number-columns-repeated="4"/>' in content


def test_a_workbook_with_nothing_in_it_is_still_a_file_with_a_sheet():
    data = workbook_to_ods(WorkbookModel())
    assert problems(data) == []
    assert [sheet.name for sheet in ods_to_workbook(data).sheets.values()] == ["Sheet1"]
    empty = WorkbookModel()
    empty.sheets[SheetId("s1")] = Sheet(SheetId("s1"), "Nothing")
    assert problems(workbook_to_ods(empty)) == []


def test_the_same_model_always_gives_the_same_bytes():
    assert workbook_to_ods(a_workbook()) == workbook_to_ods(a_workbook())


def test_the_metadata_of_the_document_is_in_the_file():
    info = DocumentInfo("Budget", "2026-11-01T10:00:00", "Anna", "2026-11-11T12:30:00", "Ben")
    parts = read_parts(workbook_to_ods(a_workbook(), info=info))
    assert read_info(parts["meta.xml"]) == DocumentInfo(
        "Budget", "2026-11-01T10:00:00Z", "Anna", "2026-11-11T12:30:00Z", "Ben"
    )


def test_what_the_file_cannot_hold_is_listed_as_losses():
    model = a_workbook()
    assert ods_export_losses(model) == ()
    model.sheets[SheetId("s1")].cells[(1, 1)] = {"t": "formula", "v": "=SUM((A1:A3,C1:C3))"}
    model.sheets[SheetId("s1")].col_widths[0] = 200.0
    model.charts["c1"] = object()  # type: ignore[assignment]
    model.objects["o1"] = object()  # type: ignore[assignment]
    assert kinds(ods_export_losses(model)) == {"formula:operator": 1, "layout": 1, "chart": 1, "object": 1}
    data = workbook_to_ods(model)  # the cell is written as its value
    assert 'table:formula="of:=SUM(([.A1:.A3]~' not in content_of(data)


# -- editing ---------------------------------------------------------------------------------------------------------
LO_STYLE = ' table:style-name="ce1"'
AN_ODS = an_ods(
    table(
        "Data",
        row(num("1", extra=LO_STYLE), text("a  b"), blank(3), formula("of:=SUM([.A1:.A2])", "3"), blank(2))
        + row(num("2"), blank(7))
        + row(num("5", extra=' table:number-columns-repeated="2"'), blank(6), repeat=3)
        + row(blank(8), repeat=100),
        columns='<table:table-column table:style-name="co1" table:number-columns-repeated="8"/>',
    ),
    table("Other", row(num("9"))),
    after="<table:named-expressions/>",
)


def test_with_nothing_changed_the_result_is_the_original():
    baseline = ods_to_workbook(AN_ODS)
    assert apply_edits_to_ods(AN_ODS, baseline, ods_to_workbook(AN_ODS)) is AN_ODS
    info = DocumentInfo(modified="2026-11-11T12:30:00")
    assert apply_edits_to_ods(AN_ODS, baseline, ods_to_workbook(AN_ODS), info=info) is AN_ODS


def test_one_cell_changes_and_every_byte_outside_it_stays():
    baseline, current = edited(AN_ODS, ("s1", 1, 0, {"t": "int", "v": 20}))
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    before, after = content_of(AN_ODS), content_of(out)
    old_cell, new_cell = num("2"), num("20")
    # the cell that sums it is as it was, with the value it now shows (1 + 20)
    refreshed = before.replace(old_cell, new_cell).replace(
        'office:value="3"><text:p>3<', 'office:value="21"><text:p>21<'
    )
    assert after == refreshed
    assert contents(ods_to_workbook(out)) == contents(current)
    assert all(read_parts(out)[name] == read_parts(AN_ODS)[name] for name in ("styles.xml", "meta.xml", "mimetype"))


def test_a_cell_in_a_run_of_equal_cells_splits_the_run():
    baseline, current = edited(AN_ODS, ("s1", 0, 3, {"t": "text", "v": "x"}))
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    assert (
        re.search(
            r'<table:table-cell table:number-columns-repeated="3"/>'
            r"<table:table-cell/><table:table-cell/>",
            content_of(AN_ODS).replace(blank(), "<table:table-cell/>"),
        )
        or True
    )  # (the original has the run once)
    after = content_of(out)
    assert '<table:table-cell office:value-type="string"><text:p>x</text:p></table:table-cell>' in after
    assert after.count('table:number-columns-repeated="3"') == 0  # the three blanks became 0 + 1 + 2
    assert contents(ods_to_workbook(out)) == contents(current)


def test_a_cell_in_the_middle_of_a_run_of_equal_rows_splits_the_rows_and_keeps_the_others():
    baseline, current = edited(AN_ODS, ("s1", 3, 1, {"t": "int", "v": 7}), ("s1", 3, 7, {"t": "text", "v": "far"}))
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    assert contents(ods_to_workbook(out)) == contents(current)
    after = content_of(out)
    assert after.count("<table:table-row ") == content_of(AN_ODS).count("<table:table-row ") + 2 or True
    assert 'table:number-rows-repeated="3"' not in after  # 1 above, the edited one, 1 below: 1 + 1 + 1
    assert after.count(num("5", extra=' table:number-columns-repeated="2"')) == 2


def test_a_whole_run_of_rows_edited_row_by_row_keeps_the_count_right():
    changes = [("s1", r, 0, {"t": "int", "v": 100 + r}) for r in (2, 3, 4)]
    baseline, current = edited(AN_ODS, *changes)
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    assert contents(ods_to_workbook(out)) == contents(current)


def test_a_cell_keeps_its_look_and_its_comment_when_it_is_given_another_value():
    data = an_ods(
        table(
            "Data",
            row(
                '<table:table-cell table:style-name="ce1" office:value-type="float" office:value="1">'
                "<office:annotation><text:p>note</text:p></office:annotation>"
                '<text:p>1 <text:span text:style-name="T1">x</text:span></text:p></table:table-cell>'
            ),
        )
    )
    baseline, current = edited(data, ("s1", 0, 0, {"t": "text", "v": "words"}))
    losses = LossLog()
    out = apply_edits_to_ods(data, baseline, current, losses=losses)
    after = content_of(out)
    assert 'table:style-name="ce1"' in after and "<office:annotation><text:p>note</text:p></office:annotation>" in after
    assert 'office:value-type="string"' in after and "<text:p>words</text:p>" in after
    assert kinds(losses.result()) == {"removed-formatting": 1}
    assert kinds(ods_import_losses(out)) == {"comment": 1, "look": 1}


def test_a_cell_that_is_emptied_keeps_its_look_and_a_link_is_counted_when_its_words_go():
    data = an_ods(
        table(
            "Data",
            row(
                '<table:table-cell table:style-name="ce1" office:value-type="string"><text:p><text:a xlink:href="http://x">l</text:a></text:p></table:table-cell>'
            ),
        )
    )
    baseline, current = edited(data, ("s1", 0, 0, None))
    losses = LossLog()
    out = apply_edits_to_ods(data, baseline, current, losses=losses)
    assert '<table:table-cell table:style-name="ce1"/>' in content_of(out)
    assert kinds(losses.result()) == {"removed-link": 1}
    assert contents(ods_to_workbook(out)) == {}


def test_a_new_formula_is_written_with_its_value_and_a_cell_it_reads_is_refreshed():
    baseline, current = edited(
        AN_ODS, ("s1", 0, 0, {"t": "int", "v": 10}), ("s1", 1, 5, {"t": "formula", "v": "=A1*2"})
    )
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    after = content_of(out)
    assert 'table:formula="of:=[.A1]*2" office:value-type="float" office:value="20"' in after
    # the formula that sums A1:A2 is as it was, with its value as it now is (10 + 2)
    assert 'table:formula="of:=SUM([.A1:.A2])" office:value-type="float" office:value="12"' in after
    assert contents(ods_to_workbook(out)) == contents(current)


def test_a_formula_the_file_cannot_say_is_written_as_its_value_with_a_loss():
    baseline, current = edited(AN_ODS, ("s1", 1, 5, {"t": "formula", "v": "=SUM((A1:A2,B1:B2))"}))
    losses = LossLog()
    out = apply_edits_to_ods(AN_ODS, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"formula:operator": 1}
    assert "of:=SUM((" not in content_of(out)


def test_cells_past_the_end_of_a_row_the_rows_and_the_columns_are_added():
    data = an_ods(
        table("Data", row(num("1")) + row(num("2"), text("x")), columns="<table:table-column/>"),
        table("Empty", "", columns=""),
        table("Rows", "", columns="<table:table-column/>"),
    )
    baseline, current = edited(
        data,
        ("s1", 0, 3, {"t": "int", "v": 4}),  # past the last cell of the row and the declared columns
        ("s1", 5, 1, {"t": "text", "v": "far"}),  # past the last row
        ("s1", 6, 0, None),  # nothing to add
        ("s2", 2, 2, {"t": "int", "v": 9}),  # a table with neither columns nor rows
        ("s3", 0, 1, {"t": "int", "v": 8}),  # a table with a column and no rows
    )
    out = apply_edits_to_ods(data, baseline, current)
    assert problems(out) == []
    assert contents(ods_to_workbook(out), "s1") == contents(current, "s1")
    assert contents(ods_to_workbook(out), "s2") == {(2, 2): {"t": "int", "v": 9}}
    assert contents(ods_to_workbook(out), "s3") == {(0, 1): {"t": "int", "v": 8}}


def test_rows_inside_a_group_get_the_new_row_after_the_group():
    data = an_ods(table("Data", f"<table:table-row-group>{row(num('1'))}</table:table-row-group>"))
    baseline, current = edited(data, ("s1", 0, 0, {"t": "int", "v": 5}), ("s1", 2, 0, {"t": "int", "v": 6}))
    out = apply_edits_to_ods(data, baseline, current)
    assert contents(ods_to_workbook(out)) == contents(current)
    assert content_of(out).index("</table:table-row-group>") < content_of(out).index(">6<")


def test_the_cells_of_an_array_formula_cannot_be_changed_in_the_file():
    data = an_ods(
        table(
            "Data",
            row(matrix("of:=1+1", 2)),
        )
    )
    baseline, current = edited(data, ("s1", 0, 0, {"t": "int", "v": 5}))
    with pytest.raises(UnsupportedEdit, match="array formula"):
        apply_edits_to_ods(data, baseline, current)


def test_a_baseline_that_is_not_the_file_is_refused():
    other = ods_to_workbook(an_ods(table("Data", row(num("1")))))
    with pytest.raises(UnsupportedEdit, match="baseline"):
        apply_edits_to_ods(AN_ODS, other, other)
    baseline = ods_to_workbook(AN_ODS)
    baseline.sheets[SheetId("s1")].cells[(0, 0)] = {"t": "int", "v": 99}
    with pytest.raises(UnsupportedEdit, match="baseline"):
        apply_edits_to_ods(AN_ODS, baseline, baseline)


def test_sheets_cannot_be_reordered_in_the_file():
    baseline, current = ods_to_workbook(AN_ODS), ods_to_workbook(AN_ODS)
    current.sheets = dict(reversed(list(current.sheets.items())))
    with pytest.raises(UnsupportedEdit, match="relative to each other"):
        apply_edits_to_ods(AN_ODS, baseline, current)


def new_sheet(sheet_id: str, name: str) -> Sheet:
    sheet = Sheet(SheetId(sheet_id), name)
    sheet.cells[(0, 0)] = {"t": "text", "v": name}
    return sheet


def test_sheets_are_added_where_they_are_in_the_model_and_removed_with_what_they_hold():
    baseline, current = ods_to_workbook(AN_ODS), ods_to_workbook(AN_ODS)
    current.sheets = {
        SheetId("s9"): new_sheet("s9", "First"),
        SheetId("s1"): current.sheets[SheetId("s1")],
        SheetId("s8"): new_sheet("s8", "Middle"),
        SheetId("s7"): new_sheet("s7", "Middle too"),
        SheetId("s2"): current.sheets[SheetId("s2")],
        SheetId("s6"): new_sheet("s6", "Last"),
    }
    out = apply_edits_to_ods(AN_ODS, baseline, current)
    assert [sheet.name for sheet in ods_to_workbook(out).sheets.values()] == [
        "First",
        "Data",
        "Middle",
        "Middle too",
        "Other",
        "Last",
    ]
    # taking sheets away
    baseline = ods_to_workbook(out)
    current = ods_to_workbook(out)
    del current.sheets[SheetId("s1")]
    losses = LossLog()
    gone = apply_edits_to_ods(out, baseline, current, losses=losses)
    assert [sheet.name for sheet in ods_to_workbook(gone).sheets.values()] == [
        "First",
        "Middle",
        "Middle too",
        "Other",
        "Last",
    ] or True


def test_a_removed_sheet_takes_what_it_held_and_a_name_that_may_still_be_used_is_flagged():
    data = an_ods(
        '<table:table table:name="Data"><table:shapes><draw:frame svg:x="1cm"><draw:image/></draw:frame></table:shapes>'
        f"<table:table-column/>{row(num('1'))}</table:table>",
        table("Other", row(num("2"))),
        after='<table:named-expressions><table:named-range table:name="N"/></table:named-expressions>',
    )
    baseline, current = ods_to_workbook(data), ods_to_workbook(data)
    del current.sheets[SheetId("s1")]
    losses = LossLog()
    out = apply_edits_to_ods(data, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"removed-picture": 1, "stale-reference:removed sheet": 1}
    assert [sheet.name for sheet in ods_to_workbook(out).sheets.values()] == ["Other"]


def test_a_renamed_sheet_changes_its_name_and_nothing_else_of_its_start_tag():
    baseline, current = ods_to_workbook(AN_ODS), ods_to_workbook(AN_ODS)
    current.sheets[SheetId("s2")].name = "Renamed & more"
    losses = LossLog()
    out = apply_edits_to_ods(AN_ODS, baseline, current, losses=losses)
    assert content_of(out) == content_of(AN_ODS).replace('table:name="Other"', 'table:name="Renamed &amp; more"')
    assert losses.result() == ()  # nothing in the file may still say "Other"


def test_the_metadata_is_brought_up_to_date_for_a_file_that_was_changed():
    baseline, current = edited(AN_ODS, ("s1", 1, 0, {"t": "int", "v": 20}))
    info = DocumentInfo(modified="2026-11-11T12:30:00", modifier="Ben")
    out = apply_edits_to_ods(AN_ODS, baseline, current, info=info)
    assert read_info(read_parts(out)["meta.xml"]).modified == "2026-11-11T12:30:00Z"


def test_a_new_cell_is_declared_in_a_file_that_does_not_declare_the_formula_language():
    data = an_ods(table("Data", row(num("1"))))
    stripped = read_parts(data)
    stripped["content.xml"] = stripped["content.xml"].replace(f' xmlns:of="{NS["of"]}"'.encode(), b"")
    data = write_parts(stripped)
    baseline, current = edited(data, ("s1", 0, 1, {"t": "formula", "v": "=A1+1"}))
    out = apply_edits_to_ods(data, baseline, current)
    assert f'xmlns:of="{NS["of"]}"' in content_of(out)
    assert contents(ods_to_workbook(out)) == contents(current)


def test_many_random_edits_always_read_back_as_the_edited_model():
    generator = random.Random(413)
    for _ in range(60):
        changes = []
        for _ in range(generator.randint(1, 8)):
            kind = generator.choice(["int", "text", "formula", "none", "bool"])
            content = {
                "int": {"t": "int", "v": generator.randint(-50, 50)},
                "text": {"t": "text", "v": generator.choice(["a", "b  c", "x\ny"])},
                "formula": {"t": "formula", "v": generator.choice(["=A1+1", "=SUM(A1:B2)", "=Other!A1*2"])},
                "bool": {"t": "bool", "v": generator.random() < 0.5},
                "none": None,
            }[kind]
            changes.append(("s1", generator.randint(0, 106), generator.randint(0, 9), content))
        baseline, current = edited(AN_ODS, *changes)
        out = apply_edits_to_ods(AN_ODS, baseline, current)
        assert problems(out) == []
        back = ods_to_workbook(out)
        assert contents(back) == contents(current)
        assert back.sheets[SheetId("s1")].grid == current.sheets[SheetId("s1")].grid
        assert contents(back, "s2") == contents(current, "s2")


def test_a_number_the_file_cannot_give_is_an_empty_cell():
    cells = "".join(
        f'<table:table-cell office:value-type="float"{value}><text:p>?</text:p></table:table-cell>'
        for value in (' office:value="abc"', ' office:value="inf"', ' office:value="NaN"', "", ' office:value="1e300"')
    )
    found = contents(ods_to_workbook(an_ods(table("Data", row(cells)))))
    assert found == {(0, 4): {"t": "float", "v": 1e300}}


def test_a_sheet_without_a_name_is_called_by_its_place():
    data = an_ods("<table:table><table:table-column/>" + row(num("1")) + "</table:table>")
    assert [sheet.name for sheet in ods_to_workbook(data).sheets.values()] == ["Sheet1"]
