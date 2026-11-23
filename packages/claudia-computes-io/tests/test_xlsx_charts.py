"""Charts in an xlsx file: written as charts of their own, read back, patched into a kept file (D463)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from claudia_computes_io import (
    UnsupportedEdit,
    apply_edits_to_xlsx,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_import_losses,
    xlsx_to_workbook,
)
from claudia_computes_io.xlsx_chart_patch import Drawings
from claudia_computes_io.xlsx_patch import PackagePatch
from claudia_computes_io.xlsx_read import open_package
from lxml import etree
from test_ods_charts import S1, a_chart_workbook, a_range, a_workbook, put_chart, the_chart

from claudia_computes import (
    CellAnchor,
    ChartSpec,
    NamedRange,
    ObjectBody,
    Sheet,
    VisualObject,
    WorkbookModel,
)
from claudia_odf_io import LossLog
from claudia_opc_io import read_parts, write_parts

C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"c": C, "a": A, "xdr": XDR, "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
LIBRARY = Path(__file__).resolve().parents[3] / "test-documents" / "xlsx" / "charts" / "source.xlsx"


def kinds(losses) -> dict[str, int]:
    out: dict[str, int] = {}
    for loss in losses:
        key = f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind
        out[key] = out.get(key, 0) + loss.count
    return out


def chart_part(data: bytes, name: str = "xl/charts/chart1.xml") -> etree._Element:
    return etree.fromstring(read_parts(data)[name])


def drawing(data: bytes, name: str = "xl/drawings/drawing1.xml") -> etree._Element:
    return etree.fromstring(read_parts(data)[name])


def edited(data: bytes, old: bytes, new: bytes, part: str = "xl/charts/chart1.xml") -> bytes:
    parts = read_parts(data)
    assert old in parts[part], old
    parts[part] = parts[part].replace(old, new)
    return write_parts(parts)


def a_kept_file(**spec) -> tuple[bytes, WorkbookModel, WorkbookModel]:
    original = workbook_to_xlsx(a_chart_workbook(**spec))
    return original, xlsx_to_workbook(original), xlsx_to_workbook(original)


# -- a new file ---------------------------------------------------------------------------------------------------
def test_a_chart_is_written_as_a_chart_of_its_own_pinned_where_it_is():
    data = workbook_to_xlsx(a_chart_workbook())
    parts = read_parts(data)
    assert {"xl/charts/chart1.xml", "xl/drawings/drawing1.xml"} <= parts.keys()
    types = parts["[Content_Types].xml"].decode()
    assert "drawingml.chart+xml" in types and "spreadsheetml" in types and "/xl/drawings/drawing1.xml" in types
    sheet = etree.fromstring(parts["xl/worksheets/sheet1.xml"])
    assert sheet.find("x:drawing", NS) is not None
    (anchor,) = drawing(data)
    assert etree.QName(anchor).localname == "oneCellAnchor"
    assert (anchor.findtext("xdr:from/xdr:col", namespaces=NS), anchor.findtext("xdr:from/xdr:row", namespaces=NS)) == (
        "1",
        "5",
    )
    extent = anchor.find("xdr:ext", NS)
    assert (extent.get("cx"), extent.get("cy")) == (str(480 * 9525), str(300 * 9525))


def test_the_chart_reads_the_cells_of_the_sheet_and_says_what_it_is_called():
    chart = chart_part(workbook_to_xlsx(a_chart_workbook(title="Sales", x_title="Region", y_title="Euro")))
    series = [
        (one.findtext("c:tx//c:f", namespaces=NS), one.findtext("c:val//c:f", namespaces=NS))
        for one in chart.iterfind(".//c:ser", NS)
    ]
    assert series == [("Data!$B$1", "Data!$B$2:$B$4"), ("Data!$C$1", "Data!$C$2:$C$4")]
    assert {one.findtext("c:cat//c:f", namespaces=NS) for one in chart.iterfind(".//c:ser", NS)} == {"Data!$A$2:$A$4"}
    titles = ["".join(t.itertext()) for t in chart.iterfind(".//c:title", NS)]
    assert titles == ["Sales", "Region", "Euro"]
    assert chart.find(".//c:legend", NS) is not None and chart.find(".//c:majorGridlines", NS) is not None


def test_a_chart_without_a_title_says_so_to_excel_and_has_no_legend_or_gridlines_when_it_has_none():
    chart = chart_part(workbook_to_xlsx(a_chart_workbook(legend=False, gridlines=False)))
    assert chart.find(".//c:legend", NS) is None and chart.find(".//c:majorGridlines", NS) is None
    assert chart.find("c:chart/c:autoTitleDeleted", NS).get("val") == "1"  # (Excel would name a chart after its series)


def test_a_chart_whose_series_are_rows_reads_them_as_rows():
    chart = chart_part(workbook_to_xlsx(a_chart_workbook(series_in="rows")))
    values = [one.findtext("c:val//c:f", namespaces=NS) for one in chart.iterfind(".//c:ser", NS)]
    assert values == ["Data!$B$2:$C$2", "Data!$B$3:$C$3", "Data!$B$4:$C$4"]
    assert chart.findtext(".//c:cat//c:f", namespaces=NS) == "Data!$B$1:$C$1"


def test_a_chart_carries_a_copy_of_its_numbers_for_a_program_that_does_not_calculate():
    chart = chart_part(workbook_to_xlsx(a_chart_workbook()))
    first = next(chart.iterfind(".//c:ser", NS))
    assert [v.text for v in first.iterfind("c:val//c:v", NS)] == ["100", "200", "130"]
    assert [v.text for v in first.iterfind("c:cat//c:v", NS)] == ["North", "South", "East"]


def test_a_sheet_name_with_a_space_is_quoted_in_the_addresses_of_a_chart():
    model = a_chart_workbook()
    model.sheets[S1].name = "Q1 Data"
    data = workbook_to_xlsx(model)
    assert chart_part(data).findtext(".//c:val//c:f", namespaces=NS) == "'Q1 Data'!$B$2:$B$4"
    assert xlsx_to_workbook(data).diagrams


def test_the_charts_of_a_workbook_get_one_part_each_and_one_drawing_for_a_sheet():
    model = a_chart_workbook()
    put_chart(model, "c2", "o2", at=(10, 0), series_in="rows")
    parts = read_parts(workbook_to_xlsx(model))
    assert {n for n in parts if n.startswith("xl/charts/")} == {"xl/charts/chart1.xml", "xl/charts/chart2.xml"}
    assert len([n for n in parts if n.startswith("xl/drawings/drawing")]) == 1


# -- reading it back ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "spec",
    [
        {"title": "Sales", "x_title": "Region", "y_title": "Euro"},
        {"series_in": "rows"},
        {"range": a_range((1, 0), (3, 2)), "header_row": False, "legend": False, "gridlines": False},
        {"range": a_range((0, 1), (3, 1))},
        {"range": a_range((0, 0), (3, 2)), "title": "A & B <c>"},
        {"range": a_range((0, 0), (3, 0))},
    ],
)
def test_a_chart_comes_back_as_it_went(spec):
    model = a_chart_workbook(**spec)
    data = workbook_to_xlsx(model)
    back = xlsx_to_workbook(data)
    then, _ = the_chart(model)
    now, found = the_chart(back)
    assert replace(now, id="c1") == then
    assert (found.id, found.anchor, found.body.w, found.body.h) == ("o1", CellAnchor(S1, 5, 1), 480, 300)
    assert xlsx_import_losses(data) == ()


def test_the_description_of_a_chart_is_what_the_frame_says_to_someone_who_cannot_see_it():
    data = workbook_to_xlsx(a_chart_workbook(description="Sales per region"))
    properties = drawing(data).find(".//xdr:cNvPr", NS)
    assert properties.get("descr") == "Sales per region"
    assert the_chart(xlsx_to_workbook(data))[1].body.description == "Sales per region"


def test_a_chart_reads_its_sheet_by_name_whatever_the_case():
    data = edited(workbook_to_xlsx(a_chart_workbook()), b"Data!", b"DATA!")
    assert xlsx_to_workbook(data).diagrams


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'<c:barDir val="col"/>', b'<c:barDir val="bar"/>'),  # horizontal
        (b'<c:grouping val="clustered"/>', b'<c:grouping val="stacked"/>'),
        (b"barChart>", b"lineChart>"),  # another kind
        (b"Data!$C$2:$C$4", b"Data!$C$2:$C$3"),  # a series that is not what the range makes of its column
        (b"Data!$B$1</c:f>", b"Data!$B$2</c:f>"),  # a name that is not the header
        (b"Data!$A$2:$A$4", b"Data!$B$2:$B$4"),  # categories that are not the first column
        (b"Data!$B$2:$B$4", b"Elsewhere!$B$2:$B$4"),  # a sheet the file does not have
        (b"Data!$B$2:$B$4", b"(Data!$B$2:$B$3,Data!$B$4)"),  # a union
        (b"<c:catAx>", b"<c:dateAx>"),  # a date axis
    ],
)
def test_a_chart_that_is_not_the_one_the_model_draws_stays_in_the_file_and_is_counted(old, new):
    data = edited(workbook_to_xlsx(a_chart_workbook()), old, new)
    assert xlsx_to_workbook(data).diagrams == {}
    assert kinds(xlsx_import_losses(data)) == {"chart": 1}


def test_a_chart_of_two_kinds_is_not_the_models():
    data = workbook_to_xlsx(a_chart_workbook())
    chart = chart_part(data)
    plot = chart.find(".//c:plotArea", NS)
    extra = etree.SubElement(plot, f"{{{C}}}lineChart")
    plot.insert(1, extra)
    parts = read_parts(data)
    parts["xl/charts/chart1.xml"] = etree.tostring(chart)
    assert xlsx_to_workbook(write_parts(parts)).diagrams == {}


def _pinned_by_two_cells(extent: tuple[int, int]) -> bytes:
    """A workbook whose chart is pinned by two cells, the frame stating ``extent`` pixels (Excel states none)."""
    parts = read_parts(workbook_to_xlsx(a_chart_workbook()))
    root = etree.fromstring(parts["xl/drawings/drawing1.xml"])
    (one,) = root
    two = etree.fromstring(
        f'<xdr:twoCellAnchor xmlns:xdr="{XDR}"><xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>'
        f"<xdr:row>5</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>"
        f"<xdr:to><xdr:col>6</xdr:col><xdr:colOff>{10 * 9525}</xdr:colOff>"
        f"<xdr:row>9</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to><xdr:clientData/></xdr:twoCellAnchor>"
    )
    frame = one.find("xdr:graphicFrame", NS)
    ext = frame.find("xdr:xfrm/a:ext", NS)
    ext.set("cx", str(extent[0] * 9525))
    ext.set("cy", str(extent[1] * 9525))
    two.insert(2, frame)
    root.replace(one, two)
    parts["xl/drawings/drawing1.xml"] = etree.tostring(root)
    return write_parts(parts)


def test_a_chart_pinned_by_two_cells_has_the_size_of_the_cells_it_reaches():
    found = the_chart(xlsx_to_workbook(_pinned_by_two_cells((0, 0))))[1]
    assert (found.anchor, found.body.w, found.body.h) == (
        CellAnchor(S1, 5, 1),
        5 * 96 + 10,
        4 * 26,
    )  # (the file's cells, a default column 96 px and row 26 px; Excel states no size of the frame)


def test_a_chart_pinned_by_two_cells_has_the_size_its_frame_states():
    found = the_chart(xlsx_to_workbook(_pinned_by_two_cells((480, 300))))[1]
    assert (found.anchor, found.body.w, found.body.h) == (CellAnchor(S1, 5, 1), 480, 300)  # (LibreOffice does)


def test_a_chart_too_small_for_an_object_of_the_model_is_not_held():
    data = workbook_to_xlsx(a_chart_workbook(size=(480, 300)))
    parts = read_parts(data)
    parts["xl/drawings/drawing1.xml"] = parts["xl/drawings/drawing1.xml"].replace(
        f'cx="{480 * 9525}"'.encode(), b'cx="9525"'
    )
    assert xlsx_to_workbook(write_parts(parts)).diagrams == {}


def test_the_import_counts_only_the_charts_the_model_does_not_hold():
    model = a_chart_workbook()
    put_chart(model, "c2", "o2", at=(12, 0), series_in="rows")
    data = edited(workbook_to_xlsx(model), b"Data!$B$2:$B$4", b"Data!$B$2:$B$3")
    assert len(xlsx_to_workbook(data).objects) == 1
    assert kinds(xlsx_import_losses(data)) == {"chart": 1}


# -- what a file cannot keep ------------------------------------------------------------------------------------------
def test_a_chart_that_follows_a_name_is_written_as_the_cells_the_name_is_now():
    model = a_workbook()
    model.names.put(NamedRange("Sales", None, a_range(), header=True))
    model.diagrams.define(ChartSpec(id="c1", kind="bar", source="Sales"))
    body = ObjectBody("o1", "diagram", 480, 300, "plain-image", ref="c1")
    model.insert_object(VisualObject(body, CellAnchor(S1, 5, 1)))
    spec, _ = the_chart(xlsx_to_workbook(workbook_to_xlsx(model)))
    assert (spec.range, spec.source) == (a_range(), "")
    assert kinds(xlsx_export_losses(model)) == {"chart:source": 1}


def test_a_chart_that_reads_nothing_is_not_written_and_that_is_said():
    model = WorkbookModel()
    model.add_sheet(Sheet(S1, "Data"), None)
    model.diagrams.define(ChartSpec(id="c1", kind="bar", source="Gone"))
    body = ObjectBody("o1", "diagram", 480, 300, "plain-image", ref="c1")
    model.insert_object(VisualObject(body, CellAnchor(S1, 5, 1)))
    data = workbook_to_xlsx(model)
    assert xlsx_to_workbook(data).diagrams == {}
    assert not [name for name in read_parts(data) if name.startswith("xl/charts")]
    assert kinds(xlsx_export_losses(model)) == {"chart:empty": 1}


def test_a_chart_that_is_turned_stands_upright_in_a_file_and_that_is_said():
    model = a_chart_workbook()
    obj = next(iter(model.objects.values()))
    model.replace_object(replace(obj, body=replace(obj.body, rotation=30)))
    assert kinds(xlsx_export_losses(model)) == {"chart:rotation": 1}


# -- the drawing of a sheet -----------------------------------------------------------------------------------------
def test_the_drawing_of_a_sheet_goes_where_the_standard_has_it():
    data = workbook_to_xlsx(a_workbook_without_charts())
    package = open_package(data)
    patch = PackagePatch(package.parts)
    sheet = patch.parts["xl/worksheets/sheet1.xml"]
    patch.parts["xl/worksheets/sheet1.xml"] = sheet.replace(b"</worksheet>", b'<tableParts count="0"/></worksheet>')
    drawings = Drawings(patch)
    drawings.add("xl/worksheets/sheet1.xml", b"<c:chartSpace/>", 0, 0, 100, 100)
    drawings.finish()
    names = [etree.QName(e).localname for e in etree.fromstring(patch.parts["xl/worksheets/sheet1.xml"])]
    assert names.index("drawing") == names.index("tableParts") - 1


def a_workbook_without_charts() -> WorkbookModel:
    return a_workbook()


def test_a_second_chart_on_a_sheet_goes_in_the_drawing_the_sheet_has_with_an_id_of_its_own():
    data = workbook_to_xlsx(a_chart_workbook())
    package = open_package(data)
    patch = PackagePatch(package.parts)
    drawings = Drawings(patch, {"xl/drawings/drawing1.xml": etree.fromstring(patch.parts["xl/drawings/drawing1.xml"])})
    drawings.add("xl/worksheets/sheet1.xml", b"<c:chartSpace/>", 9, 9, 100, 100)
    drawings.finish()
    ids = [p.get("id") for p in etree.fromstring(patch.parts["xl/drawings/drawing1.xml"]).iter(f"{{{XDR}}}cNvPr")]
    assert len(ids) == 2 and len(set(ids)) == 2


# -- a file another program wrote -------------------------------------------------------------------------------------
def _soffice(tmp_path, source: bytes, to: str, name: str = "chart.xlsx") -> bytes:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / name).write_bytes(source)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", to, "--outdir", str(tmp_path / "out"), str(tmp_path / "in" / name)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return (tmp_path / "out" / f"{Path(name).stem}.{to.split(':')[0]}").read_bytes()


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
@pytest.mark.parametrize(
    "spec",
    [
        {"title": "Sales", "x_title": "Region", "y_title": "Euro"},
        {"series_in": "rows"},
        {"range": a_range((1, 0), (3, 2)), "header_row": False, "legend": False, "gridlines": False},
        {"range": a_range((0, 1), (3, 1))},
    ],
    ids=["columns", "rows", "no-header", "one-series"],
)
def test_libreoffice_draws_our_chart_and_what_it_saves_of_it_is_the_same_chart(tmp_path, spec):
    model = a_chart_workbook(**spec)
    saved = _soffice(tmp_path, workbook_to_xlsx(model), "xlsx")
    assert replace(the_chart(xlsx_to_workbook(saved))[0], id="c1") == the_chart(model)[0]
    assert xlsx_import_losses(saved) == ()


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_makes_a_picture_of_a_chart_of_ours(tmp_path):
    pdf = _soffice(tmp_path, workbook_to_xlsx(a_chart_workbook(title="Sales")), "pdf")
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000


# -- patching a kept file ---------------------------------------------------------------------------------------------
def test_a_chart_nobody_touched_stays_byte_for_byte():
    original, baseline, current = a_kept_file()
    assert apply_edits_to_xlsx(original, baseline, current) == original


def test_a_new_chart_is_a_new_anchor_and_a_new_part_in_a_kept_file():
    original, baseline, current = a_kept_file()
    put_chart(current, "c9", "o9", at=(12, 2), size=(300, 200), series_in="rows", title="Rows")
    losses = LossLog()
    patched = apply_edits_to_xlsx(original, baseline, current, losses=losses)
    assert losses.result() == ()
    parts = read_parts(patched)
    assert parts["xl/charts/chart1.xml"] == read_parts(original)["xl/charts/chart1.xml"]
    assert "xl/charts/chart2.xml" in parts and "/xl/charts/chart2.xml" in parts["[Content_Types].xml"].decode()
    back = xlsx_to_workbook(patched)
    second = back.objects["o2"]
    assert (second.anchor, second.body.w, second.body.h) == (CellAnchor(S1, 12, 2), 300, 200)
    assert back.diagrams["c2"].title == "Rows" and back.diagrams["c2"].series_in == "rows"


def test_the_first_chart_of_a_kept_file_that_has_none_makes_the_drawing_of_the_sheet():
    original = workbook_to_xlsx(a_workbook_without_charts())
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    put_chart(current, "c1", "o1", description="Sales")
    patched = apply_edits_to_xlsx(original, baseline, current)
    assert "xl/drawings/drawing1.xml" in read_parts(patched)
    assert the_chart(xlsx_to_workbook(patched))[1].body.description == "Sales"


def test_a_chart_that_was_removed_is_taken_out_with_its_part():
    original, baseline, current = a_kept_file()
    current.delete_object("o1")
    current.diagrams.forget("c1")
    patched = apply_edits_to_xlsx(original, baseline, current)
    parts = read_parts(patched)
    assert not [name for name in parts if name.startswith("xl/charts/")]
    assert "xl/charts/chart1.xml" not in parts["[Content_Types].xml"].decode()
    assert xlsx_to_workbook(patched).objects == {}


def test_a_chart_that_was_moved_and_resized_has_its_anchor_changed_and_its_part_kept():
    original, baseline, current = a_kept_file()
    obj = current.objects["o1"]
    current.replace_object(VisualObject(replace(obj.body, w=600, h=240), CellAnchor(S1, 9, 3)))
    patched = apply_edits_to_xlsx(original, baseline, current)
    found = xlsx_to_workbook(patched).objects["o1"]
    assert (found.anchor, found.body.w, found.body.h) == (CellAnchor(S1, 9, 3), 600, 240)
    assert read_parts(patched)["xl/charts/chart1.xml"] == read_parts(original)["xl/charts/chart1.xml"]


def test_a_chart_whose_definition_changed_is_drawn_again_the_way_it_was_before():
    original, baseline, current = a_kept_file(title="Before")
    current.diagrams.replace(replace(current.diagrams["c1"], title="After", legend=False))
    losses = LossLog()
    patched = apply_edits_to_xlsx(original, baseline, current, losses=losses)
    assert losses.result() == ()
    spec, _ = the_chart(xlsx_to_workbook(patched))
    assert (spec.title, spec.legend) == ("After", False)


def test_a_chart_whose_numbers_changed_carries_the_new_ones():
    original, baseline, current = a_kept_file()
    current.store(current.sheets[S1], 1, 1, {"t": "int", "v": 777})
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_xlsx(original, baseline, current)
    first = next(chart_part(patched).iterfind(".//c:ser", NS))
    assert [v.text for v in first.iterfind("c:val//c:v", NS)][0] == "777"


def test_the_description_of_a_chart_is_patched_into_its_frame_and_taken_out_again():
    original, baseline, current = a_kept_file()
    obj = current.objects["o1"]
    current.replace_object(replace(obj, body=replace(obj.body, description="Sales per region")))
    patched = apply_edits_to_xlsx(original, baseline, current)
    assert xlsx_to_workbook(patched).objects["o1"].body.description == "Sales per region"
    again, cleared = xlsx_to_workbook(patched), xlsx_to_workbook(patched)
    obj = cleared.objects["o1"]
    cleared.replace_object(replace(obj, body=replace(obj.body, description="")))
    assert xlsx_to_workbook(apply_edits_to_xlsx(patched, again, cleared)).objects["o1"].body.description == ""


def test_a_baseline_that_does_not_know_the_charts_of_the_file_is_refused():
    original, _, current = a_kept_file()
    plain = a_workbook_without_charts()
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_xlsx(original, plain, current)


def test_what_a_kept_file_cannot_keep_of_a_chart_is_said():
    original, baseline, current = a_kept_file()
    obj = current.objects["o1"]
    current.replace_object(replace(obj, body=replace(obj.body, rotation=30)))
    losses = LossLog()
    apply_edits_to_xlsx(original, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"chart:rotation": 1}


# -- a chart LibreOffice saved ----------------------------------------------------------------------------------------
def test_a_chart_libreoffice_saved_is_held_with_the_definition_it_has():
    original = LIBRARY.read_bytes()
    model = xlsx_to_workbook(original)
    first, second = model.diagrams["c1"], model.diagrams["c2"]
    assert (first.title, first.x_title, first.y_title, first.series_in) == ("Sales", "Region", "Euro", "columns")
    assert (second.series_in, second.legend) == ("rows", False)
    assert xlsx_import_losses(original) == ()


def test_a_chart_libreoffice_saved_is_moved_and_resized_without_being_drawn_again():
    original = LIBRARY.read_bytes()
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    obj = current.objects["o1"]
    current.replace_object(VisualObject(replace(obj.body, w=600, h=240), CellAnchor(S1, 12, 1)))
    losses = LossLog()
    patched = apply_edits_to_xlsx(original, baseline, current, losses=losses)
    assert losses.result() == ()
    before, after = read_parts(original), read_parts(patched)
    chart = next(name for name in before if name.startswith("xl/charts/chart"))
    assert after[chart] == before[chart]
    found = xlsx_to_workbook(patched).objects["o1"]
    assert (found.anchor, found.body.w, found.body.h) == (CellAnchor(S1, 12, 1), 600, 240)


def test_a_chart_libreoffice_saved_is_drawn_our_way_when_its_definition_changed_and_that_is_said():
    original = LIBRARY.read_bytes()
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    current.diagrams.replace(replace(current.diagrams["c1"], title="Changed"))
    losses = LossLog()
    patched = apply_edits_to_xlsx(original, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"chart:look": 1}
    assert xlsx_to_workbook(patched).diagrams["c1"].title == "Changed"


def test_a_chart_libreoffice_saved_whose_numbers_changed_keeps_its_own_drawing():
    original = LIBRARY.read_bytes()
    baseline, current = xlsx_to_workbook(original), xlsx_to_workbook(original)
    current.store(current.sheets[S1], 1, 1, {"t": "int", "v": 5})
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_xlsx(original, baseline, current)
    before, after = read_parts(original), read_parts(patched)
    assert [after[n] for n in after if n.startswith("xl/charts/")] == [
        before[n] for n in before if n.startswith("xl/charts/")
    ]
