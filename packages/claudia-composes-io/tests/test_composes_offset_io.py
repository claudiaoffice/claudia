"""Where a floating object sits off the character it hangs from (``dx``, ``dy``), in a docx and in an odt (CODE-65,
D1067): written, read back within a pixel, and changed in a kept file. Pictures and boxes say it the same way, and so
do turned ones."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from claudia_composes_io import (
    apply_edits_to_docx,
    apply_edits_to_odt,
    docx_to_text,
    odt_to_text,
    text_to_docx,
    text_to_odt,
)
from test_composes_wrap_io import a_text, only, part, replace_part

from claudia_composes import BlockAnchor
from claudia_core import VisualObject

OFFSETS = [(0, 0), (40, 25), (-30, 12), (7, -19)]


def placed(wrap: str, dx: int, dy: int, *, picture: bool):
    model = a_text(wrap, 8, picture=picture)
    found = only(model)
    model.replace_object(VisualObject(found.body, replace(found.anchor, dx=dx, dy=dy)))
    return model


def seen(data: bytes, reader) -> BlockAnchor:
    return only(reader(data)).anchor


def close(anchor: BlockAnchor, dx: int, dy: int) -> bool:
    return abs(anchor.dx - dx) <= 1 and abs(anchor.dy - dy) <= 1


# ----------------------------------------------------------------------------------------------------------- docx
@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", ["over", "around", "above-below", "behind"])
@pytest.mark.parametrize(("dx", "dy"), OFFSETS)
def test_the_offset_of_an_object_comes_back_from_a_docx(dx, dy, wrap, picture):
    anchor = seen(text_to_docx(placed(wrap, dx, dy, picture=picture)), docx_to_text)
    assert close(anchor, dx, dy)
    assert anchor.wrap == wrap and anchor.offset == 5


def test_word_is_told_the_offset_from_the_character_and_the_line():
    xml = part(text_to_docx(placed("over", 10, 20, picture=False)), "word/document.xml")
    assert f'<wp:positionH relativeFrom="character"><wp:posOffset>{10 * 9525}</wp:posOffset>' in xml
    assert f'<wp:positionV relativeFrom="line"><wp:posOffset>{20 * 9525}</wp:posOffset>' in xml


def test_an_offset_of_a_file_that_is_measured_from_something_else_is_not_ours_to_read():
    xml = part(text_to_docx(placed("over", 10, 20, picture=False)), "word/document.xml")
    other = xml.replace('relativeFrom="character"', 'relativeFrom="column"')
    data = replace_part(text_to_docx(placed("over", 10, 20, picture=False)), "word/document.xml", other)
    anchor = seen(data, docx_to_text)
    assert (anchor.dx, anchor.dy) == (0, 20)  # the vertical one still says "line"


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
def test_a_moved_object_is_moved_in_the_kept_docx_and_nothing_else_is(picture):
    original = text_to_docx(a_text("around", 8, picture=picture))
    baseline, current = docx_to_text(original), docx_to_text(original)
    found = only(current)
    current.replace_object(VisualObject(found.body, replace(found.anchor, dx=33, dy=-14)))
    data = apply_edits_to_docx(original, baseline, current)
    anchor = seen(data, docx_to_text)
    assert close(anchor, 33, -14) and anchor.wrap == "around" and anchor.offset == 5


def test_an_object_that_is_not_moved_leaves_the_kept_docx_as_it_was_byte_for_byte():
    original = text_to_docx(placed("around", 12, 9, picture=False))
    baseline, current = docx_to_text(original), docx_to_text(original)
    data = apply_edits_to_docx(original, baseline, current)
    assert part(data, "word/document.xml") == part(original, "word/document.xml")


def test_an_offset_of_an_inline_picture_is_none():
    data = text_to_docx(placed("over", 10, 20, picture=True))
    xml = part(data, "word/document.xml")
    inline = re.sub(r"<wp:anchor .*?<wp:extent", "<wp:inline><wp:extent", xml, flags=re.S)
    inline = inline.replace("</wp:anchor>", "</wp:inline>")
    anchor = seen(replace_part(data, "word/document.xml", inline), docx_to_text)
    assert (anchor.dx, anchor.dy) == (0, 0)


# ------------------------------------------------------------------------------------------------------------ odt
@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
@pytest.mark.parametrize("wrap", ["over", "around", "above-below", "behind"])
@pytest.mark.parametrize(("dx", "dy"), OFFSETS)
def test_the_offset_of_an_object_comes_back_from_an_odt(dx, dy, wrap, picture):
    anchor = seen(text_to_odt(placed(wrap, dx, dy, picture=picture)), odt_to_text)
    assert close(anchor, dx, dy)
    assert anchor.wrap == wrap and anchor.offset == 5


def test_an_odt_measures_the_offset_from_the_character_and_the_line():
    data = text_to_odt(placed("over", 10, 20, picture=False))
    content, styles = part(data, "content.xml"), part(data, "styles.xml")
    assert 'style:horizontal-rel="char"' in content + styles and 'style:vertical-rel="line"' in content + styles


def test_an_odt_counts_the_offset_from_the_line_upwards_as_libreoffice_does():
    """LibreOffice draws ``svg:y`` against a line upwards (and writes a frame 40 px below its line as ``-0.4165in``):
    the file says what the program that opens it most often reads."""
    content = part(text_to_odt(placed("over", 0, 40, picture=False)), "content.xml")
    assert re.search(r'svg:y="-1\.0583cm"', content)


def test_a_turned_picture_keeps_its_offset_in_an_odt():
    model = placed("over", 25, 15, picture=True)
    found = only(model)
    body = replace(found.body, rotation=30)
    model.replace_object(VisualObject(body, found.anchor))
    anchor = seen(text_to_odt(model), odt_to_text)
    assert close(anchor, 25, 15)


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
def test_a_moved_object_is_moved_in_the_kept_odt_and_the_wrap_stays(picture):
    original = text_to_odt(a_text("around", 8, picture=picture))
    baseline, current = odt_to_text(original), odt_to_text(original)
    found = only(current)
    current.replace_object(VisualObject(found.body, replace(found.anchor, dx=33, dy=-14)))
    data = apply_edits_to_odt(original, baseline, current)
    anchor = seen(data, odt_to_text)
    assert close(anchor, 33, -14) and anchor.wrap == "around" and anchor.gap == 8 and anchor.offset == 5


@pytest.mark.parametrize("picture", [False, True], ids=["box", "picture"])
def test_a_second_move_of_a_kept_odt_builds_on_the_first(picture):
    original = text_to_odt(a_text("over", 8, picture=picture))
    first_base, first = odt_to_text(original), odt_to_text(original)
    found = only(first)
    first.replace_object(VisualObject(found.body, replace(found.anchor, dx=10, dy=10)))
    middle = apply_edits_to_odt(original, first_base, first)
    second_base, second = odt_to_text(middle), odt_to_text(middle)
    found = only(second)
    second.replace_object(VisualObject(found.body, replace(found.anchor, dx=-20, dy=5)))
    last = apply_edits_to_odt(middle, second_base, second)
    assert close(seen(last, odt_to_text), -20, 5)


def test_an_object_that_is_not_moved_leaves_the_kept_odt_as_it_was():
    original = text_to_odt(placed("around", 12, 9, picture=False))
    baseline, current = odt_to_text(original), odt_to_text(original)
    data = apply_edits_to_odt(original, baseline, current)
    assert part(data, "content.xml") == part(original, "content.xml")
