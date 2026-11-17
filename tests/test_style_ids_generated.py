"""The default styles of the three apps and the style of a shape's words are written once, in Python, and the layout
library and the web app read the generated file (CODE-60). Before, ``'body-text'`` was written eleven times in
TypeScript and ``'body'`` twice, and a renamed default would have drawn nothing wrong, just something else."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("generate_style_ids", ROOT / "scripts" / "generate_style_ids.py")
assert SPEC and SPEC.loader
generate_style_ids = importlib.util.module_from_spec(SPEC)
sys.modules["generate_style_ids"] = generate_style_ids
SPEC.loader.exec_module(generate_style_ids)

#: The ids the generated file names. A client or the layout may not write one as a literal (it imports the name).
_LITERAL = re.compile(r"""(?<![\w-])['"](body-text|shape-label)['"]""")
#: Where a literal of them may stay: nowhere but the generated file, so far.
_ALLOWED = {"layout/src/styles.generated.ts"}


def test_the_checked_in_file_is_what_the_models_say():
    assert generate_style_ids.OUT.read_text(encoding="utf-8") == generate_style_ids.render(), (
        "run `uv run python scripts/generate_style_ids.py`"
    )
    assert generate_style_ids.main(["--check"]) == 0


def test_the_file_names_the_defaults_of_the_three_apps():
    text = generate_style_ids.render()
    assert "composes: 'body'" in text
    assert "computes: 'body-text'" in text
    assert "creates: 'body-text'" in text
    assert "SHAPE_LABEL_STYLE = 'shape-label'" in text


def test_no_client_or_layout_module_writes_a_default_style_id_as_a_literal():
    offenders = []
    for folder, patterns in (("layout/src", ("**/*.ts",)), ("web/app", ("**/*.ts", "**/*.vue"))):
        for pattern in patterns:
            for path in (ROOT / folder).glob(pattern):
                place = path.relative_to(ROOT).as_posix()
                if place in _ALLOWED or "node_modules" in path.parts:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    if _LITERAL.search(line):
                        offenders.append(f"{place}:{number}: {line.strip()[:90]}")
    assert not offenders, "import DEFAULT_STYLE or SHAPE_LABEL_STYLE from @claudia/layout:\n" + "\n".join(offenders)


def test_the_called_out_styles_of_the_format_menu_are_built_in_styles_of_composes():
    """The Format menu groups three built-ins by name (D127); a rename in composes must not leave the group empty."""
    from claudia_composes import BUILTIN_STYLES

    source = (ROOT / "web" / "app" / "components" / "TextWorkspace.vue").read_text(encoding="utf-8")
    named = re.search(r"const CALLED_OUT_STYLE_IDS = \[(.*?)\]", source)
    assert named, "TextWorkspace.vue no longer names CALLED_OUT_STYLE_IDS"
    ids = re.findall(r"'([a-z-]+)'", named.group(1))
    assert ids
    assert set(ids) <= {style.id for style in BUILTIN_STYLES}
