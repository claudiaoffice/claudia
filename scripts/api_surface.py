"""The public API of claudia-core as plain data: names, kinds and signatures.

``uv run python scripts/api_surface.py``          print it
``uv run python scripts/api_surface.py --write``  update tests/api/<package>.json for every package

The test ``tests/test_public_api.py`` compares the code with those files. A change to the public API therefore shows
up in a diff that a reviewer must read, and comes with a version bump and a CHANGELOG entry (docs/versioning.md).
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the packages whose API is a promise
PACKAGES = (
    "claudia_core",
    "claudia_server",
    "claudia_client",
    "claudia_container",
    "claudia_creates",
    "claudia_fonts",
    "claudia_typeset",
    # under the policy since 2026-11-10: the apps' models and their file formats, the AI and the test library
    "claudia_computes",
    "claudia_composes",
    "claudia_ai",
    "claudia_opc_io",
    "claudia_odf_io",
    "claudia_composes_io",
    "claudia_computes_io",
    "claudia_creates_io",
    "claudia_test_documents",
)


def portable(text: str) -> str:
    """``text`` without the memory addresses a repr carries ("<function name at ADDRESS>" -> "<function name>").

    The address differs on every run, and its format is not portable either: glibc/macOS's `%p` gives lowercase hex
    with a "0x" prefix, MSVC's gives uppercase hex with none (e.g. "0x7f3a2bc12340" vs "000001ED86581A60") -- both
    must be stripped the same way everywhere, or the snapshot made on one platform never matches a check made on
    the other."""
    return re.sub(r" at (?:0x)?[0-9A-Fa-f]+", "", text)


def signature(obj) -> str:
    try:
        # A default that is a function reprs with its address (`portable`).
        return portable(str(inspect.signature(obj)))
    except (TypeError, ValueError):
        return "(...)"


def surface(module) -> dict:
    out: dict[str, object] = {"version": module.__version__}
    for name in sorted(module.__all__):
        if name == "__version__":
            continue
        obj = getattr(module, name)
        if inspect.isclass(obj):
            members = {
                member: signature(getattr(obj, member))
                for member in sorted(vars(obj))
                if not member.startswith("_")
                and callable(getattr(obj, member, None))
                and not isinstance(vars(obj)[member], property)
            }
            properties = sorted(m for m, v in vars(obj).items() if isinstance(v, property) and not m.startswith("_"))
            out[name] = {
                "class": [b.__name__ for b in obj.__bases__],
                "init": signature(obj),
                "methods": members,
                "properties": properties,
            }
        elif callable(obj):
            out[name] = {"function": signature(obj)}
        else:
            out[name] = {
                "value": portable(repr(obj))
                if isinstance(obj, int | float | str | tuple | dict)
                else f"<{type(obj).__name__}>"
            }
    return out


def snapshot_path(name: str) -> Path:
    """Where the snapshot of package ``name`` is kept."""
    return ROOT / "tests" / "api" / f"{name}.json"


def main() -> None:
    """Print the API surfaces, or with ``--write`` update the snapshots."""
    import importlib

    for name in PACKAGES:
        text = json.dumps(surface(importlib.import_module(name)), indent=1, sort_keys=False) + "\n"
        if "--write" in sys.argv:
            snapshot_path(name).write_text(text)
            print(f"wrote {snapshot_path(name)}")
        else:
            print(f"# {name}\n{text}", end="")


if __name__ == "__main__":
    main()
