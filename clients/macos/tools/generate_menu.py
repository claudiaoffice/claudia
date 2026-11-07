#!/usr/bin/env python3
"""Write the shared menu manifest (``clients/linux/src/claudia_shell_gtk/manifest.py``) as JSON for the macOS
client to read (E5.11, D159).

Why this exists at all: the manifest already is plain data with no GTK import (see that module's own docstring), on
purpose, "so the layout stays in XML (D27) and manifest can be tested anywhere" — this script is the "anywhere"
D159 needed. The macOS client is TypeScript and runs outside the uv workspace (same boundary as the Linux shell,
D116); rather than hand-duplicate File/Edit/Tools/Help across two languages and risk the same kind of drift D28 and
D121 each had to fix once already, the Python manifest stays the one source and this script is the bridge.

Usage::

    python3 generate_menu.py creates            # regenerate src/generated/menu.creates.json
    python3 generate_menu.py --all              # regenerate every app the Linux client has a manifest for
    python3 generate_menu.py creates --check    # exit 1 if the checked-in file is not what the manifest produces

``npm run generate-menu`` in this package's ``package.json`` runs the ``--all`` form; a CI job runs ``--check`` for
every app so an edit to ``manifest.py`` that nobody regenerated for is caught the same way D28's link drift was
caught by hand, a release late.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LINUX_SRC = REPO / "clients" / "linux" / "src"
OUT_DIR = HERE.parent / "src" / "generated"

__all__ = ["UnknownApp", "build", "flatten", "write", "main"]


class UnknownApp(KeyError):
    """The Linux client's manifest module has no builder for this app name."""

    def __str__(self) -> str:  # KeyError's default repr wraps the message in quotes
        return str(self.args[0])


def _manifest_module() -> Any:
    """Import ``claudia_shell_gtk.manifest`` without installing the package: it has no GTK dependency (the module's
    own docstring says so), so adding its source directory to ``sys.path`` is enough, and avoids making this
    developer-only script depend on the Linux client being pip-installed."""
    if str(LINUX_SRC) not in sys.path:
        sys.path.insert(0, str(LINUX_SRC))
    from claudia_shell_gtk import manifest  # import-after-path-tweak is the point (PLC0415 ignored repo-wide)

    return manifest


def build(app_name: str) -> dict[str, Any]:
    """``manifest.<app_name>().describe()`` — the plain-data menu listing, roles included."""
    manifest = _manifest_module()
    builders: dict[str, Any] = {
        "composes": manifest.composes,
        "computes": manifest.computes,
        "creates": manifest.creates,
    }
    try:
        builder = builders[app_name]
    except KeyError:
        available = ", ".join(sorted(builders))
        raise UnknownApp(f"no Linux client manifest for '{app_name}'; available: {available}") from None
    result: dict[str, Any] = builder().describe()
    return result


def flatten(menu: dict[str, Any]) -> list[dict[str, Any]]:
    """Every actionable item of one ``describe()`` menu, a submenu's own items in place of the submenu itself —
    the JSON-side equivalent of ``manifest.Menu.all_actions``."""
    out: list[dict[str, Any]] = []
    for section in menu["sections"]:
        for entry in section:
            out.extend(entry.get("items", [entry]))
    return out


def _dumps(listing: dict[str, Any]) -> str:
    """One stable rendering so regenerating an unchanged manifest never touches the file (and a changed one shows
    a clean, reviewable diff): sorted keys, 2-space indent, a trailing newline."""
    return json.dumps(listing, indent=2, sort_keys=True) + "\n"


def write(app_name: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dumps(build(app_name)), encoding="utf-8")


def _check(app_name: str, out_dir: Path) -> bool:
    path = out_dir / f"menu.{app_name}.json"
    if not path.is_file():
        print(f"menu.{app_name}.json does not exist yet; run without --check to create it", file=sys.stderr)
        return False
    current = path.read_text(encoding="utf-8")
    fresh = _dumps(build(app_name))
    if current != fresh:
        print(
            f"menu.{app_name}.json is stale (manifest.py changed since it was generated); "
            f"run `python3 {HERE.name}/generate_menu.py {app_name}` to refresh it",
            file=sys.stderr,
        )
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app", nargs="?", choices=["composes", "computes", "creates"], help="which app to generate")
    parser.add_argument("--all", action="store_true", help="generate every app")
    parser.add_argument(
        "--check", action="store_true", help="fail if the checked-in file is not current; writes nothing"
    )
    args = parser.parse_args(argv)

    if not args.all and not args.app:
        parser.error("give an app name or --all")
    apps = ["composes", "computes", "creates"] if args.all else [args.app]

    if args.check:
        ok = all(_check(app, OUT_DIR) for app in apps)
        return 0 if ok else 1

    for app in apps:
        write(app, OUT_DIR / f"menu.{app}.json")
        print(f"wrote {OUT_DIR / f'menu.{app}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
