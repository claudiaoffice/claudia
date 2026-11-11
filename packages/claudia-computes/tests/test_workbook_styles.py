"""The styles a workbook starts with (D62, D73, D305, D310): the object styles, each of the kind of its slot."""

from claudia_computes import BUILTIN_STYLES, DEFAULT_STYLE, builtin_styles

#: The same ids as in creates and composes (E10.16), so an object carried between the apps keeps its style.
OBJECT_STYLES = {
    "body-text": "paragraph",
    "shape-label": "paragraph",
    "plain-shape": "outline",
    "plain-box": "box",
    "plain-image": "box",
}


#: The cell styles a workbook starts with (D313), named by purpose, each a paragraph style that may hold a box.
CELL_STYLES = {"header": "paragraph", "input": "paragraph", "result": "paragraph", "note": "paragraph"}


def test_a_new_workbook_has_the_object_styles_of_all_three_apps_each_with_its_kind():
    assert {style.id: style.kind for style in BUILTIN_STYLES} == {**OBJECT_STYLES, **CELL_STYLES}
    assert set(builtin_styles().ids()) == set(OBJECT_STYLES) | set(CELL_STYLES)


def test_a_shapes_outline_and_its_words_are_two_styles():
    """D310: the outline style holds only ``fill``/``stroke``/``stroke-width``; the centring of the words moved to
    ``shape-label``, so a shape on a sheet looks as it did."""
    book = builtin_styles()
    assert book.computed("plain-shape") == {"fill": "@accent/14", "stroke": "@accent", "stroke-width": "2px"}
    assert book.get("shape-label").based_on == DEFAULT_STYLE
    assert book.computed("shape-label")["text-align"] == "center"


def test_only_paragraph_styles_are_based_on_body_text():
    for style in builtin_styles():
        if style.id == DEFAULT_STYLE or style.kind != "paragraph":
            assert style.based_on is None, style.id
        else:
            assert style.based_on == DEFAULT_STYLE, style.id


def test_the_cell_styles_say_what_a_cell_is_for_and_hold_no_literal_colour():
    """D313: Header, Input, Result and Note, all based on Body text and written in palette roles (D200)."""
    book = builtin_styles()
    for style_id in CELL_STYLES:
        style = book.get(style_id)
        assert style.based_on == DEFAULT_STYLE and style.purpose
        for prop, value in style.css.items():
            if prop in ("color", "background-color") or prop.startswith("border"):
                assert "@" in value, f"{style_id} sets {prop} to the literal {value!r}"
    assert book.computed("header")["font-weight"] == "600" and "background-color" in book.computed("header")
    assert book.computed("note")["font-style"] == "italic"
