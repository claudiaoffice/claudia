"""The levels of a numbering scheme as OpenDocument says them, both ways (E9.22)."""

from __future__ import annotations

import pytest
from lxml import etree

from claudia_core import LevelFormat, ListDef, builtin_scheme
from claudia_odf_io import LEVEL_BULLET, LEVEL_NUMBER, NS, OUTLINE_LEVEL, level_style, list_style, read_levels
from claudia_odf_io.lists import counts, odf_level, read_odf_level

DECLARED = " ".join(f'xmlns:{p}="{NS[p]}"' for p in ("text", "style", "fo"))


def style_of(*levels: str) -> etree._Element:
    return etree.fromstring(f'<text:list-style {DECLARED} style:name="L">{"".join(levels)}</text:list-style>')


@pytest.mark.parametrize(
    "level",
    [
        LevelFormat("decimal", from_level=0),
        LevelFormat("lower-alpha", after=".", from_level=2),
        LevelFormat("upper-roman", before="Part ", after=":", from_level=1),
        LevelFormat("bullet", "–", from_level=2),
        LevelFormat("none", before="§", from_level=2),
    ],
)
def test_a_level_comes_back_as_it_was_written(level):
    said = odf_level(level, 2)
    attributes = {key: value for key, value in said.items() if value}
    assert read_odf_level(attributes, 2, bullet=level.format == "bullet") == level


def test_what_a_level_of_the_model_cannot_say_reads_as_none():
    assert read_odf_level({"num-format": "１, ２, ３, ..."}, 0, bullet=False) is None
    assert read_odf_level({"num-format": "1", "display-levels": "x"}, 0, bullet=False) is None
    assert read_odf_level({"num-format": "1", "display-levels": "3"}, 0, bullet=False) is None
    assert read_odf_level({"bullet-char": ""}, 0, bullet=True) is None
    assert read_odf_level({"num-prefix": "x" * 21}, 0, bullet=False) is None


def test_a_list_style_has_nine_levels_drawn_as_its_scheme_and_its_start():
    chapters = builtin_scheme("chapters")
    assert chapters is not None
    style = etree.fromstring(list_style(ListDef("l1", "chapters", 3, 'A "B"'), chapters, "L1"))
    assert style.get(f"{{{NS['style']}}}display-name") == 'A "B"'
    levels = read_levels(style, (LEVEL_NUMBER, LEVEL_BULLET))
    assert [levels[n] for n in range(9)] == list(chapters.levels)
    assert style[0].get(f"{{{NS['text']}}}start-value") == "3"
    assert counts(style) and not counts(None)


def test_the_outline_draws_a_bullet_as_no_number_and_bullets_do_not_count():
    outline = level_style("outline-level-style", LevelFormat("bullet", "•", "(", ")", 0), 0)
    assert outline.startswith("<text:outline-level-style") and 'style:num-format=""' in outline
    bullets = style_of(level_style("list-level-style", LevelFormat("bullet", "•", from_level=0), 0))
    assert not counts(bullets)
    numbered = style_of(level_style("outline-level-style", LevelFormat("decimal"), 0), '<text:p text:level="x"/>')
    assert read_levels(numbered, (OUTLINE_LEVEL,)) == {0: LevelFormat("decimal")}  # a level without a number is skipped
    assert read_levels(numbered, (LEVEL_NUMBER,)) == {}  # an outline level is no list level
