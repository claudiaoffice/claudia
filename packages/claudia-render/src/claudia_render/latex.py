"""LaTeX as a container type: the typesetter of E3.4 behind the plugin contract (D393).

LaTeX is the one built-in that is code and not data: it keeps the font catalogue, the fontconfig of the job and the log
reading of ``claudia-typeset``, which a declarative manifest cannot express. It only *adapts*: the tools come from the
same registry as every other plugin's, so the administrator has one place to say where TeX Live is."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from claudia_fonts import Catalogue
from claudia_typeset import (
    BadJob,
    EngineUnavailable,
    FontUnavailable,
    Job,
    Limits,
    Mode,
    SandboxError,
    TypesetFailed,
    Typesetter,
    UnsafeOutput,
)

from .diagnostics import Diagnostic
from .manifest import Manifest
from .plugin import Plugin, RenderFailed, RenderRequest, RenderResult
from .svgsize import svg_size
from .tools import ResolvedTool


class LatexPlugin(Plugin):
    """Typesets LaTeX with XeLaTeX and the fonts of the catalogue; the settings are ``mode`` and ``width_mm``."""

    def __init__(self, manifest: Manifest, catalogue: Catalogue, directory: str | Path) -> None:
        self.manifest = manifest
        self._catalogue = catalogue
        self._directory = Path(directory)
        self._typesetters: dict[tuple[Path, Path, Limits], Typesetter] = {}

    def _typesetter(self, tools: Mapping[str, ResolvedTool], limits: Limits) -> Typesetter:
        key = (tools["xelatex"].program, tools["pdftocairo"].program, limits)
        if key not in self._typesetters:
            self._typesetters[key] = Typesetter(
                self._catalogue, self._directory, limits=limits, xelatex=key[0], pdftocairo=key[1]
            )
        return self._typesetters[key]

    async def render(self, request: RenderRequest, tools: Mapping[str, ResolvedTool], limits: Limits) -> RenderResult:
        """Typeset ``request``; TeX's own complaint comes back as one diagnostic with the line of the text."""
        try:
            job = Job(Mode(request.params["mode"]), request.source, width_mm=float(request.params["width_mm"]))  # type: ignore[arg-type]
            done = await self._typesetter(tools, limits).typeset(job)
            width, height = svg_size(done.svg)
        except TypesetFailed as error:
            raise RenderFailed(str(error), (Diagnostic("error", error.error.message, error.error.line),)) from error
        except (BadJob, FontUnavailable, EngineUnavailable, SandboxError, UnsafeOutput, ValueError) as error:
            raise RenderFailed(f"LaTeX: {error}") from error
        return RenderResult(done.svg, width, height)
