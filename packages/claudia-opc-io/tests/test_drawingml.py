"""What a DrawingML drawing says of itself, in a docx, an xlsx or a pptx alike: how it is turned, whether it is cropped,
which part it draws and whether it is decorative (D464, D1478)."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_opc_io import (
    DECORATIVE_URI,
    DRAWINGML,
    PRESET,
    SHAPE_OF,
    SVG_URI,
    UNKNOWN,
    add_svg,
    cropped,
    is_decorative,
    look_in,
    mark_decorative,
    outline,
    shown_part,
    solid,
    turn_of,
)

A, R = DRAWINGML["a"], DRAWINGML["r"]


def element(xml: str) -> etree._Element:
    return etree.fromstring(f'<root xmlns:a="{A}" xmlns:r="{R}">{xml}</root>')[0]


@pytest.mark.parametrize(
    ("xml", "turn"),
    [
        ('<a:xfrm rot="5400000"/>', 90),
        ('<a:xfrm rot="-1800000"/>', 330),
        ("<a:xfrm/>", 0),
        ('<a:xfrm rot="x"/>', 0),
        ('<a:xfrm flipH="1"/>', None),
        ('<a:xfrm flipV="true" rot="60000"/>', None),
    ],
)
def test_the_turn_of_a_drawing_is_in_whole_degrees_clockwise_and_a_flipped_one_has_none(xml, turn):
    assert turn_of(element(xml)) == turn


def test_a_drawing_without_a_transform_is_not_turned():
    assert turn_of(None) == 0


def test_a_picture_is_cropped_when_its_source_rectangle_cuts_something_off():
    assert cropped(element('<a:srcRect l="1000"/>'))
    assert not cropped(element('<a:srcRect l="0" t="0"/>'))
    assert not cropped(None)


def test_a_picture_draws_its_svg_when_it_has_one_beside_the_ordinary_picture():
    blip = f'<asvg:svgBlip xmlns:asvg="{DRAWINGML["asvg"]}" r:embed="rId3"/>'
    svg = f'<a:extLst><a:ext uri="{SVG_URI}">{blip}</a:ext></a:extLst>'
    assert shown_part(element(f'<a:blip r:embed="rId2">{svg}</a:blip>')) == "rId3"
    assert shown_part(element('<a:blip r:embed="rId2"/>')) == "rId2"


def test_a_drawing_says_it_is_decorative_by_office_s_mark():
    flag = f'<adec:decorative xmlns:adec="{DRAWINGML["adec"]}" val="1"/>'
    mark = f'<a:extLst><a:ext uri="{DECORATIVE_URI}">{flag}</a:ext></a:extLst>'
    assert is_decorative(element(f'<cNvPr descr="">{mark}</cNvPr>'))
    assert not is_decorative(element('<cNvPr descr="A logo"/>'))
    assert not is_decorative(None)


# -- the look of a shape (D465, D1479) ---------------------------------------------------------------------------------
def test_a_shape_is_drawn_filled_and_outlined_as_its_look_says_and_read_back_so():
    xml = f'<spPr xmlns:a="{A}">{solid((255, 0, 16))}{outline((0, 0, 0), 12700)}</spPr>'
    assert look_in(etree.fromstring(xml), styled=False) == ((255, 0, 16), (0, 0, 0), 12700)
    bare = f'<spPr xmlns:a="{A}">{solid(None)}{outline(None, 0)}</spPr>'
    assert look_in(etree.fromstring(bare), styled=False) == (None, None, 0)


def test_a_colour_that_is_no_plain_colour_is_unknown_and_what_a_style_gives_too():
    theme = f'<spPr xmlns:a="{A}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></spPr>'
    assert look_in(etree.fromstring(theme), styled=False)[0] == UNKNOWN
    assert look_in(etree.fromstring(f'<spPr xmlns:a="{A}"/>'), styled=True) == (UNKNOWN, UNKNOWN, 0)
    assert look_in(None, styled=False) == (None, None, 0)


def test_the_outlines_of_the_model_have_their_names_in_drawingml():
    assert PRESET == {"circle": "ellipse", "rectangle": "rect", "triangle": "triangle"}
    assert {SHAPE_OF[name] for name in PRESET.values()} == set(PRESET)


def test_a_drawing_marked_decorative_says_so_and_has_no_description():
    properties = etree.fromstring('<cNvPr id="2" name="Logo" descr="A logo"/>')
    mark_decorative(properties)
    assert is_decorative(properties)
    assert properties.get("descr") == ""


def test_a_line_width_that_is_no_number_is_none():
    xml = f'<spPr xmlns:a="{A}"><a:ln w="thick">{solid((0, 0, 0))}</a:ln></spPr>'
    assert look_in(etree.fromstring(xml), styled=False) == (None, (0, 0, 0), 0)


def test_an_svg_put_beside_a_picture_is_the_part_it_draws():
    blip = element('<a:blip r:embed="rId2"/>')
    add_svg(blip, "rId3")
    assert shown_part(blip) == "rId3"
    assert blip.find(f"{{{A}}}extLst/{{{A}}}ext").get("uri") == SVG_URI
