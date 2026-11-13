"""slides_to_odp / odp_to_slides / apply_edits_to_odp: the presentation app's OpenDocument import, export and
edit-and-reexport (D412). Edit-and-reexport keeps what Claudia never modeled, byte for byte where it was not edited."""

from __future__ import annotations

import random
import re
import struct
from dataclasses import replace

import pytest
from claudia_creates_io import (
    UnsupportedEdit,
    apply_edits_to_odp,
    odp_export_losses,
    odp_import_losses,
    odp_to_slides,
    slides_to_odp,
)
from lxml import etree

from claudia_core import ImageAsset, ImageImport, ObjectBody, StyleDef, VisualObject, decode_image, paragraph_for
from claudia_creates import ShapeLibrary, SlideAnchor, SlideModel
from claudia_odf_io import NS, DocumentInfo, LossLog, OdfError, new_package, problems, read_info
from claudia_opc_io import read_parts

DECLS = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
CM_PER_UNIT = 28 / 1600  # a 28 cm wide slide shows 1600 units


def an_odp(pages: str, *, width: str = "28cm", height: str = "15.75cm", automatic: str = "") -> bytes:
    styles = (
        f'{HEAD}<office:document-styles {DECLS} office:version="1.3"><office:automatic-styles>'
        f'<style:page-layout style:name="PM1"><style:page-layout-properties fo:page-width="{width}" '
        f'fo:page-height="{height}"/></style:page-layout></office:automatic-styles><office:master-styles>'
        '<style:master-page style:name="Default" style:page-layout-name="PM1"/></office:master-styles>'
        "</office:document-styles>"
    )
    content = (
        f'{HEAD}<office:document-content {DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        f"<office:automatic-styles>{automatic}</office:automatic-styles>"
        f"<office:body><office:presentation>{pages}</office:presentation></office:body></office:document-content>"
    )
    return new_package("presentation", content.encode(), styles.encode())


def page(inner: str, name: str = "page1") -> str:
    return f'<draw:page draw:name="{name}" draw:master-page-name="Default">{inner}</draw:page>'


def textbox(x="2cm", y="3cm", w="10cm", h="2cm", words='<text:p text:style-name="P1">Hello</text:p>', extra="") -> str:
    return (
        f'<draw:frame draw:style-name="gr1" svg:x="{x}" svg:y="{y}" svg:width="{w}" svg:height="{h}"{extra}>'
        f"<draw:text-box>{words}</draw:text-box></draw:frame>"
    )


def ellipse(x="14cm", y="3cm", w="4cm", h="4cm", words="") -> str:
    return (
        f'<draw:ellipse draw:style-name="gr2" svg:x="{x}" svg:y="{y}" svg:width="{w}" svg:height="{h}">'
        f"{words}</draw:ellipse>"
    )


def custom(kind: str, x="1cm", y="1cm", w="3cm", h="3cm") -> str:
    return (
        f'<draw:custom-shape svg:x="{x}" svg:y="{y}" svg:width="{w}" svg:height="{h}"><text:p/>'
        f'<draw:enhanced-geometry draw:type="{kind}"/></draw:custom-shape>'
    )


PICTURE = (
    '<draw:frame svg:x="1cm" svg:y="1cm" svg:width="2cm" svg:height="2cm">'
    '<draw:image xlink:href="Pictures/a.png"/></draw:frame>'
)
TABLE = (
    '<draw:frame svg:x="1cm" svg:y="5cm" svg:width="8cm" svg:height="4cm"><table:table table:name="t"/></draw:frame>'
)
GROUP = '<draw:g><draw:rect svg:x="1cm" svg:y="1cm" svg:width="1cm" svg:height="1cm"/></draw:g>'
LINE = '<draw:line svg:x1="1cm" svg:y1="1cm" svg:x2="3cm" svg:y2="3cm"/>'
NOTES = (
    "<presentation:notes><draw:page-thumbnail/><draw:frame><draw:text-box><text:p>Say this slowly.</text:p>"
    "</draw:text-box></draw:frame></presentation:notes>"
)
EMPTY_NOTES = "<presentation:notes><draw:page-thumbnail/><draw:frame><draw:text-box/></draw:frame></presentation:notes>"
BARE = (
    '<style:style style:name="bare" style:family="graphic" style:parent-style-name="base"/>'
    '<style:style style:name="base" style:family="graphic"><style:graphic-properties draw:fill="none" '
    'draw:stroke="none"/></style:style>'
    '<style:style style:name="filled" style:family="graphic"><style:graphic-properties draw:fill="solid" '
    'draw:stroke="none"/></style:style>'
)

RICH = an_odp(
    page(textbox() + ellipse() + PICTURE + TABLE + custom("isosceles-triangle") + NOTES)
    + page(textbox(words="<text:p>Line one</text:p><text:p>Line two</text:p>") + custom("rectangle"), "page2")
)


def content(data: bytes) -> str:
    return read_parts(data)["content.xml"].decode()


def tree(data: bytes) -> etree._Element:
    return etree.fromstring(read_parts(data)["content.xml"])


def pages_of(data: bytes) -> list[etree._Element]:
    return tree(data).findall(".//draw:page", NS)


def length(element: etree._Element, name: str) -> float:
    value = element.get(f"{{{NS['svg']}}}{name}")
    assert value is not None and value.endswith("cm")
    return float(value[:-2])


def an_object(object_id, slide, kind, x, y, w, h, style, text="", shape=None) -> VisualObject:
    """``style`` is the style of what a person sees as the object's look: a text box's words, a shape's outline; the
    other slot gets its default (D304, D310)."""
    box, words = ("plain-box", style) if kind == "text" else (style, "shape-label")
    body = ObjectBody(object_id, kind, w, h, box, paragraph_for(object_id, words, text, "ana"), shape=shape)
    return VisualObject(body, SlideAnchor(slide, x, y))


def a_deck() -> SlideModel:
    model = SlideModel()
    library = ShapeLibrary.load()
    for shape_id in ("circle", "rectangle", "triangle"):
        model.define_shape(library.get(shape_id))
    model.insert_slide("s1")
    model.insert_slide("s2")
    model.insert_object(an_object("o1", "s1", "text", 160, 90, 800, 120, "body-text", "Hello & <welcome>"))
    model.insert_object(an_object("o2", "s1", "shape", 1000, 200, 300, 300, "plain-shape", "", "circle"))
    model.insert_object(an_object("o3", "s2", "shape", 100, 100, 200, 100, "plain-shape", "boxed", "rectangle"))
    model.insert_object(an_object("o4", "s2", "shape", 400, 100, 200, 200, "plain-shape", "", "triangle"))
    return model


# -- export --------------------------------------------------------------------------------------------------------
def test_an_exported_deck_is_an_opendocument_presentation():
    data = slides_to_odp(a_deck())
    assert problems(data) == []
    assert read_parts(data)["mimetype"] == b"application/vnd.oasis.opendocument.presentation"


def test_a_slide_is_a_page_and_its_objects_follow_in_stacking_order():
    pages = pages_of(slides_to_odp(a_deck()))
    assert len(pages) == 2
    assert [etree.QName(child).localname for child in pages[0]] == ["frame", "ellipse"]
    assert [etree.QName(child).localname for child in pages[1]] == ["rect", "custom-shape"]


def test_a_text_object_is_a_frame_with_its_words_at_the_place_it_has():
    frame = pages_of(slides_to_odp(a_deck()))[0][0]
    assert frame.findtext("draw:text-box/text:p", namespaces=NS) == "Hello & <welcome>"
    assert length(frame, "x") == pytest.approx(160 * CM_PER_UNIT, abs=0.001)
    assert length(frame, "width") == pytest.approx(800 * CM_PER_UNIT, abs=0.001)


def test_shapes_are_written_as_the_shapes_they_are():
    first, second = pages_of(slides_to_odp(a_deck()))
    assert first[1].tag == f"{{{NS['draw']}}}ellipse"
    assert second[0].tag == f"{{{NS['draw']}}}rect"
    triangle = second[1].find("draw:enhanced-geometry", NS)
    assert triangle is not None and triangle.get(f"{{{NS['draw']}}}type") == "isosceles-triangle"


def test_the_words_of_a_shape_are_in_it():
    assert pages_of(slides_to_odp(a_deck()))[1][0].findtext("text:p", namespaces=NS) == "boxed"


def test_lines_of_text_are_paragraphs():
    model = a_deck()
    model.objects["o1"] = an_object("o1", "s1", "text", 160, 90, 800, 120, "body-text", "one\ntwo")
    frame = pages_of(slides_to_odp(model))[0][0]
    assert [p.text for p in frame.iterfind("draw:text-box/text:p", NS)] == ["one", "two"]


def test_what_a_style_says_is_written_as_automatic_styles_in_values_a_file_can_hold():
    data = slides_to_odp(a_deck())
    root = tree(data)
    styled = next(root.iter(f"{{{NS['draw']}}}ellipse"))
    name = styled.get(f"{{{NS['draw']}}}style-name")
    style = next(
        s
        for s in root.iterfind(".//office:automatic-styles/style:style", NS)
        if s.get(f"{{{NS['style']}}}name") == name
    )
    props = style.find("style:graphic-properties", NS)
    assert props is not None
    assert re.fullmatch(r"#[0-9a-f]{6}", props.get(f"{{{NS['draw']}}}fill-color", ""))
    assert "@" not in content(data)  # a palette role is not a colour a file can hold


def test_an_image_is_a_picture_with_its_own_bytes_in_the_package():
    asset = a_gif()
    model = a_deck()
    model.define_image(asset)
    body = ObjectBody("o9", "image", 400, 200, "plain-image", image=asset.id, imported=an_import(asset))
    model.insert_object(VisualObject(body, SlideAnchor("s1", 10, 10)))
    data = slides_to_odp(model)
    frame = pages_of(data)[0][-1]
    href = frame.find("draw:image", NS).get(f"{{{NS['xlink']}}}href")
    assert href.startswith("Pictures/")
    assert read_parts(data)[href] == asset.data
    assert problems(data) == []


def a_gif(width: int = 40, height: int = 20) -> ImageAsset:
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)
    frame = b"\x2c" + struct.pack("<HHHH", 0, 0, width, height) + b"\x00" + b"\x02\x01\x00\x00"
    return decode_image(header + frame + b"\x3b")


def an_import(asset: ImageAsset) -> ImageImport:
    return ImageImport.from_data(
        {
            "asset": asset.id,
            "alt": "a picture",
            "imported_by": "ana",
            "imported_at": "2026-11-07T10:00:00.000Z",
            "source": "disk",
            "source_name": "pic.gif",
            "source_path": None,
        }
    )


def test_the_title_and_dates_are_in_the_metadata():
    info = DocumentInfo("Pitch", "2026-01-02T03:04:05Z", "Ann", "2026-11-11T17:13:05Z", "Bob")
    assert read_info(read_parts(slides_to_odp(a_deck(), info=info))["meta.xml"]) == info


def test_the_same_deck_gives_the_same_bytes():
    assert slides_to_odp(a_deck()) == slides_to_odp(a_deck())


def test_an_empty_deck_is_a_valid_presentation():
    data = slides_to_odp(SlideModel.empty())
    assert problems(data) == []
    assert len(pages_of(data)) == len(SlideModel.empty().slides)


def test_a_round_trip_keeps_the_deck():
    deck = a_deck()
    again = odp_to_slides(slides_to_odp(deck))
    assert again.slides == deck.slides
    for slide in deck.slides:
        mine = [
            (o.body.kind, o.body.shape, o.body.paragraph.text if o.body.paragraph else "")
            for o in deck.objects_on(slide)
        ]
        theirs = [
            (o.body.kind, o.body.shape, o.body.paragraph.text if o.body.paragraph else "")
            for o in again.objects_on(slide)
        ]
        assert theirs == mine
    first = again.objects["o1"]
    assert (first.anchor.x, first.anchor.y, first.body.w, first.body.h) == (160, 90, 800, 120)


def test_export_losses_name_what_the_file_cannot_hold():
    losses = odp_export_losses(a_deck())
    assert {loss.kind for loss in losses} <= {"authorship", "diagram"}


# -- import --------------------------------------------------------------------------------------------------------
def test_a_slide_per_page_and_an_object_per_text_box_or_shape():
    model = odp_to_slides(RICH)
    assert list(model.slides) == ["s1", "s2"]
    assert [(o.id, o.body.kind, o.body.shape) for o in model.objects_on("s1")] == [
        ("o1", "text", None),
        ("o2", "shape", "circle"),
        ("o3", "shape", "triangle"),
    ]
    assert [(o.id, o.body.kind, o.body.shape) for o in model.objects_on("s2")] == [
        ("o4", "text", None),
        ("o5", "shape", "rectangle"),
    ]


@pytest.mark.parametrize(
    ("kind", "shape"),
    [("ooxml-rect", "rectangle"), ("ooxml-ellipse", "circle"), ("ooxml-triangle", "triangle")],
)
def test_the_preset_shapes_libreoffice_names_ooxml_are_the_shapes_they_are(kind, shape):
    model = odp_to_slides(an_odp(page(custom(kind))))
    assert [(o.body.kind, o.body.shape) for o in model.objects_on("s1")] == [("shape", shape)]
    assert odp_import_losses(an_odp(page(custom(kind)))) == ()


def test_an_empty_notes_page_is_not_something_the_model_leaves_out():
    plain = ellipse().replace(' draw:style-name="gr2"', "")  # no style: nothing else to report
    assert odp_import_losses(an_odp(page(plain + EMPTY_NOTES))) == ()
    assert [loss.kind for loss in odp_import_losses(an_odp(page(plain + NOTES)))] == ["notes"]


def libreoffice_text_box(style: str, words: str = "<text:p>Hi</text:p>") -> str:
    return (
        f'<draw:custom-shape draw:style-name="{style}" svg:x="1cm" svg:y="1cm" svg:width="5cm" svg:height="2cm">'
        f'{words}<draw:enhanced-geometry draw:type="ooxml-rect"/></draw:custom-shape>'
    )


def test_a_rectangle_with_words_and_no_fill_or_outline_is_a_text_box():
    # LibreOffice writes PowerPoint's text boxes this way; the style says "none" through its parent
    data = an_odp(page(libreoffice_text_box("bare")), automatic=BARE)
    model = odp_to_slides(data)
    assert [(o.body.kind, o.body.shape, o.body.paragraph.text) for o in model.objects_on("s1")] == [
        ("text", None, "Hi")
    ]


@pytest.mark.parametrize(
    ("style", "words"), [("filled", "<text:p>Hi</text:p>"), ("bare", "<text:p/>"), ("none", "<text:p>Hi</text:p>")]
)
def test_a_rectangle_with_a_fill_or_without_words_or_style_stays_a_shape(style, words):
    data = an_odp(page(libreoffice_text_box(style, words)), automatic=BARE)
    assert [o.body.kind for o in odp_to_slides(data).objects_on("s1")] == ["shape"]


def test_the_words_of_a_libreoffice_text_box_can_be_edited_and_added_in_place():
    data = an_odp(page(libreoffice_text_box("bare") + libreoffice_text_box("bare", "<text:p/>")), automatic=BARE)
    baseline, current = odp_to_slides(data), odp_to_slides(data)
    first = current.objects["o1"]
    current.replace_object(first.with_body(paragraph=first.body.paragraph.with_text("Changed", ()).written_by("ana")))
    edited = apply_edits_to_odp(data, baseline, current)
    assert odp_to_slides(edited).objects["o1"].body.paragraph.text == "Changed"
    assert "<text:p>Changed</text:p>" in content(edited)


def test_a_table_with_a_preview_picture_is_a_table():
    previewed = (
        '<draw:frame svg:x="1cm" svg:y="5cm" svg:width="8cm" svg:height="4cm"><table:table table:name="t"/>'
        '<draw:image xlink:href="Pictures/p.svm"/></draw:frame>'
    )
    assert [loss.kind for loss in odp_import_losses(an_odp(page(previewed)))] == ["table"]


def test_the_words_of_a_text_box_are_its_paragraphs_one_per_line():
    model = odp_to_slides(RICH)
    assert model.objects["o1"].body.paragraph.text == "Hello"
    assert model.objects["o4"].body.paragraph.text == "Line one\nLine two"


def test_places_and_sizes_come_in_slide_units():
    first = odp_to_slides(RICH).objects["o1"]
    assert (first.anchor.x, first.anchor.y, first.body.w, first.body.h) == (
        round(2 / CM_PER_UNIT),
        round(3 / CM_PER_UNIT),
        round(10 / CM_PER_UNIT),
        round(2 / CM_PER_UNIT),
    )


@pytest.mark.parametrize(
    ("given", "units"),
    [
        ("20mm", 20 / 10 / CM_PER_UNIT),
        ("1in", 2.54 / CM_PER_UNIT),
        ("72pt", 2.54 / CM_PER_UNIT),
        ("1.5cm", 1.5 / CM_PER_UNIT),
    ],
)
def test_every_length_unit_of_the_format_is_understood(given, units):
    data = an_odp(page(textbox(x=given)))
    assert odp_to_slides(data).objects["o1"].anchor.x == round(units)


def test_the_scale_comes_from_the_page_not_from_an_assumed_shape():
    data = an_odp(page(textbox(x="14cm", y="5cm", w="7cm", h="2.5cm")), width="28cm", height="21cm")  # 4:3
    first = odp_to_slides(data).objects["o1"]
    assert (first.anchor.x, first.anchor.y) == (800, round(5 / 21 * 900))


def test_a_deck_without_pages_is_an_empty_deck():
    assert odp_to_slides(an_odp("")).slides == SlideModel.empty().slides


@pytest.mark.parametrize(
    "markup",
    [
        textbox(extra=' draw:transform="rotate (0.5) translate (1cm 1cm)"'),
        textbox(x="30cm"),
        textbox(w="auto"),
    ],
)
def test_an_object_that_cannot_be_placed_is_not_in_the_model_and_is_reported(markup):
    data = an_odp(page(markup))
    assert odp_to_slides(data).objects == {}
    assert odp_import_losses(data)


def test_what_the_model_does_not_show_is_reported():
    kinds = {loss.kind: loss.count for loss in odp_import_losses(RICH)}
    assert kinds == {"picture": 1, "table": 1, "notes": 1, "look": 3}


def test_other_things_on_a_slide_are_reported_by_what_they_are():
    data = an_odp(page(GROUP + LINE + custom("star5") + textbox()))
    kinds = {loss.kind for loss in odp_import_losses(data)}
    assert {"group", "shape"} <= kinds


def test_a_transition_and_an_animation_are_reported():
    automatic = (
        '<style:style style:name="dp1" style:family="drawing-page"><style:drawing-page-properties '
        'presentation:transition-type="automatic" presentation:duration="PT5S"/></style:style>'
    )
    data = an_odp(
        '<draw:page draw:name="page1" draw:style-name="dp1" draw:master-page-name="Default">'
        + textbox()
        + "<anim:par/></draw:page>",
        automatic=automatic,
    )
    kinds = {loss.kind for loss in odp_import_losses(data)}
    assert {"transition", "animation"} <= kinds


def test_a_file_that_is_not_an_opendocument_presentation_is_an_error_with_a_sentence():
    with pytest.raises(OdfError):
        odp_to_slides(b"not a zip")
    text = new_package("text", b"<x/>", b"<y/>")
    with pytest.raises(OdfError, match="presentation"):
        odp_to_slides(text)


@pytest.mark.parametrize(
    ("parts", "sentence"),
    [
        ({"content.xml": b"<x/>"}, "no mimetype"),
        ({"mimetype": b"text/plain", "content.xml": b"<x/>"}, "no mimetype"),
        ({"mimetype": b"application/vnd.oasis.opendocument.presentation"}, "no content.xml"),
    ],
)
def test_a_package_that_lacks_what_an_odp_has_is_an_error_with_a_sentence(parts, sentence):
    from claudia_opc_io import write_parts

    with pytest.raises(OdfError, match=sentence):
        odp_to_slides(write_parts(parts))


def test_content_that_is_not_xml_or_has_no_presentation_is_an_error_with_a_sentence():
    from claudia_opc_io import write_parts

    mime = b"application/vnd.oasis.opendocument.presentation"
    with pytest.raises(OdfError, match="well-formed"):
        odp_to_slides(write_parts({"mimetype": mime, "content.xml": b"<office:document-content"}))
    bare = f"{HEAD}<office:document-content {DECLS}><office:body/></office:document-content>".encode()
    with pytest.raises(OdfError, match="no slides"):
        odp_to_slides(write_parts({"mimetype": mime, "content.xml": bare}))


def test_a_deck_without_styles_or_masters_is_as_big_as_a_new_slide():
    from claudia_opc_io import read_parts, write_parts

    parts = read_parts(an_odp(page(textbox(), "p").replace(' draw:master-page-name="Default"', "")))
    del parts["styles.xml"]
    first = odp_to_slides(write_parts(parts)).objects["o1"]
    assert (first.anchor.x, first.body.w) == (round(2 / CM_PER_UNIT), round(10 / CM_PER_UNIT))


def test_an_animation_is_reported_once_per_slide_however_many_there_are():
    two = "<anim:par/><anim:seq/>"
    assert [(loss.kind, loss.count) for loss in odp_import_losses(an_odp(page(two)))] == [("animation", 1)]


def test_a_frame_with_something_else_in_it_is_reported_and_a_comment_between_objects_is_ignored():
    odd = '<draw:frame svg:x="1cm" svg:y="1cm" svg:width="2cm" svg:height="2cm"><draw:plugin/></draw:frame>'
    data = an_odp(page("<!-- a note -->" + odd + textbox()))
    assert ("frame", 1) in [(loss.kind, loss.count) for loss in odp_import_losses(data)]
    assert list(odp_to_slides(data).objects) == ["o1"]


def test_more_objects_than_the_model_holds_are_left_out_and_reported():
    many = "".join(
        textbox(x=f"{0.1 + 0.7 * (n % 40):.1f}cm", y=f"{0.1 + 0.7 * (n // 40):.1f}cm", w="0.6cm", h="0.6cm")
        for n in range(503)
    )
    model = odp_to_slides(an_odp(page(many)))
    assert len(model.objects) == 500
    assert ("unfit-object", 3) in {(loss.kind, loss.count) for loss in odp_import_losses(an_odp(page(many)))}


def test_a_deck_that_nobody_wrote_words_in_loses_nothing_and_an_empty_one_neither():
    model = SlideModel.empty()
    assert odp_export_losses(model) == ()
    assert odp_export_losses(a_deck()) != ()  # the words of a deck have authors, which a file cannot keep


# -- edit and re-export ----------------------------------------------------------------------------------------------
def edit(original: bytes, change, **options) -> tuple[bytes, SlideModel, SlideModel]:
    baseline, current = odp_to_slides(original), odp_to_slides(original)
    change(current)
    return apply_edits_to_odp(original, baseline, current, **options), baseline, current


def move(model: SlideModel, object_id: str, x: int, y: int) -> None:
    old = model.objects[object_id]
    model.replace_object(VisualObject(old.body, SlideAnchor(old.anchor.slide, x, y)))


def retext(model: SlideModel, object_id: str, text: str) -> None:
    old = model.objects[object_id]
    paragraph = paragraph_for(object_id, old.body.paragraph.style, text, "ana")
    model.replace_object(VisualObject(replace(old.body, paragraph=paragraph), old.anchor))


def test_without_edits_the_file_comes_back_exactly_as_it_was():
    assert apply_edits_to_odp(RICH, odp_to_slides(RICH), odp_to_slides(RICH)) == RICH


def test_moving_an_object_changes_its_start_tag_and_nothing_else_in_the_file():
    edited, _, _ = edit(RICH, lambda model: move(model, "o1", 800, 450))
    old, new = content(RICH), content(edited)
    start = old.index("<draw:frame")
    end = old.index(">", start)
    assert new.startswith(old[:start]) and new.endswith(old[end + 1 :])
    assert 'svg:x="14cm"' in new[start : new.index(">", start) + 1]
    for name in set(read_parts(RICH)) - {"content.xml"}:
        assert read_parts(edited)[name] == read_parts(RICH)[name]
    assert problems(edited) == []


def test_only_the_values_that_changed_are_written():
    edited, _, _ = edit(RICH, lambda model: move(model, "o1", 800, model.objects["o1"].anchor.y))
    first = pages_of(edited)[0][0]
    assert first.get(f"{{{NS['svg']}}}y") == "3cm" and first.get(f"{{{NS['svg']}}}width") == "10cm"


def test_retexting_a_paragraph_edits_it_in_place():
    original = an_odp(
        page(
            textbox(
                words=(
                    '<text:p text:style-name="P1">Hello <text:span text:style-name="T1">big</text:span> world</text:p>'
                )
            )
        )
    )
    edited, _, _ = edit(original, lambda model: retext(model, "o1", "Hello big planet"))
    assert '<text:span text:style-name="T1">big</text:span>' in content(edited)
    assert odp_to_slides(edited).objects["o1"].body.paragraph.text == "Hello big planet"


def test_a_text_with_more_lines_gets_more_paragraphs_and_one_with_fewer_loses_them():
    more, _, _ = edit(RICH, lambda model: retext(model, "o1", "a\nb\nc"))
    assert odp_to_slides(more).objects["o1"].body.paragraph.text == "a\nb\nc"
    fewer, _, _ = edit(RICH, lambda model: retext(model, "o4", "only"))
    assert odp_to_slides(fewer).objects["o4"].body.paragraph.text == "only"
    assert problems(more) == problems(fewer) == []


def test_a_shape_with_no_words_can_get_some():
    edited, _, _ = edit(RICH, lambda model: retext(model, "o2", "now with words"))
    assert odp_to_slides(edited).objects["o2"].body.paragraph.text == "now with words"


def test_what_the_model_does_not_show_is_still_there_after_an_edit():
    edited, _, _ = edit(RICH, lambda model: retext(model, "o1", "changed"))
    new = content(edited)
    for kept in (PICTURE, TABLE, NOTES):
        assert kept in new


def test_a_new_object_goes_on_its_slide_in_front_and_before_the_notes():
    def add(model: SlideModel) -> None:
        model.insert_object(an_object("o9", "s1", "text", 100, 100, 200, 100, "body-text", "new"))

    edited, _, _ = edit(RICH, add)
    names = [etree.QName(child).localname for child in pages_of(edited)[0]]
    assert names[-1] == "notes" and names[-2] == "frame"
    assert "new" in content(edited) and problems(edited) == []
    assert odp_to_slides(edited).objects_on("s1")[-1].body.paragraph.text == "new"


def test_a_removed_object_is_gone_and_the_rest_is_as_it_was():
    edited, _, _ = edit(RICH, lambda model: model.delete_object("o2"))
    assert ellipse() not in content(edited) and PICTURE in content(edited)
    assert odp_to_slides(edited).objects["o2"].body.shape == "triangle"  # ids are places: the triangle moved up


def test_a_removed_slide_and_what_was_on_it_are_reported():
    def drop(model: SlideModel) -> None:
        for object_id in model.stack_of("s1"):
            model.delete_object(object_id)
        model.delete_slide("s1")

    log = LossLog()
    baseline, current = odp_to_slides(RICH), odp_to_slides(RICH)
    drop(current)
    edited = apply_edits_to_odp(RICH, baseline, current, losses=log)
    assert len(pages_of(edited)) == 1
    assert {loss.kind for loss in log.result()} >= {"removed-picture", "removed-table", "removed-notes"}


def test_a_new_slide_goes_where_it_is_with_the_master_of_its_neighbour():
    def add(model: SlideModel) -> None:
        model.insert_slide("s9", 1)
        model.insert_object(an_object("o9", "s9", "text", 10, 10, 300, 100, "body-text", "between"))

    edited, _, _ = edit(RICH, add)
    pages = pages_of(edited)
    assert len(pages) == 3
    assert pages[1].get(f"{{{NS['draw']}}}master-page-name") == "Default"
    assert pages[1].findtext(".//text:p", namespaces=NS) == "between"
    assert problems(edited) == []


def test_a_new_first_slide_goes_before_the_others_with_the_first_ones_master():
    def add(model: SlideModel) -> None:
        model.insert_slide("s9", 0)
        model.insert_object(an_object("o9", "s9", "text", 10, 10, 300, 100, "body-text", "first"))

    edited, _, _ = edit(RICH, add)
    assert [read_text_of(page) for page in pages_of(edited)][0] == "first"
    assert pages_of(edited)[0].get(f"{{{NS['draw']}}}master-page-name") == "Default"
    assert problems(edited) == []


def read_text_of(page_element: etree._Element) -> str:
    return "".join(page_element.itertext()).strip()


def test_slides_and_objects_can_be_added_to_a_deck_with_no_pages_and_to_an_empty_page():
    def fill(model: SlideModel) -> None:
        if not model.objects:
            model.insert_object(an_object("o1", "s1", "text", 100, 100, 300, 100, "body-text", "hello"))

    empty_deck = an_odp("")
    edited, _, current = edit(empty_deck, fill)
    assert [o.body.paragraph.text for o in odp_to_slides(edited).objects.values()] == ["hello"]
    assert len(pages_of(edited)) == 1 and current.slides == ["s1"]

    empty_page = an_odp(page(""))
    edited, _, _ = edit(empty_page, fill)
    assert [o.body.paragraph.text for o in odp_to_slides(edited).objects.values()] == ["hello"]
    assert len(pages_of(edited)) == 1


def test_a_second_slide_is_added_after_the_first_of_a_deck_that_has_one_page():
    def add(model: SlideModel) -> None:
        model.insert_slide("s2")
        model.insert_object(an_object("o9", "s2", "text", 100, 100, 200, 100, "body-text", "second"))

    edited, _, _ = edit(an_odp(page(textbox())), add)
    assert len(pages_of(edited)) == 2 and problems(edited) == []


def test_slides_in_another_order_cannot_be_patched():
    baseline, current = odp_to_slides(RICH), odp_to_slides(RICH)
    current.slides.reverse()
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_odp(RICH, baseline, current)


def test_a_baseline_that_is_not_the_file_cannot_be_patched():
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_odp(RICH, SlideModel.empty(), SlideModel.empty())


def test_changing_the_look_of_an_object_gives_it_a_style_of_its_own():
    def restyle(model: SlideModel) -> None:
        # An outline without a fill: a shape's own slot takes outline styles only (D304, D305).
        model.styles.add(StyleDef("hollow", "Hollow", "an unfilled outline", None, {"fill": "none"}, kind="outline"))
        old = model.objects["o2"]
        model.replace_object(VisualObject(replace(old.body, style="hollow"), old.anchor))

    edited, _, _ = edit(RICH, restyle)
    assert problems(edited) == []
    shape = next(e for e in tree(edited).iter(f"{{{NS['draw']}}}ellipse"))
    name = shape.get(f"{{{NS['draw']}}}style-name")
    assert name != "gr2"  # not the style the file had: that one is for whoever else uses it
    style = next(
        s
        for s in tree(edited).iterfind(".//office:automatic-styles/style:style", NS)
        if s.get(f"{{{NS['style']}}}name") == name
    )
    props = style.find("style:graphic-properties", NS)
    assert props is not None and props.get(f"{{{NS['draw']}}}fill") == "none"
    assert 'draw:style-name="gr2"' in content(RICH) and 'draw:name="gr2"' not in content(edited)


def test_the_metadata_of_a_changed_file_says_who_changed_it_and_when():
    info = DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob")
    edited, _, _ = edit(RICH, lambda model: move(model, "o1", 800, 450), info=info)
    found = read_info(read_parts(edited)["meta.xml"])
    assert (found.modified, found.modifier) == ("2026-11-11T17:13:05Z", "Bob")


def test_the_metadata_of_a_file_that_was_not_changed_is_not_touched():
    info = DocumentInfo(modified="2026-11-11T17:13:05Z", modifier="Bob")
    assert apply_edits_to_odp(RICH, odp_to_slides(RICH), odp_to_slides(RICH), info=info) == RICH


# -- the property that matters ---------------------------------------------------------------------------------------
def test_random_moves_and_retexts_always_give_the_edited_deck_and_leave_the_rest_alone():
    rng = random.Random(412)
    words = ["alpha", "beta", "x,", "  ", "ünï", "…", "a\nb"]
    old = content(RICH)
    for _ in range(120):
        baseline, current = odp_to_slides(RICH), odp_to_slides(RICH)
        for object_id in list(current.objects):
            roll = rng.random()
            if roll < 0.3:
                move(current, object_id, rng.randint(0, 600), rng.randint(0, 400))
            elif roll < 0.55:
                retext(current, object_id, "".join(rng.choice(words) for _ in range(rng.randint(0, 4))))
        edited = apply_edits_to_odp(RICH, baseline, current)
        assert problems(edited) == []
        again = odp_to_slides(edited)
        for object_id, wanted in current.objects.items():
            got = again.objects[object_id]
            assert (got.anchor.x, got.anchor.y) == (wanted.anchor.x, wanted.anchor.y)
            assert got.body.paragraph.text == wanted.body.paragraph.text
        new = content(edited)
        for kept in (PICTURE, TABLE, NOTES):
            assert kept in new
        assert new.startswith(old[: old.index("<draw:page")])


# -- what an object says to someone who cannot see it (BITV 1.1.1) -------------------------------------------------
def a_deck_with_picture(**changes) -> SlideModel:
    deck = SlideModel.empty()
    asset = a_gif()
    deck.define_image(asset)
    body = ObjectBody("o1", "image", 40, 20, "plain-image", image=asset.id, imported=an_import(asset), **changes)
    deck.insert_object(VisualObject(body, SlideAnchor("s1", 10, 10)))
    return deck


def a_picture_frame(data: bytes):
    (frame,) = etree.fromstring(read_parts(data)["content.xml"]).iter(f"{{{NS['draw']}}}frame")
    return frame


def test_a_picture_carries_its_description_as_svg_desc():
    frame = a_picture_frame(slides_to_odp(a_deck_with_picture(description="two cyclists at a finish line")))
    assert frame.find("svg:desc", NS).text == "two cyclists at a finish line"


def test_a_picture_without_a_description_of_its_own_is_described_by_what_it_was_imported_with():
    assert a_picture_frame(slides_to_odp(a_deck_with_picture())).find("svg:desc", NS).text == "a picture"


def test_a_decorative_picture_has_no_text_alternative_in_the_file():
    frame = a_picture_frame(slides_to_odp(a_deck_with_picture(decorative=True)))
    assert frame.find("svg:desc", NS) is None and frame.find("svg:title", NS) is None


def test_the_export_report_says_odf_cannot_keep_the_decorative_mark():
    """ODF 1.3 has no attribute for it, so a reader of the file sees an undescribed picture: that is a loss."""
    losses = odp_export_losses(a_deck_with_picture(decorative=True))
    assert [(loss.kind, loss.count) for loss in losses] == [("decorative", 1)]
    assert odp_export_losses(a_deck_with_picture()) == ()


# -- a rendered text container is a picture to a file (D344) ---------------------------------------------------------
GLYPHS = (
    b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="10">'
    b'<defs><symbol id="g"><path d="M0 0L5 5"/></symbol></defs><use xlink:href="#g"/></svg>'
)


def a_deck_with_container(*, pictured: bool = True, **changes) -> SlideModel:
    from claudia_core import RenderedDefinition

    deck = SlideModel.empty()
    asset = decode_image(GLYPHS, checked_drawing=True)
    deck.define_image(asset)
    deck.define_rendering(RenderedDefinition("r1", "typst", "= Hi", image=asset.id if pictured else None))
    body = ObjectBody("c1", "rendered", 300, 100, "plain-image", rendered="r1", **changes)
    deck.insert_object(VisualObject(body, SlideAnchor("s1", 10, 10)))
    return deck


def test_a_rendered_container_is_written_as_the_picture_made_from_its_text(tmp_path):
    data = slides_to_odp(a_deck_with_container(description="a heading that says Hi"))
    frame = a_picture_frame(data)
    href = frame.find("draw:image", NS).get(f"{{{NS['xlink']}}}href")
    assert href.endswith(".svg") and b"<use" in read_parts(data)[href]
    assert frame.find("svg:desc", NS).text == "a heading that says Hi"
    assert problems(data) == []


def test_a_container_nothing_was_made_for_yet_is_left_out_and_the_report_says_so():
    deck = a_deck_with_container(pictured=False)
    assert etree.fromstring(read_parts(slides_to_odp(deck))["content.xml"]).find(".//draw:frame", NS) is None
    assert [(loss.kind, loss.count) for loss in odp_export_losses(deck)] == [("rendering-pending", 1)]


def test_without_a_rasteriser_the_svg_goes_in_and_the_report_says_other_programs_may_draw_it_wrongly():
    assert [(loss.kind, loss.count) for loss in odp_export_losses(a_deck_with_container())] == [("svg-picture", 1)]


def test_with_a_rasteriser_the_picture_is_a_png_every_program_draws_and_nothing_is_lost():
    png = b"\x89PNG\r\n\x1a\nstand-in"
    seen = []

    def rasterise(svg: bytes, width: int, height: int) -> bytes:
        seen.append((svg[:4], width, height))
        return png

    deck = a_deck_with_container()
    data = slides_to_odp(deck, rasterise=rasterise)
    href = a_picture_frame(data).find("draw:image", NS).get(f"{{{NS['xlink']}}}href")
    assert href.endswith(".png") and read_parts(data)[href] == png and seen == [(b"<svg", 300, 100)]
    assert odp_export_losses(deck, rasterised=True) == () and problems(data) == []
