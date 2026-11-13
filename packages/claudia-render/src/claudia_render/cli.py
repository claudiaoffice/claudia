"""A plugin that is only data: it asks a registered tool for a picture the way its manifest says (D343).

Everything a person or a setting can influence goes into *arguments* (never a shell line) and into *structured support
files* (a setting is a value in a JSON document, so it can never break out of a quotation). The job gets a folder of its
own, a clean environment whose home is that folder, the limits of the service, and nothing is left behind.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from claudia_typeset import Completed, Limits, SandboxError, UnsafeOutput, check_svg, run_sandboxed

from .diagnostics import read_diagnostics
from .manifest import STDOUT, CliSpec, Manifest
from .plugin import Plugin, RenderFailed, RenderRequest, RenderResult
from .svgsize import svg_size
from .tools import ResolvedTool

_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")
_WHOLE = re.compile(r"\$\{([^}]*)\}")
_MISSING = object()

#: Longest path of a job folder. A browser puts a socket in a folder inside it and a socket path may have at most 107
#: characters, so a deep work folder would make Chromium fail to start with an error that names neither.
MAX_JOB_PATH = 60


class _Context:
    """What the placeholders of one job stand for."""

    def __init__(self, spec: CliSpec, request: RenderRequest, tools: Mapping[str, ResolvedTool]) -> None:
        self.spec, self.params, self.tools = spec, request.params, tools

    def value(self, body: str) -> object:
        """What ``body`` (without ``${`` and ``}``) stands for; ``_MISSING`` for an unset optional option."""
        optional = body.endswith("?")
        name = body.removesuffix("?")
        parts = name.split(".")
        if name == "input":
            return self.spec.input
        if name == "output":
            return self.spec.output
        if parts[0] == "param":
            return self.params[parts[1]]
        tool = self.tools[parts[1]]
        if len(parts) == 2:
            return str(tool.program)
        if parts[2] in tool.options:
            return tool.options[parts[2]]
        if optional:
            return _MISSING
        raise RenderFailed(f"the administrator has not set {parts[2]!r} for {parts[1]}")


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _expand(template: str, context: _Context) -> object:
    """``template`` with its placeholders filled; ``_MISSING`` if an optional one is not set. A template that is
    exactly one placeholder gives the value itself (a list stays a list), anything else gives text."""
    whole = _WHOLE.fullmatch(template)
    if whole:
        return context.value(whole[1])
    missing = False

    def fill(found: re.Match[str]) -> str:
        nonlocal missing
        value = context.value(found[1])
        if value is _MISSING:
            missing = True
            return ""
        return _text(value)

    filled = _PLACEHOLDER.sub(fill, template)
    return _MISSING if missing else filled


def _fill(node: Any, context: _Context) -> object:
    """A support file's content with every placeholder filled and every key or item that is unset left out."""
    if isinstance(node, str):
        return _expand(node, context)
    if isinstance(node, Mapping):
        filled = {key: _fill(value, context) for key, value in node.items()}
        return {key: value for key, value in filled.items() if value is not _MISSING}
    if isinstance(node, list):
        return [item for item in (_fill(value, context) for value in node) if item is not _MISSING]
    return node


def _line(text: str) -> str:
    return " ".join(text.split())[:300]


class CliPlugin(Plugin):
    """A plugin whose manifest has a ``cli``: see the module description."""

    def __init__(self, manifest: Manifest, workdir: str | Path) -> None:
        if manifest.cli is None:
            raise ValueError(f"{manifest.type}: a CliPlugin needs a manifest with a cli")
        self.manifest = manifest
        self._cli: CliSpec = manifest.cli
        self._workdir = Path(workdir)

    async def render(self, request: RenderRequest, tools: Mapping[str, ResolvedTool], limits: Limits) -> RenderResult:
        """Run the tool on a private folder; see `Plugin.render`."""
        folder = self._job_folder()
        try:
            return await self._run(request, tools, limits, folder)
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _job_folder(self) -> Path:
        """A private new folder: in the work folder if its path is short enough, else in the system's temporary one."""
        self._workdir.mkdir(parents=True, exist_ok=True)
        if len(str(self._workdir.resolve())) + 12 <= MAX_JOB_PATH:
            return Path(tempfile.mkdtemp(prefix="j", dir=self._workdir)).resolve()
        return Path(tempfile.mkdtemp(prefix="claudia-")).resolve()

    async def _run(
        self, request: RenderRequest, tools: Mapping[str, ResolvedTool], limits: Limits, folder: Path
    ) -> RenderResult:
        spec, context = self._cli, _Context(self._cli, request, tools)
        prefix, suffix = (_expand(text, context) for text in (spec.prefix, spec.suffix))
        prefix, suffix = (text if isinstance(text, str) else "" for text in (prefix, suffix))
        (folder / spec.input).write_text(prefix + request.source + suffix, encoding="utf-8")
        for name, content in spec.files.items():
            filled = _fill(content, context)
            (folder / name).write_text(
                filled if isinstance(filled, str) else json.dumps(filled, ensure_ascii=False), encoding="utf-8"
            )
        argv = [_text(value) for template in spec.argv if (value := _expand(template, context)) is not _MISSING]
        env = {"HOME": str(folder), "TMPDIR": str(folder)}
        for name, template in spec.env.items():
            if (value := _expand(template, context)) is not _MISSING:
                env[name] = _text(value)
        title = self.manifest.title
        try:
            done = await run_sandboxed(
                argv, cwd=folder, env=env, limits=limits, search_path=[tool.program.parent for tool in tools.values()]
            )
        except SandboxError as error:
            raise RenderFailed(f"{title} {error}") from error
        except OSError as error:
            raise RenderFailed(f"{title} could not be started ({error.strerror or error})") from error
        offset = prefix.count("\n")
        found = read_diagnostics(spec.diagnostics, done.output, line_offset=offset)
        if done.returncode != 0:
            raise RenderFailed(found[0].message if found else self._silent(done), found)
        svg = self._picture(done, folder)
        try:
            check_svg(svg, extra_elements=self.manifest.svg_elements)
            width, height = svg_size(svg)
        except (UnsafeOutput, ValueError) as error:
            raise RenderFailed(f"{title} made a picture that is not accepted: {error}") from error
        return RenderResult(svg, width, height, tuple(d for d in found if d.severity == "warning"))

    def _silent(self, done: Completed) -> str:
        said = _line(done.output)
        return f"{self.manifest.title} failed" + (f": {said}" if said else f" (exit code {done.returncode})")

    def _picture(self, done: Completed, folder: Path) -> str:
        spec = self._cli
        if spec.output == STDOUT:
            start, end = done.output.find("<svg"), done.output.rfind("</svg>")
            if start < 0 or end < 0:
                raise RenderFailed(f"{self.manifest.title} wrote no picture")
            return done.output[start : end + len("</svg>")]
        try:
            return (folder / spec.output).read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise RenderFailed(f"{self.manifest.title} wrote no picture") from error
        except UnicodeDecodeError as error:
            raise RenderFailed(f"{self.manifest.title} wrote a picture that is not text") from error
