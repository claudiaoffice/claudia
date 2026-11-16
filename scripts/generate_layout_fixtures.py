"""Write the layout library's test fixtures that stand for what the server sends, from the server's own code.

``uv run python scripts/generate_layout_fixtures.py``          rewrite ``layout/tests/composes-styles.json``
``uv run python scripts/generate_layout_fixtures.py --check``  fail if the checked-in file is not what this would write

The layout tests lay out composes' built-in styles "exactly as a server sends them". Copied by hand once, that copy went
on looking right while the styles moved on (it lacked ``hyphens`` and every heading level); made here, a test fails the
day the two differ (tests/test_layout_fixtures.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from claudia_composes import TextModel

ROOT = Path(__file__).resolve().parent.parent
STYLES = ROOT / "layout" / "tests" / "composes-styles.json"
#: What of a style view the layout reads (``TextStyle`` in ``layout/src/apps/objects.ts``).
_KEYS = ("id", "based_on", "kind", "resolved", "heading")


def render_styles() -> str:
    """composes' built-in styles as ``TextModel().styles.views(palette colours)`` gives them, in the layout's keys."""
    model = TextModel()
    views = model.styles.views(model.palette.colours())
    return json.dumps([{key: view[key] for key in _KEYS} for view in views], indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check that the fixture is current")
    args = parser.parse_args(argv)
    wanted = render_styles()
    if args.check:
        if STYLES.read_text(encoding="utf-8") != wanted:
            print(f"{STYLES.relative_to(ROOT)} is not what the server sends: run scripts/generate_layout_fixtures.py")
            return 1
        return 0
    STYLES.write_text(wanted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
