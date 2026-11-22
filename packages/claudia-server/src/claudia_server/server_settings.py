"""The server's own settings: the access secret, the document cap, the AI model and the LaTeX installation.

These belong to the server, never to a document (``admin.py`` explains why that is a different thing from D20 and
D35). They are kept in memory while the server runs and written to ``settings.json`` under the server's state
folder (``state.py``, next to ``admins.json`` and the TLS certificate) whenever something changes, so a restart
comes back the way it was left.

**Precedence.** An operator who gives a setting on the command line (``--access-secret-file``, ``--ai``, ...)
always wins at start-up over whatever an administrator saved through the settings pages — the command line is
how a headless deployment is pinned to one configuration on purpose. Leave the option out, and whatever was last
saved through the settings pages applies; leave both out, and the built-in default applies. ``cli.py`` resolves
this once, at start-up; nothing here decides it.

The access secret is kept here in the clear (not hashed, unlike a password): the settings page can "Reveal" it,
so it has to be possible to get back. The file it is written to is private to the server's own account
(``write_private``), the same as the TLS private key."""

from __future__ import annotations

import contextlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from claudia_core.clock import utc_now

from .state import private_dir, write_private

ADMIN_SUBDIR = "admin"
SETTINGS_FILE = "settings.json"
ADMINS_FILE = "admins.json"


@dataclass(frozen=True)
class Changed:
    """Who last changed one setting, and when — the "Last changed by ... " line of its page."""

    by: str
    at: str  # ISO 8601 UTC


STAND_IN = "stand-in"
LOCAL = "local"
CLAUDE = "claude"
PROVIDERS = (STAND_IN, LOCAL, CLAUDE)
"""The providers of the AI the administrator may choose; the one name of each, used by every module."""
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"


@dataclass
class ClaudeSettings:
    """Claude as the AI provider (E7.11, D266): the model id the administrator typed, the provider key, and who
    confirmed that document content is sent to Anthropic, and when (D264: the administrator's half of the two opt-ins).

    The key is kept here, in the private settings file like the access secret, and is never sent to a page
    (``AiSettings.public``): a page gets its last four characters."""

    model: str = DEFAULT_CLAUDE_MODEL
    key: str | None = field(default=None, repr=False)  # a repr is in logs and test output: never the key
    confirmed: Changed | None = None


@dataclass
class AiSettings:
    """Who answers ``@ai`` (``provider``: the scripted stand-in, a local model, or Claude), and how.

    ``model_dir`` is a folder converted for OpenVINO and ``device`` where to run it; ``max_tokens`` is the longest
    answer and ``timeout`` the longest an answer may take, for every provider. The settings of a provider that is not
    chosen are kept, so choosing it again needs no typing. Settings saved before there were providers (no
    ``provider``) mean the local model when there is a ``model_dir``, else the stand-in; the document gets no assistant
    at all only with ``--no-assistant``."""

    provider: str = STAND_IN
    model_dir: str | None = None
    device: str = "GPU"
    max_tokens: int = 512
    timeout: float = 180.0
    claude: ClaudeSettings = field(default_factory=ClaudeSettings)

    @classmethod
    def load(cls, data: dict) -> AiSettings:
        """The settings of :meth:`ServerSettings.dump`, or an older file's."""
        fields = dict(data)
        claude = dict(fields.pop("claude", {}))
        if claude.get("confirmed"):
            claude["confirmed"] = Changed(**claude["confirmed"])
        fields.setdefault("provider", LOCAL if fields.get("model_dir") else STAND_IN)
        return cls(**fields, claude=ClaudeSettings(**claude))

    def public(self) -> dict:
        """What a page may see: never the key, only whether there is one and its last four characters."""
        shown = asdict(self)
        key = shown["claude"].pop("key")
        shown["claude"] |= {"key_set": key is not None, "key_tail": key[-4:] if key else None}
        return shown


@dataclass
class TypesetSettings:
    """Where this server's LaTeX installation is. Each may be a full path, the folder it lives in, or a bare
    program name to look up on the PATH (``claudia_typeset.programs.resolve_program``); ``None`` looks for the
    usual name (``xelatex``, ``pdftocairo``) on the PATH."""

    xelatex: str | None = None
    pdftocairo: str | None = None


@dataclass
class RenderSettings:
    """The tools behind containers (D392): a logical name (``typst``, ``mmdc``) to a program, given as a path
    or as a mapping with a ``path`` and the options of that tool (``mmdc`` takes the ``chrome`` to drive and
    ``browser_args``). A tool not named here is looked for on the PATH. ``plugins_dir`` is a folder of manifests (data
    only) that add container types; ``None`` means ``STATE_DIR/plugins``. The LaTeX programs are not here: they are
    ``TypesetSettings``."""

    tools: dict[str, Any] = field(default_factory=dict)
    plugins_dir: str | None = None


@dataclass
class SecuritySettings:
    """How slow password hashing should be for new documents, in seconds on this machine (D1267). The server measures
    what that means for it (``kdf_policy.py``); documents made before keep the cost they were made with."""

    kdf_target_seconds: float = 0.75


@dataclass
class ServerSettings:
    """The mutable part of a server's configuration, plus who last changed each part of it. Nothing here is a
    document, and nothing here is kept per document."""

    max_documents: int
    access_secret: str | None = None
    ai: AiSettings = field(default_factory=AiSettings)
    typeset: TypesetSettings = field(default_factory=TypesetSettings)
    render: RenderSettings = field(default_factory=RenderSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    changed: dict[str, Changed] = field(default_factory=dict)

    def note_changed(self, key: str, by: str) -> None:
        """Record that ``by`` (an administrator's name) just changed the setting named ``key``."""
        self.changed[key] = Changed(by, utc_now())

    def to_public_dict(self) -> dict:
        """Everything a settings page may see: never the access secret itself, only whether one is set."""
        return {
            "max_documents": self.max_documents,
            "access_secret_set": self.access_secret is not None,
            "ai": self.ai.public(),
            "typeset": asdict(self.typeset),
            "render": asdict(self.render),
            "security": asdict(self.security),
            "changed": {key: asdict(value) for key, value in self.changed.items()},
        }

    def dump(self) -> dict:
        """Everything, including the access secret in the clear. Only ever written to the private settings
        file (see module docstring); never sent to a client as this."""
        return {
            "max_documents": self.max_documents,
            "access_secret": self.access_secret,
            "ai": asdict(self.ai),
            "typeset": asdict(self.typeset),
            "render": asdict(self.render),
            "security": asdict(self.security),
            "changed": {key: asdict(value) for key, value in self.changed.items()},
        }

    @classmethod
    def load(cls, data: dict) -> ServerSettings:
        """The settings of :meth:`dump`."""
        settings = cls(
            max_documents=int(data["max_documents"]),
            access_secret=data.get("access_secret"),
            ai=AiSettings.load(data.get("ai", {})),
            typeset=TypesetSettings(**data.get("typeset", {})),
            render=RenderSettings(**data.get("render", {})),
            security=SecuritySettings(**data.get("security", {})),
        )
        settings.changed = {key: Changed(**value) for key, value in data.get("changed", {}).items()}
        return settings


def admin_dir(state_dir: Path) -> Path:
    """The folder the administrator state lives in, under the server's state folder."""
    return state_dir / ADMIN_SUBDIR


def load_settings(state_dir: Path, *, default_max_documents: int) -> ServerSettings:
    """The settings last saved under ``state_dir``, or freshly made ones if there are none yet (or the file is
    damaged: a server must still start)."""
    path = admin_dir(state_dir) / SETTINGS_FILE
    if path.is_file():
        try:
            return ServerSettings.load(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return ServerSettings(max_documents=default_max_documents)


def save_settings(state_dir: Path, settings: ServerSettings) -> None:
    """Write ``settings`` to ``state_dir``, replacing it atomically (the same guarantee the TLS key gets)."""
    folder = private_dir(admin_dir(state_dir))
    write_private(folder / SETTINGS_FILE, json.dumps(settings.dump()).encode("utf-8"))


def load_admins(state_dir: Path, directory) -> None:
    """Load the administrators last saved under ``state_dir`` into ``directory`` (an :class:`AdminDirectory`), if
    there are any. A damaged file leaves ``directory`` empty rather than stopping the server."""
    path = admin_dir(state_dir) / ADMINS_FILE
    if path.is_file():
        with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
            directory.load(json.loads(path.read_text(encoding="utf-8")))


def save_admins(state_dir: Path, directory) -> None:
    """Write the administrators of ``directory`` to ``state_dir``, replacing the file atomically."""
    folder = private_dir(admin_dir(state_dir))
    write_private(folder / ADMINS_FILE, json.dumps(directory.dump()).encode("utf-8"))
