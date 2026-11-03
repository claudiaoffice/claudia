"""Telling a person what to do about what TeX said (E13: help in context)."""

import pytest

from claudia_typeset import hint_for


@pytest.mark.parametrize(
    ("message", "package"),
    [
        ("LaTeX Error: File `standalone.cls' not found.", "standalone"),
        ("LaTeX Error: File `unicode-math.sty' not found.", "unicode-math"),
        ("LaTeX Error: File `fontspec.sty' not found.", "fontspec"),
    ],
)
def test_a_missing_package_comes_with_the_commands_to_install_it(message, package):
    hint = hint_for(message)
    assert f"tlmgr install {package}" in hint
    assert "MiKTeX" in hint


def test_a_file_that_is_not_a_package_does_not_get_a_package_command():
    assert "tlmgr install" not in hint_for("LaTeX Error: File `figure.png' not found.")


def test_a_missing_font_points_to_the_font_catalogue():
    hint = hint_for('The font "Nope" cannot be found')
    assert "catalogue" in hint


def test_something_unknown_gets_no_hint_rather_than_a_wrong_one():
    assert hint_for("Undefined control sequence.") == ""
