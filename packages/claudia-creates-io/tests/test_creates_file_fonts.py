"""The fonts of a deck survive a file written from nothing (E3.13, bug 2), on the shared sample, and are no loss: what
``pptx_to_slides`` and ``odp_to_slides`` read is what ``slides_to_pptx`` and ``slides_to_odp`` write."""

import re
from io import BytesIO
from pathlib import Path

import pytest
from claudia_creates_io import (
    odp_import_losses,
    odp_to_slides,
    pptx_import_losses,
    pptx_to_slides,
    slides_to_odp,
    slides_to_pptx,
)
from pptx import Presentation

from claudia_opc_io import read_parts, write_parts

LIBRARY = Path(__file__).resolve().parents[3] / "test-documents"
FORMATS = {
    "pptx": (pptx_to_slides, slides_to_pptx, pptx_import_losses),
    "odp": (odp_to_slides, slides_to_odp, odp_import_losses),
}


def fonts(model) -> dict[str, str]:
    """The font of each box of the first slide, by its words."""
    return {
        o.body.paragraph.text: model.styles.computed(o.body.paragraph.style)["font-family"]
        for o in model.objects_on("s1")
    }


def sample(fmt: str) -> bytes:
    return (LIBRARY / fmt / "stand-in-fonts" / f"source.{fmt}").read_bytes()


@pytest.mark.parametrize("fmt", FORMATS)
def test_the_fonts_of_the_sample_come_back_from_a_file_written_from_nothing(fmt):
    read, write, _ = FORMATS[fmt]
    model = read(sample(fmt))
    assert fonts(read(write(model))) == fonts(model)


def _without_fonts(pptx: bytes) -> bytes:
    """The same deck with no font named on any run: what the losses would be if fonts were not modelled at all."""
    parts = read_parts(pptx)
    for name in [n for n in parts if n.startswith("ppt/slides/slide")]:
        parts[name] = re.sub(rb"<a:latin [^>]*/>", b"", parts[name])
    return write_parts(parts)


def test_the_fonts_of_the_pptx_sample_add_no_loss():
    """The sample's boxes still lose their size (PowerPoint's 18 points, which the model does not hold: ``look``), but
    their fonts add nothing: the losses are those of the same deck with no font named."""
    data = sample("pptx")
    assert pptx_import_losses(data) == pptx_import_losses(_without_fonts(data))
    assert "formatting" not in [loss.kind for loss in pptx_import_losses(data)]


def test_the_fonts_of_the_odp_sample_are_no_loss():
    assert [loss.kind for loss in odp_import_losses(sample("odp"))] == []


def test_a_box_in_two_fonts_takes_the_first_and_says_the_other_is_formatting():
    prs = Presentation()
    box = prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_textbox(0, 0, 3_000_000, 500_000)
    paragraph = box.text_frame.paragraphs[0]
    for words, font in (("Plain ", "Georgia"), ("code", "Courier New")):
        run = paragraph.add_run()
        run.text, run.font.name = words, font
    data = BytesIO()
    prs.save(data)
    model = pptx_to_slides(data.getvalue())
    words = model.objects_on("s1")[0].body.paragraph
    assert model.styles.computed(words.style)["font-family"] == "Georgia, serif"
    assert "formatting" in [loss.kind for loss in pptx_import_losses(data.getvalue())]


def test_an_odp_box_in_two_fonts_takes_the_first_and_says_the_other_is_formatting():
    """Words in a second font are ``formatting``; a span whose style says only a font is not, on its own."""
    content = read_parts(sample("odp"))["content.xml"].decode()
    two = re.sub(
        r'(<text:span text:style-name="T1">[^<]*</text:span>)',
        r'\1<text:span text:style-name="T2"> and more</text:span>',
        content,
        count=1,
    )
    parts = read_parts(sample("odp"))
    parts["content.xml"] = two.encode()
    data = write_parts(parts)
    assert [loss.kind for loss in odp_import_losses(data)] == ["formatting"]
    model = odp_to_slides(data)
    first = next(o for o in model.objects_on("s1") if o.body.paragraph.text.endswith(" and more"))
    assert model.styles.computed(first.body.paragraph.style)["font-family"].startswith("Helvetica")


def test_a_written_odp_names_the_body_font_once_and_no_stand_in():
    written = read_parts(slides_to_odp(odp_to_slides(sample("odp"))))
    assert b'style:family="graphic"><style:text-properties fo:font-family="Arial"/>' in written["styles.xml"]
    assert b"Arimo" not in written["content.xml"] + written["styles.xml"]
