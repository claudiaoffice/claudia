"""The pictures floating over a text are written to docx and odt as pictures, read back as image objects, and patched
into a kept file with their alt text (D464)."""

from __future__ import annotations

import struct
from dataclasses import replace
from io import BytesIO

import pytest
from claudia_composes_io import (
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_export_losses,
    docx_import_losses,
    docx_to_text,
    odt_export_losses,
    odt_import_losses,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)
from docx import Document
from docx.oxml.ns import qn

from claudia_composes import DEFAULT_STYLE, Block, BlockAnchor, TextModel
from claudia_core import ImageAsset, ImageImport, ObjectBody, VisualObject, decode_image
from claudia_odf_io import Loss, LossLog, problems, read_manifest
from claudia_opc_io import read_parts


def a_picture(width: int = 40, height: int = 20, shade: int = 0) -> ImageAsset:
    """A tiny, valid GIF (the shade makes its bytes differ)."""
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01" + bytes([shade]) + b"\x00"
    return decode_image(header + frame + b"\x3b")


def an_import(asset: ImageAsset) -> ImageImport:
    return ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": "",
            "imported_by": "ana",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": None,
        }
    )


def a_text(*texts: str) -> TextModel:
    return TextModel([Block(f"b{n}", DEFAULT_STYLE, text) for n, text in enumerate(texts, start=1)])


def put_picture(model: TextModel, object_id="o1", *, at=("b1", 5), size=(200, 100), shade=0, **changes) -> ImageAsset:
    asset = a_picture(shade=shade)
    model.images.define(asset)
    body = ObjectBody(object_id, "image", *size, "plain-image", ref=asset.id, imported=an_import(asset), **changes)
    model.insert_object(VisualObject(body, BlockAnchor(*at)))
    return asset


def a_picture_text(**changes) -> tuple[TextModel, ImageAsset]:
    model = a_text("Hello world", "Second paragraph")
    return model, put_picture(model, **changes)


def only(model: TextModel) -> VisualObject:
    (found,) = model.objects.values()
    return found


FORMATS = pytest.mark.parametrize(
    "to_file, to_model", [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)], ids=["docx", "odt"]
)


@FORMATS
def test_a_picture_comes_back_as_an_image_object_with_its_bytes_its_place_and_its_size(to_file, to_model):
    model, asset = a_picture_text(description="two cyclists")
    back = to_model(to_file(model))
    found = only(back)
    assert found.body.kind == "image"
    assert (found.anchor, found.body.w, found.body.h) == (BlockAnchor("b1", 5), 200, 100)
    assert found.body.description == "two cyclists"
    assert back.images[found.body.image].data == asset.data
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


@FORMATS
def test_a_picture_at_the_start_and_at_the_end_of_a_paragraph_keeps_its_place(to_file, to_model):
    model = a_text("Hello world", "Second paragraph")
    put_picture(model, "o1", at=("b1", 0))
    put_picture(model, "o2", at=("b2", 16), shade=1)
    back = to_model(to_file(model))
    assert sorted((o.anchor.block, o.anchor.offset) for o in back.objects.values()) == [("b1", 0), ("b2", 16)]


@FORMATS
def test_a_picture_in_a_paragraph_with_nothing_in_it_is_written(to_file, to_model):
    model = a_text("", "Second")
    put_picture(model, at=("b1", 0))
    assert only(to_model(to_file(model))).anchor == BlockAnchor("b1", 0)


@FORMATS
def test_two_pictures_in_one_paragraph_keep_their_order(to_file, to_model):
    model = a_text("Hello world")
    put_picture(model, "o1", at=("b1", 8), shade=0)
    put_picture(model, "o2", at=("b1", 2), shade=1)
    back = to_model(to_file(model))
    assert sorted(o.anchor.offset for o in back.objects.values()) == [2, 8]
    assert back.blocks[0].text == "Hello world"


@FORMATS
def test_a_turned_picture_stays_turned(to_file, to_model):
    model, _ = a_picture_text(rotation=30)
    assert only(to_model(to_file(model))).body.rotation == 30


def test_a_decorative_picture_comes_back_decorative_from_a_docx():
    model, _ = a_picture_text(decorative=True)
    found = only(docx_to_text(text_to_docx(model))).body
    assert (found.description, found.decorative) == ("", True)


def test_a_decorative_picture_is_written_to_an_odt_without_a_description_and_the_export_says_so():
    """ODF 1.3 has no mark for decoration: the picture comes back as one nobody described, and it is a loss."""
    model, _ = a_picture_text(decorative=True)
    found = only(odt_to_text(text_to_odt(model))).body
    assert (found.description, found.decorative) == ("", False)
    assert [(loss.kind, loss.count) for loss in odt_export_losses(model)] == [("decorative", 1)]


@FORMATS
def test_a_picture_is_not_a_loss_of_the_export(to_file, to_model):
    model, _ = a_picture_text(description="two cyclists")
    losses = docx_export_losses(model) if to_file is text_to_docx else odt_export_losses(model)
    assert losses == ()


@FORMATS
def test_the_same_picture_twice_is_one_file_in_the_package(to_file, to_model):
    model = a_text("Hello world")
    asset = put_picture(model, "o1", at=("b1", 1))
    body = ObjectBody("o2", "image", 100, 50, "plain-image", ref=asset.id, imported=an_import(asset))
    model.insert_object(VisualObject(body, BlockAnchor("b1", 3)))
    data = to_file(model)
    media = [name for name in read_parts(data) if name.startswith(("word/media/", "Pictures/"))]
    assert len(media) == 1
    back = to_model(data)
    assert len(back.objects) == 2 and len(back.images) == 1


# --------------------------------------------------------------------------------------------- a kept docx
def media(data: bytes) -> dict[str, bytes]:
    return {name: part for name, part in read_parts(data).items() if name.startswith("word/media/")}


def drawings(data: bytes) -> list:
    """The ``w:drawing`` elements of the body, in order."""
    return list(Document(BytesIO(data)).element.body.iter(qn("w:drawing")))


def patched_docx(edit, *, original: bytes | None = None, losses: LossLog | None = None):
    """The kept file (a text with two paragraphs and a picture on the first, unless ``original``) after ``edit``
    changed the model it was read as; with the model read back from the result."""
    if original is None:
        model, _ = a_picture_text(description="two cyclists")
        original = text_to_docx(model)
    baseline, current = docx_to_text(original), docx_to_text(original)
    edit(current)
    data = apply_edits_to_docx(original, baseline, current, losses=losses)
    return original, data, docx_to_text(data)


def test_a_picture_that_is_not_edited_comes_back_as_it_was_byte_for_byte():
    original, data, back = patched_docx(lambda model: None)
    assert media(data) == media(original)
    assert [etree_text(each) for each in drawings(data)] == [etree_text(each) for each in drawings(original)]
    assert only(back).anchor == BlockAnchor("b1", 5)


def etree_text(element) -> bytes:
    from lxml import etree

    return etree.tostring(element)


def test_a_new_description_is_written_into_the_drawing_and_nothing_else_changes():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="two cyclists on a hill"), found.anchor))

    original, data, back = patched_docx(edit)
    assert only(back).body.description == "two cyclists on a hill"
    assert media(data) == media(original)
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_a_picture_made_decorative_loses_its_description_and_carries_the_mark():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="", decorative=True), found.anchor))

    _, _, back = patched_docx(edit)
    assert (only(back).body.description, only(back).body.decorative) == ("", True)


def test_a_picture_moved_to_another_paragraph_and_place_is_drawn_there():
    def edit(model: TextModel) -> None:
        found = model.delete_object("o1")[0]  # (an object never changes its paragraph: it is put there anew)
        model.insert_object(VisualObject(found.body, BlockAnchor("b2", 6)))

    original, data, back = patched_docx(edit)
    assert only(back).anchor == BlockAnchor("b2", 6)
    assert media(data) == media(original)


def test_a_picture_moved_inside_its_paragraph_keeps_the_formatting_of_the_words_it_cuts():
    model = a_text("Hello world")
    put_picture(model, at=("b1", 2))
    original = text_to_docx(model)
    bold = Document(BytesIO(original))
    for run in bold.paragraphs[0].runs:
        run.bold = True
    out = BytesIO()
    bold.save(out)

    def edit(current: TextModel) -> None:
        found = only(current)
        current.replace_object(VisualObject(found.body, BlockAnchor("b1", 7)))

    _, data, back = patched_docx(edit, original=out.getvalue())
    assert only(back).anchor == BlockAnchor("b1", 7)
    runs = Document(BytesIO(data)).paragraphs[0].runs
    assert "".join(run.text for run in runs) == "Hello world"  # (the cut of the first place stays: it is only a cut)
    assert all(run.bold for run in runs if run.text)


def test_a_picture_resized_and_turned_changes_only_its_size_and_turn():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, w=400, h=200, rotation=90), found.anchor))

    original, data, back = patched_docx(edit)
    assert (only(back).body.w, only(back).body.h, only(back).body.rotation) == (400, 200, 90)
    assert media(data) == media(original)


def test_a_picture_that_is_removed_takes_its_drawing_out_of_the_file():
    def edit(model: TextModel) -> None:
        model.delete_object("o1")

    _, data, back = patched_docx(edit)
    assert back.objects == {} and drawings(data) == []
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_a_picture_added_to_a_kept_file_is_drawn_where_the_text_says():
    original = text_to_docx(a_text("Hello world", "Second paragraph"))

    def edit(model: TextModel) -> None:
        put_picture(model, "o1", at=("b2", 3), description="a new one")

    _, data, back = patched_docx(edit, original=original)
    found = only(back)
    assert (found.anchor, found.body.description) == (BlockAnchor("b2", 3), "a new one")
    assert len(media(data)) == 1
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_a_picture_follows_the_words_of_its_paragraph_when_they_change():
    def edit(model: TextModel) -> None:
        model.blocks[0] = replace(model.blocks[0], text="Hello wide world")
        found = only(model)
        model.replace_object(VisualObject(found.body, BlockAnchor("b1", 11)))

    original, data, back = patched_docx(edit)
    assert (only(back).anchor, back.blocks[0].text) == (BlockAnchor("b1", 11), "Hello wide world")
    assert media(data) == media(original)


def test_the_package_of_a_patched_file_is_the_one_of_the_original_except_for_what_changed():
    def edit(model: TextModel) -> None:
        put_picture(model, "o2", at=("b2", 1), shade=3)

    original, data, _ = patched_docx(edit)
    after, before = read_parts(data), read_parts(original)
    unchanged = set(before) - {"word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
    assert all(after[name] == before[name] for name in unchanged)
    assert len(media(data)) == 2


# ------------------------------------------------------------------------------------- a file from another program
def gif_stream(shade: int = 0, width: int = 40, height: int = 20) -> BytesIO:
    return BytesIO(a_picture(width, height, shade).data)


def a_foreign_docx(*, crop: bool = False, in_table: bool = False, size_cm=(4.0, 2.0)) -> bytes:
    """What Word makes: an *inline* picture, in a paragraph of its own or in a table, perhaps cropped."""
    from docx.shared import Cm

    document = Document()
    document.add_paragraph("Before")
    target = (
        document.add_table(rows=1, cols=1).cell(0, 0).paragraphs[0] if in_table else document.add_paragraph("Here:")
    )
    target.add_run().add_picture(gif_stream(), width=Cm(size_cm[0]), height=Cm(size_cm[1]))
    if crop:
        blip_fill = target._p.xpath(".//pic:blipFill")[0]
        from docx.oxml import parse_xml

        blip_fill.insert(
            1, parse_xml('<a:srcRect xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" l="10000"/>')
        )
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def test_an_inline_picture_of_a_file_comes_in_as_an_image_object_where_the_words_are():
    back = docx_to_text(a_foreign_docx())
    found = only(back)
    assert found.anchor == BlockAnchor("b2", 5)  # (after "Here:")
    assert (found.body.w, found.body.h) == (151, 76)  # 4 cm by 2 cm at 96 to the inch
    assert docx_import_losses(a_foreign_docx()) == ()


def test_a_cropped_picture_stays_in_the_file_and_is_listed_as_a_picture():
    data = a_foreign_docx(crop=True)
    assert docx_to_text(data).objects == {}
    assert [(loss.kind, loss.count) for loss in docx_import_losses(data)] == [("picture", 1)]


def test_a_picture_in_a_table_stays_in_the_file_and_is_listed_as_a_picture():
    data = a_foreign_docx(in_table=True)
    assert docx_to_text(data).objects == {}
    assert ("picture", 1) in [(loss.kind, loss.count) for loss in docx_import_losses(data)]


def test_a_picture_stretched_to_other_proportions_is_not_held():
    data = a_foreign_docx(size_cm=(4.0, 4.0))
    assert docx_to_text(data).objects == {}
    assert [(loss.kind, loss.count) for loss in docx_import_losses(data)] == [("picture", 1)]


def test_a_picture_the_model_does_not_hold_survives_an_edit_of_its_paragraph_and_the_one_it_holds_stays_too():
    data = a_foreign_docx(crop=True)
    baseline, current = docx_to_text(data), docx_to_text(data)
    block = current.blocks[1]
    current.blocks[1] = replace(block, text="Changed:")
    patched = apply_edits_to_docx(data, baseline, current)
    assert len(drawings(patched)) == 1
    assert media(patched) == media(data)


def test_an_edit_of_a_foreign_file_with_a_held_picture_keeps_the_picture_in_its_paragraph_after_the_new_words():
    data = a_foreign_docx()
    baseline, current = docx_to_text(data), docx_to_text(data)
    current.blocks[1] = replace(current.blocks[1], text="Now there:")
    found = only(current)
    current.replace_object(VisualObject(found.body, BlockAnchor("b2", 10)))
    patched = apply_edits_to_docx(data, baseline, current)
    back = docx_to_text(patched)
    assert (back.blocks[1].text, only(back).anchor) == ("Now there:", BlockAnchor("b2", 10))
    assert media(patched) == media(data)


def test_what_a_picture_says_in_a_file_from_another_program_becomes_its_description():
    document = Document()
    run = document.add_paragraph("x").add_run()
    run.add_picture(gif_stream())
    run._r.xpath(".//wp:docPr")[0].set("descr", "a hand-drawn bicycle")
    out = BytesIO()
    document.save(out)
    assert only(docx_to_text(out.getvalue())).body.description == "a hand-drawn bicycle"


# --------------------------------------------------------------------------------------------- a kept odt
def odt_media(data: bytes) -> dict[str, bytes]:
    return {name: part for name, part in read_parts(data).items() if name.startswith("Pictures/")}


def frames(data: bytes) -> list:
    """The ``draw:frame`` elements of the text, in order."""
    from lxml import etree

    root = etree.fromstring(read_parts(data)["content.xml"])
    return list(root.iter("{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}frame"))


def patched_odt(edit, *, original: bytes | None = None, losses: LossLog | None = None):
    """The kept file (a text with two paragraphs and a picture on the first, unless ``original``) after ``edit``
    changed the model it was read as; with the model read back from the result."""
    if original is None:
        model, _ = a_picture_text(description="two cyclists")
        original = text_to_odt(model)
    baseline, current = odt_to_text(original), odt_to_text(original)
    edit(current)
    data = apply_edits_to_odt(original, baseline, current, losses=losses)
    assert problems(data) == []
    return original, data, odt_to_text(data)


def test_an_odt_picture_that_is_not_edited_leaves_the_file_as_it_was():
    original, data, _ = patched_odt(lambda model: None)
    assert data == original


def test_a_new_description_is_written_into_the_frame_and_the_image_stays():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="two cyclists on a hill"), found.anchor))

    original, data, back = patched_odt(edit)
    assert only(back).body.description == "two cyclists on a hill"
    assert odt_media(data) == odt_media(original)
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_an_odt_picture_resized_and_turned_changes_its_size_and_turn_only():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, w=400, h=200, rotation=90), found.anchor))

    original, data, back = patched_odt(edit)
    assert (only(back).body.w, only(back).body.h, only(back).body.rotation) == (400, 200, 90)
    assert odt_media(data) == odt_media(original)


def test_an_odt_picture_moved_to_another_paragraph_is_drawn_there():
    def edit(model: TextModel) -> None:
        found = model.delete_object("o1")[0]
        model.insert_object(VisualObject(found.body, BlockAnchor("b2", 6)))

    _, data, back = patched_odt(edit)
    assert only(back).anchor == BlockAnchor("b2", 6)
    assert len(frames(data)) == 1


def test_an_odt_picture_moved_inside_its_paragraph_keeps_the_words():
    _, data, back = patched_odt(
        lambda model: model.replace_object(VisualObject(only(model).body, BlockAnchor("b1", 8)))
    )
    assert (only(back).anchor, back.blocks[0].text) == (BlockAnchor("b1", 8), "Hello world")


def test_an_odt_picture_that_is_removed_takes_its_frame_and_its_image_out_of_the_file():
    _, data, back = patched_odt(lambda model: model.delete_object("o1"))
    assert back.objects == {} and frames(data) == []
    assert odt_media(data) == {}
    assert not [
        name for name in read_manifest(read_parts(data)["META-INF/manifest.xml"]) if name.startswith("Pictures/")
    ]
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_a_picture_added_to_a_kept_odt_is_drawn_where_the_text_says_and_its_image_is_listed():
    original = text_to_odt(a_text("Hello world", "Second paragraph"))
    _, data, back = patched_odt(
        lambda model: put_picture(model, "o1", at=("b2", 3), description="a new one"), original=original
    )
    found = only(back)
    assert (found.anchor, found.body.description) == (BlockAnchor("b2", 3), "a new one")
    (name,) = odt_media(data)
    assert read_manifest(read_parts(data)["META-INF/manifest.xml"])[name] == "image/gif"
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_an_odt_picture_follows_the_words_of_its_paragraph_when_they_change():
    def edit(model: TextModel) -> None:
        model.blocks[0] = replace(model.blocks[0], text="Hello wide world")
        model.replace_object(VisualObject(only(model).body, BlockAnchor("b1", 11)))

    original, data, back = patched_odt(edit)
    assert (only(back).anchor, back.blocks[0].text) == (BlockAnchor("b1", 11), "Hello wide world")
    assert odt_media(data) == odt_media(original)


def test_an_odt_picture_whose_image_is_swapped_for_another_leaves_one_image_behind():
    def edit(model: TextModel) -> None:
        found = model.delete_object("o1")[0]
        put_picture(model, "o2", at=(found.anchor.block, found.anchor.offset), shade=5)

    original, data, back = patched_odt(edit)
    assert len(odt_media(data)) == 1 and odt_media(data) != odt_media(original)
    assert only(back).anchor == BlockAnchor("b1", 5)


def test_the_package_of_a_patched_odt_is_the_original_except_for_what_changed():
    original, data, _ = patched_odt(lambda model: put_picture(model, "o2", at=("b2", 1), shade=3))
    after, before = read_parts(data), read_parts(original)
    unchanged = set(before) - {"content.xml", "META-INF/manifest.xml"}
    assert all(after[name] == before[name] for name in unchanged)
    assert len(odt_media(data)) == 2


def test_the_style_of_the_frames_is_added_once_to_a_file_that_has_none():
    original = text_to_odt(a_text("Hello world", "Second paragraph"))
    _, data, _ = patched_odt(
        lambda model: (put_picture(model, "o1", at=("b1", 1)), put_picture(model, "o2", at=("b2", 1), shade=2)),
        original=original,
    )
    assert read_parts(data)["content.xml"].count(b'style:name="Claudia_20_picture"') == 1


# ------------------------------------------------------------------------------------------ losses of a patch
def an_svg_asset() -> ImageAsset:
    return decode_image(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20"/></svg>'
    )


def test_a_decorative_picture_added_to_a_kept_odt_says_the_file_cannot_mark_it():
    found = LossLog()
    original = text_to_odt(a_text("Hello world", "Second paragraph"))
    patched_odt(lambda model: put_picture(model, "o1", at=("b1", 1), decorative=True), original=original, losses=found)
    assert Loss("decorative") in found.result()


def test_an_svg_added_to_a_kept_docx_says_its_fallback_picture_is_empty():
    found = LossLog()
    original = text_to_docx(a_text("Hello world", "Second paragraph"))

    def edit(model: TextModel) -> None:
        asset = an_svg_asset()
        model.images.define(asset)
        model.insert_object(
            VisualObject(
                ObjectBody("o1", "image", 80, 40, "plain-image", ref=asset.id, imported=an_import(asset)),
                BlockAnchor("b1", 1),
            )
        )

    _, data, back = patched_docx(edit, original=original, losses=found)
    assert Loss("svg-fallback") in found.result()
    assert back.images[only(back).body.image].format == "svg"


# ------------------------------------------------------------------------------- containers
def a_container_text(*, pictured: bool = True, svg: bool = True) -> TextModel:
    """A text with a container (what typst or mermaid made of its source) hanging from the first paragraph."""
    from claudia_core import ContainerDefinition

    model = a_text("Hello world", "Second paragraph")
    image = None
    if pictured:
        asset = an_svg_asset() if svg else a_picture(shade=7)
        model.images.define(asset)
        image = asset.id
    model.containers.define(ContainerDefinition("r1", "typst", "= Hi", image=image))
    body = ObjectBody("c1", "container", 200, 100, "plain-image", ref="r1")
    model.insert_object(VisualObject(body, BlockAnchor("b1", 3)))
    return model


def draw(data: bytes, width: int, height: int) -> bytes:
    from claudia_core import blank_png

    return blank_png(width, height)


def codes(losses) -> set[str]:
    return {loss.kind for loss in losses}


def test_a_container_nobody_has_drawn_yet_is_left_out_and_the_export_says_so():
    model = a_container_text(pictured=False)
    assert "rendering-pending" in codes(docx_export_losses(model))
    assert "rendering-pending" in codes(odt_export_losses(model))
    assert docx_to_text(text_to_docx(model)).objects == {} and odt_to_text(text_to_odt(model)).objects == {}


def test_a_container_is_a_picture_of_its_own_in_both_files():
    model = a_container_text()
    assert docx_to_text(text_to_docx(model)).get_object("o1").body.kind == "image"
    assert odt_to_text(text_to_odt(model)).get_object("o1").body.kind == "image"


def test_a_container_is_drawn_as_a_png_when_there_is_something_to_draw_it_with():
    model = a_container_text()
    assert "svg-picture" in codes(odt_export_losses(model))
    assert "svg-picture" not in codes(odt_export_losses(model, rasterised=True))
    assert "svg-fallback" in codes(docx_export_losses(model))
    assert "svg-fallback" not in codes(docx_export_losses(model, rasterised=True))
    names = read_parts(text_to_odt(model, rasterise=draw))
    assert [name for name in names if name.startswith("Pictures/")] == [
        f"Pictures/{model.images[next(iter(model.images))].id}-200x100.png"
    ]
    assert docx_to_text(text_to_docx(model, rasterise=draw)).get_object("o1").body.w == 200


def test_two_containers_of_one_picture_share_one_png():
    model = a_container_text()
    from claudia_core import ContainerDefinition

    model.containers.define(ContainerDefinition("r2", "typst", "= Hi", image=next(iter(model.images))))
    model.insert_object(
        VisualObject(ObjectBody("c2", "container", 200, 100, "plain-image", ref="r2"), BlockAnchor("b2", 1))
    )
    data = text_to_odt(model, rasterise=draw)
    assert len([name for name in read_parts(data) if name.startswith("Pictures/")]) == 1
    assert len(odt_to_text(data).objects) == 2


def test_a_container_added_to_a_kept_odt_says_what_a_program_without_svg_shows():
    original = text_to_odt(a_text("Hello world", "Second paragraph"))
    found = LossLog()
    baseline, current = odt_to_text(original), odt_to_text(original)
    container = a_container_text()
    current.images.define(next(iter(container.images.values())))
    current.containers.define(container.containers["r1"])
    current.insert_object(container.get_object("c1"))
    data = apply_edits_to_odt(original, baseline, current, losses=found)
    assert "svg-picture" in codes(found.result()) and problems(data) == []
    assert len(odt_to_text(data).objects) == 1


def test_a_container_nothing_has_drawn_is_listed_when_a_kept_file_is_patched():
    for to_text, patch, text_to in (
        (odt_to_text, apply_edits_to_odt, text_to_odt),
        (docx_to_text, apply_edits_to_docx, text_to_docx),
    ):
        original = text_to(a_text("Hello world", "Second paragraph"))
        found = LossLog()
        baseline, current = to_text(original), to_text(original)
        container = a_container_text(pictured=False)
        current.containers.define(container.containers["r1"])
        current.insert_object(container.get_object("c1"))
        patch(original, baseline, current, losses=found)
        assert "rendering-pending" in codes(found.result())


# ------------------------------------------------------------------------------- what an odt frame says
def odt_with(data: bytes, **replacements: str) -> bytes:
    """The odt ``data`` with text of its ``content.xml`` replaced (``old=new``, ``__`` for ``:`` in the old text)."""
    from claudia_opc_io import write_parts

    parts = read_parts(data)
    content = parts["content.xml"].decode()
    for key, new in replacements.items():
        old = key.replace("__", ":")
        assert old in content, old
        content = content.replace(old, new)
    parts["content.xml"] = content.encode()
    return write_parts(parts)


def an_odt_with_a_picture(**changes) -> bytes:
    model = a_text("Hello world", "Second paragraph")
    put_picture(model, **changes)
    return text_to_odt(model)


def test_a_frame_in_proportion_with_a_turn_it_cannot_read_is_not_held():
    data = odt_with(an_odt_with_a_picture(), **{"svg__x": "draw:transform='matrix(1 0 0 1 0 0)' svg:x"})
    assert odt_to_text(data).objects == {} and Loss("picture") in odt_import_losses(data)


def test_a_frame_too_small_or_stretched_is_not_held():
    base = an_odt_with_a_picture()
    from lxml import etree

    root = etree.fromstring(read_parts(base)["content.xml"])
    frame = next(root.iter("{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}frame"))
    width = frame.get("{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}width")
    height = frame.get("{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}height")
    for new_width, new_height in (("0.1cm", "0.05cm"), ("9cm", "1cm")):
        data = odt_with(base, **{f'svg__width="{width}"': f'svg:width="{new_width}"'})
        data = odt_with(data, **{f'svg__height="{height}"': f'svg:height="{new_height}"'})
        assert odt_to_text(data).objects == {}
        assert Loss("picture") in odt_import_losses(data)


def test_an_odt_picture_given_back_its_upright_place_loses_its_turn():
    original = an_odt_with_a_picture(rotation=90)
    assert b"draw:transform" in read_parts(original)["content.xml"]

    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, rotation=0), found.anchor))

    _, data, back = patched_odt(edit, original=original)
    assert only(back).body.rotation == 0
    content = read_parts(data)["content.xml"]
    assert b"draw:transform" not in content and b'svg:x="0cm"' in content


def test_an_odt_picture_resized_while_upright_keeps_its_place():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, w=300, h=150), found.anchor))

    _, data, back = patched_odt(edit)
    assert (only(back).body.w, only(back).body.h) == (300, 150)


def test_an_odt_picture_made_decorative_has_no_description_in_the_file_and_the_export_says_so():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="", decorative=True), found.anchor))

    found = LossLog()
    _, data, _ = patched_odt(edit, losses=found)
    assert b"<svg:desc" not in read_parts(data)["content.xml"]
    assert Loss("decorative") in found.result()


def test_a_picture_that_takes_the_name_of_one_that_went_gets_a_name_of_its_own():
    original = an_odt_with_a_picture()
    (old,) = [name for name in read_parts(original) if name.startswith("Pictures/")]

    def edit(model: TextModel) -> None:
        found = model.delete_object("o1")[0]
        model.insert_object(VisualObject(replace(found.body, id="o7"), found.anchor))

    _, data, back = patched_odt(edit, original=original)
    names = [name for name in read_parts(data) if name.startswith("Pictures/")]
    assert len(names) == 1 and len(back.objects) == 1


# ------------------------------------------------------------------------------- what a drawing of a docx says
def a_docx_with(**replacements: str) -> bytes:
    """A docx with one picture whose ``document.xml`` has text replaced (``old=new``; ``__`` is ``:`` in the old)."""
    from claudia_opc_io import write_parts

    data = text_to_docx(a_picture_text(description="two cyclists")[0])
    parts = read_parts(data)
    content = parts["word/document.xml"].decode()
    for key, new in replacements.items():
        old = key.replace("__", ":")
        assert old in content, old
        content = content.replace(old, new, 1)
    parts["word/document.xml"] = content.encode()
    return write_parts(parts)


@pytest.mark.parametrize(
    "replacements",
    [
        {"<wp__extent cx=": "<wp:extent cx='x' dummy="},  # no size it can read
        {"<a__xfrm": "<a:xfrm flipH='1'"},  # flipped
        {"<wp__extent ": "<wp:extentless "},  # no extent at all
        {"r__embed=": "r:embed='rId999' dummy="},  # a picture that is not in the package
    ],
    ids=["no-size", "flipped", "no-extent", "no-picture"],
)
def test_a_drawing_the_model_cannot_show_stays_in_the_file_and_is_listed(replacements):
    data = a_docx_with(**replacements)
    assert docx_to_text(data).objects == {} and Loss("picture") in docx_import_losses(data)


def test_a_turn_that_is_not_a_number_is_no_turn():
    data = a_docx_with(**{"<a__xfrm": "<a:xfrm rot='many'"})
    assert only(docx_to_text(data)).body.rotation == 0


def test_a_crop_of_nothing_is_no_crop():
    from docx.oxml import parse_xml

    document = Document(BytesIO(text_to_docx(a_picture_text()[0])))
    fill = document.element.body.xpath(".//pic:blipFill")[0]
    fill.insert(1, parse_xml('<a:srcRect xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" l="0"/>'))
    out = BytesIO()
    document.save(out)
    assert len(docx_to_text(out.getvalue()).objects) == 1


def test_a_picture_that_is_made_undecorative_and_upright_again_loses_the_mark_and_the_turn():
    model = a_text("Hello world")
    put_picture(model, at=("b1", 2), decorative=True, rotation=90)
    original = text_to_docx(model)

    def edit(current: TextModel) -> None:
        found = only(current)
        current.replace_object(
            VisualObject(replace(found.body, decorative=False, description="now described", rotation=0), found.anchor)
        )

    _, data, back = patched_docx(edit, original=original)
    assert (only(back).body.decorative, only(back).body.description, only(back).body.rotation) == (
        False,
        "now described",
        0,
    )
    assert b"decorative" not in read_parts(data)["word/document.xml"]


def test_a_picture_swapped_for_another_in_a_kept_docx_leaves_one_picture():
    def edit(model: TextModel) -> None:
        found = only(model)
        other = a_picture(shade=9)
        model.images.define(other)
        body = replace(found.body, ref=other.id, imported=an_import(other))
        model.replace_object(VisualObject(body, found.anchor))

    original, data, back = patched_docx(edit)
    assert len(media(data)) == 2 and len(back.objects) == 1  # (the old one stays in the package: nothing may drop it)
    assert back.images[only(back).body.image].data != a_picture().data


def test_a_picture_taken_out_of_a_run_that_has_words_leaves_the_words():
    from docx.shared import Cm

    document = Document()
    run = document.add_paragraph().add_run("Words")
    run.add_picture(gif_stream(), width=Cm(4), height=Cm(2))
    out = BytesIO()
    document.save(out)
    original = out.getvalue()
    _, data, back = patched_docx(lambda model: model.delete_object("o1"), original=original)
    assert back.objects == {} and back.blocks[0].text == "Words"


def test_a_picture_put_into_a_paragraph_with_a_tab_and_a_link_lands_after_what_cannot_be_cut():
    document = Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("a\tb")
    document.add_paragraph("second")
    out = BytesIO()
    document.save(out)
    original = out.getvalue()
    _, data, back = patched_docx(lambda model: put_picture(model, "o1", at=("b1", 1)), original=original)
    assert only(back).anchor.block == "b1" and back.blocks[0].text == "a\tb"


def test_two_svg_pictures_of_one_asset_share_the_svg_part_of_a_docx():
    model = a_text("Hello world")
    asset = an_svg_asset()
    model.images.define(asset)
    for number, offset in ((1, 1), (2, 5)):
        body = ObjectBody(f"o{number}", "image", 80, 40, "plain-image", ref=asset.id, imported=an_import(asset))
        model.insert_object(VisualObject(body, BlockAnchor("b1", offset)))
    parts = read_parts(text_to_docx(model))
    assert len([name for name in parts if name.endswith(".svg")]) == 1
