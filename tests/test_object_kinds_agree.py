"""The kinds of floating object have one list, ``claudia_core.OBJECT_KINDS`` (CODE-60).

The layout library names them in a type (``ObjectKind``) and the web imports that type instead of writing the list
again; a client that spells the whole list out is how the layout once came to lack ``rendered``. This test refuses a
second spelling and checks that the one there is the same as the server's.
"""

from __future__ import annotations

import re
from pathlib import Path

from claudia_core import OBJECT_KINDS

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_TYPE = ROOT / "layout" / "src" / "apps" / "objects.ts"
#: A union of quoted words that names at least the three kinds every app has.
_UNION = re.compile(r"""(?:'[a-z]+'\s*\|\s*)+'[a-z]+'""")


def _unions(text: str) -> list[set[str]]:
    return [set(re.findall(r"'([a-z]+)'", match.group())) for match in _UNION.finditer(text)]


def test_the_layout_names_the_kinds_the_server_has():
    declared = re.search(r"export type ObjectKind = (.+)", LAYOUT_TYPE.read_text(encoding="utf-8"))
    assert declared, "layout/src/apps/objects.ts no longer exports ObjectKind"
    assert tuple(re.findall(r"'([a-z]+)'", declared.group(1))) == OBJECT_KINDS


def test_no_client_spells_out_the_list_of_kinds_again():
    own = set(OBJECT_KINDS)
    offenders = []
    for folder, patterns in (("layout/src", ("**/*.ts",)), ("web/app", ("**/*.ts", "**/*.vue"))):
        for pattern in patterns:
            for path in (ROOT / folder).glob(pattern):
                if path == LAYOUT_TYPE or "node_modules" in path.parts:
                    continue
                offenders.extend(
                    f"{path.relative_to(ROOT).as_posix()}: {sorted(union)}"
                    for union in _unions(path.read_text(encoding="utf-8"))
                    if len(union & own) >= 4
                )
    assert not offenders, "write `ObjectKind` (from @claudia/layout), not the list: " + "; ".join(offenders)
