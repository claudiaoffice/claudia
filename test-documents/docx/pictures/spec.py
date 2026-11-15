"""Two pictures LibreOffice saved into a docx (one in the middle of a paragraph, one at the start of the next),
each with its description. Both come in as image objects hanging from their character. One is described anew, resized
and turned; the one nobody touched comes back as LibreOffice wrote it, and the pictures' own bytes are not touched
at all (D464)."""

from __future__ import annotations

from dataclasses import replace

from claudia_composes import BlockAnchor, TextModel
from claudia_core import VisualObject
from claudia_test_documents.case import Case

PICTURES = ["word/media/image1.gif", "word/media/image2.gif"]


def import_checks(model: TextModel) -> None:
    first, second = model.get_object("o1"), model.get_object("o2")
    assert (first.anchor, first.body.description, (first.body.w, first.body.h)) == (
        BlockAnchor("b2", 22),
        "Two cyclists on a hill",
        (180, 90),
    )
    assert (second.anchor, second.body.description) == (BlockAnchor("b3", 0), "A small mark")
    assert [block.text for block in model.blocks][0] == "Pictures"


def modify(model: TextModel) -> TextModel:
    found = model.get_object("o1")
    body = replace(found.body, description="Two cyclists on a green hill", w=360, h=180, rotation=90)
    model.replace_object(VisualObject(body, found.anchor))
    return model


def after_checks(model: TextModel) -> None:
    first, second = model.get_object("o1"), model.get_object("o2")
    assert (first.body.description, (first.body.w, first.body.h), first.body.rotation) == (
        "Two cyclists on a green hill",
        (360, 180),
        90,
    )
    assert (second.anchor, second.body.description, second.body.rotation) == (BlockAnchor("b3", 0), "A small mark", 0)
    assert model.blocks[2].text == "Nothing here changes."


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, preserve_parts=PICTURES)
