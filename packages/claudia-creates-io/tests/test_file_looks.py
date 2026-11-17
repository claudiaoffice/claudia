"""What a file says of the look of a shape (D467): read from the XML of a pptx shape and the styles of an odp, and
made into styles of the model."""

from __future__ import annotations

import pytest
from claudia_creates_io._file_looks import LookBook
from claudia_creates_io._odp_looks import StyleIndex
from claudia_creates_io._pptx_looks import Theme, read_look
from lxml import etree

from claudia_creates import SlideModel
from claudia_odf_io import NS

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
UNITS_PER_EMU = 1 / 7620  # a 16:9 slide of 12,192,000 EMU shows 1600 units
THEME = f"""<a:theme xmlns:a="{A}"><a:themeElements><a:clrScheme name="t">
<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
<a:accent1><a:srgbClr val="4F81BD"/></a:accent1><a:accent2><a:srgbClr val="00FF00"/></a:accent2>
</a:clrScheme></a:themeElements></a:theme>""".encode()


def shape(properties: str = "", words: str = "", style: str = "") -> etree._Element:
    return etree.fromstring(
        f'<p:sp xmlns:a="{A}" xmlns:p="{P}"><p:spPr>{properties}</p:spPr>{style}'
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{words}</p:txBody></p:sp>"
    )


def test_a_theme_gives_the_colour_a_name_stands_for_and_system_colours_their_last_value():
    theme = Theme(THEME)

    def of(xml: str) -> tuple[str | None, bool]:
        return theme.colour(etree.fromstring(f'<a:solidFill xmlns:a="{A}">{xml}</a:solidFill>'))

    assert of('<a:schemeClr val="accent2"/>') == ("#00ff00", False)
    assert of('<a:schemeClr val="bg1"/>') == ("#ffffff", False)  # the page, which the theme calls light 1
    assert of('<a:schemeClr val="tx1"/>') == ("#000000", False)
    assert of('<a:srgbClr val="102030"/>') == ("#102030", False)
    assert of('<a:schemeClr val="accent1"><a:lumMod val="50000"/></a:schemeClr>') == ("#4f81bd", True)
    assert of('<a:schemeClr val="accent9"/>') == (None, False)
    assert of('<a:prstClr val="red"/>') == (None, True)  # a colour that is not named in a way the converter knows
    assert Theme().colour(etree.fromstring(f'<a:solidFill xmlns:a="{A}"/>')) == (None, False)


def test_a_fill_and_a_line_are_read_with_their_colours_and_width():
    found = read_look(
        shape(
            '<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>'
            '<a:ln w="25400"><a:solidFill><a:schemeClr val="accent2"/></a:solidFill></a:ln>'
        ),
        Theme(THEME),
        UNITS_PER_EMU,
        outline=True,
    )
    assert found.outline == {"fill": "#ff0000", "stroke": "#00ff00", "stroke-width": "3.3px"}
    assert not found.unread


def test_no_fill_and_no_line_are_read_as_none():
    found = read_look(shape("<a:noFill/><a:ln><a:noFill/></a:ln>"), Theme(), UNITS_PER_EMU, outline=True)
    assert found.outline == {"fill": "none", "stroke": "none"} and not found.unread


@pytest.mark.parametrize(
    "properties",
    [
        "<a:gradFill/>",
        "<a:pattFill/>",
        "<a:blipFill/>",
        '<a:solidFill><a:schemeClr val="accent9"/></a:solidFill>',
        "<a:ln><a:gradFill/></a:ln>",
        '<a:ln><a:solidFill><a:schemeClr val="accent9"/></a:solidFill></a:ln>',
        '<a:ln><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:prstDash val="dash"/></a:ln>',
        "<a:effectLst><a:outerShdw/></a:effectLst>",
    ],
)
def test_what_the_model_has_no_property_for_is_unread(properties):
    assert read_look(shape(properties), Theme(THEME), UNITS_PER_EMU, outline=True).unread


def test_a_shape_that_says_nothing_but_points_at_the_theme_gets_the_colour_of_the_theme():
    style = (
        '<p:style><a:lnRef idx="2"><a:schemeClr val="accent2"/></a:lnRef>'
        '<a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef><a:effectRef idx="0"/>'
        '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></p:style>'
    )
    found = read_look(shape(style=style, words="<a:p><a:r><a:t>Hi</a:t></a:r></a:p>"), Theme(THEME), 1, outline=True)
    assert found.outline == {"fill": "#4f81bd", "stroke": "#00ff00"}
    assert found.words == {"color": "#ffffff"}
    zero = '<p:style><a:lnRef idx="0"><a:schemeClr val="accent2"/></a:lnRef><a:fillRef idx="0"/></p:style>'
    assert read_look(shape(style=zero), Theme(THEME), 1, outline=True).outline == {}


def test_a_text_box_has_no_outline_and_what_is_drawn_around_it_is_said_to_be_unread():
    drawn = read_look(
        shape('<a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>'), Theme(), UNITS_PER_EMU, outline=False
    )
    assert drawn.outline == {} and drawn.unread
    bare = read_look(shape("<a:noFill/>"), Theme(), UNITS_PER_EMU, outline=False)
    assert bare.outline == {} and not bare.unread


def test_the_words_of_a_run_are_read_over_the_defaults_of_its_box():
    words = (
        '<a:p><a:pPr algn="ctr"/><a:r><a:rPr sz="3000" b="1" i="1"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill>'
        '<a:latin typeface="Segoe UI"/></a:rPr><a:t>Hi</a:t></a:r></a:p>'
    )
    xml = shape(words=words)
    xml.find(f".//{{{A}}}lstStyle").append(
        etree.fromstring(f'<a:lvl1pPr xmlns:a="{A}"><a:defRPr sz="2000" b="0"/></a:lvl1pPr>')
    )
    found = read_look(xml, Theme(), 1 / 12_700 * 1.0, outline=True)  # one unit is a point
    assert found.words == {
        "font-size": "30.0px",
        "font-weight": "bold",
        "font-style": "italic",
        "color": "#ff0000",
        "text-align": "center",
    }


def test_a_gradient_and_words_that_are_empty_say_nothing_or_are_unread():
    graded = "<a:p><a:r><a:rPr><a:gradFill/></a:rPr><a:t>Hi</a:t></a:r></a:p>"
    assert read_look(shape(words=graded), Theme(), 1, outline=True).unread
    assert read_look(shape(words="<a:p><a:r><a:t> </a:t></a:r></a:p>"), Theme(), 1, outline=True).words == {}
    no_words = etree.fromstring(f'<p:sp xmlns:a="{A}" xmlns:p="{P}"><p:spPr/></p:sp>')
    assert read_look(no_words, Theme(), 1, outline=True).words == {}


def test_a_look_the_model_cannot_hold_is_left_out_of_a_style_and_the_rest_is_kept():
    book = LookBook(SlideModel.empty())
    style = book.words("body-text", {"font-size": "banana", "color": "#ff0000"})
    assert style.startswith("file-paragraph-")
    assert book.words("body-text", {"font-size": "banana"}) == "body-text"
    assert book.words("body-text", {"color": "#ff0000"}) == style  # the same look is the same style


def test_the_styles_of_an_odp_are_found_by_family_and_name_with_the_ones_they_are_based_on():
    prefixes = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")
    root = etree.fromstring(
        f"<office:document-content {prefixes}><office:font-face-decls>"
        '<style:font-face style:name="Fira" svg:font-family="\'Fira Sans\'"/></office:font-face-decls>'
        '<office:automatic-styles><style:style style:name="a" style:family="paragraph" style:parent-style-name="b">'
        '<style:text-properties fo:color="#ff0000"/></style:style>'
        '<style:style style:name="b" style:family="paragraph"><style:text-properties fo:color="#00ff00" '
        'fo:font-weight="bold"/></style:style></office:automatic-styles></office:document-content>'
    )
    index = StyleIndex(None, root)
    assert index.attributes("paragraph", "a", "style:text-properties") == {
        "fo:color": "#ff0000",
        "fo:font-weight": "bold",
    }
    assert index.attributes("paragraph", "missing", "style:text-properties") == {}
