"""The styles of an odt: every paragraph style of the model written with its look and the colours of its palette,
and replaced in a kept file when the model changed them (D455)."""

from __future__ import annotations

from claudia_composes_io import apply_edits_to_odt, odt_export_losses, odt_to_text, text_to_odt
from lxml import etree
from test_odt import model_of

from claudia_composes import Block, TextModel
from claudia_core import StyleDef
from claudia_odf_io import NS, Loss
from claudia_opc_io import read_parts


def style_in(data: bytes, name: str) -> etree._Element:
    root = etree.fromstring(read_parts(data)["styles.xml"])
    found = root.find(f"office:styles/style:style[@style:name='{name}']", NS)
    assert found is not None, name
    return found


def text_of(style: etree._Element) -> dict[str, str]:
    found = style.find("style:text-properties", NS)
    return {} if found is None else {etree.QName(k).localname: v for k, v in found.attrib.items()}


def paragraph_of(style: etree._Element) -> dict[str, str]:
    found = style.find("style:paragraph-properties", NS)
    return {} if found is None else {etree.QName(k).localname: v for k, v in found.attrib.items()}


def with_style(css: dict[str, str], *, based_on: str | None = "body", name: str = "Call out") -> TextModel:
    model = model_of(("callout", "words"))
    model.styles.add(StyleDef("callout", name, "", based_on, css))
    return model


def test_the_built_in_styles_are_written_under_the_names_other_programs_know():
    data = text_to_odt(model_of(("title", "t"), ("heading-1", "h"), ("quote", "q"), ("body", "b")))
    assert style_in(data, "Title").get(f"{{{NS['style']}}}parent-style-name") == "Standard"
    assert style_in(data, "Heading_20_1").get(f"{{{NS['style']}}}default-outline-level") == "1"
    assert style_in(data, "Quotations") is not None
    assert style_in(data, "Standard").get(f"{{{NS['style']}}}parent-style-name") is None


def test_a_style_is_written_with_its_own_look_and_not_with_that_of_its_parent():
    data = text_to_odt(model_of(("title", "t")))
    look = text_of(style_in(data, "Title"))
    assert look["font-size"] == "30pt" and look["font-weight"] == "500" and look["font-family"].startswith("Fraunces")
    assert "color" not in look  # it has the body's colour by being based on it


def test_the_colour_a_style_names_is_the_colour_of_the_palette_role_it_names():
    model = with_style({"color": "@accent"})
    assert text_of(style_in(text_to_odt(model), "Call_20_out"))["color"] == "#5B4BC4"
    model.palette.set_colour("accent", "#112233")
    assert text_of(style_in(text_to_odt(model), "Call_20_out"))["color"] == "#112233"


def test_a_translucent_colour_is_written_as_the_colour_it_shows_on_white_paper():
    paragraph = paragraph_of(style_in(text_to_odt(with_style({"background-color": "@accent/8"})), "Call_20_out"))
    assert paragraph["background-color"] == "#F2F1FA"


def test_the_borders_and_paddings_of_a_style_are_written_by_side():
    paragraph = paragraph_of(style_in(text_to_odt(model_of(("quote", "q"))), "Quotations"))
    assert paragraph["border-left"] == "2.25pt solid #F2A057" and paragraph["padding-left"] == "15.4pt"


def test_a_style_of_the_model_that_is_not_built_in_is_written_by_its_name_and_used_by_its_blocks():
    data = text_to_odt(with_style({"font-weight": "700"}))
    style = style_in(data, "Call_20_out")
    assert style.get(f"{{{NS['style']}}}display-name") is None  # the name spells the display name already
    assert style.get(f"{{{NS['style']}}}parent-style-name") == "Standard"
    assert text_of(style)["font-weight"] == "bold"
    paragraph = etree.fromstring(read_parts(data)["content.xml"]).find(".//text:p", NS)
    assert paragraph is not None and paragraph.get(f"{{{NS['text']}}}style-name") == "Call_20_out"


def test_a_custom_style_never_takes_the_name_of_another():
    styles = etree.fromstring(read_parts(text_to_odt(with_style({}, name="Standard")))["styles.xml"])
    names = [s.get(f"{{{NS['style']}}}name") for s in styles.iterfind("office:styles/style:style", NS)]
    assert len(names) == len(set(names)) and "Standard_2" in names


def test_what_a_file_cannot_say_of_a_style_is_a_loss_and_a_style_the_model_lacks_is_one_too():
    model = with_style({"word-spacing": "3pt"})
    model.blocks.append(Block("b9", "missing", "x"))
    assert odt_export_losses(model) == (Loss("style", "missing"), Loss("style-property", "callout: word-spacing"))


def test_the_look_survives_a_trip_through_the_file():
    model = model_of(("heading-1", "h"), ("body", "b"))
    again = odt_to_text(text_to_odt(model))
    assert [b.style for b in again.blocks] == ["heading-1", "body"]


def test_a_kept_file_is_left_as_it_is_when_the_styles_did_not_change():
    original = text_to_odt(model_of(("body", "b")))
    baseline = odt_to_text(original)
    assert apply_edits_to_odt(original, baseline, odt_to_text(original)) == original


def test_a_changed_palette_colour_replaces_the_styles_that_use_it_and_leaves_the_others():
    original = text_to_odt(model_of(("body", "b")))
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.palette.set_colour("text", "#112233")
    patched = apply_edits_to_odt(original, baseline, current)
    assert text_of(style_in(patched, "Standard"))["color"] == "#112233"
    assert text_of(style_in(patched, "Title")) == text_of(style_in(original, "Title"))  # it has the body's colour


def test_a_style_the_file_has_under_the_name_of_a_new_style_is_not_written_over():
    original = text_to_odt(with_style({"color": "@accent"}))  # the file has "Call out", the text read from it does not
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.styles.add(StyleDef("callout", "Call out", "", "body", {"font-style": "italic"}))
    current.blocks[0] = Block(current.blocks[0].id, "callout", "words")
    patched = apply_edits_to_odt(original, baseline, current)
    assert text_of(style_in(patched, "Call_20_out")) == text_of(style_in(original, "Call_20_out"))
    assert text_of(style_in(patched, "Call_20_out_2"))["font-style"] == "italic"


def test_a_style_made_after_the_file_was_read_is_added_to_it_and_used_by_the_paragraph_that_has_it():
    original = text_to_odt(model_of(("body", "b")))
    baseline = odt_to_text(original)
    current = odt_to_text(original)
    current.styles.add(StyleDef("callout", "Call out", "", "body", {"font-style": "italic"}))
    current.blocks[0] = Block(current.blocks[0].id, "callout", "b")
    patched = apply_edits_to_odt(original, baseline, current)
    assert text_of(style_in(patched, "Call_20_out"))["font-style"] == "italic"
    paragraph = etree.fromstring(read_parts(patched)["content.xml"]).find(".//text:p", NS)
    assert paragraph is not None and paragraph.get(f"{{{NS['text']}}}style-name") == "Call_20_out"


def test_a_style_has_its_underline_and_its_strike_through():
    look = text_of(style_in(text_to_odt(with_style({"text-decoration": "underline line-through"})), "Call_20_out"))
    assert look["text-underline-style"] == "solid" and look["text-line-through-style"] == "solid"
    plain = text_of(style_in(text_to_odt(with_style({"text-decoration": "none"})), "Call_20_out"))
    assert plain["text-underline-style"] == "none" and plain["text-line-through-style"] == "none"
