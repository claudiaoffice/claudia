"""A typeset SVG is shown in other people's browsers, so it is checked before it is stored (E3.4, D66)."""

import pytest

from claudia_typeset import UnsafeOutput, check_svg

GOOD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="20pt" height="10pt">'
    '<defs><g id="glyph0-1"><path d="M 0 0 L 1 1"/></g></defs>'
    '<use xlink:href="#glyph0-1" x="1" y="2"/>'
    "</svg>"
)


def test_what_a_pdf_converter_makes_is_accepted():
    assert check_svg(GOOD) == GOOD


def test_an_embedded_raster_figure_is_accepted():
    svg = GOOD.replace("<use", '<image xlink:href="data:image/png;base64,iVBORw0KGgo=" width="1" height="1"/><use')
    assert check_svg(svg) == svg


SVG = "xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'"


@pytest.mark.parametrize(
    "inside",
    [
        "<script>alert(1)</script>",
        "<foreignObject><p>x</p></foreignObject>",
        "<image xlink:href='http://evil/x.png'/>",
        "<a xlink:href='javascript:alert(1)'/>",
        "<image xlink:href='data:text/html;base64,PGI+'/>",
        "<style>@import url(http://evil/x.css);</style>",
        "<iframe src='x'/>",
        "<animate attributeName='href' to='javascript:x'/>",
        "<rect fill='url(http://evil/x.svg#a)'/>",
    ],
)
def test_active_content_and_outside_references_are_refused(inside):
    with pytest.raises(UnsafeOutput):
        check_svg(f"<svg {SVG}>{inside}</svg>")


def test_an_event_handler_is_refused():
    with pytest.raises(UnsafeOutput, match="event handler"):
        check_svg(f"<svg {SVG} onload='alert(1)'/>")


def test_a_reference_to_a_gradient_inside_the_picture_is_accepted():
    check_svg(f"<svg {SVG}><defs><linearGradient id='g'/></defs><rect fill='url(#g)'/></svg>")


def test_a_document_type_declaration_is_refused_because_entities_can_expand_without_end():
    bomb = '<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>'
    with pytest.raises(UnsafeOutput, match="DOCTYPE"):
        check_svg(bomb)


def test_something_that_is_not_xml_is_refused():
    with pytest.raises(UnsafeOutput, match="not valid"):
        check_svg("<svg><path")


def test_the_root_must_be_an_svg():
    with pytest.raises(UnsafeOutput, match="svg"):
        check_svg("<html xmlns='http://www.w3.org/1999/xhtml'/>")


# -- what some diagram tools draw besides paths: a profile widens the allowlist, never the rules about references ----
DIAGRAM = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'>"
    "<style>.node{fill:#fff;stroke:#333}</style>"
    "<marker id='m' markerWidth='4' markerHeight='4'><path d='M0 0L4 2L0 4z'/></marker>"
    "<text x='1' y='2'><tspan>hello</tspan></text></svg>"
)
DIAGRAM_ELEMENTS = frozenset({"style", "marker", "text", "tspan"})


def test_text_and_style_are_refused_unless_the_profile_names_them():
    with pytest.raises(UnsafeOutput, match="not allowed"):
        check_svg(DIAGRAM)
    assert check_svg(DIAGRAM, extra_elements=DIAGRAM_ELEMENTS) == DIAGRAM


def test_a_profile_cannot_allow_what_can_run_or_fetch():
    for name in ("script", "foreignObject", "iframe", "a", "animate", "set"):
        with pytest.raises(ValueError, match="never allowed"):
            check_svg(GOOD, extra_elements=frozenset({name}))


@pytest.mark.parametrize(
    "css",
    [
        "@import url(http://evil.example/x.css);",
        ".a{background:url(http://evil.example/x.png)}",
        ".a{background:url('https://evil.example/x.png')}",
        ".a{behavior:expression(alert(1))}",
        ".a{background:url(javascript:alert(1))}",
    ],
)
def test_style_text_that_reaches_outside_the_picture_is_refused(css):
    svg = DIAGRAM.replace(".node{fill:#fff;stroke:#333}", css)
    with pytest.raises(UnsafeOutput, match="style"):
        check_svg(svg, extra_elements=DIAGRAM_ELEMENTS)


def test_style_text_may_refer_to_something_in_the_picture():
    svg = DIAGRAM.replace(".node{fill:#fff;stroke:#333}", ".a{fill:url(#grad)}")
    assert check_svg(svg, extra_elements=DIAGRAM_ELEMENTS) == svg


def test_a_style_element_may_not_hold_other_elements():
    svg = DIAGRAM.replace("<style>.node{fill:#fff;stroke:#333}</style>", "<style><g/></style>")
    with pytest.raises(UnsafeOutput, match="style"):
        check_svg(svg, extra_elements=DIAGRAM_ELEMENTS)
