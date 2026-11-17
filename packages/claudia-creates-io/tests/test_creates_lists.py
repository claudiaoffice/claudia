"""Lists in the text boxes of a presentation, in a pptx and an odp (E9.21, E9.22, step D): written, read back, and
what neither can hold is said."""

from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import pytest
from claudia_creates_io import (
    UnsupportedEdit,
    apply_edits_to_odp,
    apply_edits_to_pptx,
    odp_import_losses,
    odp_to_slides,
    pptx_export_losses,
    pptx_to_slides,
    slides_to_odp,
    slides_to_pptx,
)
from lxml import etree
from pptx import Presentation

from claudia_core import ListDef, ListItem, ObjectBody, VisualObject, paragraph_for
from claudia_creates import SlideAnchor, SlideModel
from claudia_odf_io import NS
from claudia_opc_io import read_parts

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def box(object_id: str, slide: str, text: str, item: ListItem | None = None, style: str = "body-text"):
    words = paragraph_for(object_id, style, text).with_item(item)
    return VisualObject(ObjectBody(object_id, "text", 400, 120, "plain-box", words), SlideAnchor(slide, 100, 100))


def deck(scheme: str = "numbers") -> SlideModel:
    """Two slides: on the first the items one and two (level 0, 1), on the second the item three (level 0) and a
    plain box."""
    model = SlideModel.empty()
    model.insert_slide("s2")
    model.lists.add(ListDef("l1", scheme))
    model.insert_object(box("o1", "s1", "one", ListItem("l1")))
    model.insert_object(box("o2", "s1", "two", ListItem("l1", 1)))
    model.insert_object(box("o3", "s2", "three", ListItem("l1")))
    model.insert_object(box("o4", "s2", "plain"))
    return model


def markers(model: SlideModel) -> list[str]:
    labels = model.labels()
    return [labels[p.paragraph.id].marker for p in model.reading_order() if p.paragraph.id in labels]


def bullets(data: bytes) -> list[tuple[str | None, dict]]:
    """The bullet element of the first paragraph of every shape, in order, with its attributes."""
    found = []
    for slide in Presentation(BytesIO(data)).slides:
        for shape in slide.shapes:
            properties = shape.text_frame.paragraphs[0]._p.pPr
            element = (
                None
                if properties is None
                else next((c for c in properties if etree.QName(c).localname in ("buAutoNum", "buChar")), None)
            )
            found.append(
                (
                    None if element is None else etree.QName(element).localname,
                    dict(element.attrib) if element is not None else {},
                )
            )
    return found


# ----------------------------------------------------------------------------- pptx
def test_a_list_across_boxes_is_written_as_automatic_numbers_that_count_on():
    data = slides_to_pptx(deck())
    assert bullets(data) == [
        ("buAutoNum", {"type": "arabicPeriod"}),
        ("buAutoNum", {"type": "alphaLcPeriod"}),
        ("buAutoNum", {"type": "arabicPeriod", "startAt": "2"}),
        (None, {}),
    ]
    assert pptx_export_losses(deck()) == pptx_export_losses(SlideModel.empty())


def test_a_list_read_back_from_a_pptx_runs_on_across_its_boxes():
    model = pptx_to_slides(slides_to_pptx(deck()))
    assert markers(model) == ["1.", "a.", "2."]
    assert len(model.lists) == 1


def test_bullets_are_written_as_bullet_signs_and_read_back():
    data = slides_to_pptx(deck("bullets"))
    assert [kind for kind, _ in bullets(data)][:3] == ["buChar"] * 3
    assert markers(pptx_to_slides(data)) == ["•", "◦", "•"]


def test_numbered_slide_titles_are_written_as_plain_numbers():
    model = SlideModel.empty()
    model.insert_slide("s2")
    model.lists.add(ListDef("outline", "chapters"))
    model.styles.set_numbering("slide-title", "outline")
    model.insert_object(box("t1", "s1", "Why", style="slide-title"))
    model.insert_object(box("t2", "s2", "How", style="slide-title"))
    data = slides_to_pptx(model)
    assert bullets(data) == [
        ("buAutoNum", {"type": "arabicPlain"}),
        ("buAutoNum", {"type": "arabicPlain", "startAt": "2"}),
    ]
    assert markers(pptx_to_slides(data)) == ["1", "2"]


def test_a_marker_powerpoint_cannot_number_is_left_out_and_said():
    model = deck("chapters")
    assert [kind for kind, _ in bullets(slides_to_pptx(model))] == ["buAutoNum", None, "buAutoNum", None]
    assert ("list-look", 1) in [(loss.kind, loss.count) for loss in pptx_export_losses(model)]


def test_making_a_box_an_item_is_patched_into_the_original_file():
    original = slides_to_pptx(deck())
    baseline, current = pptx_to_slides(original), pptx_to_slides(original)
    words = current.get_object("o4").body.paragraph
    current.replace_object(current.get_object("o4").with_body(paragraph=words.with_item(ListItem("l1"))))
    patched = pptx_to_slides(apply_edits_to_pptx(original, baseline, current))
    assert markers(patched) == ["1.", "a.", "2.", "3."]


# ----------------------------------------------------------------------------- odp
def test_a_list_across_boxes_is_one_list_in_an_odp_and_comes_back():
    data = slides_to_odp(deck())
    content = etree.fromstring(read_parts(data)["content.xml"])
    tops = [e for e in content.iter(f"{{{NS['text']}}}list") if e.getparent().tag != f"{{{NS['text']}}}list-item"]
    assert tops[0].get(f"{{{NS['xml']}}}id") == "list1"
    assert [t.get(f"{{{NS['text']}}}continue-list") for t in tops[1:]] == ["list1", "list1"]
    model = odp_to_slides(data)
    assert markers(model) == ["1.", "a.", "2."] and len(model.lists) == 1
    assert ("list-look", 1) not in [(loss.kind, loss.count) for loss in odp_import_losses(data)]


def test_a_scheme_of_the_presentations_own_goes_into_the_odp_and_comes_back():
    model = deck()
    numbers = model.schemes.get("numbers")
    model.schemes.replace(replace(numbers, levels=(replace(numbers.levels[0], before="Step "), *numbers.levels[1:])))
    back = odp_to_slides(slides_to_odp(model))
    assert markers(back) == ["Step 1.", "a.", "Step 2."]


@pytest.mark.parametrize("scheme", ["bullets", "chapters"])
def test_every_built_in_scheme_survives_an_odp(scheme):
    assert markers(odp_to_slides(slides_to_odp(deck(scheme)))) == markers(deck(scheme))


# ----------------------------------------------------------------------------- agendas (E9.31)
def with_agenda() -> SlideModel:
    from claudia_core import Toc

    model = SlideModel.empty()
    model.insert_slide("s2")
    model.insert_object(box("t1", "s1", "Why", style="slide-title"))
    model.insert_object(box("t2", "s2", "How", style="slide-title"))
    agenda = paragraph_for("ag", "body-text", "").with_generated(Toc(1, 1))
    model.insert_object(
        VisualObject(ObjectBody("ag", "text", 400, 300, "plain-box", agenda), SlideAnchor("s1", 100, 300))
    )
    return model


@pytest.mark.parametrize(
    ("write", "read", "losses"),
    [(slides_to_pptx, pptx_to_slides, pptx_export_losses), (slides_to_odp, odp_to_slides, None)],
)
def test_an_agenda_is_written_as_the_lines_it_shows_and_the_loss_is_said(write, read, losses):
    back = read(write(with_agenda()))
    words = [
        o.body.paragraph.text
        for o in back.objects.values()
        if o.body.paragraph and "Why" in o.body.paragraph.text and "How" in o.body.paragraph.text
    ]
    assert words == ["Why\t1\nHow\t2"]
    if losses is not None:
        assert ("agenda", 1) in [(loss.kind, loss.count) for loss in losses(with_agenda())]


def test_a_retitled_slide_rewrites_the_agenda_of_a_kept_pptx():
    baseline, current = with_agenda(), with_agenda()
    original = slides_to_pptx(baseline)
    titled = current.objects["t1"]
    current.replace_object(titled.with_body(paragraph=paragraph_for("t1", "slide-title", "Why we did it")))
    patched = pptx_to_slides(apply_edits_to_pptx(original, baseline, current))
    words = [o.body.paragraph.text for o in patched.objects.values() if o.body.paragraph]
    assert "Why we did it\t1\nHow\t2" in words


def test_a_kept_odp_whose_agenda_changed_is_written_afresh_instead():
    baseline, current = with_agenda(), with_agenda()
    current.replace_object(
        current.objects["t1"].with_body(paragraph=paragraph_for("t1", "slide-title", "Why we did it"))
    )
    with pytest.raises(UnsupportedEdit):  # the file keeps no agenda, nor ids: it is written afresh
        apply_edits_to_odp(slides_to_odp(baseline), baseline, current)
