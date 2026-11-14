"""The web app's key table is made from the shared menu manifest, and is what the manifest makes (UX-35, D360)."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("generate_keys", ROOT / "scripts" / "generate_keys.py")
assert SPEC and SPEC.loader
generate_keys = importlib.util.module_from_spec(SPEC)
sys.modules["generate_keys"] = generate_keys
SPEC.loader.exec_module(generate_keys)


def test_the_checked_in_table_is_what_the_manifest_makes():
    assert generate_keys.OUT.read_text(encoding="utf-8") == generate_keys.render(), (
        "run `uv run python scripts/generate_keys.py`"
    )
    assert generate_keys.NOTE.read_text(encoding="utf-8") == generate_keys.render_note()
    assert generate_keys.main(["--check"]) == 0


@pytest.mark.parametrize(
    ("accelerator", "text"),
    [
        ("<Primary><Alt><Shift>s", "Ctrl+Shift+Alt+S"),
        ("<Primary>question", "Ctrl+?"),
        ("<Alt><Shift>Up", "Shift+Alt+↑"),
    ],
)
def test_the_table_for_people_shows_keys_as_the_web_menus_do(accelerator, text):
    assert generate_keys.shown(accelerator) == text


@pytest.mark.parametrize(
    ("accelerator", "chord"),
    [
        ("<Primary>p", {"key": "p", "code": "KeyP", "ctrl": True}),
        ("<Primary><Alt><Shift>s", {"key": "s", "code": "KeyS", "ctrl": True, "shift": True, "alt": True}),
        ("<Primary><Shift>8", {"key": "8", "code": "Digit8", "ctrl": True, "shift": True}),
        ("<Shift>F10", {"key": "F10", "shift": True}),
        ("<Alt><Shift>Up", {"key": "ArrowUp", "shift": True, "alt": True}),
        ("<Primary>minus", {"key": "-", "ctrl": True}),
        ("<Primary>question", {"key": "?", "ctrl": True, "shift": True}),  # the event says Shift: it typed "?"
        ("<Primary><Alt>underscore", {"key": "_", "ctrl": True, "shift": True, "alt": True}),
        ("Return", {"key": "Enter"}),
        ("<Shift>Tab", {"key": "Tab", "shift": True}),
    ],
)
def test_a_gtk_key_becomes_the_key_a_browser_reports(accelerator, chord):
    assert generate_keys.chord_of(accelerator) == chord


def test_a_key_name_nobody_taught_it_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="KP_Add"):
        generate_keys.chord_of("<Primary>KP_Add")


def test_every_action_of_every_app_with_a_key_is_in_the_table():
    table = generate_keys.table()
    manifest = generate_keys._manifest_module()
    for app in ("composes", "computes", "creates"):
        for action in manifest.for_app(app).actions:
            if action.accelerators:
                assert table[action.id]["owner"] == action.key_owner.value, action.id
