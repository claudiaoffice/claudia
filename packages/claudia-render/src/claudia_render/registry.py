"""The container types a server offers: built in, or dropped into a folder as data (D341).

A folder may bring *manifests* (data that names registered tools), never code: that is the whole of the third-party
story, and it keeps D38 intact (whoever controls the server's folder controls what runs, so a folder gets no way to
run anything of its own)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .cli import CliPlugin
from .manifest import ManifestError, parse_manifest
from .plugin import Plugin


class UnknownType(ValueError):
    """Nobody here renders this type; the message names the ones that are there."""


@dataclass(frozen=True)
class LoadReport:
    """What became of one manifest file: ``error`` is ``None`` if its plugin was registered."""

    file: str
    error: str | None = None


class PluginRegistry:
    """The plugins of a server by type."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Add ``plugin``; ``ValueError`` if its type is taken (a later plugin never replaces an earlier one)."""
        kind = plugin.manifest.type
        if kind in self._plugins:
            raise ValueError(
                f"the type {kind!r} is already registered (version {self._plugins[kind].manifest.version})"
            )
        self._plugins[kind] = plugin

    def get(self, kind: str) -> Plugin:
        """The plugin for ``kind``; `UnknownType` if there is none."""
        try:
            return self._plugins[kind]
        except KeyError:
            there = ", ".join(sorted(self._plugins)) or "none"
            raise UnknownType(f"no container type {kind[:40]!r} here (there are: {there})") from None

    def plugins(self) -> tuple[Plugin, ...]:
        """All of them, by type."""
        return tuple(self._plugins[kind] for kind in sorted(self._plugins))

    def load_directory(self, folder: str | Path, workdir: str | Path) -> tuple[LoadReport, ...]:
        """Register the declarative plugins whose manifests (``*.json``) are in ``folder``.

        One file that cannot be taken never stops the others; each is reported with the reason. A manifest that asks for
        an ``adapter`` (code that is part of the server) is refused: a folder brings data only."""
        directory = Path(folder)
        if not directory.is_dir():
            return ()
        reports = []
        for path in sorted(directory.glob("*.json")):
            try:
                manifest = parse_manifest(json.loads(path.read_text(encoding="utf-8")))
                if manifest.cli is None:
                    raise ManifestError("an adapter is code, and a folder brings data only; use a cli")
                self.register(CliPlugin(manifest, workdir))
            except (OSError, ValueError) as error:  # ManifestError, JSON errors and a taken type are all ValueErrors
                reports.append(LoadReport(path.name, str(error)))
            else:
                reports.append(LoadReport(path.name))
        return tuple(reports)
