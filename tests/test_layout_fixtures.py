"""The layout library's fixtures that stand for what the server sends are what the server sends (E9.22).

A fixture copied by hand drifts silently: the composes styles of the layout tests lacked ``hyphens`` long before
anybody noticed. These tests make the server's own code the source of the fixture."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "generate_layout_fixtures", ROOT / "scripts" / "generate_layout_fixtures.py"
)
assert SPEC and SPEC.loader
fixtures = importlib.util.module_from_spec(SPEC)
sys.modules["generate_layout_fixtures"] = fixtures
SPEC.loader.exec_module(fixtures)


def test_the_composes_styles_of_the_layout_tests_are_what_the_server_sends():
    assert fixtures.STYLES.read_text(encoding="utf-8") == fixtures.render_styles(), (
        "run `uv run python scripts/generate_layout_fixtures.py`"
    )
    assert fixtures.main(["--check"]) == 0
