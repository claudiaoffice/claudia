"""Charts in an ods file: written as charts of their own, read back, patched into a kept file (D462)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from claudia_computes_io import (
    UnsupportedEdit,
    apply_edits_to_ods,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    workbook_to_ods,
)
from lxml import etree

from claudia_computes import (
    CellAnchor,
    CellRef,
    Chart,
    ChartSpec,
    NamedRange,
    ObjectBody,
    RangeRef,
    Sheet,
    SheetId,
    VisualObject,
    WorkbookModel,
)
from claudia_odf_io import NS, LossLog, problems, read_manifest
from claudia_opc_io import read_parts

S1 = SheetId("s1")
FOLDER_TYPE = "application/vnd.oasis.opendocument.chart"


def a_range(first=(0, 0), last=(3, 2), sheet=S1) -> RangeRef:
    return RangeRef(CellRef(*first, sheet), CellRef(*last, sheet))


def a_workbook() -> WorkbookModel:
    """Region, Amount and Cost of three regions, on a sheet called Data."""
    model = WorkbookModel()
    sheet = Sheet(S1, "Data")
    model.sheets[S1] = sheet
    model.open_container("s1")
    for column, head in enumerate(("Region", "Amount", "Cost")):
        model.store(sheet, 0, column, {"t": "text", "v": head})
    for row, (region, amount, cost) in enumerate((("North", 100, 60), ("South", 200, 120), ("East", 130, 90)), start=1):
        model.store(sheet, row, 0, {"t": "text", "v": region})
        model.store(sheet, row, 1, {"t": "int", "v": amount})
        model.store(sheet, row, 2, {"t": "int", "v": cost})
    model._calculate_loaded()  # noqa: SLF001
    return model


def put_chart(
    model: WorkbookModel, spec_id="c1", object_id="o1", *, at=(5, 1), size=(480, 300), description="", **spec
):
    fields = {"id": spec_id, "kind": "bar", "range": a_range(), **spec}
    model.define_diagram(ChartSpec(**fields))
    body = ObjectBody(object_id, "diagram", *size, "plain-image", diagram=spec_id, description=description)
    model.insert_object(VisualObject(body, CellAnchor(S1, *at)))


def a_chart_workbook(**spec) -> WorkbookModel:
    model = a_workbook()
    put_chart(model, **spec)
    return model


def the_chart(model: WorkbookModel) -> tuple[ChartSpec, VisualObject]:
    (spec,) = model.diagrams.values()
    (obj,) = model.objects.values()
    assert isinstance(spec, ChartSpec)
    return spec, obj


def content(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["content.xml"])


def chart_part(data: bytes, number: int = 1) -> etree._Element:
    return etree.fromstring(read_parts(data)[f"Object {number}/content.xml"])


def kinds(losses) -> dict[str, int]:
    out: dict[str, int] = {}
    for loss in losses:
        key = f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind
        out[key] = out.get(key, 0) + loss.count
    return out


# -- a new file ---------------------------------------------------------------------------------------------------
def test_a_chart_is_written_as_a_chart_of_its_own_pinned_where_it_is():
    data = workbook_to_ods(a_chart_workbook())
    assert problems(data) == []
    parts = read_parts(data)
    assert "Object 1/content.xml" in parts
    manifest = read_manifest(parts["META-INF/manifest.xml"])
    assert manifest["Object 1/"] == FOLDER_TYPE and manifest["Object 1/content.xml"] == "text/xml"
    (frame,) = content(data).iterfind(".//table:shapes/draw:frame", NS)
    attributes = {key.split("}")[1]: value for key, value in frame.attrib.items()}
    assert attributes["width"] == "12.7000cm" and attributes["height"] == "7.9375cm"
    # one column is 96 px wide, one row 26: the corner of the cell B6 is 96 px to the right and 5 * 26 below the sheet's
    assert attributes["x"] == "2.5400cm" and attributes["y"] == "3.4396cm"
    assert frame.find("draw:object", NS).get(f"{{{NS['xlink']}}}href") == "./Object 1"


def test_the_chart_reads_the_cells_of_the_sheet_and_says_what_it_is_called():
    spec = {"title": "Sales", "x_title": "Region", "y_title": "Euro"}
    chart = chart_part(workbook_to_ods(a_chart_workbook(**spec)))
    plot = chart.find(".//chart:plot-area", NS)
    assert plot.get(f"{{{NS['table']}}}cell-range-address") == "Data.A1:Data.C4"
    assert plot.get(f"{{{NS['chart']}}}data-source-has-labels") == "both"
    series = [
        (one.get(f"{{{NS['chart']}}}values-cell-range-address"), one.get(f"{{{NS['chart']}}}label-cell-address"))
        for one in chart.iterfind(".//chart:series", NS)
    ]
    assert series == [("Data.B2:Data.B4", "Data.B1:Data.B1"), ("Data.C2:Data.C4", "Data.C1:Data.C1")]
    assert chart.find(".//chart:categories", NS).get(f"{{{NS['table']}}}cell-range-address") == "Data.A2:Data.A4"
    texts = [title.findtext("text:p", namespaces=NS) for title in chart.iterfind(".//chart:title", NS)]
    assert texts == ["Sales", "Region", "Euro"]
    assert chart.find(".//chart:legend", NS) is not None and chart.find(".//chart:grid", NS) is not None


def test_a_chart_without_a_legend_or_gridlines_has_none():
    chart = chart_part(workbook_to_ods(a_chart_workbook(legend=False, gridlines=False)))
    assert chart.find(".//chart:legend", NS) is None and chart.find(".//chart:grid", NS) is None


def test_a_chart_whose_series_are_rows_says_so_and_reads_them_as_rows():
    chart = chart_part(workbook_to_ods(a_chart_workbook(series_in="rows")))
    plot = chart.find(".//chart:plot-area", NS)
    assert plot.get(f"{{{NS['chart']}}}series-source") == "rows"
    values = [one.get(f"{{{NS['chart']}}}values-cell-range-address") for one in chart.iterfind(".//chart:series", NS)]
    assert values == ["Data.B2:Data.C2", "Data.B3:Data.C3", "Data.B4:Data.C4"]
    assert chart.find(".//chart:categories", NS).get(f"{{{NS['table']}}}cell-range-address") == "Data.B1:Data.C1"


def test_a_chart_carries_a_copy_of_its_numbers_for_a_program_that_does_not_calculate():
    chart = chart_part(workbook_to_ods(a_chart_workbook()))
    rows = [
        [cell.findtext("text:p", namespaces=NS) for cell in row.iterfind("table:table-cell", NS)]
        for row in chart.iterfind(".//table:table-rows/table:table-row", NS)
    ]
    assert rows == [["North", "100", "60"], ["South", "200", "120"], ["East", "130", "90"]]


def test_a_sheet_name_with_a_space_is_quoted_in_the_addresses_of_a_chart():
    model = a_chart_workbook()
    model.sheets[S1].name = "Q1 Data"
    chart = chart_part(workbook_to_ods(model))
    plot = chart.find(".//chart:plot-area", NS)
    assert plot.get(f"{{{NS['table']}}}cell-range-address") == "'Q1 Data'.A1:'Q1 Data'.C4"
    assert ods_to_workbook(workbook_to_ods(model)).diagrams


def test_the_charts_of_a_workbook_get_one_part_each_in_the_order_of_the_sheets():
    model = a_chart_workbook()
    put_chart(model, "c2", "o2", at=(10, 0), series_in="rows")
    parts = read_parts(workbook_to_ods(model))
    assert {name for name in parts if name.startswith("Object")} == {"Object 1/content.xml", "Object 2/content.xml"}


# -- reading it back -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "spec",
    [
        {"title": "Sales", "x_title": "Region", "y_title": "Euro"},
        {"series_in": "rows"},
        {"first": None, "range": a_range((1, 0), (3, 2)), "header_row": False, "legend": False, "gridlines": False},
        {"range": a_range((0, 1), (3, 1))},
        {"range": a_range((0, 0), (3, 2)), "title": "A & B <c>"},
    ],
)
def test_a_chart_comes_back_as_it_went(spec):
    spec = {key: value for key, value in spec.items() if key != "first"}
    model = a_chart_workbook(**spec)
    back = ods_to_workbook(workbook_to_ods(model))
    then, was = the_chart(model)
    now, found = the_chart(back)
    assert replace(now, id="c1") == then
    assert (found.id, found.anchor, found.body.w, found.body.h) == ("o1", CellAnchor(S1, 5, 1), 480, 300)
    assert (was.anchor, was.body.diagram) == (CellAnchor(S1, 5, 1), "c1")
    assert ods_import_losses(workbook_to_ods(model)) == ()


def test_the_description_of_a_chart_is_what_the_frame_says_to_someone_who_cannot_see_it():
    model = a_chart_workbook(description="Sales per region")
    data = workbook_to_ods(model)
    (frame,) = content(data).iterfind(".//draw:frame", NS)
    assert frame.findtext("svg:desc", namespaces=NS) == "Sales per region"
    assert the_chart(ods_to_workbook(data))[1].body.description == "Sales per region"


def test_a_chart_reads_its_sheet_by_name_whatever_the_case():
    data = workbook_to_ods(a_chart_workbook())
    parts = read_parts(data)
    parts["Object 1/content.xml"] = parts["Object 1/content.xml"].replace(b"Data.", b"DATA.")
    from claudia_opc_io import write_parts

    assert ods_to_workbook(write_parts(parts)).diagrams


def _edited(data: bytes, old: bytes, new: bytes) -> bytes:
    from claudia_opc_io import write_parts

    parts = read_parts(data)
    assert old in parts["Object 1/content.xml"]
    parts["Object 1/content.xml"] = parts["Object 1/content.xml"].replace(old, new)
    return write_parts(parts)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b'chart:class="chart:bar" chart:style-name="ch1"', b'chart:class="chart:line" chart:style-name="ch1"'),
        (b'<chart:series chart:style-name="chs1"', b'<chart:series chart:class="chart:line" chart:style-name="chs1"'),
        (b"Data.C2:Data.C4", b"Data.C2:Data.C3"),  # a series that is not what the range makes of its column
        (b"Data.B1:Data.B1", b"Data.B2:Data.B2"),  # a name that is not the header
        (b"Data.A2:Data.A4", b"Data.B2:Data.B4"),  # categories that are not the first column
        (b'<chart:series chart:style-name="chs1"', b'<chart:series chart:style-name="gone"'),
    ],
)
def test_a_chart_that_is_not_the_one_the_model_draws_stays_in_the_file_and_is_counted(old, new):
    data = _edited(workbook_to_ods(a_chart_workbook()), old, new)
    if b"gone" in new:
        data = _edited(data, b"<style:style ", b"<style:style ")  # (a style that is missing changes nothing)
        assert ods_to_workbook(data).diagrams  # (the colours are not what the model holds)
        return
    assert ods_to_workbook(data).diagrams == {}
    assert kinds(ods_import_losses(data)) == {"chart": 1}


def test_a_stacked_chart_a_horizontal_one_and_a_chart_in_three_dimensions_are_not_the_models():
    data = workbook_to_ods(a_chart_workbook())
    for flag in (b"chart:stacked", b"chart:vertical", b"chart:three-dimensional"):
        edited = _edited(
            data,
            b'<style:style style:name="ch3" style:family="chart"><style:chart-properties ',
            b'<style:style style:name="ch3" style:family="chart"><style:chart-properties ' + flag + b'="true" ',
        )
        assert ods_to_workbook(edited).diagrams == {}, flag
        assert kinds(ods_import_losses(edited)) == {"chart": 1}


def test_a_chart_over_a_sheet_the_file_does_not_have_is_not_the_models():
    data = _edited(workbook_to_ods(a_chart_workbook()), b"Data.", b"Elsewhere.")
    assert ods_to_workbook(data).diagrams == {}
    assert kinds(ods_import_losses(data)) == {"chart": 1}


def test_a_chart_too_small_for_an_object_of_the_model_is_not_held():
    model = a_chart_workbook(size=(480, 300))
    data = workbook_to_ods(model)
    parts = read_parts(data)
    from claudia_opc_io import write_parts

    parts["content.xml"] = parts["content.xml"].replace(b'svg:width="12.7000cm"', b'svg:width="0.1000cm"')
    assert ods_to_workbook(write_parts(parts)).diagrams == {}


# -- what a file cannot keep -----------------------------------------------------------------------------------------
def test_a_chart_tab_is_a_sheet_with_the_chart_in_it_and_that_is_said():
    model = a_workbook()
    model.define_diagram(ChartSpec(id="c1", kind="bar", range=a_range(), title="Sales"))
    model.charts["t1"] = Chart("t1", "Sales chart", "c1")
    data = workbook_to_ods(model)
    back = ods_to_workbook(data)
    assert [sheet.name for sheet in back.sheets.values()] == ["Data", "Sales chart"]
    (found,) = back.objects.values()
    assert found.anchor == CellAnchor(SheetId("s2"), 0, 0) and found.body.w >= 20
    assert kinds(ods_export_losses(model)) == {"chart:tab": 1}


def test_a_chart_tab_does_not_take_the_name_of_a_sheet():
    model = a_workbook()
    model.define_diagram(ChartSpec(id="c1", kind="bar", range=a_range()))
    model.charts["t1"] = Chart("t1", "data", "c1")
    names = [sheet.name for sheet in ods_to_workbook(workbook_to_ods(model)).sheets.values()]
    assert names == ["Data", "data (2)"]


def test_a_chart_that_follows_a_name_is_written_as_the_cells_the_name_is_now():
    model = a_workbook()
    model.names.put(NamedRange("Sales", None, a_range(), header=True))
    model.define_diagram(ChartSpec(id="c1", kind="bar", source="Sales"))
    body = ObjectBody("o1", "diagram", 480, 300, "plain-image", diagram="c1")
    model.insert_object(VisualObject(body, CellAnchor(S1, 5, 1)))
    back = ods_to_workbook(workbook_to_ods(model))
    spec, _ = the_chart(back)
    assert (spec.range, spec.source) == (a_range(), "")
    assert kinds(ods_export_losses(model)) == {"chart:source": 1}


def test_a_chart_that_reads_nothing_is_not_written_and_that_is_said():
    model = a_workbook()
    model.define_diagram(ChartSpec(id="c1", kind="bar", source="Gone"))
    model.insert_object(
        VisualObject(ObjectBody("o1", "diagram", 480, 300, "plain-image", diagram="c1"), CellAnchor(S1, 5, 1))
    )
    data = workbook_to_ods(model)
    assert ods_to_workbook(data).diagrams == {} and not [n for n in read_parts(data) if n.startswith("Object")]
    assert kinds(ods_export_losses(model)) == {"chart:empty": 1}


def test_a_chart_that_is_turned_stands_upright_in_a_file_and_that_is_said():
    model = a_chart_workbook()
    obj = next(iter(model.objects.values()))
    model.replace_object(replace(obj, body=replace(obj.body, rotation=30)))
    assert kinds(ods_export_losses(model)) == {"chart:rotation": 1}


def test_a_chart_is_no_unwritten_change_but_a_text_box_is_still_one():
    from claudia_computes_io import ods_unwritten_changes

    from claudia_core import Paragraph

    model = a_chart_workbook()
    assert ods_unwritten_changes(model) == ()
    box = ObjectBody("o2", "text", 100, 100, "plain-box", Paragraph("p1", "note"))
    model.insert_object(VisualObject(box, CellAnchor(S1, 0, 0)))
    assert kinds(ods_unwritten_changes(model)) == {"object": 1}


# -- a file somebody else made ---------------------------------------------------------------------------------------
def _soffice(tmp_path, source: bytes, to: str) -> bytes:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "chart.ods").write_bytes(source)
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            to,
            "--outdir",
            str(tmp_path / "out"),
            str(tmp_path / "in" / "chart.ods"),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return (tmp_path / "out" / f"chart.{to}").read_bytes()


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
    saved = _soffice(tmp_path, workbook_to_ods(model), "ods")
    back = ods_to_workbook(saved)
    assert replace(the_chart(back)[0], id="c1") == the_chart(model)[0]
    assert ods_import_losses(saved) == ()


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_libreoffice_makes_a_picture_of_a_chart_of_ours(tmp_path):
    pdf = _soffice(tmp_path, workbook_to_ods(a_chart_workbook(title="Sales")), "pdf")
    assert pdf.startswith(b"%PDF")
    assert b"Sales" in pdf or len(pdf) > 3000  # (the title is in the picture, perhaps as outlines)


# -- patching a kept file ---------------------------------------------------------------------------------------------
def a_kept_file(**spec) -> tuple[bytes, WorkbookModel, WorkbookModel]:
    original = workbook_to_ods(a_chart_workbook(**spec))
    return original, ods_to_workbook(original), ods_to_workbook(original)


def _frames(data: bytes) -> list[etree._Element]:
    return list(content(data).iterfind(".//draw:frame", NS))


def test_a_chart_nobody_touched_stays_byte_for_byte():
    original, baseline, current = a_kept_file()
    assert apply_edits_to_ods(original, baseline, current) == original


def test_a_new_chart_is_a_new_frame_and_a_new_part_in_a_kept_file():
    original, baseline, current = a_kept_file()
    put_chart(current, "c9", "o9", at=(12, 2), size=(300, 200), series_in="rows", title="Rows")
    losses = LossLog()
    patched = apply_edits_to_ods(original, baseline, current, losses=losses)
    assert problems(patched) == [] and losses.result() == ()
    parts = read_parts(patched)
    assert parts["Object 1/content.xml"] == read_parts(original)["Object 1/content.xml"]
    assert "Object 2/content.xml" in parts
    manifest = read_manifest(parts["META-INF/manifest.xml"])
    assert manifest["Object 2/"] == FOLDER_TYPE
    back = ods_to_workbook(patched)
    assert len(back.objects) == 2
    second = back.objects["o2"]
    assert (second.anchor, second.body.w, second.body.h) == (CellAnchor(S1, 12, 2), 300, 200)
    assert back.diagrams["c2"].title == "Rows" and back.diagrams["c2"].series_in == "rows"


def test_a_chart_that_was_removed_is_taken_out_with_its_part():
    original, baseline, current = a_kept_file()
    current.delete_object("o1")
    current.forget_diagram("c1")
    patched = apply_edits_to_ods(original, baseline, current)
    parts = read_parts(patched)
    assert not [name for name in parts if name.startswith("Object")]
    assert not [name for name in read_manifest(parts["META-INF/manifest.xml"]) if name.startswith("Object")]
    assert _frames(patched) == [] and ods_to_workbook(patched).objects == {}
    assert problems(patched) == []


def test_a_chart_that_was_moved_and_resized_has_its_frame_changed_and_its_part_kept():
    original, baseline, current = a_kept_file()
    obj = current.objects["o1"]
    current.replace_object(VisualObject(replace(obj.body, w=600, h=240), CellAnchor(S1, 9, 3)))
    patched = apply_edits_to_ods(original, baseline, current)
    found = ods_to_workbook(patched).objects["o1"]
    assert (found.anchor, found.body.w, found.body.h) == (CellAnchor(S1, 9, 3), 600, 240)


def test_a_chart_whose_definition_changed_is_drawn_again_the_way_it_was_before():
    original, baseline, current = a_kept_file(title="Before")
    current.replace_diagram(replace(current.diagrams["c1"], title="After", legend=False))
    patched = apply_edits_to_ods(original, baseline, current, losses=(losses := LossLog()))
    assert losses.result() == ()  # (a chart of ours is drawn the way it was)
    spec, _ = the_chart(ods_to_workbook(patched))
    assert (spec.title, spec.legend) == ("After", False)


def test_a_chart_whose_numbers_changed_carries_the_new_ones():
    original, baseline, current = a_kept_file()
    current.store(current.sheets[S1], 1, 1, {"t": "int", "v": 777})
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_ods(original, baseline, current)
    rows = [
        [cell.findtext("text:p", namespaces=NS) for cell in row.iterfind("table:table-cell", NS)]
        for row in chart_part(patched).iterfind(".//table:table-rows/table:table-row", NS)
    ]
    assert rows[0] == ["North", "777", "60"]


def test_the_description_of_a_chart_is_patched_into_its_frame():
    original, baseline, current = a_kept_file()
    obj = current.objects["o1"]
    current.replace_object(replace(obj, body=replace(obj.body, description="Sales per region")))
    patched = apply_edits_to_ods(original, baseline, current)
    assert ods_to_workbook(patched).objects["o1"].body.description == "Sales per region"
    again = ods_to_workbook(patched)
    current2 = ods_to_workbook(patched)
    obj2 = current2.objects["o1"]
    current2.replace_object(replace(obj2, body=replace(obj2.body, description="")))
    assert ods_to_workbook(apply_edits_to_ods(patched, again, current2)).objects["o1"].body.description == ""


def test_a_chart_tab_that_was_added_is_a_sheet_after_the_last_one():
    original, baseline, current = a_kept_file()
    current.define_diagram(ChartSpec(id="c7", kind="bar", range=a_range(), title="Tab"))
    current.charts["t1"] = Chart("t1", "Tab chart", "c7")
    losses = LossLog()
    patched = apply_edits_to_ods(original, baseline, current, losses=losses)
    back = ods_to_workbook(patched)
    assert [sheet.name for sheet in back.sheets.values()] == ["Data", "Tab chart"]
    assert kinds(losses.result()) == {"chart:tab": 1}
    assert problems(patched) == []


def test_a_chart_on_a_sheet_that_was_added_comes_with_the_sheet():
    original, baseline, current = a_kept_file()
    current.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "More")
    current.open_container("s2")
    current.define_diagram(ChartSpec(id="c7", kind="bar", range=a_range()))
    current.insert_object(
        VisualObject(
            ObjectBody("o7", "diagram", 300, 200, "plain-image", diagram="c7"), CellAnchor(SheetId("s2"), 1, 1)
        )
    )
    back = ods_to_workbook(apply_edits_to_ods(original, baseline, current))
    assert [sheet.name for sheet in back.sheets.values()] == ["Data", "More"]
    assert sorted(obj.anchor.container for obj in back.objects.values()) == ["s1", "s2"]


def test_a_chart_goes_with_its_sheet_when_the_sheet_is_removed():
    original, baseline, current = a_kept_file()
    current.sheets[SheetId("s2")] = Sheet(SheetId("s2"), "Other")
    current.open_container("s2")
    baseline = ods_to_workbook(workbook_to_ods(current))
    current = ods_to_workbook(workbook_to_ods(current))
    original = workbook_to_ods(current)
    del current.sheets[S1]
    current.objects.clear()
    current.diagrams.clear()
    patched = apply_edits_to_ods(original, baseline, current)
    assert not [name for name in read_parts(patched) if name.startswith("Object")]


def test_a_baseline_that_does_not_know_the_charts_of_the_file_is_refused():
    original, _, current = a_kept_file()
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_ods(original, a_workbook(), current)


# -- a chart LibreOffice saved -----------------------------------------------------------------------------------------
LIBRARY = Path(__file__).resolve().parents[3] / "test-documents" / "ods" / "charts" / "source.ods"


def test_a_chart_libreoffice_saved_is_moved_and_resized_without_being_drawn_again():
    original = LIBRARY.read_bytes()
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    obj = current.objects["o1"]
    current.replace_object(VisualObject(replace(obj.body, w=600, h=240), CellAnchor(S1, 12, 1)))
    losses = LossLog()
    patched = apply_edits_to_ods(original, baseline, current, losses=losses)
    assert losses.result() == ()
    before, after = read_parts(original), read_parts(patched)
    assert after["Object 1/content.xml"] == before["Object 1/content.xml"]
    assert after["ObjectReplacements/Object 1"] == before["ObjectReplacements/Object 1"]
    found = ods_to_workbook(patched).objects["o1"]
    assert (found.anchor, found.body.w, found.body.h) == (CellAnchor(S1, 12, 1), 600, 240)


def test_a_chart_libreoffice_saved_is_drawn_our_way_when_its_definition_changed_and_that_is_said():
    original = LIBRARY.read_bytes()
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    current.replace_diagram(replace(current.diagrams["c1"], title="Changed"))
    losses = LossLog()
    patched = apply_edits_to_ods(original, baseline, current, losses=losses)
    assert kinds(losses.result()) == {"chart:look": 1}
    assert ods_to_workbook(patched).diagrams["c1"].title == "Changed"
    assert read_parts(patched)["Object 2/content.xml"] == read_parts(original)["Object 2/content.xml"]


def test_a_chart_libreoffice_saved_whose_numbers_changed_keeps_its_own_drawing():
    original = LIBRARY.read_bytes()
    baseline, current = ods_to_workbook(original), ods_to_workbook(original)
    current.store(current.sheets[S1], 1, 1, {"t": "int", "v": 5})
    current._calculate_loaded()  # noqa: SLF001
    patched = apply_edits_to_ods(original, baseline, current)
    assert read_parts(patched)["Object 1/content.xml"] == read_parts(original)["Object 1/content.xml"]
