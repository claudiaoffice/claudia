"""A deck with the fonts odp files set (E3.13, bug 2; ``test-documents/stand-in-fonts.json``): Body text takes the
deck's body font, and a text box in another font (the title in the heading font, a box somebody gave a font) gets a
style of its own, based on Body text, named by its font until somebody names it. No stand-in is written into the
document. An edit to one box's words keeps its font, and the file keeps naming every font."""

from __future__ import annotations

import json
from pathlib import Path

from claudia_creates import SlideModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

TABLE = json.loads((Path(__file__).parents[2] / "stand-in-fonts.json").read_text(encoding="utf-8"))
GENERIC = {entry["family"]: entry["generic"] for entry in TABLE["fonts"]}
STAND_INS = {e["stand_in"] for e in TABLE["fonts"]} - {e["family"] for e in TABLE["fonts"]} - {None}
BODY, TITLE = TABLE["slides"]["body"], TABLE["slides"]["title"]
EDITED = "Helvetica"


def _stack(family: str) -> str:
    return f"{chr(39) + family + chr(39) if ' ' in family else family}, {GENERIC[family]}"


def _font(words: str) -> str:
    """The font the box whose words are ``words`` is in: its words name it (the title the heading font)."""
    return words.removesuffix(" (edited)")


def import_checks(model: SlideModel) -> None:
    assert model.styles.computed("body-text")["font-family"] == _stack(BODY)
    boxes = model.objects_on("s1")
    assert sorted(_font(o.body.paragraph.text) for o in boxes) == sorted(
        [TITLE, *(e["family"] for e in TABLE["fonts"])]
    )
    for box in boxes:
        family = _font(box.body.paragraph.text)
        style = model.styles.get(box.body.paragraph.style)
        assert model.styles.computed(style.id)["font-family"] == _stack(family), family
        if family == BODY:
            assert style.id == "body-text"
        else:
            assert (style.based_on, style.name, style.to_name) == ("body-text", f"Body text · {family}", True)


def modify(model: SlideModel) -> SlideModel:
    box = next(o for o in model.objects_on("s1") if o.body.paragraph.text == EDITED)
    words = box.body.paragraph.with_text(f"{EDITED} (edited)", ()).written_by("ana")
    model.replace_object(box.with_body(paragraph=words))
    return model


def after_checks(model: SlideModel) -> None:
    import_checks(model)
    assert any(o.body.paragraph.text == f"{EDITED} (edited)" for o in model.objects_on("s1"))


def no_stand_in_is_written(exported: bytes) -> None:
    written = b"".join(read_parts(exported).values()).decode("utf-8", "ignore")
    for stand_in in STAND_INS:
        assert stand_in not in written, f"{stand_in} is a stand-in, never written into the file"


CASE = Case(import_checks=import_checks, modify=modify, after_checks=after_checks, export_checks=no_stand_in_is_written)
