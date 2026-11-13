"""How big a picture is, read from the SVG itself, and what to say about it to somebody who cannot see it (D344)."""

import pytest

from claudia_render import default_alt, svg_size

NS = 'xmlns="http://www.w3.org/2000/svg"'


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ('width="120" height="60"', (120.0, 60.0)),
        ('width="90pt" height="45pt"', (120.0, 60.0)),
        ('width="25.4mm" height="2.54cm"', (96.0, 96.0)),
        ('width="1in" height="0.5in"', (96.0, 48.0)),
        ('width="12px" height="6px"', (12.0, 6.0)),
        ('width="100%" viewBox="0 0 300 150"', (300.0, 150.0)),
        ('viewBox="0 0 300 150"', (300.0, 150.0)),
        ('viewBox="10,20,300,150"', (300.0, 150.0)),
    ],
)
def test_size_is_read_from_the_attributes_or_the_view_box_in_pixels(attrs, expected):
    assert svg_size(f"<svg {NS} {attrs}/>") == expected


@pytest.mark.parametrize(
    "attrs", ["", 'width="0" height="10"', 'width="x" height="10"', 'viewBox="0 0 0 5"', 'viewBox="1 2"']
)
def test_a_picture_with_no_usable_size_is_refused(attrs):
    with pytest.raises(ValueError, match="size"):
        svg_size(f"<svg {NS} {attrs}/>")


def test_a_picture_that_is_absurdly_large_is_refused():
    with pytest.raises(ValueError, match="size"):
        svg_size(f'<svg {NS} width="100000" height="10"/>')


def test_the_alt_text_is_the_title_of_the_picture_when_it_has_one_else_the_kind_and_the_first_words():
    assert default_alt("mermaid", "flowchart LR\n A-->B", f"<svg {NS}><title>Order flow</title></svg>") == "Order flow"
    assert default_alt("mermaid", "flowchart LR\n A-->B", f"<svg {NS}/>") == "mermaid: flowchart LR A-->B"
    assert len(default_alt("latex", "x" * 500, f"<svg {NS}/>")) <= 200
