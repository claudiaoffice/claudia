"""The text boxes and shapes floating over a text are written to docx and odt as drawings of a shape, read back as
text box and shape objects, and patched into a kept file (D465)."""

from __future__ import annotations

import re
import zipfile
from collections.abc import Callable
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
from claudia_core import ObjectBody, Run, VisualObject, paragraph_for, primitive
from claudia_odf_io import Loss, LossLog


def a_text(*texts: str) -> TextModel:
    return TextModel([Block(f"b{n}", DEFAULT_STYLE, text) for n, text in enumerate(texts, start=1)])


def put_box(model: TextModel, object_id="o1", *, at=("b1", 5), size=(300, 100), words="Some words", **changes):
    """A text box with ``words`` (a shape, with its label in the style of one, when ``shape`` is given)."""
    shape = changes.pop("shape", None)
    if shape is None:
        body = ObjectBody(object_id, "text", *size, "plain-box", paragraph_for(object_id, "body", words), **changes)
    else:
        if shape not in model.shapes:
            model.shapes.define(primitive(shape))
        paragraph = paragraph_for(object_id, changes.pop("words_style", "shape-label"), words)
        body = ObjectBody(object_id, "shape", *size, "plain-shape", paragraph, ref=shape, **changes)
    model.insert_object(VisualObject(body, BlockAnchor(*at)))


def a_box_text(**changes) -> TextModel:
    model = a_text("Hello world", "Second paragraph")
    put_box(model, **changes)
    return model


def objects(model: TextModel) -> dict[str, VisualObject]:
    return dict(model.objects)


def only(model: TextModel) -> VisualObject:
    (found,) = model.objects.values()
    return found


def reworded(body: ObjectBody, text: str):
    """The paragraph of ``body`` with other words (written by nobody in particular)."""
    assert body.paragraph is not None
    return replace(body.paragraph, text=text, runs=(Run(len(text), None),) if text else ())


def words(obj: VisualObject) -> str:
    assert obj.body.paragraph is not None
    return obj.body.paragraph.text


# ---------------------------------------------------------------------------------------------------- docx: fresh
def test_a_text_box_comes_back_as_a_text_box_with_its_words_its_place_and_its_size():
    back = docx_to_text(text_to_docx(a_box_text(description="a note")))
    found = only(back)
    assert (found.body.kind, found.body.style, words(found)) == ("text", "plain-box", "Some words")
    assert (found.anchor, found.body.w, found.body.h, found.body.description) == (
        BlockAnchor("b1", 5),
        300,
        100,
        "a note",
    )
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


@pytest.mark.parametrize("shape", ["circle", "rectangle", "triangle"])
def test_a_shape_comes_back_as_the_shape_with_its_label_and_its_turn(shape):
    model = a_text("Hello world")
    put_box(model, shape=shape, size=(120, 120), words="Label", rotation=30)
    found = only(docx_to_text(text_to_docx(model)))
    assert (found.body.kind, found.body.shape, found.body.style) == ("shape", shape, "plain-shape")
    assert (words(found), found.body.paragraph.style, found.body.rotation) == ("Label", "shape-label", 30)
    assert (found.body.w, found.body.h) == (120, 120)


def test_a_box_with_no_words_is_written_and_read_back_empty():
    model = a_text("Hello world")
    put_box(model, words="")
    assert words(only(docx_to_text(text_to_docx(model)))) == ""


def test_a_decorative_box_comes_back_decorative():
    found = only(docx_to_text(text_to_docx(a_box_text(decorative=True))))
    assert (found.body.decorative, found.body.description) == (True, "")


def test_the_boxes_of_a_file_are_numbered_in_the_order_of_the_file_and_after_the_pictures_by_their_own_numbers():
    model = a_text("Hello", "World")
    put_box(model, "a", at=("b2", 0), words="second")
    put_box(model, "b", at=("b1", 0), words="first")
    back = docx_to_text(text_to_docx(model))
    assert {obj.id: words(obj) for obj in back.objects.values()} == {"x1": "first", "x2": "second"}


def test_boxes_and_pictures_of_one_paragraph_keep_their_order_and_their_drawings_have_numbers_of_their_own():
    from test_composes_pictures import put_picture

    model = a_text("Hello world")
    put_picture(model, "p", at=("b1", 2))
    put_box(model, "q", at=("b1", 2), words="Box")
    data = text_to_docx(model)
    back = docx_to_text(data)
    assert sorted(obj.body.kind for obj in back.objects.values()) == ["image", "text"]
    numbers = [d.get("id") for d in Document(BytesIO(data)).element.body.iter(qn("wp:docPr"))]
    assert len(numbers) == len(set(numbers)) == 2


def test_a_box_is_not_a_loss_of_the_export_and_an_outline_of_the_model_is_written_by_name():
    model = a_text("Hello world")
    put_box(model, shape="circle", size=(100, 100), words="Label")
    put_box(model, "o2", words="Text")
    assert docx_export_losses(model) == ()


def test_a_shape_the_model_has_but_files_do_not_know_is_not_written_and_the_export_says_so():
    model = a_text("Hello world")
    model.shapes.define(
        replace(primitive("rectangle"), id="arrow", name="Arrow", path="M0 0 L100 50 L0 100 Z"),
    )
    body = ObjectBody("o1", "shape", 100, 60, "plain-shape", paragraph_for("o1", "shape-label", "x"), ref="arrow")
    model.insert_object(VisualObject(body, BlockAnchor("b1", 0)))
    data = text_to_docx(model)
    assert not docx_to_text(data).objects
    assert Loss("not-written", "objects", 1) in docx_export_losses(model)
    assert Loss("not-written", "shapes", 1) in docx_export_losses(model)


def test_who_wrote_the_words_of_a_box_is_not_kept_and_the_export_says_so():
    model = a_text("Hello world")
    put_box(model, words="Some words")
    found = only(model)
    paragraph = found.body.paragraph.written_by("ana")
    model.replace_object(VisualObject(replace(found.body, paragraph=paragraph), found.anchor))
    assert Loss("authorship", "", 1) in docx_export_losses(model)


# ---------------------------------------------------------------------------------------------------- docx: foreign
def changed(data: bytes, change: Callable[[str], str]) -> bytes:
    """``data`` with its ``word/document.xml`` changed by ``change``."""
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "word/document.xml":
                content = change(content.decode()).encode()
            target.writestr(item, content)
    return out.getvalue()


def a_word_box() -> bytes:
    """A text box the way Word writes it: the drawing in an ``mc:AlternateContent`` next to its legacy picture, with a
    fill and a line of its own."""
    data = text_to_docx(a_box_text(description="a note"))

    def wrap(xml: str) -> str:
        found = re.search(r"<w:drawing>.*?</w:drawing>", xml, re.S)
        assert found
        mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
        drawing = found.group(0).replace("<a:noFill/>", '<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>', 1)
        wrapped = (
            f'<mc:AlternateContent xmlns:mc="{mc}"><mc:Choice Requires="wps">{drawing}</mc:Choice>'
            '<mc:Fallback><w:pict><v:rect xmlns:v="urn:schemas-microsoft-com:vml"/></w:pict></mc:Fallback>'
            "</mc:AlternateContent>"
        )
        return xml.replace(found.group(0), wrapped, 1)

    return changed(data, wrap)


def test_a_text_box_the_way_word_writes_it_comes_in_and_is_one_text_box_of_the_file_not_two_frames():
    data = a_word_box()
    found = only(docx_to_text(data))
    assert (found.body.kind, words(found), found.anchor) == ("text", "Some words", BlockAnchor("b1", 5))
    assert [loss.kind for loss in docx_import_losses(data)] == ["look"]


def test_a_box_that_looks_otherwise_in_the_file_than_the_model_has_it_says_look():
    data = changed(
        text_to_docx(a_box_text()),
        lambda xml: xml.replace("<a:noFill/>", '<a:solidFill><a:srgbClr val="00FF00"/></a:solidFill>', 1),
    )
    assert docx_import_losses(data) == (Loss("look", "", 1),)


def test_a_box_that_looks_as_the_model_has_it_says_nothing():
    assert docx_import_losses(text_to_docx(a_box_text())) == ()


def test_a_box_with_two_paragraphs_stays_in_the_file_and_is_listed_as_a_frame():
    data = changed(
        text_to_docx(a_box_text()), lambda xml: xml.replace("</w:p></w:txbxContent>", "</w:p><w:p/></w:txbxContent>", 1)
    )
    assert not docx_to_text(data).objects
    assert docx_import_losses(data) == (Loss("frame", "", 1),)


def test_a_box_with_a_table_or_a_field_in_it_is_not_held():
    data = changed(
        text_to_docx(a_box_text()), lambda xml: xml.replace("<w:txbxContent><w:p>", "<w:txbxContent><w:tbl/><w:p>", 1)
    )
    assert not docx_to_text(data).objects


def test_a_flipped_or_an_oval_or_a_tiny_box_is_not_held():
    base = text_to_docx(a_box_text(shape="circle", size=(100, 100)))
    assert only(docx_to_text(base)).body.shape == "circle"
    flipped = changed(base, lambda xml: xml.replace("<a:xfrm>", '<a:xfrm flipH="1">', 1))
    oval = changed(base, lambda xml: xml.replace(f'cy="{100 * 9525}"', f'cy="{60 * 9525}"'))
    tiny = changed(base, lambda xml: xml.replace(str(100 * 9525), str(5 * 9525)))
    assert [len(docx_to_text(each).objects) for each in (flipped, oval, tiny)] == [0, 0, 0]


def test_a_shape_the_model_has_no_outline_for_is_not_held():
    data = changed(
        text_to_docx(a_box_text(shape="triangle", size=(100, 100))),
        lambda xml: xml.replace('prst="triangle"', 'prst="star5"'),
    )
    assert not docx_to_text(data).objects


def test_runs_with_their_own_formatting_in_a_box_are_read_as_their_words():
    data = changed(
        text_to_docx(a_box_text()),
        lambda xml: xml.replace(
            '<w:r><w:t xml:space="preserve">Some words</w:t></w:r>',
            "<w:r><w:rPr><w:b/></w:rPr><w:t>Some </w:t></w:r><w:r><w:t>words</w:t></w:r>",
        ),
    )
    assert words(only(docx_to_text(data))) == "Some words"


# ---------------------------------------------------------------------------------------------------- docx: patch
def patched_docx(edit, *, original: bytes | None = None, losses: LossLog | None = None):
    """The kept file (two paragraphs and a text box on the first, unless ``original``) after ``edit`` changed the model
    it was read as; with the model read back from the result."""
    if original is None:
        original = text_to_docx(a_box_text(description="a note"))
    baseline, current = docx_to_text(original), docx_to_text(original)
    edit(current)
    data = apply_edits_to_docx(original, baseline, current, losses=losses)
    return original, data, docx_to_text(data)


def body_xml(data: bytes) -> str:
    return zipfile.ZipFile(BytesIO(data)).read("word/document.xml").decode()


def test_a_box_that_is_not_edited_comes_back_as_it_was_byte_for_byte():
    original, data, back = patched_docx(lambda model: None)
    assert body_xml(data) == body_xml(original)
    assert only(back).anchor == BlockAnchor("b1", 5)


def test_new_words_are_written_into_the_box_and_nothing_else_changes():
    def edit(model: TextModel) -> None:
        found = only(model)
        paragraph = reworded(found.body, "Other words")
        model.replace_object(VisualObject(replace(found.body, paragraph=paragraph), found.anchor))

    original, data, back = patched_docx(edit)
    assert words(only(back)) == "Other words"
    assert re.sub("Other words", "Some words", body_xml(data)) == body_xml(original)


def test_a_new_style_of_the_words_is_written_into_the_box():
    def edit(model: TextModel) -> None:
        found = only(model)
        paragraph = replace(found.body.paragraph, style="remark")
        model.replace_object(VisualObject(replace(found.body, paragraph=paragraph), found.anchor))

    assert only(patched_docx(edit)[2]).body.paragraph.style == "remark"


def test_a_new_description_and_a_decorative_mark_are_written_into_the_drawing():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="a different note"), found.anchor))

    assert only(patched_docx(edit)[2]).body.description == "a different note"

    def decorate(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, description="", decorative=True), found.anchor))

    assert only(patched_docx(decorate)[2]).body.decorative


def test_a_box_resized_and_turned_changes_only_its_size_and_turn():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, w=250, h=80, rotation=15), found.anchor))

    back = patched_docx(edit)[2]
    assert (only(back).body.w, only(back).body.h, only(back).body.rotation) == (250, 80, 15)
    assert words(only(back)) == "Some words"


def test_a_box_given_back_its_upright_place_loses_its_turn():
    start = text_to_docx(a_box_text(rotation=20))

    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, rotation=0), found.anchor))

    assert only(patched_docx(edit, original=start)[2]).body.rotation == 0


def test_a_box_moved_to_another_paragraph_is_drawn_there():
    def edit(model: TextModel) -> None:
        found = model.delete_object("x1")[0]
        model.insert_object(VisualObject(replace(found.body, id="x9"), BlockAnchor("b2", 3)))

    back = patched_docx(edit)[2]
    assert (only(back).anchor, words(only(back))) == (BlockAnchor("b2", 3), "Some words")


def test_a_box_moved_inside_its_paragraph_keeps_the_words_it_cuts():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(found.body, BlockAnchor("b1", 8)))

    back = patched_docx(edit)[2]
    assert (only(back).anchor, back.blocks[0].text) == (BlockAnchor("b1", 8), "Hello world")


def test_a_box_that_is_removed_takes_its_drawing_out_of_the_file():
    def edit(model: TextModel) -> None:
        model.delete_object("x1")

    _, data, back = patched_docx(edit)
    assert not back.objects and "wps:wsp" not in body_xml(data)
    assert [block.text for block in back.blocks] == ["Hello world", "Second paragraph"]


def test_a_box_added_to_a_kept_file_is_drawn_where_the_text_says():
    def edit(model: TextModel) -> None:
        put_box(model, "n1", at=("b2", 4), size=(100, 100), shape="circle", words="New")

    back = patched_docx(edit)[2]
    new = [o for o in back.objects.values() if o.body.kind == "shape"]
    assert [(words(o), o.anchor, o.body.shape) for o in new] == [("New", BlockAnchor("b2", 4), "circle")]
    assert len(back.objects) == 2


def test_a_box_follows_the_words_of_its_paragraph_when_they_change():
    def edit(model: TextModel) -> None:
        model.blocks[0] = replace(model.blocks[0], text="Hello there, world")
        found = only(model)
        model.replace_object(VisualObject(found.body, BlockAnchor("b1", 11)))

    back = patched_docx(edit)[2]
    assert (back.blocks[0].text, only(back).anchor) == ("Hello there, world", BlockAnchor("b1", 11))


def test_a_box_whose_outline_changes_is_drawn_anew_and_a_foreign_look_is_said_to_be_lost():
    data = changed(
        text_to_docx(a_box_text(shape="rectangle", size=(100, 50))),
        lambda xml: re.sub(r'<a:srgbClr val="[0-9A-F]{6}"/>', '<a:srgbClr val="FF0000"/>', xml, count=1),
    )

    def edit(model: TextModel) -> None:
        found = only(model)
        model.shapes.define(primitive("triangle"))
        model.replace_object(VisualObject(replace(found.body, ref="triangle"), found.anchor))

    losses = LossLog()
    _, _, back = patched_docx(edit, original=data, losses=losses)
    assert only(back).body.shape == "triangle"
    assert Loss("look", "", 1) in losses.result()


def test_a_foreign_look_stays_when_only_the_words_and_the_size_change():
    data = a_word_box()

    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(
            VisualObject(replace(found.body, w=200, paragraph=reworded(found.body, "New")), found.anchor)
        )

    _, patched, back = patched_docx(edit, original=data)
    assert "FF0000" in body_xml(patched) and "AlternateContent" in body_xml(patched)
    assert (words(only(back)), only(back).body.w) == ("New", 200)


def test_a_word_box_that_is_removed_takes_its_legacy_picture_with_it():
    _, data, back = patched_docx(lambda model: model.delete_object("x1"), original=a_word_box())
    assert not back.objects and "AlternateContent" not in body_xml(data)


def test_a_box_the_model_does_not_hold_survives_an_edit_next_to_one_it_holds():
    data = changed(
        text_to_docx(a_box_text()), lambda xml: xml.replace("</w:p></w:txbxContent>", "</w:p><w:p/></w:txbxContent>", 1)
    )
    _, patched, _ = patched_docx(
        lambda model: model.blocks.__setitem__(1, replace(model.blocks[1], text="Edited")), original=data
    )
    assert "txbxContent" in body_xml(patched)


# ---------------------------------------------------------------------------------------------------- both: fresh
FORMATS = pytest.mark.parametrize(
    "to_file, to_model", [(text_to_docx, docx_to_text), (text_to_odt, odt_to_text)], ids=["docx", "odt"]
)


@FORMATS
def test_the_words_of_a_box_keep_the_style_they_have(to_file, to_model):
    model = a_text("Hello world")
    put_box(model, at=("b1", 0), words="Said")
    put_box(model, "o2", shape="rectangle", size=(100, 50), words="Careful", words_style="remark")
    back = to_model(to_file(model))
    assert {words(o): o.body.paragraph.style for o in back.objects.values()} == {"Said": "body", "Careful": "remark"}


@FORMATS
def test_a_text_box_and_a_shape_come_back_with_their_place_size_turn_and_description(to_file, to_model):
    model = a_text("Hello world", "Second paragraph")
    put_box(model, "o1", at=("b1", 5), description="a note")
    put_box(model, "o2", at=("b2", 0), shape="triangle", size=(120, 90), words="Tri", rotation=45)
    put_box(model, "o3", at=("b2", 16), shape="circle", size=(80, 80), words="", description="a dot")
    found = {o.id: o for o in to_model(to_file(model)).objects.values()}
    assert [(o.body.kind, o.body.shape, o.body.w, o.body.h, o.body.rotation) for o in found.values()] == [
        ("text", None, 300, 100, 0),
        ("shape", "triangle", 120, 90, 45),
        ("shape", "circle", 80, 80, 0),
    ]
    assert [o.anchor for o in found.values()] == [BlockAnchor("b1", 5), BlockAnchor("b2", 0), BlockAnchor("b2", 16)]
    assert [words(o) for o in found.values()] == ["Some words", "Tri", ""]
    assert [o.body.description for o in found.values()] == ["a note", "", "a dot"]


@FORMATS
def test_a_shape_the_model_has_but_files_do_not_know_is_not_written_and_the_export_says_so_in_both(to_file, to_model):
    model = a_text("Hello world")
    model.shapes.define(replace(primitive("rectangle"), id="arrow", name="Arrow", path="M0 0 L100 50 L0 100 Z"))
    body = ObjectBody("o1", "shape", 100, 60, "plain-shape", paragraph_for("o1", "shape-label", "x"), ref="arrow")
    model.insert_object(VisualObject(body, BlockAnchor("b1", 0)))
    assert not to_model(to_file(model)).objects


@FORMATS
def test_a_box_hanging_from_a_paragraph_with_nothing_in_it_is_written(to_file, to_model):
    model = a_text("", "Second")
    put_box(model, at=("b1", 0))
    assert only(to_model(to_file(model))).anchor == BlockAnchor("b1", 0)


def test_the_export_to_odt_says_a_decorative_box_has_no_mark_and_that_authors_are_not_kept():
    model = a_box_text(decorative=True)
    found = only(model)
    paragraph = found.body.paragraph.written_by("ana")
    model.replace_object(VisualObject(replace(found.body, paragraph=paragraph), found.anchor))
    losses = odt_export_losses(model)
    assert Loss("decorative", "", 1) in losses and Loss("authorship", "", 1) in losses
    assert not any(loss.kind == "not-written" for loss in losses)


def test_a_box_and_a_picture_in_one_odt_paragraph_both_come_back():
    from test_composes_pictures import put_picture

    model = a_text("Hello world")
    put_picture(model, "p", at=("b1", 2))
    put_box(model, "q", at=("b1", 2), words="Box")
    back = odt_to_text(text_to_odt(model))
    assert sorted(obj.body.kind for obj in back.objects.values()) == ["image", "text"]


# ---------------------------------------------------------------------------------------------------- odt: foreign
def changed_odt(data: bytes, change: Callable[[str], str]) -> bytes:
    """``data`` with its ``content.xml`` changed by ``change``."""
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "content.xml":
                content = change(content.decode()).encode()
            target.writestr(item, content)
    return out.getvalue()


def content_xml(data: bytes) -> str:
    return zipfile.ZipFile(BytesIO(data)).read("content.xml").decode()


def a_box_odt(**changes) -> bytes:
    return text_to_odt(a_box_text(**changes))


def test_a_box_that_looks_as_the_model_has_it_says_nothing_in_an_odt():
    assert odt_import_losses(a_box_odt()) == ()


def test_an_odt_box_that_looks_otherwise_than_the_model_has_it_says_look():
    data = changed_odt(
        text_to_odt(a_box_text(shape="rectangle", size=(100, 50))),
        lambda xml: xml.replace('draw:fill="solid" draw:fill-color="#', 'draw:fill="solid" draw:fill-color="#ff', 1),
    )
    assert odt_import_losses(data) == (Loss("look", "", 1),)


def test_an_odt_text_box_with_two_paragraphs_stays_in_the_file_and_is_listed_as_a_frame():
    data = changed_odt(
        a_box_odt(), lambda xml: xml.replace("</draw:text-box>", "<text:p>more</text:p></draw:text-box>", 1)
    )
    assert not odt_to_text(data).objects
    assert odt_import_losses(data) == (Loss("frame", "", 1),)


def test_an_odt_box_that_is_flipped_or_an_oval_or_tiny_or_of_another_outline_is_not_held():
    base = text_to_odt(a_box_text(shape="circle", size=(100, 100)))
    assert only(odt_to_text(base)).body.shape == "circle"
    oval = changed_odt(base, lambda xml: xml.replace('svg:height="2.6458cm"', 'svg:height="1.5cm"', 1))
    tiny = changed_odt(base, lambda xml: re.sub(r'svg:(width|height)="2.6458cm"', r'svg:\1="0.1cm"', xml))
    skewed = changed_odt(base, lambda xml: xml.replace('svg:x="0cm"', 'draw:transform="skewX (0.5)"', 1))
    arc = changed_odt(base, lambda xml: xml.replace("<draw:ellipse ", '<draw:ellipse draw:start-angle="30" ', 1))
    assert [len(odt_to_text(each).objects) for each in (oval, tiny, skewed, arc)] == [0, 0, 0, 0]


def test_a_shape_with_the_geometry_of_a_star_is_not_held():
    base = text_to_odt(a_box_text(shape="triangle", size=(100, 100)))
    star = changed_odt(base, lambda xml: xml.replace('draw:type="isosceles-triangle"', 'draw:type="star5"'))
    assert not odt_to_text(star).objects


def test_a_shape_the_way_libreoffice_writes_a_rectangle_comes_in():
    data = changed_odt(
        text_to_odt(a_box_text(shape="rectangle", size=(100, 50))),
        lambda xml: xml.replace("<draw:rect ", "<draw:custom-shape ").replace(
            "</draw:rect>", '<draw:enhanced-geometry draw:type="rectangle"/></draw:custom-shape>'
        ),
    )
    assert only(odt_to_text(data)).body.shape == "rectangle"


# ---------------------------------------------------------------------------------------------------- odt: patch
def patched_odt(edit, *, original: bytes | None = None, losses: LossLog | None = None):
    """The kept file (two paragraphs and a text box on the first, unless ``original``) after ``edit`` changed the model
    it was read as; with the model read back from the result."""
    if original is None:
        original = a_box_odt(description="a note")
    baseline, current = odt_to_text(original), odt_to_text(original)
    edit(current)
    data = apply_edits_to_odt(original, baseline, current, losses=losses)
    return original, data, odt_to_text(data)


def test_an_odt_box_that_is_not_edited_leaves_the_file_as_it_was():
    original, data, back = patched_odt(lambda model: None)
    assert data == original
    assert only(back).anchor == BlockAnchor("b1", 5)


def test_new_words_are_written_into_the_odt_box_and_nothing_else_changes():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(
            VisualObject(replace(found.body, paragraph=reworded(found.body, "Other words")), found.anchor)
        )

    original, data, back = patched_odt(edit)
    assert words(only(back)) == "Other words"
    assert content_xml(data).replace("Other words", "Some words") == content_xml(original)


def test_a_new_style_of_the_words_is_written_into_the_odt_box_and_the_file_has_the_style():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(
            VisualObject(replace(found.body, paragraph=replace(found.body.paragraph, style="remark")), found.anchor)
        )

    assert only(patched_odt(edit)[2]).body.paragraph.style == "remark"


def test_a_new_description_size_and_turn_are_written_into_the_odt_box():
    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(
            VisualObject(replace(found.body, description="other", w=250, h=80, rotation=15), found.anchor)
        )

    body = only(patched_odt(edit)[2]).body
    assert (body.description, body.w, body.h, body.rotation, words(only(patched_odt(edit)[2]))) == (
        "other",
        250,
        80,
        15,
        "Some words",
    )


def test_an_odt_box_given_back_its_upright_place_loses_its_turn_and_a_description_can_go():
    start = a_box_odt(rotation=20, description="x")

    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(VisualObject(replace(found.body, rotation=0, description=""), found.anchor))

    body = only(patched_odt(edit, original=start)[2]).body
    assert (body.rotation, body.description) == (0, "")


def test_an_odt_box_moved_to_another_paragraph_is_drawn_there():
    def edit(model: TextModel) -> None:
        found = model.delete_object("x1")[0]
        model.insert_object(VisualObject(replace(found.body, id="x9"), BlockAnchor("b2", 3)))

    back = patched_odt(edit)[2]
    assert (only(back).anchor, words(only(back))) == (BlockAnchor("b2", 3), "Some words")


def test_an_odt_box_moved_inside_its_paragraph_keeps_the_words_it_cuts():
    def edit(model: TextModel) -> None:
        model.replace_object(VisualObject(only(model).body, BlockAnchor("b1", 8)))

    back = patched_odt(edit)[2]
    assert (only(back).anchor, back.blocks[0].text) == (BlockAnchor("b1", 8), "Hello world")


def test_an_odt_box_that_is_removed_takes_its_frame_out_of_the_file():
    _, data, back = patched_odt(lambda model: model.delete_object("x1"))
    assert not back.objects and "draw:text-box" not in content_xml(data)


def test_a_box_added_to_a_kept_odt_is_drawn_where_the_text_says_with_a_style_of_its_own():
    def edit(model: TextModel) -> None:
        put_box(model, "n1", at=("b2", 4), size=(100, 100), shape="circle", words="New")

    original, data, back = patched_odt(edit)
    new = [o for o in back.objects.values() if o.body.kind == "shape"]
    assert [(words(o), o.anchor, o.body.shape) for o in new] == [("New", BlockAnchor("b2", 4), "circle")]
    assert len(back.objects) == 2
    assert (
        content_xml(data).count('style:name="Claudia_box_')
        == content_xml(original).count('style:name="Claudia_box_') + 1
    )


def test_the_styles_of_two_new_boxes_that_look_alike_are_one_style():
    def edit(model: TextModel) -> None:
        put_box(model, "n1", at=("b2", 1), size=(100, 100), shape="circle", words="A")
        put_box(model, "n2", at=("b2", 2), size=(60, 60), shape="circle", words="B")

    _, data, _ = patched_odt(edit)
    assert (
        content_xml(data).count('style:family="graphic"') == 2
    )  # (the text box of the file, and the one of the circles)


def test_an_odt_box_follows_the_words_of_its_paragraph_when_they_change():
    def edit(model: TextModel) -> None:
        model.blocks[0] = replace(model.blocks[0], text="Hello there, world")
        model.replace_object(VisualObject(only(model).body, BlockAnchor("b1", 11)))

    back = patched_odt(edit)[2]
    assert (back.blocks[0].text, only(back).anchor) == ("Hello there, world", BlockAnchor("b1", 11))


def test_an_odt_box_whose_outline_changes_is_drawn_anew_and_a_foreign_look_is_said_to_be_lost():
    data = changed_odt(
        text_to_odt(a_box_text(shape="rectangle", size=(100, 50))),
        lambda xml: xml.replace('draw:fill-color="#', 'draw:fill-color="#ff', 1),
    )

    def edit(model: TextModel) -> None:
        found = only(model)
        model.shapes.define(primitive("triangle"))
        model.replace_object(VisualObject(replace(found.body, ref="triangle"), found.anchor))

    losses = LossLog()
    _, _, back = patched_odt(edit, original=data, losses=losses)
    assert only(back).body.shape == "triangle"
    assert Loss("look", "", 1) in losses.result()


def test_a_foreign_odt_look_stays_when_only_the_words_and_the_size_change():
    data = changed_odt(
        a_box_odt(), lambda xml: xml.replace('fo:padding="0cm"', 'fo:padding="0cm" fo:background-color="#ff0000"', 1)
    )

    def edit(model: TextModel) -> None:
        found = only(model)
        model.replace_object(
            VisualObject(replace(found.body, w=200, paragraph=reworded(found.body, "New")), found.anchor)
        )

    _, patched, back = patched_odt(edit, original=data)
    assert "#ff0000" in content_xml(patched)
    assert (words(only(back)), only(back).body.w) == ("New", 200)


def test_a_decorative_box_added_to_a_kept_odt_says_the_file_cannot_mark_it():
    losses = LossLog()
    patched_odt(lambda model: put_box(model, "n1", at=("b2", 0), decorative=True), losses=losses)
    assert Loss("decorative", "", 1) in losses.result()


def test_an_odt_box_the_model_does_not_hold_survives_an_edit_next_to_one_it_holds():
    data = changed_odt(
        a_box_odt(), lambda xml: xml.replace("</draw:text-box>", "<text:p>more</text:p></draw:text-box>", 1)
    )
    _, patched, _ = patched_odt(
        lambda model: model.blocks.__setitem__(1, replace(model.blocks[1], text="Edited")), original=data
    )
    assert "more" in content_xml(patched)


# ---------------------------------------------------------------------------------------------- odd files
def tampered(data: bytes, part: str, old: str | re.Pattern[str], new: str) -> bytes:
    """``data`` with ``old`` replaced by ``new`` in ``part``."""
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == part:
                text = content.decode()
                changed = old.sub(new, text, count=1) if isinstance(old, re.Pattern) else text.replace(old, new, 1)
                assert changed != text
                content = changed.encode()
            target.writestr(item, content)
    return out.getvalue()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (re.compile(r"<a:xfrm"), '<a:xfrm flipH="1"'),  # a mirrored shape is not one the model has
        (re.compile(r'rot="\d+"'), 'rot="x"'),
        (re.compile(r"<a:srgbClr val=\"[0-9A-F]{6}\""), '<a:srgbClr val="ZZZZZZ"'),
        (re.compile(r"<a:srgbClr val=\"[0-9A-F]{6}\""), '<a:srgbClr val="12"'),
        (re.compile(r"<w:r>"), "<w:r><w:br/>"),  # a run with a break is not plain words
    ],
)
def test_a_docx_drawing_that_is_odd_is_left_to_the_file_or_read_as_far_as_it_goes(old, new):
    data = text_to_docx(a_box_text(shape="rectangle", rotation=30))
    odd = tampered(data, "word/document.xml", old, new)
    assert len(docx_to_text(odd).objects) <= 1  # read as far as it goes, and never an error


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (re.compile(r'draw:stroke-color="#[0-9a-f]{6}"|svg:stroke-color="#[0-9a-f]{6}"'), 'svg:stroke-color="#zzzzzz"'),
        (re.compile(r'draw:fill-color="#[0-9a-f]{6}"'), 'draw:fill-color="#12345"'),
        (re.compile(r'draw:fill="solid"'), 'draw:fill="solid" fo:border="2pt solid #123456"'),
    ],
)
def test_an_odt_shape_with_a_look_the_model_cannot_read_still_comes_back_as_the_shape(old, new):
    data = text_to_odt(a_box_text(shape="rectangle"))
    for part in ("content.xml", "styles.xml"):
        try:
            data = tampered(data, part, old, new)
        except AssertionError:
            continue
    assert only(odt_to_text(data)).body.shape == "rectangle"


FILL = re.compile(r'draw:fill="solid" draw:fill-color="#[0-9a-f]{6}"')
STROKE = re.compile(r'draw:stroke="solid" svg:stroke-color="#[0-9a-f]{6}" svg:stroke-width="[0-9.]+pt"')


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (FILL, 'fo:background-color="#336699"'),
        (FILL, 'fo:background-color="transparent"'),
        (FILL, 'draw:fill="none"'),
        (STROKE, 'fo:border="2pt solid #123456"'),
        (STROKE, 'fo:border="none"'),
        (STROKE, 'draw:stroke="none"'),
    ],
)
def test_the_fill_and_the_line_of_an_odt_shape_are_read_in_any_way_the_format_says_them(old, new):
    data = tampered(text_to_odt(a_box_text(shape="rectangle")), "content.xml", old, new)
    back = odt_to_text(data)
    assert only(back).body.shape == "rectangle"
    assert {loss.kind for loss in odt_import_losses(data)} >= {"look"}  # it is not the look the model would write
