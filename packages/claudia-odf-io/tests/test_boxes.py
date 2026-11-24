"""The OpenDocument elements of a text box or a shape, shared by the text, the spreadsheet and the presentation app
(D465, D1479, CODE-84)."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_odf_io import NS, OUTLINES, BoxLook, fill_and_line, graphic_styles, hex_of, outline_element, put_words


def q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


@pytest.mark.parametrize(
    ("shape", "tag"), [(None, "frame"), ("circle", "ellipse"), ("rectangle", "rect"), ("triangle", "custom-shape")]
)
def test_each_outline_of_the_model_is_the_element_odf_draws_it_with(shape, tag):
    element = outline_element(shape)
    assert etree.QName(element).localname == tag
    if shape is None:
        assert element.find(q("draw", "text-box")) is not None
    if shape == "triangle":
        assert element.find(q("draw", "enhanced-geometry")).get(q("draw", "type")) == "isosceles-triangle"


def test_words_go_into_the_text_box_of_a_frame_and_before_the_geometry_of_a_custom_shape():
    words = [etree.Element(q("text", "p")), etree.Element(q("text", "p"))]
    frame = outline_element(None)
    put_words(frame, words)
    assert len(frame.find(q("draw", "text-box"))) == 2
    triangle = outline_element("triangle")
    put_words(triangle, [etree.Element(q("text", "p"))])
    assert [etree.QName(child).localname for child in triangle] == ["p", "enhanced-geometry"]


def test_the_outlines_a_file_names_include_those_libreoffice_takes_from_powerpoint():
    assert OUTLINES["isosceles-triangle"] == OUTLINES["ooxml-triangle"] == "triangle"
    assert OUTLINES["ellipse"] == OUTLINES["ooxml-ellipse"] == "circle"
    assert OUTLINES["rectangle"] == OUTLINES["ooxml-rect"] == "rectangle"


def test_a_fill_and_a_line_are_said_as_odf_says_them():
    assert fill_and_line(BoxLook((255, 0, 16), (0, 0, 0), 12700)) == (
        'draw:fill="solid" draw:fill-color="#ff0010" draw:stroke="solid" svg:stroke-color="#000000" '
        'svg:stroke-width="1pt"'
    )
    assert fill_and_line(BoxLook(None, None, 0)) == 'draw:fill="none" draw:stroke="none"'
    assert hex_of((1, 2, 3)) == "#010203"


def test_an_automatic_style_wins_over_a_common_style_of_the_same_name():
    def styles(colour: str) -> etree._Element:
        return etree.fromstring(
            f'<office:styles xmlns:office="{NS["office"]}" xmlns:style="{NS["style"]}">'
            f'<style:style style:name="gr1" style:family="graphic" style:display-name="{colour}"/></office:styles>'
        )

    found = graphic_styles(styles("automatic"), styles("common"))
    assert found["gr1"].get(q("style", "display-name")) == "automatic"
