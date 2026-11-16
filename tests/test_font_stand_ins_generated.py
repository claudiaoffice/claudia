"""The layout library's font stand-ins are made from ``claudia_fonts``, and are what it makes (E3.13)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "generate_font_stand_ins", ROOT / "scripts" / "generate_font_stand_ins.py"
)
assert SPEC and SPEC.loader
generate = importlib.util.module_from_spec(SPEC)
sys.modules["generate_font_stand_ins"] = generate
SPEC.loader.exec_module(generate)


def test_the_checked_in_table_is_what_claudia_fonts_makes():
    assert generate.OUT.read_text(encoding="utf-8") == generate.render(), (
        "run `uv run python scripts/generate_font_stand_ins.py`"
    )
    assert generate.main(["--check"]) == 0


def test_the_table_names_every_stand_in_and_every_word():
    from claudia_fonts import CLOSENESS, DEFAULT_GENERICS, DEFAULT_SUBSTITUTIONS

    text = generate.render()
    for word in CLOSENESS:
        assert f'"{word}"' in text
    for office, stand_in in {**DEFAULT_SUBSTITUTIONS, **DEFAULT_GENERICS}.items():
        assert f'"{office}": "{stand_in}",' in text
