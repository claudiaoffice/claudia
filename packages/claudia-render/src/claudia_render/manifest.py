"""What a plugin says about itself: its identity, the tools it needs, its settings and how a tool is asked (D391, D393).

A manifest is plain data (JSON). An administrator may drop one into a folder, so it can run nothing by itself: it
*names* tools that the server has registered (:mod:`claudia_render.tools`), and says how to ask one of them for a
picture as a list of arguments, never as a shell line. Every field is checked here, before anything is run, and a field
nobody knows is an error, so that a typo is not silently ignored.

Placeholders in a template are written ``${...}``: ``${input}`` and ``${output}`` (file names in the job folder),
``${param.NAME}`` (a setting the person chose), ``${tool.NAME}`` (the path of a required tool) and
``${tool.NAME.OPTION}`` (an option the administrator gave that tool). A trailing ``?`` makes one optional: where it is
missing, its argument, or its key in a support file, is left out.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from claudia_core import MAX_RENDERING_SOURCE
from claudia_typeset import NEVER_ALLOWED

#: The version of the contract between the server and a plugin. A manifest names the one it was written for.
API_VERSION = 1

#: The ways a tool's complaints can be read into messages with a line (see :mod:`claudia_render.diagnostics`).
DIAGNOSTIC_READERS = ("plain", "typst-short", "mermaid-parse")

TIERS = ("static",)
PARAM_TYPES = ("string", "integer", "number", "boolean")

MAX_TEXT = 2000
STDOUT = "stdout"

_TYPE = re.compile(r"[a-z][a-z0-9-]{0,31}")
_VERSION = re.compile(r"\d+(\.\d+){0,3}")
_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}")
_ENV = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")
_TOP = frozenset(
    {"api", "type", "version", "title", "tier", "requires", "params", "cli", "adapter", "svg_elements", "limits",
     "editor", "max_source_chars", "forbid"}
)  # fmt: skip


class ManifestError(ValueError):
    """A manifest is not one this server will take; the message names the field and what is wrong."""


def _text(value: object, what: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise ManifestError(f"{what}: text of at most {limit} characters")
    return value


def _mapping(value: object, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestError(f"{what}: a mapping is expected")
    return value


def _only(data: Mapping[str, Any], allowed: frozenset[str] | set[str], what: str) -> None:
    for key in data:
        if key not in allowed:
            raise ManifestError(f"{what}: {key!r} is not a field of a manifest")


@dataclass(frozen=True)
class ToolRequirement:
    """A tool the plugin needs, by the logical name the administrator registers it under."""

    tool: str
    version_at_least: str | None = None


@dataclass(frozen=True)
class ParamSpec:
    """One setting a person may choose: its kind, its default and the values it may take."""

    name: str
    type: str
    default: object
    choices: tuple[object, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None

    def check(self, value: object) -> object:
        """``value`` if this setting accepts it; ``ValueError`` (naming the setting) if not."""
        ok = {
            "string": lambda v: isinstance(v, str) and len(v) <= 200,
            "integer": lambda v: type(v) is int,
            "number": lambda v: type(v) in (int, float),
            "boolean": lambda v: type(v) is bool,
        }[self.type](value)
        if not ok:
            raise ValueError(f"setting {self.name!r}: expected {self.type}, got {str(value)[:40]!r}")
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"setting {self.name!r}: one of {', '.join(map(str, self.choices))}")
        if self.minimum is not None and value < self.minimum:  # type: ignore[operator]
            raise ValueError(f"setting {self.name!r}: at least {self.minimum:g}")
        if self.maximum is not None and value > self.maximum:  # type: ignore[operator]
            raise ValueError(f"setting {self.name!r}: at most {self.maximum:g}")
        return value

    def to_data(self) -> dict:
        """The plain-data form a client builds its settings controls from."""
        return {
            "name": self.name,
            "type": self.type,
            "default": self.default,
            "choices": None if self.choices is None else list(self.choices),
            "minimum": self.minimum,
            "maximum": self.maximum,
        }


@dataclass(frozen=True)
class CliSpec:
    """How a command line tool is asked for a picture (see the module description for the placeholders).

    The tool reads ``input`` (a file in the job folder holding the person's text, with ``prefix`` and ``suffix`` put
    around it) and writes the SVG to ``output`` (a file there, or ``"stdout"``). ``files`` are support files written
    next to the input before the run: structured content, so a setting can never break out of a quotation.
    ``diagnostics`` names how the tool's complaints are read into messages with a line."""

    argv: tuple[str, ...]
    output: str
    input: str = "input.txt"
    env: Mapping[str, str] = field(default_factory=dict)
    files: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: str = "plain"
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True)
class LimitSpec:
    """What one run of the plugin asks for; the server's policy caps every value."""

    seconds: float = 20.0
    memory_mb: int = 2048
    output_mb: int = 8
    address_space: bool = True


@dataclass(frozen=True)
class EditorHints:
    """What an editor and the AI are told about the text: its syntax name, an example and a short guide."""

    syntax: str = ""
    example: str = ""
    ai_hint: str = ""


@dataclass(frozen=True)
class Forbidden:
    """A pattern that makes a text unacceptable before anything is run, and what to tell the person.

    This is how a plugin closes a door its tool leaves open (Typst's ``@preview`` packages are fetched from the
    network): the text is refused with a message of the plugin's own words, not run and left to fail."""

    pattern: str
    message: str

    def matches(self, text: str) -> re.Match[str] | None:
        """The first place in ``text`` that this pattern finds, or ``None``."""
        return re.search(self.pattern, text)


@dataclass(frozen=True)
class Manifest:
    """A plugin's identity, needs, settings and way of rendering. Build one with :func:`parse_manifest`.

    Exactly one of ``cli`` (a declarative way to run a tool) and ``adapter`` (the name of a plugin built into the
    server, which is code and so never comes from a folder) says how it renders."""

    api: int
    type: str
    version: str
    title: str
    tier: str = "static"
    requires: tuple[ToolRequirement, ...] = ()
    params: tuple[ParamSpec, ...] = ()
    cli: CliSpec | None = None
    adapter: str | None = None
    svg_elements: frozenset[str] = frozenset()
    limits: LimitSpec = field(default_factory=LimitSpec)
    editor: EditorHints = field(default_factory=EditorHints)
    max_source_chars: int = 200_000
    forbid: tuple[Forbidden, ...] = ()

    def check_params(self, given: Mapping[str, object]) -> dict[str, object]:
        """The settings with defaults filled in; ``ValueError`` (naming the setting) if one is wrong or unknown."""
        known = {spec.name: spec for spec in self.params}
        for name in given:
            if name not in known:
                raise ValueError(f"setting {name!r}: {self.type} has no such setting")
        return {name: spec.check(given[name]) if name in given else spec.default for name, spec in known.items()}

    def to_data(self) -> dict:
        """What a client and the AI are told: identity, settings and hints. Never how the tool is run."""
        return {
            "api": self.api,
            "type": self.type,
            "version": self.version,
            "title": self.title,
            "tier": self.tier,
            "requires": [{"tool": r.tool, "version_at_least": r.version_at_least} for r in self.requires],
            "params": [spec.to_data() for spec in self.params],
            "editor": {"syntax": self.editor.syntax, "example": self.editor.example, "ai_hint": self.editor.ai_hint},
            "max_source_chars": self.max_source_chars,
        }


# --------------------------------------------------------------------------- reading
def _requirements(raw: object, what: str) -> tuple[ToolRequirement, ...]:
    if not isinstance(raw, list):
        raise ManifestError(f"{what}: a list is expected")
    found: list[ToolRequirement] = []
    for entry in raw:
        item = _mapping(entry, f"{what} item")
        _only(item, {"tool", "version_at_least"}, what)
        name = item.get("tool")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ManifestError(f"{what}: tool must be a plain lower-case name")
        least = item.get("version_at_least")
        if least is not None and (not isinstance(least, str) or not _VERSION.fullmatch(least)):
            raise ManifestError(f"{what}: version_at_least must be dotted numbers")
        found.append(ToolRequirement(name, least))
    return tuple(found)


def _param(raw: object) -> ParamSpec:
    item = _mapping(raw, "params item")
    _only(item, {"name", "type", "default", "choices", "minimum", "maximum"}, "params")
    name = item.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ManifestError("params: name must be a plain lower-case name")
    kind = item.get("type")
    if kind not in PARAM_TYPES:
        raise ManifestError(f"params {name}: type must be one of {', '.join(PARAM_TYPES)}")
    if "default" not in item:
        raise ManifestError(f"params {name}: a default is required")
    choices = item.get("choices")
    spec = ParamSpec(
        name,
        kind,
        item["default"],
        None if choices is None else tuple(choices),
        item.get("minimum"),
        item.get("maximum"),
    )
    try:
        spec.check(spec.default)
    except ValueError as error:
        raise ManifestError(f"params {name}: the default is not acceptable ({error})") from error
    return spec


def _placeholders(text: str, *, params: set[str], tools: set[str], files_ok: bool, where: str) -> list[str]:
    """The placeholders of ``text``, each checked to name something that exists; ``ManifestError`` if not."""
    found = []
    for raw in _PLACEHOLDER.findall(text):
        body = raw.removesuffix("?")
        parts = body.split(".")
        valid = (
            (body in ("input", "output") and files_ok)
            or (parts[0] == "param" and len(parts) == 2 and parts[1] in params)
            or (
                parts[0] == "tool"
                and len(parts) in (2, 3)
                and parts[1] in tools
                and (len(parts) == 2 or _NAME.fullmatch(parts[2]))
            )
        )
        if not valid:
            raise ManifestError(f"{where}: placeholder ${{{raw[:40]}}} names nothing this plugin has")
        found.append(body)
    return found


def _walk_strings(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, Mapping):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_strings(value)


def _argv(argv: object, params: tuple[ParamSpec, ...], names: set[str], tools: set[str]) -> list[str]:
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise ManifestError("cli argv: a list of text is expected")
    if not re.fullmatch(r"\$\{tool\.[a-z][a-z0-9_]{0,31}\}", argv[0]) or argv[0][7:-1] not in tools:
        raise ManifestError("cli argv: the first argument must be a required tool, written ${tool.NAME}")
    free_text = {spec.name for spec in params if spec.type == "string" and spec.choices is None}
    for argument in argv:
        for body in _placeholders(argument, params=names, tools=tools, files_ok=True, where="cli argv"):
            if body.startswith("param.") and body[6:] in free_text:
                raise ManifestError(f"cli argv: setting {body[6:]!r} is free text and needs choices to be an argument")
    return argv


def _cli_files(raw: object, taken: tuple[object, ...], names: set[str], tools: set[str]) -> Mapping[str, object]:
    files = _mapping(raw, "cli files")
    for name, content in files.items():
        if not _FILE.fullmatch(name) or name in taken:
            raise ManifestError(f"cli files: {name[:40]!r} is not a plain file name of its own")
        for string in _walk_strings(content):
            _placeholders(string, params=names, tools=tools, files_ok=False, where=f"cli files {name}")
    return files


def _cli(raw: object, params: tuple[ParamSpec, ...], requires: tuple[ToolRequirement, ...]) -> CliSpec:
    item = _mapping(raw, "cli")
    _only(item, {"argv", "output", "input", "env", "files", "diagnostics", "prefix", "suffix"}, "cli")
    names, tools = {spec.name for spec in params}, {r.tool for r in requires}
    argv = _argv(item.get("argv"), params, names, tools)
    output = item.get("output")
    if output != STDOUT and not (isinstance(output, str) and _FILE.fullmatch(output)):
        raise ManifestError(f"cli output: {STDOUT!r} or a plain file name")
    source = item.get("input", "input.txt")
    if not isinstance(source, str) or not _FILE.fullmatch(source):
        raise ManifestError("cli input: a plain file name")
    diagnostics = item.get("diagnostics", "plain")
    if diagnostics not in DIAGNOSTIC_READERS:
        raise ManifestError(f"cli diagnostics: one of {', '.join(DIAGNOSTIC_READERS)}")
    env = _mapping(item.get("env", {}), "cli env")
    for name, template in env.items():
        if not _ENV.fullmatch(name):
            raise ManifestError(f"cli env: {name!r} is not an upper-case variable name")
        _placeholders(_text(template, "cli env value", 500), params=names, tools=tools, files_ok=False, where="cli env")
    files = _cli_files(item.get("files", {}), (source, output), names, tools)
    wrapping = {key: _text(item.get(key, ""), f"cli {key}", 500) for key in ("prefix", "suffix")}
    for string in wrapping.values():
        _placeholders(string, params=names, tools=tools, files_ok=False, where="cli prefix/suffix")
    return CliSpec(
        tuple(argv), output, source, MappingProxyType(dict(env)), MappingProxyType(dict(files)), diagnostics, **wrapping
    )


def _forbid(raw: object) -> tuple[Forbidden, ...]:
    if not isinstance(raw, list) or len(raw) > 20:
        raise ManifestError("forbid: a list of at most 20 patterns")
    found = []
    for entry in raw:
        item = _mapping(entry, "forbid item")
        _only(item, {"pattern", "message"}, "forbid")
        if set(item) != {"pattern", "message"}:
            raise ManifestError("forbid: each item needs a pattern and a message")
        pattern = _text(item["pattern"], "forbid pattern", 200)
        try:
            re.compile(pattern)
        except re.error as error:
            raise ManifestError(f"forbid pattern {pattern[:40]!r}: not a regular expression ({error})") from error
        found.append(Forbidden(pattern, _text(item["message"], "forbid message", 300)))
    return tuple(found)


def _limits(raw: object) -> LimitSpec:
    item = _mapping(raw, "limits")
    _only(item, {"seconds", "memory_mb", "output_mb", "address_space"}, "limits")
    for key in ("seconds", "memory_mb", "output_mb"):
        if key in item and type(item[key]) not in (int, float):
            raise ManifestError(f"limits {key}: a number")
    spec = LimitSpec(**item)
    if not (0 < spec.seconds <= 600 and 16 <= spec.memory_mb <= 65536 and 1 <= spec.output_mb <= 256):
        raise ManifestError("limits: seconds up to 600, memory_mb from 16 to 65536, output_mb from 1 to 256")
    if type(spec.address_space) is not bool:
        raise ManifestError("limits address_space: true or false")
    return spec


def _editor(raw: object) -> EditorHints:
    item = _mapping(raw, "editor")
    _only(item, {"syntax", "example", "ai_hint"}, "editor")
    syntax = item.get("syntax", "")
    if not isinstance(syntax, str) or (syntax and not _TYPE.fullmatch(syntax)):
        raise ManifestError("editor syntax: a plain lower-case name")
    return EditorHints(
        syntax, _text(item.get("example", ""), "editor example"), _text(item.get("ai_hint", ""), "editor ai_hint")
    )


def parse_manifest(data: Mapping[str, Any]) -> Manifest:
    """Read and check a manifest from plain data; `ManifestError` says what is wrong, field by field."""
    if not isinstance(data, Mapping):
        raise ManifestError("a manifest is a mapping")
    _only(data, _TOP, "manifest")
    if data.get("api") != API_VERSION:
        raise ManifestError(f"manifest api {data.get('api')!r}: this server reads api {API_VERSION}")
    for key in ("type", "version", "title"):
        if key not in data:
            raise ManifestError(f"manifest {key}: required")
    kind, version = data["type"], data["version"]
    if not isinstance(kind, str) or not _TYPE.fullmatch(kind):
        raise ManifestError(f"manifest type {str(kind)[:40]!r}: a plain lower-case name of at most 32 characters")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ManifestError(f"manifest version {str(version)[:40]!r}: dotted numbers such as 1.2.0")
    tier = data.get("tier", "static")
    if tier not in TIERS:
        raise ManifestError(f"manifest tier {tier!r}: this server runs only {', '.join(TIERS)}")
    requires = _requirements(data.get("requires", []), "requires")
    params = tuple(_param(item) for item in data.get("params", []))
    if len({spec.name for spec in params}) != len(params):
        raise ManifestError("params: a name is used twice")
    cli = None if data.get("cli") is None else _cli(data["cli"], params, requires)
    adapter = data.get("adapter")
    if (cli is None) == (adapter is None):
        raise ManifestError(
            "manifest: either a cli or an adapter, and not both" if cli else "manifest: a cli or an adapter"
        )
    elements = frozenset(data.get("svg_elements", []))
    if elements & NEVER_ALLOWED:
        raise ManifestError(f"svg_elements: <{sorted(elements & NEVER_ALLOWED)[0]}> is never allowed")
    if not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z]+", name) for name in elements):
        raise ManifestError("svg_elements: element names")
    limit = data.get("max_source_chars", 200_000)
    if type(limit) is not int or not 1 <= limit <= MAX_RENDERING_SOURCE:
        raise ManifestError(f"manifest max_source_chars: a whole number up to {MAX_RENDERING_SOURCE}")
    return Manifest(
        API_VERSION,
        kind,
        version,
        _text(data["title"], "manifest title", 80),
        tier,
        requires,
        params,
        cli,
        adapter,
        elements,
        _limits(data.get("limits", {})),
        _editor(data.get("editor", {})),
        limit,
        _forbid(data.get("forbid", [])),
    )
