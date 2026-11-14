"""The render service: a text in, a checked picture out, with every rule about safety in one place (D392, D393).

A plugin only runs. This is where its tools are found and tried, its limits are capped by the server's policy, the text
is refused if it asks for what the plugin forbids, the number of renders at once is bounded and the result is kept by
everything that went into it."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from claudia_typeset import Limits, ResultCache, UnsafeOutput, check_svg

from .diagnostics import Diagnostic
from .plugin import RenderFailed, RenderRequest
from .registry import PluginRegistry
from .svgsize import svg_size
from .tools import ToolRegistry, ToolUnavailable

#: Bumped when the way a job is keyed or run changes, so that old pictures are not reused.
SERVICE_VERSION = 1
MAX_RENDERER_NOTE = 200


@dataclass(frozen=True)
class RenderPolicy:
    """What the server allows, whatever a plugin asks for."""

    max_seconds: float = 60.0
    max_memory_mb: int = 4096
    max_output_mb: int = 32
    concurrency: int = 2

    def __post_init__(self) -> None:
        if min(self.max_seconds, self.max_memory_mb, self.max_output_mb, self.concurrency) <= 0:
            raise ValueError("every limit of a policy must be positive")


@dataclass(frozen=True)
class Rendered:
    """A picture, its size in pixels, the note of what made it, what the tool warned about, and whether it was kept."""

    svg: str
    width: float
    height: float
    renderer: str
    cached: bool = False
    warnings: tuple[Diagnostic, ...] = ()


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


class RenderService:
    """Renders the text of container types; see the module description."""

    def __init__(
        self, plugins: PluginRegistry, tools: ToolRegistry, directory: str | Path, policy: RenderPolicy | None = None
    ) -> None:
        self.plugins = plugins
        self.tools = tools
        self.policy = policy or RenderPolicy()
        self._cache = ResultCache(Path(directory) / "results")
        self._gate: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        if self._gate is None:  # made inside the running loop
            self._gate = asyncio.Semaphore(self.policy.concurrency)
        return self._gate

    async def render(self, kind: str, source: str, params: dict[str, object] | None = None) -> Rendered:
        """The picture of ``source`` as a container of ``kind``.

        `UnknownType` and ``ValueError`` (a setting) before anything runs; `RenderFailed` when the text is refused or
        the tool makes no picture; `ToolUnavailable` when a tool is missing or too old."""
        plugin = self.plugins.get(kind)
        manifest = plugin.manifest
        settings = manifest.check_params(params or {})
        self._check_text(manifest, source)
        tools = {r.tool: await self.tools.resolve(r) for r in manifest.requires}
        identities = [tool.identity for tool in tools.values()]
        renderer = f"{kind} {manifest.version} | " + " | ".join(identities)
        key = hashlib.sha256(
            json.dumps(
                [SERVICE_VERSION, manifest.api, kind, manifest.version, source, settings, identities], sort_keys=True
            ).encode()
        ).hexdigest()
        kept = self._cache.get(key)
        if kept is not None:
            try:
                check_svg(kept, extra_elements=manifest.svg_elements)
                width, height = svg_size(kept)
            except (UnsafeOutput, ValueError):
                pass  # a stale or damaged file is just a miss
            else:
                return Rendered(kept, width, height, renderer[:MAX_RENDERER_NOTE], cached=True)
        wanted = manifest.limits
        limits = Limits(
            seconds=min(wanted.seconds, self.policy.max_seconds),
            memory_mb=min(wanted.memory_mb, self.policy.max_memory_mb),
            output_mb=min(wanted.output_mb, self.policy.max_output_mb),
            address_space=wanted.address_space,
        )
        async with self._semaphore():
            made = await plugin.render(RenderRequest(source, settings), tools, limits)
        self._cache.put(key, made.svg)
        return Rendered(made.svg, made.width, made.height, renderer[:MAX_RENDERER_NOTE], False, made.warnings)

    @staticmethod
    def _check_text(manifest, source: str) -> None:  # noqa: ANN001 - Manifest, imported lazily would only be noise
        if len(source) > manifest.max_source_chars:
            raise RenderFailed(
                f"the text is too long for {manifest.title}: at most {manifest.max_source_chars} characters"
            )
        if not source.strip():
            raise RenderFailed("there is nothing to render yet: the text is empty")
        for rule in manifest.forbid:
            found = rule.matches(source)
            if found:
                raise RenderFailed(rule.message, (Diagnostic("error", rule.message, _line_of(source, found.start())),))

    async def describe_types(self) -> list[dict]:
        """What clients and the AI are told about every type, and whether its tools work right now."""
        described = []
        for plugin in self.plugins.plugins():
            problems = []
            for requirement in plugin.manifest.requires:
                try:
                    await self.tools.resolve(requirement)
                except ToolUnavailable as error:
                    problems.append(str(error))
            described.append({**plugin.manifest.to_data(), "available": not problems, "problem": " ".join(problems)})
        return described
