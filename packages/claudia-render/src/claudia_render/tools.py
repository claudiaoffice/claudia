"""The tools behind the plugins: which program stands behind a logical name, and whether it works (D342).

LaTeX is not a library inside Claudia, it is a large installation the administrator owns, and so is every engine a
plugin drives (Typst, Mermaid's command line, Graphviz). The server therefore keeps a table from *logical tool names*
to installations, set by whoever controls the server, and a plugin only names what it needs. This is the one place
where an installation is found, tried and given an identity; the sandbox that then runs it is
:func:`claudia_typeset.run_sandboxed`.

Resolution is lazy and a failure is never remembered: a server without a tool starts, the first request says what is
missing, and installing the tool fixes it without a restart (as D98 settled for LaTeX).
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from claudia_typeset import EngineUnavailable, Limits, SandboxError, resolve_program, run_sandboxed

from .manifest import ToolRequirement

#: The help topic that explains how to register tools.
HELP_TOPIC = "render.configure-tools"

_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
_VERSION = re.compile(r"\d+(?:\.\d+)*")
_PROBE = Limits(seconds=30, memory_mb=1024, output_mb=1, address_space=False)

#: How a tool is asked for its version when it is not ``--version``.
DEFAULT_VERSION_ARGS: Mapping[str, tuple[str, ...]] = MappingProxyType({"pdftocairo": ("-v",)})


class ToolUnavailable(RuntimeError):
    """A tool a plugin needs is not registered, not found, does not run or is too old; the message says what to do."""

    def __init__(self, tool: str, message: str) -> None:
        super().__init__(message)
        self.tool = tool


@dataclass(frozen=True)
class ToolEntry:
    """One line of the administrator's table: a logical name, the program (or ``None`` to look on the PATH) and the
    options the tool's plugin may read (``${tool.NAME.OPTION}``)."""

    name: str
    path: str | None = None
    options: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class ResolvedTool:
    """A tool found and tried: its program, the version it reports and its options."""

    name: str
    program: Path
    version: str
    options: Mapping[str, Any]

    @property
    def identity(self) -> str:
        """What goes into a cache key and into a document's note of what made a picture: the name, the version and
        a short digest of the options, because the same program with other options may draw something else."""
        digest = hashlib.sha256(json.dumps(dict(self.options), sort_keys=True).encode()).hexdigest()[:8]
        return f"{self.name} {self.version} {digest}"


@dataclass(frozen=True)
class ToolStatus:
    """What an administrator is told about one tool: whether it works, its version, and what to do if not."""

    name: str
    ok: bool
    version: str
    detail: str
    hint: str = ""


def _entry(name: str, raw: object) -> ToolEntry:
    if not _NAME.fullmatch(name):
        raise ValueError(f"tool {name[:40]!r}: a plain lower-case name")
    if isinstance(raw, str) or raw is None:
        return ToolEntry(name, raw or None)
    if not isinstance(raw, Mapping):
        raise ValueError(f"tool {name!r}: a path or a mapping with a path and options")
    options = {key: value for key, value in raw.items() if key != "path"}
    path = raw.get("path")
    if path is not None and not isinstance(path, str):
        raise ValueError(f"tool {name!r}: path must be text")
    for key in options:
        if not _NAME.fullmatch(key):
            raise ValueError(f"tool {name!r}: option {str(key)[:40]!r} is not a plain lower-case name")
    return ToolEntry(name, path or None, MappingProxyType(options))


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _hint(name: str) -> str:
    return (
        f" Install {name} and set tools.{name}.path in the server settings to the program or the folder it is in, "
        f"or put it on the PATH (help topic: {HELP_TOPIC})."
    )


class ToolRegistry:
    """The administrator's table of tools, and the tools found through it.

    ``settings`` maps a logical name to a path, or to a mapping with a ``path`` and options. ``version_args`` says how
    to ask a tool for its version where it is not ``--version``."""

    def __init__(
        self,
        settings: Mapping[str, object] | None = None,
        *,
        version_args: Mapping[str, tuple[str, ...]] = DEFAULT_VERSION_ARGS,
    ) -> None:
        self._entries = {name: _entry(name, raw) for name, raw in (settings or {}).items()}
        self._version_args = version_args
        self._resolved: dict[str, ResolvedTool] = {}

    def configured(self) -> tuple[ToolEntry, ...]:
        """What the administrator registered, by name."""
        return tuple(self._entries[name] for name in sorted(self._entries))

    def forget(self) -> None:
        """Look at every tool again the next time it is asked for (after an installation, say)."""
        self._resolved.clear()

    async def resolve(self, requirement: ToolRequirement) -> ResolvedTool:
        """The tool ``requirement`` names, found and tried; `ToolUnavailable` says what is wrong and what to do."""
        name = requirement.tool
        tool = self._resolved.get(name) or await self._find(name)
        least = requirement.version_at_least
        if least is not None:
            if not _VERSION.fullmatch(tool.version):
                raise ToolUnavailable(name, f"{name}: its version cannot be read, and {least} or newer is needed.")
            if _numbers(tool.version) < _numbers(least):
                raise ToolUnavailable(
                    name, f"{name} {tool.version} is too old: {least} or newer is needed." + _hint(name)
                )
        self._resolved[name] = tool
        return tool

    async def status(self, name: str) -> ToolStatus:
        """Try one tool and say how it is, as a sentence for the administrator; never raises."""
        try:
            tool = self._resolved.get(name) or await self._find(name)
        except ToolUnavailable as error:
            return ToolStatus(name, False, "", str(error), _hint(name).strip())
        return ToolStatus(name, True, tool.version, f"{tool.program}: {tool.version}")

    async def _find(self, name: str) -> ResolvedTool:
        entry = self._entries.get(name) or ToolEntry(name)
        try:
            program = resolve_program(name, entry.path, name, hint=_hint(name))
        except EngineUnavailable as error:
            raise ToolUnavailable(name, str(error)) from error
        version = await self._version(name, program)
        return ResolvedTool(name, program, version, entry.options)

    async def _version(self, name: str, program: Path) -> str:
        args = self._version_args.get(name, ("--version",))
        with tempfile.TemporaryDirectory() as folder:
            try:
                done = await run_sandboxed(
                    [str(program), *args], cwd=Path(folder), env={}, limits=_PROBE, search_path=[program.parent]
                )
            except (OSError, SandboxError) as error:
                raise ToolUnavailable(name, f"{program} could not be run ({error}).{_hint(name)}") from error
        if done.returncode != 0:
            raise ToolUnavailable(name, f"{program} did not run properly: {done.output.strip()[:200]}.{_hint(name)}")
        found = _VERSION.search(done.output)
        return found.group(0) if found else "unknown"
