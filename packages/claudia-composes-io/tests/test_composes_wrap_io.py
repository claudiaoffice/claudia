"""How the text flows round a floating object, in a docx and in an odt (D1061, D1066): written, read back, and changed
in a kept file. Pictures and boxes say it the same way."""

from __future__ import annotations

import re
import zipfile
from dataclasses import replace
from io import BytesIO

import pytest
from claudia_composes_io import (
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_to_text,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)

from claudia_composes import DEFAULT_STYLE, Paragraph, ParagraphAnchor, TextModel
from claudia_core import ObjectBody, VisualObject, paragraph_for, picture_body
from claudia_core.assets import ImageAsset

MODES = ["over", "around", "above-below", "behind"]


def png() -> ImageAsset:
    import base64

    from claudia_core import decode_image

    one_pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return decode_image(one_pixel)


def a_text(wrap="over", gap=8, *, picture=False) -> TextModel:
    model = TextModel(
        [Paragraph("b1", DEFAULT_STYLE, "Hello world and some more words"), Paragraph("b2", DEFAULT_STYLE, "Next")]
    )
    anchor = ParagraphAnchor("b1", 5, wrap=wrap, gap=gap)
    if picture:
        asset = png()
        model.images.define(asset)
        body = picture_body("o1", asset, (90, 90), name="p", description="a picture", decorative=False, rotation=0)
    else:
        body = ObjectBody("o1", "text", 200, 100, "plain-box", paragraph_for("o1", "body", "Words"))
    model.insert_object(VisualObject(body, anchor))
    return model


def only(model: TextModel) -> VisualObject:
    (found,) = model.objects.values()
    return found


def part(data: bytes, name: str) -> str:
    return zipfile.ZipFile(BytesIO(data)).read(name).decode()


# ----------------------------------------------------------------------------------------------------------- docx
@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", MODES)
def test_the_wrap_of_an_object_comes_back_from_a_docx(wrap, picture):
    back = docx_to_text(text_to_docx(a_text(wrap, 20, picture=picture)))
    anchor = only(back).anchor
    assert anchor.wrap == wrap
    assert anchor.gap == (20 if wrap in ("around", "above-below") else 8)


def test_word_is_told_in_its_own_words_which_way_the_text_flows():
    said = {wrap: part(text_to_docx(a_text(wrap, 10)), "word/document.xml") for wrap in MODES}
    assert "<wp:wrapNone/>" in said["over"] and 'behindDoc="0"' in said["over"]
    assert '<wp:wrapSquare wrapText="bothSides"/>' in said["around"]
    assert f'distL="{10 * 9525}"' in said["around"] and f'distT="{10 * 9525}"' in said["around"]
    assert "<wp:wrapTopAndBottom/>" in said["above-below"]
    assert 'distL="0"' in said["above-below"] and f'distT="{10 * 9525}"' in said["above-below"]
    assert "<wp:wrapNone/>" in said["behind"] and 'behindDoc="1"' in said["behind"]


def test_an_object_that_floats_over_the_text_is_written_as_it_always_was():
    xml = part(text_to_docx(a_text()), "word/document.xml")
    assert 'distT="0" distB="0" distL="0" distR="0"' in xml and 'behindDoc="0"' in xml


@pytest.mark.parametrize(
    ("tag", "wrap"),
    [("wrapTight", "around"), ("wrapThrough", "around"), ("wrapSquare", "around"), ("wrapTopAndBottom", "above-below")],
)
def test_the_wrapping_a_program_other_than_ours_writes_reads_as_the_nearest_mode(tag, wrap):
    data = text_to_docx(a_text("around", 8))
    xml = part(data, "word/document.xml")
    changed = re.sub(r'<wp:wrapSquare wrapText="bothSides"/>', f"<wp:{tag}/>", xml)
    assert only(docx_to_text(replace_part(data, "word/document.xml", changed))).anchor.wrap == wrap


def replace_part(data: bytes, name: str, text: str) -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            target.writestr(item, text.encode() if item.filename == name else source.read(item.filename))
    return out.getvalue()


def test_an_inline_picture_floats_over_the_text_as_before():
    data = text_to_docx(a_text(picture=True))
    xml = part(data, "word/document.xml")
    inline = re.sub(r"<wp:anchor .*?<wp:extent", "<wp:inline><wp:extent", xml, flags=re.S)
    inline = re.sub(r"<wp:wrapNone/>", "", inline)
    inline = inline.replace("</wp:anchor>", "</wp:inline>")
    back = docx_to_text(replace_part(data, "word/document.xml", inline))
    assert only(back).anchor.wrap == "over"


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", ["around", "above-below", "behind", "over"])
def test_a_wrap_changed_in_the_model_is_changed_in_the_kept_file_and_nothing_else(wrap, picture):
    original = text_to_docx(a_text("over" if wrap != "over" else "around", 8, picture=picture))
    baseline, current = docx_to_text(original), docx_to_text(original)
    found = only(current)
    current.replace_object(VisualObject(found.body, replace(found.anchor, wrap=wrap, gap=14)))
    data = apply_edits_to_docx(original, baseline, current)
    assert only(docx_to_text(data)).anchor.wrap == wrap
    assert only(docx_to_text(data)).anchor.offset == 5 and only(docx_to_text(data)).body.id == found.body.id


def test_a_wrap_that_does_not_change_leaves_the_kept_file_as_it_was_byte_for_byte():
    original = text_to_docx(a_text("around", 8))
    baseline, current = docx_to_text(original), docx_to_text(original)
    data = apply_edits_to_docx(original, baseline, current)
    assert part(data, "word/document.xml") == part(original, "word/document.xml")


# ------------------------------------------------------------------------------------------------------------ odt
@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", MODES)
def test_the_wrap_of_an_object_comes_back_from_an_odt(wrap, picture):
    anchor = only(odt_to_text(text_to_odt(a_text(wrap, 20, picture=picture)))).anchor
    assert anchor.wrap == wrap
    assert abs(anchor.gap - (20 if wrap in ("around", "above-below") else 8)) <= 1  # (centimetres, to 3 places)


def graphic_properties(data: bytes) -> list[str]:
    xml = part(data, "content.xml") + part(data, "styles.xml")
    return re.findall(r"<style:graphic-properties[^>]*>", xml)


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
def test_an_odt_says_in_the_words_of_odf_which_way_the_text_flows(picture):
    said = {wrap: " ".join(graphic_properties(text_to_odt(a_text(wrap, 10, picture=picture)))) for wrap in MODES}
    assert 'style:wrap="run-through" style:run-through="foreground"' in said["over"]
    assert 'style:wrap="parallel"' in said["around"] and 'fo:margin-left="0.265cm"' in said["around"]
    assert 'style:wrap="none"' in said["above-below"] and 'fo:margin-left="0cm"' in said["above-below"]
    assert 'style:wrap="run-through" style:run-through="background"' in said["behind"]


def test_an_object_that_floats_over_the_text_is_no_longer_written_so_that_the_text_is_pushed_off_the_page():
    """ODF's ``wrap="none"`` keeps the words above and below a frame (D1066); the export wrote it for every object."""
    for picture in (False, True):
        assert 'style:wrap="none"' not in " ".join(graphic_properties(text_to_odt(a_text(picture=picture))))


@pytest.mark.parametrize(
    ("wrap", "mode"),
    [("parallel", "around"), ("dynamic", "around"), ("left", "around"), ("biggest", "around"), ("none", "above-below")],
)
def test_the_wrapping_a_program_other_than_ours_writes_reads_as_the_nearest_mode_in_an_odt(wrap, mode):
    data = text_to_odt(a_text("around", 8))
    xml = part(data, "content.xml").replace('style:wrap="parallel"', f'style:wrap="{wrap}"')
    assert only(odt_to_text(replace_part(data, "content.xml", xml))).anchor.wrap == mode


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", ["around", "above-below", "behind", "over"])
def test_a_wrap_changed_in_the_model_is_changed_in_the_kept_odt_and_the_look_stays(wrap, picture):
    original = text_to_odt(a_text("over" if wrap != "over" else "around", 8, picture=picture))
    baseline, current = odt_to_text(original), odt_to_text(original)
    found = only(current)
    current.replace_object(VisualObject(found.body, replace(found.anchor, wrap=wrap, gap=14)))
    data = apply_edits_to_odt(original, baseline, current)
    back = only(odt_to_text(data))
    assert back.anchor.wrap == wrap and back.anchor.offset == 5 and back.body.id == found.body.id
    assert (back.body.w, back.body.h) == (found.body.w, found.body.h)
    if not picture:
        assert back.body.paragraph.text == "Words"


def test_a_wrap_that_does_not_change_leaves_the_kept_odt_as_it_was():
    original = text_to_odt(a_text("around", 8))
    baseline, current = odt_to_text(original), odt_to_text(original)
    data = apply_edits_to_odt(original, baseline, current)
    assert part(data, "content.xml") == part(original, "content.xml")


def test_a_second_change_of_the_wrap_of_a_kept_odt_builds_on_the_first():
    original = text_to_odt(a_text("over", 8))
    first_base, first = odt_to_text(original), odt_to_text(original)
    found = only(first)
    first.replace_object(VisualObject(found.body, replace(found.anchor, wrap="around", gap=12)))
    middle = apply_edits_to_odt(original, first_base, first)
    second_base, second = odt_to_text(middle), odt_to_text(middle)
    found = only(second)
    second.replace_object(VisualObject(found.body, replace(found.anchor, wrap="above-below", gap=4)))
    last = apply_edits_to_odt(middle, second_base, second)
    assert only(odt_to_text(last)).anchor.wrap == "above-below"
