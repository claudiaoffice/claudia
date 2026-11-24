"""Pictures floating on a sheet, written to xlsx and ods (D1233): a picture, and a container's picture, pinned
to its cell, with its size, turn, name and what it says to someone who cannot see it. Computes has no text boxes and
shapes (D1232), so these two kinds stay unwritten and are reported."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from claudia_computes_io import (
    apply_edits_to_ods,
    apply_edits_to_xlsx,
    ods_export_losses,
    ods_import_losses,
    ods_to_workbook,
    ods_unwritten_changes,
    workbook_to_ods,
    workbook_to_xlsx,
    xlsx_export_losses,
    xlsx_import_losses,
    xlsx_to_workbook,
    xlsx_unwritten_changes,
)
from lxml import etree
from test_ods_charts import S1, a_workbook, put_chart

from claudia_computes import CellAnchor, ObjectBody, VisualObject, WorkbookModel
from claudia_core import ContainerDefinition, ImageAsset, ImageImport, Paragraph, blank_png, decode_image
from claudia_odf_io import NS as ODF
from claudia_odf_io import Loss, problems, read_manifest
from claudia_opc_io import read_parts

XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
X = {"xdr": XDR, "a": A, "r": R}
_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20" viewBox="0 0 40 20">'
    b'<rect width="40" height="20"/></svg>'
)
EMU = 9525


def a_png(width: int = 40, height: int = 20) -> ImageAsset:
    return decode_image(blank_png(width, height))


def an_svg() -> ImageAsset:
    return decode_image(_SVG)


def an_import(asset_id: str) -> ImageImport:
    return ImageImport.from_data(
        {
            "asset": asset_id,
            "alt": "",
            "imported_by": "ana",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.png",
            "source_path": None,
        }
    )


def put_picture(
    model: WorkbookModel, asset: ImageAsset | None = None, object_id: str = "p1", *, at=(2, 1), size=(200, 100), **body
) -> ImageAsset:
    asset = asset or a_png()
    if asset.id not in model.images:
        model.images.define(asset)
    fields = {"style": "plain-image", "ref": asset.id, "imported": an_import(asset.id), **body}
    model.insert_object(VisualObject(ObjectBody(object_id, "image", *size, **fields), CellAnchor(S1, *at)))
    return asset


def drawing(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["xl/drawings/drawing1.xml"])


def pictures_of(data: bytes) -> list[etree._Element]:
    return drawing(data).findall(".//xdr:pic", X)


def kinds(losses) -> dict[str, int]:
    out: dict[str, int] = {}
    for loss in losses:
        key = f"{loss.kind}:{loss.detail}" if loss.detail else loss.kind
        out[key] = out.get(key, 0) + loss.count
    return out


# ------------------------------------------------------------------------------------------------------------ xlsx
def test_xlsx_a_picture_is_pinned_to_its_cell_with_its_size_and_its_bytes():
    model = a_workbook()
    asset = put_picture(model, at=(2, 1), size=(200, 100))
    data = workbook_to_xlsx(model)
    (anchor,) = drawing(data).findall("xdr:oneCellAnchor", X)
    assert [anchor.findtext(f"xdr:from/xdr:{n}", namespaces=X) for n in ("col", "row")] == ["1", "2"]
    extent = anchor.find("xdr:ext", X)
    assert (extent.get("cx"), extent.get("cy")) == (str(200 * EMU), str(100 * EMU))
    rid = anchor.find(".//a:blip", X).get(f"{{{R}}}embed")
    rels = etree.fromstring(read_parts(data)["xl/drawings/_rels/drawing1.xml.rels"])
    (target,) = [r.get("Target") for r in rels if r.get("Id") == rid]
    assert read_parts(data)["xl/media/" + target.rsplit("/", 1)[1]] == asset.data
    assert b'Extension="png"' in read_parts(data)["[Content_Types].xml"]


def test_xlsx_the_picture_opens_in_openpyxl_too():
    import openpyxl

    model = a_workbook()
    put_picture(model)
    sheet = openpyxl.load_workbook(BytesIO(workbook_to_xlsx(model)))["Data"]
    assert len(sheet._images) == 1  # noqa: SLF001


def test_xlsx_an_upright_picture_has_no_turn_and_a_turned_one_has_it_in_sixty_thousandths_of_a_degree():
    model = a_workbook()
    put_picture(model, object_id="p1")
    put_picture(model, object_id="p2", at=(8, 1), rotation=30)
    upright, turned = pictures_of(workbook_to_xlsx(model))
    assert upright.find("xdr:spPr/a:xfrm", X).get("rot") is None
    assert turned.find("xdr:spPr/a:xfrm", X).get("rot") == "1800000"


def test_xlsx_the_name_and_what_it_says_are_kept_and_a_decorative_picture_says_so():
    model = a_workbook()
    put_picture(model, object_id="p1", name="Logo", description="The company's logo")
    put_picture(model, object_id="p2", at=(9, 1), decorative=True)
    seen, flourish = (p.find("xdr:nvPicPr/xdr:cNvPr", X) for p in pictures_of(workbook_to_xlsx(model)))
    assert (seen.get("name"), seen.get("descr")) == ("Logo", "The company's logo")
    assert flourish.get("descr") == ""
    assert flourish.find(".//{http://schemas.microsoft.com/office/drawing/2017/decorative}decorative") is not None


def test_xlsx_one_asset_shown_twice_is_one_media_part():
    model = a_workbook()
    asset = put_picture(model, object_id="p1")
    put_picture(model, asset, object_id="p2", at=(9, 1))
    data = workbook_to_xlsx(model)
    assert len(pictures_of(data)) == 2
    assert [n for n in read_parts(data) if n.startswith("xl/media/")] == ["xl/media/image1.png"]


def test_xlsx_a_picture_and_a_chart_share_the_drawing_in_the_order_they_are_stacked():
    model = a_workbook()
    put_picture(model, object_id="below")
    put_chart(model, object_id="chart")
    put_picture(model, a_png(), object_id="above", at=(20, 1))
    data = workbook_to_xlsx(model)
    order = [etree.QName(e[3]).localname if len(e) > 3 else "?" for e in drawing(data)]
    assert [e.tag.rsplit("}", 1)[1] for e in drawing(data)] == ["oneCellAnchor"] * 3
    assert [c.tag.rsplit("}", 1)[1] for c in (a[2] for a in drawing(data))] == ["pic", "graphicFrame", "pic"], order


def test_xlsx_an_svg_picture_is_a_png_where_a_rasteriser_is_given_and_a_blank_one_with_the_svg_beside_it_else():
    model = a_workbook()
    svg = put_picture(model, an_svg()).data
    drawn = blank_png(40, 20) + b"drawn"
    with_one = workbook_to_xlsx(model, rasterise=lambda svg, w, h: drawn)
    assert drawn in read_parts(with_one).values()
    assert (
        pictures_of(with_one)[0].find(".//{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip") is None
    )
    without = workbook_to_xlsx(model)
    assert svg in read_parts(without).values()
    assert (
        pictures_of(without)[0].find(".//{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip")
        is not None
    )
    assert kinds(xlsx_export_losses(model)) == {"svg-fallback": 1}
    assert kinds(xlsx_export_losses(model, rasterised=True)) == {}


def test_xlsx_a_container_is_the_picture_last_made_of_it_and_one_never_drawn_is_left_out():
    model = a_workbook()
    asset = a_png()
    model.images.define(asset)
    model.containers.define(ContainerDefinition("r1", "latex", "x", image=asset.id, renderer="latex 1"))
    model.containers.define(ContainerDefinition("r2", "latex", "y"))
    for object_id, ref, at in (("c1", "r1", (2, 1)), ("c2", "r2", (9, 1))):
        model.insert_object(
            VisualObject(ObjectBody(object_id, "container", 200, 100, "plain-image", ref=ref), CellAnchor(S1, *at))
        )
    data = workbook_to_xlsx(model)
    assert len(pictures_of(data)) == 1
    assert kinds(xlsx_export_losses(model)) == {"rendering-pending": 1}


def test_xlsx_a_picture_is_written_so_it_is_no_loss_but_a_text_box_still_is():
    model = a_workbook()
    put_picture(model)
    assert xlsx_unwritten_changes(model) == ()
    box = ObjectBody("t1", "text", 100, 50, "plain-box", Paragraph("pa", "note"))
    model.insert_object(VisualObject(box, CellAnchor(S1, 0, 0)))
    assert xlsx_unwritten_changes(model) == (Loss("object", "", 1),)


def test_xlsx_a_picture_added_to_an_imported_file_is_still_reported_until_a_kept_file_is_patched():
    before = a_workbook()
    original = workbook_to_xlsx(before)
    after = a_workbook()
    put_picture(after)
    assert xlsx_unwritten_changes(after, before) == (Loss("object", "", 2),)  # (the object and the image it shows)
    assert apply_edits_to_xlsx(original, before, after) is not None


# ------------------------------------------------------------------------------------------------------------- ods
def content_of(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["content.xml"])


def frames_of(data: bytes) -> list[etree._Element]:
    return content_of(data).xpath("//table:shapes/draw:frame[draw:image]", namespaces=ODF)


def test_ods_a_picture_is_a_frame_with_an_image_in_the_shapes_of_its_sheet_and_its_bytes_are_a_part():
    model = a_workbook()
    asset = put_picture(model, at=(2, 1), size=(200, 100))
    data = workbook_to_ods(model)
    (frame,) = frames_of(data)
    href = frame.find("draw:image", ODF).get(f"{{{ODF['xlink']}}}href")
    assert read_parts(data)[href] == asset.data
    assert read_manifest(read_parts(data)["META-INF/manifest.xml"])[href] == "image/png"
    assert problems(data) == []
    assert frame.get(f"{{{ODF['svg']}}}width") == "5.2917cm"
    assert frame.get(f"{{{ODF['svg']}}}x") is not None


def test_ods_a_turned_picture_has_a_transform_and_no_place_of_its_own():
    model = a_workbook()
    put_picture(model, object_id="p1")
    put_picture(model, object_id="p2", at=(8, 1), rotation=90)
    upright, turned = frames_of(workbook_to_ods(model))
    assert upright.get(f"{{{ODF['draw']}}}transform") is None
    assert turned.get(f"{{{ODF['draw']}}}transform", "").startswith("rotate (")
    assert turned.get(f"{{{ODF['svg']}}}x") is None


def test_ods_the_name_and_description_are_kept_and_a_decorative_picture_is_a_loss():
    model = a_workbook()
    put_picture(model, object_id="p1", name="Logo", description="The company's logo")
    put_picture(model, object_id="p2", at=(9, 1), decorative=True)
    data = workbook_to_ods(model)
    seen, flourish = frames_of(data)
    assert seen.get(f"{{{ODF['draw']}}}name") == "Logo"
    assert seen.findtext("svg:desc", namespaces=ODF) == "The company's logo"
    assert flourish.find("svg:desc", ODF) is None
    assert kinds(ods_export_losses(model)) == {"decorative": 1}


def test_ods_one_asset_shown_twice_is_one_picture_part_and_charts_keep_their_numbers():
    model = a_workbook()
    asset = put_picture(model, object_id="p1")
    put_picture(model, asset, object_id="p2", at=(9, 1))
    put_chart(model, object_id="chart", at=(15, 1))
    data = workbook_to_ods(model)
    assert len(frames_of(data)) == 2
    assert [n for n in read_parts(data) if n.startswith("Pictures/")] == ["Pictures/" + asset.id + ".png"]
    assert "Object 1/content.xml" in read_parts(data)


def test_ods_an_svg_picture_is_a_png_where_a_rasteriser_is_given_and_the_svg_itself_else():
    model = a_workbook()
    svg = put_picture(model, an_svg()).data
    drawn = blank_png(40, 20) + b"drawn"
    assert drawn in read_parts(workbook_to_ods(model, rasterise=lambda svg, w, h: drawn)).values()
    assert svg in read_parts(workbook_to_ods(model)).values()
    assert kinds(ods_export_losses(model)) == {"svg-fallback": 1}
    assert kinds(ods_export_losses(model, rasterised=True)) == {}


def test_ods_a_picture_is_written_so_it_is_no_loss_but_a_text_box_still_is():
    model = a_workbook()
    put_picture(model)
    assert ods_unwritten_changes(model) == ()
    box = ObjectBody("t1", "text", 100, 50, "plain-box", Paragraph("pa", "note"))
    model.insert_object(VisualObject(box, CellAnchor(S1, 0, 0)))
    assert ods_unwritten_changes(model) == (Loss("object", "", 1),)


@pytest.mark.parametrize("write", [workbook_to_xlsx, workbook_to_ods])
def test_a_workbook_without_pictures_is_written_as_before(write):
    model = a_workbook()
    assert replace is not None and write(model)  # (no drawing, no pictures part)
    assert "xl/media" not in "".join(read_parts(write(model))) and not [
        n for n in read_parts(write(model)) if n.startswith(("xl/media/", "Pictures/"))
    ]


# --------------------------------------------------------------------------------------- a picture of a file (CODE-67)
@pytest.mark.parametrize("fmt", ["xlsx", "ods"])
def test_a_picture_of_a_file_is_read_in_and_written_back_where_it_was(fmt):
    write, read, import_losses = {
        "xlsx": (workbook_to_xlsx, xlsx_to_workbook, xlsx_import_losses),
        "ods": (workbook_to_ods, ods_to_workbook, ods_import_losses),
    }[fmt]
    model = a_workbook()
    asset = put_picture(model, at=(2, 2), size=(200, 100), rotation=15, name="Logo", description="Our logo")
    data = write(model)
    again = read(data)
    (picture,) = [obj for obj in again.objects.values() if obj.body.kind == "image"]
    assert (picture.anchor.sheet, picture.anchor.row, picture.anchor.col) == (S1, 2, 2)
    body = picture.body
    assert (body.w, body.h, body.rotation, body.description) == (200, 100, 15, "Our logo")
    assert again.images[body.ref].data == asset.data
    assert "picture" not in kinds(import_losses(data))
    if fmt == "xlsx":
        (anchor,) = drawing(write(again)).findall("xdr:oneCellAnchor", X)
        assert [anchor.findtext(f"xdr:from/xdr:{n}", namespaces=X) for n in ("col", "row")] == ["2", "2"]
    else:
        (frame,) = frames_of(write(again))
        assert frame.get(f"{{{ODF['draw']}}}transform") == frames_of(data)[0].get(f"{{{ODF['draw']}}}transform")


@pytest.mark.parametrize("fmt", ["xlsx", "ods"])
def test_a_picture_of_a_file_comes_in_with_the_charts_and_an_edit_keeps_it(fmt):
    write, read, patch = {
        "xlsx": (workbook_to_xlsx, xlsx_to_workbook, apply_edits_to_xlsx),
        "ods": (workbook_to_ods, ods_to_workbook, apply_edits_to_ods),
    }[fmt]
    model = a_workbook()
    put_picture(model)
    original = write(model)
    baseline, current = read(original), read(original)
    current.store(current.sheets[S1], 0, 0, {"t": "text", "v": "Area"})
    again = read(patch(original, baseline, current))
    assert [obj.body.kind for obj in again.objects.values()] == ["image"]
