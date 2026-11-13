"""claudia-render: rendered text containers of a Claudia server (D340-D346)."""

from ._version import __version__
from .builtin import builtin_registry
from .cli import CliPlugin
from .diagnostics import Diagnostic, read_diagnostics
from .latex import LatexPlugin
from .manifest import (
    API_VERSION,
    DIAGNOSTIC_READERS,
    CliSpec,
    EditorHints,
    Forbidden,
    LimitSpec,
    Manifest,
    ManifestError,
    ParamSpec,
    ToolRequirement,
    parse_manifest,
)
from .plugin import Plugin, RenderFailed, RenderRequest, RenderResult
from .registry import LoadReport, PluginRegistry, UnknownType
from .service import Rendered, RenderPolicy, RenderService
from .svgsize import default_alt, svg_size
from .tools import HELP_TOPIC, ResolvedTool, ToolEntry, ToolRegistry, ToolStatus, ToolUnavailable

__all__ = [
    "API_VERSION",
    "DIAGNOSTIC_READERS",
    "HELP_TOPIC",
    "CliPlugin",
    "CliSpec",
    "Diagnostic",
    "EditorHints",
    "Forbidden",
    "LatexPlugin",
    "LimitSpec",
    "LoadReport",
    "Manifest",
    "ManifestError",
    "ParamSpec",
    "Plugin",
    "PluginRegistry",
    "RenderFailed",
    "RenderPolicy",
    "RenderService",
    "RenderRequest",
    "RenderResult",
    "Rendered",
    "ResolvedTool",
    "ToolEntry",
    "ToolRegistry",
    "ToolRequirement",
    "ToolStatus",
    "ToolUnavailable",
    "UnknownType",
    "__version__",
    "builtin_registry",
    "default_alt",
    "parse_manifest",
    "read_diagnostics",
    "svg_size",
]
