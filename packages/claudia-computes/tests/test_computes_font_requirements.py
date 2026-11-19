"""The fonts a computes document asks for are its requirements (E1.9, D1306)."""

from claudia_computes import WorkbookModel
from claudia_core import FontRequirement, StyleDef


def test_a_font_named_by_a_style_is_a_requirement_and_a_generic_one_is_not():
    model = WorkbookModel.empty()
    model.styles.add(StyleDef("fira", "Fira", "", None, {"font-family": "'Fira Sans', sans-serif"}))
    model.styles.add(StyleDef("plain", "Plain", "", None, {"font-family": "monospace"}))
    assert FontRequirement("Fira Sans") in model.requirements().fonts
    assert all(f.family.lower() != "monospace" for f in model.requirements().fonts)


def test_the_requirements_are_each_family_once():
    model = WorkbookModel.empty()
    model.styles.add(StyleDef("a", "A", "", None, {"font-family": "Fira Sans"}))
    model.styles.add(StyleDef("b", "B", "", None, {"font-family": "'Fira Sans', serif"}))
    names = [f.family for f in model.requirements().fonts]
    assert names.count("Fira Sans") == 1
