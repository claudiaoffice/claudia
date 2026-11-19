"""The fonts a document's styles ask for (E1.9, D1306): what a server is asked to have."""

from claudia_core import StyleBook, StyleDef


def book(*css: str) -> StyleBook:
    return StyleBook(StyleDef(f"s{i}", f"S{i}", "", None, {"font-family": value}) for i, value in enumerate(css))


def test_every_first_family_is_asked_for_once_in_order_of_name():
    assert book("'Fira Sans', sans-serif", "Georgia, serif", '"Fira Sans"').font_families() == ("Fira Sans", "Georgia")


def test_a_generic_family_is_no_requirement():
    assert book("sans-serif", "monospace", "system-ui").font_families() == ()


def test_a_style_that_names_no_font_asks_for_none():
    assert StyleBook([StyleDef("s", "S", "", None, {"color": "#000"})]).font_families() == ()


def test_a_family_further_down_the_list_is_a_fall_back_not_a_requirement():
    assert book("Georgia, 'Charter', serif").font_families() == ("Georgia",)
