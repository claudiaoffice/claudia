"""The real engine: XeLaTeX and pdftocairo with the fonts of the catalogue. Skipped where TeX is not installed."""

import asyncio
import re

import pytest

from claudia_typeset import Job, Mode, TypesetFailed, Typesetter, check_svg

pytestmark = pytest.mark.usefixtures("needs_tex")


@pytest.fixture
def typesetter(tmp_path, tex_catalogue):
    return Typesetter(tex_catalogue, tmp_path / "work")


def typeset(typesetter, job):
    return asyncio.run(typesetter.typeset(job))


def test_a_fraction_becomes_a_self_contained_svg(typesetter):
    result = typeset(typesetter, Job(Mode.MATH, r"\frac{x}{y}"))
    assert result.svg.lstrip().startswith(("<?xml", "<svg"))
    assert "<path" in result.svg or "<use" in result.svg
    check_svg(result.svg)
    assert not re.search(r"https?://(?!www\.w3\.org)", result.svg)


def test_a_formula_with_amsmath_and_unicode_math_is_set(typesetter):
    source = r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2} \quad \text{und } \alpha \in \mathbb{R}"
    check_svg(typeset(typesetter, Job(Mode.MATH, source)).svg)


def test_a_paragraph_with_inline_math_is_set_to_a_page_width(typesetter):
    source = "Der Satz des Pythagoras: $a^2 + b^2 = c^2$.\n\nZweiter Absatz mit \\textbf{Fett} und \\emph{Kursiv}."
    check_svg(typeset(typesetter, Job(Mode.PAGE, source, width_mm=100)).svg)


def test_the_same_formula_gives_the_same_picture_byte_for_byte(tmp_path, tex_catalogue):
    first = typeset(Typesetter(tex_catalogue, tmp_path / "a"), Job(Mode.MATH, r"\frac{x}{y}"))
    second = typeset(Typesetter(tex_catalogue, tmp_path / "b"), Job(Mode.MATH, r"\frac{x}{y}"))
    assert first.svg == second.svg


def test_the_second_request_is_answered_from_the_cache(typesetter):
    assert typeset(typesetter, Job(Mode.MATH, r"x^2")).cached is False
    assert typeset(typesetter, Job(Mode.MATH, r"x^2")).cached is True


def test_an_error_is_found_in_the_users_own_line(typesetter):
    with pytest.raises(TypesetFailed) as raised:
        typeset(typesetter, Job(Mode.PAGE, "fine\n\\undefinedcommand{x}\nfine"))
    error = raised.value.error
    assert "Undefined control sequence" in error.message
    assert error.line == 2
    assert "undefinedcommand" in error.context
    assert "/tmp" not in str(raised.value)


def test_an_unclosed_group_is_reported(typesetter):
    with pytest.raises(TypesetFailed) as raised:
        typeset(typesetter, Job(Mode.MATH, r"\frac{x}{y"))
    assert raised.value.error.message


def test_a_font_is_found_by_the_catalogue_not_by_the_machine(typesetter, tex_catalogue):
    """A family that only the machine has (a system font) is not available; the catalogue decides."""
    from claudia_typeset import FontUnavailable

    with pytest.raises(FontUnavailable):
        typeset(typesetter, Job(Mode.PAGE, "x", font="DejaVu Sans"))


def test_the_text_font_of_the_job_is_embedded_in_the_pdf(tmp_path, tex_catalogue):
    """What was drawn was drawn with the catalogue's fonts: the SVG is made of their glyphs, not of system text."""
    result = typeset(Typesetter(tex_catalogue, tmp_path / "w"), Job(Mode.PAGE, "Hello"))
    assert "<text" not in result.svg
    assert "glyph" in result.svg
