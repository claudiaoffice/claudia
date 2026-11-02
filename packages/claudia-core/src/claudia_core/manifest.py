"""Document manifest and requirements (E1.9, thin).

A document declares what it needs from the server it is opened on: the app and its schema versions, the
fonts it uses, and the UserFunctions (name, version, digest) its cells call. ``check`` compares that with
what the server has and returns a precise report; nothing is fetched here (the font service and the
function folder are other epics).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FunctionRequirement:
    name: str
    version: str
    digest: str

    def to_data(self) -> dict:
        """The plain-data form of the requirement."""
        return {"name": self.name, "version": self.version, "digest": self.digest}


@dataclass(frozen=True)
class FontRequirement:
    family: str

    def to_data(self) -> dict:
        """The plain-data form of the requirement."""
        return {"family": self.family}


@dataclass(frozen=True)
class Requirements:
    functions: tuple[FunctionRequirement, ...] = ()
    fonts: tuple[FontRequirement, ...] = ()


@dataclass(frozen=True)
class Manifest:
    app: str
    state_schema: int
    command_schemas: Mapping[str, int] = field(default_factory=dict)  # kinds used in the log -> highest schema
    requirements: Requirements = Requirements()
    format: int = 1

    def to_data(self) -> dict:
        """The plain-data form of the manifest."""
        return {
            "format": self.format,
            "app": self.app,
            "state_schema": self.state_schema,
            "command_schemas": dict(self.command_schemas),
            "functions": [f.to_data() for f in self.requirements.functions],
            "fonts": [f.to_data() for f in self.requirements.fonts],
        }

    @classmethod
    def from_data(cls, data: dict) -> Manifest:
        """Inverse of ``to_data``."""
        return cls(
            data["app"],
            data["state_schema"],
            dict(data.get("command_schemas", {})),
            Requirements(
                tuple(FunctionRequirement(**f) for f in data.get("functions", [])),
                tuple(FontRequirement(**f) for f in data.get("fonts", [])),
            ),
            data.get("format", 1),
        )


@dataclass(frozen=True)
class FunctionInfo:
    version: str
    digest: str


@dataclass(frozen=True)
class Environment:
    """What the server has."""

    app: str
    state_schema: int
    command_schemas: Mapping[str, int]  # every kind it understands -> its current schema
    functions: Mapping[str, FunctionInfo] = field(default_factory=dict)
    fonts: frozenset[str] = frozenset()  # installed
    providable_fonts: frozenset[str] = frozenset()  # the font service could deliver these


@dataclass(frozen=True)
class RequirementReport:
    wrong_app: str | None = None
    state_too_new: bool = False
    unknown_commands: tuple[str, ...] = ()
    commands_too_new: tuple[tuple[str, int, int], ...] = ()  # (kind, found, known)
    missing_functions: tuple[str, ...] = ()
    stale_functions: tuple[tuple[str, str, str], ...] = ()  # (name, expected digest, found digest)
    fonts_to_provide: tuple[str, ...] = ()
    fonts_unavailable: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """The document can be opened and edited (stale functions and providable fonts do not block)."""
        return not (
            self.wrong_app
            or self.state_too_new
            or self.unknown_commands
            or self.commands_too_new
            or self.missing_functions
        )

    @property
    def clean(self) -> bool:
        """True if the document opens and, beyond that, nothing is stale, to be delivered or unavailable."""
        return self.ok and not (self.stale_functions or self.fonts_to_provide or self.fonts_unavailable)

    @property
    def stale_names(self) -> tuple[str, ...]:
        """Names of the functions whose digest changed."""
        return tuple(name for name, _, _ in self.stale_functions)

    def describe(self) -> list[str]:
        """The report as sentences fit for the user."""
        lines: list[str] = []
        if self.wrong_app:
            lines.append(f"This is a {self.wrong_app} document and cannot be opened here.")
        if self.state_too_new:
            lines.append("The document was saved by a newer version of Claudia. Please update.")
        lines += [f"Unknown command {k!r}: an extension is not installed." for k in self.unknown_commands]
        lines += [f"Command {k!r} has schema {f}, this version knows up to {n}." for k, f, n in self.commands_too_new]
        lines += [f"Function {n} is not installed." for n in self.missing_functions]
        lines += [
            f"Function {n} has changed (document: {a[:8]}, installed: {b[:8]}); its results are stale."
            for n, a, b in self.stale_functions
        ]
        lines += [f"Font {f} will be delivered by the server." for f in self.fonts_to_provide]
        lines += [f"Font {f} is not available; a substitute will be used." for f in self.fonts_unavailable]
        return lines


def check(manifest: Manifest, env: Environment) -> RequirementReport:
    """Compare what a document requires with what this installation offers; nothing is fetched here."""
    wrong_app = manifest.app if manifest.app != env.app else None
    unknown = tuple(sorted(k for k in manifest.command_schemas if k not in env.command_schemas))
    too_new = tuple(
        sorted(
            (k, v, env.command_schemas[k])
            for k, v in manifest.command_schemas.items()
            if k in env.command_schemas and v > env.command_schemas[k]
        )
    )
    missing, stale = [], []
    for need in manifest.requirements.functions:
        have = env.functions.get(need.name)
        if have is None:
            missing.append(need.name)
        elif have.digest != need.digest:
            stale.append((need.name, need.digest, have.digest))
    provide: list[str] = []
    unavailable: list[str] = []
    for font in manifest.requirements.fonts:
        if font.family in env.fonts:
            continue
        (provide if font.family in env.providable_fonts else unavailable).append(font.family)
    return RequirementReport(
        wrong_app,
        manifest.state_schema > env.state_schema,
        unknown,
        too_new,
        tuple(sorted(missing)),
        tuple(sorted(stale)),
        tuple(sorted(provide)),
        tuple(sorted(unavailable)),
    )
