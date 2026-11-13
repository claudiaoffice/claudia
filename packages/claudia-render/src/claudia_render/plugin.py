"""What a plugin is to the server: a manifest and a way to turn a text into a checked picture (D341, D343).

The service resolves the tools a plugin needs, caps its limits and caches the result; the plugin only runs. That keeps
a plugin small (a declarative one is data) and keeps everything that matters for safety in one place."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

from claudia_typeset import Limits

from .diagnostics import Diagnostic
from .manifest import Manifest
from .tools import ResolvedTool


@dataclass(frozen=True)
class RenderRequest:
    """The text to render and the settings (already checked against the manifest, defaults filled in)."""

    source: str
    params: Mapping[str, object]


@dataclass(frozen=True)
class RenderResult:
    """A checked SVG, its size in pixels and anything the tool said that is not an error."""

    svg: str
    width: float
    height: float
    warnings: tuple[Diagnostic, ...] = ()


class RenderFailed(Exception):
    """The tool ran (or was stopped) and made no picture; ``diagnostics`` say what and where, for the person."""

    def __init__(self, message: str, diagnostics: tuple[Diagnostic, ...] = ()) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or (Diagnostic("error", message),)


class Plugin(ABC):
    """A container type. ``manifest`` says what it is and needs; :meth:`render` makes the picture."""

    manifest: Manifest

    @abstractmethod
    async def render(self, request: RenderRequest, tools: Mapping[str, ResolvedTool], limits: Limits) -> RenderResult:
        """Turn ``request`` into a picture using ``tools`` (the ones the manifest requires, found and tried) within
        ``limits``; raise `RenderFailed` if no picture can be made."""
