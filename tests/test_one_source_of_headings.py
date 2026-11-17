"""What a heading is has one source: the heading level of a style (E9.22).

Before it, five places kept their own list of heading styles by name (the composes model and its search, the docx and
odt exporters, the layout library, the web app twice), and they disagreed: the layout kept "heading-3" and a
"subtitle" no app had, the model did not. A built-in style id written into a client, the layout or another server
module is how such a list starts again, so this test refuses one outside the places that define or map the built-in
styles (the apps' own style modules and the exporters' name tables, which map them to the names other programs use).
"""

from __future__ import annotations

import re
from pathlib import Path, PurePath, PureWindowsPath

ROOT = Path(__file__).resolve().parent.parent
_ID = re.compile(r"""["'](?:heading-[1-9]|slide-title|subtitle)["']""")
#: The places that may name a heading style: where the built-ins are made, and the exporters' tables of names.
_ALLOWED = {
    "packages/claudia-composes/src/claudia_composes/model.py",
    "packages/claudia-creates/src/claudia_creates/styles.py",
    "packages/claudia-composes-io/src/claudia_composes_io/_odt_styles.py",
    "packages/claudia-composes-io/src/claudia_composes_io/_docx_styles.py",
}


def _place(path: PurePath, root: PurePath) -> str:
    """Where a file is, written the way ``_ALLOWED`` writes it: with slashes, whatever the system uses."""
    return path.relative_to(root).as_posix()


def _sources() -> list[Path]:
    found: list[Path] = []
    for folder, patterns in (
        ("packages", ("*/src/**/*.py",)),
        ("layout/src", ("**/*.ts",)),
        ("web/app", ("**/*.ts", "**/*.vue")),
        ("clients", ("**/src/**/*.py", "**/src/**/*.ts", "**/src/**/*.js")),
    ):
        for pattern in patterns:
            found += [p for p in (ROOT / folder).glob(pattern) if "node_modules" not in p.parts]
    return found


def test_no_client_layout_or_other_module_keeps_a_list_of_heading_styles_by_name():
    offenders = [
        f"{_place(path, ROOT)}:{number}: {line.strip()}"
        for path in _sources()
        if _place(path, ROOT) not in _ALLOWED
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if _ID.search(line)
    ]
    assert not offenders, "a heading is a style's heading level, not its name:\n" + "\n".join(offenders)


def test_a_place_is_named_with_slashes_on_every_system():
    """On Windows a path is written with backslashes, and the table of allowed places is not: the guard once found
    every exporter on Windows and nowhere else."""
    root = PureWindowsPath("D:/a/claudia/claudia")
    styles = root / "packages" / "claudia-creates" / "src" / "claudia_creates" / "styles.py"
    assert _place(styles, root) == "packages/claudia-creates/src/claudia_creates/styles.py"
    assert _place(styles, root) in _ALLOWED


def test_the_guard_finds_what_it_is_for():
    assert _ID.search("const KEEP = new Set(['title', 'heading-1'])")
    assert _ID.search('_LEVEL = {"heading-2": 2}')
    assert not _ID.search("f'heading-{level}'")
    assert len(_sources()) > 100
