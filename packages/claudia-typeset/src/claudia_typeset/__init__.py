"""claudia-typeset: the typesetting service of a Claudia server (E3.4, E3.10)."""

from ._version import __version__
from .cache import ResultCache, cache_key
from .diagnosis import Diagnosis, Step, hint_for
from .engine import Typeset, TypesetFailed, Typesetter
from .job import BadJob, Job, Limits, Mode
from .programs import HELP_TOPIC, SETTINGS, EngineUnavailable, resolve_program
from .sandbox import Completed, OutputTooLarge, SandboxError, Timeout, run_sandboxed
from .source import Built, FontUnavailable, TexError, build_source, parse_log
from .svg import NEVER_ALLOWED, UnsafeOutput, check_svg

__all__ = [
    "BadJob",
    "Built",
    "Completed",
    "Diagnosis",
    "EngineUnavailable",
    "FontUnavailable",
    "Job",
    "Limits",
    "Mode",
    "OutputTooLarge",
    "HELP_TOPIC",
    "NEVER_ALLOWED",
    "ResultCache",
    "SETTINGS",
    "SandboxError",
    "Step",
    "TexError",
    "Timeout",
    "Typeset",
    "TypesetFailed",
    "Typesetter",
    "UnsafeOutput",
    "__version__",
    "build_source",
    "cache_key",
    "check_svg",
    "hint_for",
    "parse_log",
    "resolve_program",
    "run_sandboxed",
]
