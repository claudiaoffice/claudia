"""The CSS a style may hold (E1.10, D75): a short, versioned allow-list; nothing that can reach outside the page."""

import pytest

from claudia_core import ALLOWED_CSS, CSS_VERSION, CssError, format_css, parse_css, validate_css


# ----------------------------------------------------------------------------- the list
def test_the_list_is_versioned_and_has_what_the_style_menu_needs():
    # 2: a colour may be a role of the palette (D200); 3: a cell's box (D307); 4: hyphens (D912)
    assert CSS_VERSION == 4
    assert {
        "color",
        "background-color",
        "font-family",
        "font-size",
        "font-weight",
        "font-style",
        "text-decoration",
        "text-align",
        "line-height",
        "fill",
        "stroke",
        "stroke-width",
    } <= ALLOWED_CSS


# ----------------------------------------------------------------------------- values that are accepted
@pytest.mark.parametrize(
    ("prop", "value"),
    [
        ("color", "#1F1A33"),
        ("color", "#fff"),
        ("color", "#1f1a33cc"),
        ("color", "rgb(31, 26, 51)"),
        ("color", "rgba(31, 26, 51, 0.5)"),
        ("color", "hsl(250 50% 40%)"),
        ("color", "hsl(250, 50%, 40%)"),
        ("color", "rebeccapurple"),
        ("color", "transparent"),
        ("background-color", "#F7F3EC"),
        ("font-size", "12pt"),
        ("font-size", "14px"),
        ("font-size", "1.25rem"),
        ("font-size", "110%"),
        ("font-weight", "bold"),
        ("font-weight", "600"),
        ("font-style", "italic"),
        ("text-decoration", "underline"),
        ("text-decoration", "underline line-through"),
        ("text-decoration", "none"),
        ("text-align", "justify"),
        ("line-height", "1.4"),
        ("line-height", "normal"),
        ("line-height", "18pt"),
        ("letter-spacing", "0.02em"),
        ("letter-spacing", "normal"),
        ("word-spacing", "2px"),
        ("margin-top", "12pt"),
        ("margin-left", "0"),
        ("padding-left", "1.1em"),
        ("padding-top", "0"),
        ("border-left", "3px solid #D6477A"),
        ("border-bottom", "1px dotted rgba(0, 0, 0, 0.3)"),
        ("border-top", "none"),
        ("font-family", "Inter, system-ui, sans-serif"),
        ("font-family", "'Segoe UI', Fraunces, serif"),
        ("font-family", '"JetBrains Mono", monospace'),
        ("fill", "#E7E1F4"),
        ("fill", "none"),
        ("stroke", "#5B4BC4"),
        ("stroke-width", "4px"),
    ],
)
def test_allowed_values_pass_and_keep_their_spelling(prop, value):
    assert validate_css({prop: value}) == {prop: value}


def test_a_border_is_written_in_one_clean_form():
    assert validate_css({"border-left": "3PX  SOLID   #D6477A"}) == {"border-left": "3px solid #D6477A"}


def test_keywords_are_lower_cased_and_spaces_collapsed():
    cleaned = validate_css({"font-weight": " BOLD ", "text-decoration": "Underline   Line-Through"})
    assert cleaned == {"font-weight": "bold", "text-decoration": "underline line-through"}


# ----------------------------------------------------------------------------- values that are refused
@pytest.mark.parametrize(
    ("prop", "value"),
    [
        ("color", "url(http://example.com/x.png)"),
        ("color", "var(--accent)"),
        ("color", "red !important"),
        ("color", "#12"),
        ("color", "notacolour"),
        ("color", "rgb(1, 2)"),
        ("color", "red; background: url(x)"),
        ("font-size", "calc(1em + 2px)"),
        ("font-size", "-3pt"),
        ("font-size", "0"),
        ("font-size", "5000px"),
        ("font-size", "large-ish"),
        ("font-weight", "650"),
        ("font-weight", "heavy"),
        ("font-style", "slanted"),
        ("text-decoration", "underline blink"),
        ("text-decoration", "underline underline"),
        ("text-align", "middle"),
        ("line-height", "-1"),
        ("line-height", "99"),
        ("margin-top", "auto"),
        ("padding-left", "-1em"),
        ("border-left", "3px"),
        ("border-left", "thick solid red"),
        ("border-left", "3px groove red"),
        ("border-left", "3px solid url(x)"),
        ("border-left", "300px solid red"),
        ("font-family", "url(x.woff2)"),
        ("font-family", "Inter; color: red"),
        ("font-family", "Inter }"),
        ("font-family", "'unclosed"),
        ("font-family", ""),
        ("font-family", "a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p, q, r, s, t, u"),
        ("fill", "url(#x)"),
        ("stroke-width", "-1px"),
    ],
)
def test_dangerous_or_malformed_values_are_refused_and_the_property_is_named(prop, value):
    with pytest.raises(CssError) as caught:
        validate_css({prop: value})
    (problem,) = caught.value.problems
    assert problem.property == prop
    assert prop in str(caught.value)


@pytest.mark.parametrize(
    "prop", ["position", "background", "background-image", "behavior", "content", "--x", "@import", "font"]
)
def test_properties_that_are_not_on_the_list_are_refused(prop):
    with pytest.raises(CssError) as caught:
        validate_css({prop: "none"})
    assert caught.value.problems[0].property == prop


def test_all_problems_of_a_style_are_reported_together():
    with pytest.raises(CssError) as caught:
        validate_css({"color": "nope", "font-size": "huge", "font-weight": "bold"})
    assert sorted(p.property for p in caught.value.problems) == ["color", "font-size"]


# ----------------------------------------------------------------------------- text <-> dict
def test_parsing_a_block_of_declarations():
    css, problems = parse_css("font-size: 12pt;\ncolor: #1F1A33;\nfont-family: 'Segoe UI', serif;\n")
    assert problems == []
    assert css == {"font-size": "12pt", "color": "#1F1A33", "font-family": "'Segoe UI', serif"}


def test_the_last_semicolon_is_optional_and_empty_declarations_are_ignored():
    assert parse_css("color: red;;\n\nfont-style: italic")[0] == {"color": "red", "font-style": "italic"}


def test_a_semicolon_inside_quotes_does_not_split_the_declaration():
    css, problems = parse_css("font-family: 'A;B', serif; color: red")
    assert css == {"color": "red"}
    assert [p.property for p in problems] == ["font-family"]  # one problem, not a second one for “B', serif”


def test_parsing_reports_the_line_and_keeps_what_is_valid():
    css, problems = parse_css(
        "color: red;\nfont-size: huge;\nposition: absolute;\nfont-style italic;\nfont-weight: bold"
    )
    assert css == {"color": "red", "font-weight": "bold"}
    assert [(p.line, p.property) for p in problems] == [(2, "font-size"), (3, "position"), (4, None)]
    assert "property: value" in problems[2].message


def test_a_property_set_twice_is_a_problem_not_a_silent_choice():
    css, problems = parse_css("color: red;\ncolor: blue;")
    assert css == {"color": "red"}
    assert [(p.line, p.property) for p in problems] == [(2, "color")]


def test_comments_are_refused_because_they_would_not_be_kept():
    _, problems = parse_css("/* big */ font-size: 12pt")
    assert problems and "comment" in problems[0].message.lower()


def test_the_text_of_a_style_has_a_fixed_order_and_round_trips():
    css = {"stroke": "none", "color": "#000", "font-size": "12pt", "font-family": "serif", "text-align": "left"}
    text = format_css(css)
    assert text == "font-family: serif;\nfont-size: 12pt;\ncolor: #000;\ntext-align: left;\nstroke: none;"
    assert parse_css(text) == (css, [])
    assert format_css({}) == ""


def test_problems_are_plain_data():
    with pytest.raises(CssError) as caught:
        validate_css({"color": "nope"})
    data = caught.value.problems[0].to_data()
    assert data["property"] == "color" and data["line"] is None and "color" in data["message"]


@pytest.mark.parametrize(
    ("prop", "value"), [("vertical-align", "middle"), ("white-space", "pre-wrap"), ("white-space", "nowrap")]
)
def test_a_cells_box_may_say_where_its_content_sits_and_whether_it_wraps(prop, value):
    """CSS_VERSION 3 (D307): two keywords a cell needs and no style had."""
    assert validate_css({prop: value}) == {prop: value}


@pytest.mark.parametrize(("prop", "value"), [("vertical-align", "baseline"), ("white-space", "pre")])
def test_only_the_keywords_a_cell_uses_are_allowed(prop, value):
    with pytest.raises(CssError, match=prop):
        validate_css({prop: value})


@pytest.mark.parametrize("value", ["none", "manual", "auto", "AUTO"])
def test_a_paragraph_may_say_whether_its_words_are_hyphenated(value):
    """CSS_VERSION 4 (D912): the CSS keywords, nothing else."""
    assert validate_css({"hyphens": value}) == {"hyphens": value.lower()}


def test_hyphens_takes_only_its_keywords():
    with pytest.raises(CssError, match="hyphens"):
        validate_css({"hyphens": "always"})
