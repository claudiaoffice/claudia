"""The plugins that come with the server: Typst and Mermaid as data, LaTeX as an adapter (D343, D345)."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from claudia_fonts import Catalogue

from .cli import CliPlugin
from .latex import LatexPlugin
from .manifest import parse_manifest
from .registry import PluginRegistry


def builtin_registry(catalogue: Catalogue, directory: str | Path) -> PluginRegistry:
    """A registry holding the built-in plugins, which keep their files under ``directory``.

    ``plugins/*.json`` of this package are the manifests; the one that names the ``latex`` adapter is the only
    one built here from code. A server then adds the administrator's folder with ``load_directory``."""
    base = Path(directory)
    registry = PluginRegistry()
    for item in sorted(resources.files("claudia_render").joinpath("plugins").iterdir(), key=lambda i: i.name):
        if not item.name.endswith(".json"):
            continue
        manifest = parse_manifest(json.loads(item.read_text(encoding="utf-8")))
        if manifest.adapter == "latex":
            registry.register(LatexPlugin(manifest, catalogue, base / "latex"))
        elif manifest.cli is not None:
            registry.register(CliPlugin(manifest, base / manifest.type))
        else:
            raise ValueError(f"{item.name}: an adapter nobody here knows ({manifest.adapter!r})")
    return registry
