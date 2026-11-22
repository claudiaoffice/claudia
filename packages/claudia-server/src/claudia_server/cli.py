"""Command line of the server: ``python3 -m claudia_server``.

Local use (the default) binds to 127.0.0.1:

    python3 -m claudia_server

Secure by default: the connection is encrypted (https:// and wss://). The server makes itself a certificate the first
time (browsers warn about it once; the desktop client asks the person to trust its fingerprint, which is printed at
start-up), or it is given one:

    python3 -m claudia_server --tls-cert fullchain.pem --tls-key privkey.pem
    python3 -m claudia_server --tls-name claudia.example.org      # the name people will type
    python3 -m claudia_server --no-tls                           # plain text: only for this computer
    python3 -m claudia_server --no-tls --host 0.0.0.0 --behind-proxy   # a proxy that encrypts stands in front

Plain text is only for this computer: passwords would cross the network in the clear, so ``--no-tls`` on any other
address is refused unless ``--behind-proxy`` says that a proxy in front of the server encrypts (SEC-07).

The server answers only to ``localhost``, to IP addresses, to the name of this computer and to the names it is told
about with ``--allow-host`` (and ``--tls-name`` and ``--host``): a web page that has pointed its own name at this
computer is refused (SEC-01). Behind a proxy that passes the name people typed on, add that name with ``--allow-host``.

Whoever can reach the server can make documents, up to ``--max-documents``. To keep strangers out, give the server an
access secret (``--access-secret-file FILE`` or the environment variable ``CLAUDIA_ACCESS_SECRET``): only those who know
it can make documents or read the list (SEC-02).

The web app (built in ``web/``) is served from the same address with ``--web``. A page served from another origin (the
Nuxt dev server on :3000, say) must be named with ``--allow-origin``. Documents live in memory unless ``--dir`` names
a folder: there every document is a sealed (encrypted) file that only its people can open. ``--plain-dir`` keeps the
old unencrypted store of the early demos; it has to be asked for by name.

The AI user answers with a language model that runs on this machine, with OpenVINO (``pip install openvino-genai``).
Give it the folder of a model converted for OpenVINO; it is loaded before the server starts listening, so a wrong
folder, a missing library or a device that is not there stops the server with a message that says what to do:

    python3 -m claudia_server --dir ./documents --ai ~/models/qwen2.5-7b-instruct-int4-ov --ai-device GPU

Who may configure the server once it is running, rather than choosing everything up front, is a different question
(``admin.py``): the first administrator is named on the settings pages with the setup code this server says in its
start banner (``admin_start.py``, SEC-12), or at start with ``--admin NAME`` and ``--admin-password-file``; after that
administrators manage it (and each other) from there, at ``/api/admin/*``. ``--reset-administrators`` forgets them
all, for whoever can start the server, and keeps every setting. What they
set is saved under the server's own state (``--state-dir``, next to its TLS certificate) and applies at every later
start. ``--max-documents``, ``--access-secret-file``/``CLAUDIA_ACCESS_SECRET`` and ``--ai``/``--ai-device`` remain
useful without ever touching the settings pages (a container that must start the same way every time, say): given on
the command line or in the environment, each is an *operator override* for that run only — used exactly as given,
never written back to what the settings pages hold, so the next run without it goes back to whatever was saved
there. Leave all three out, and a freshly started server behaves exactly as one that has never been configured at
all: the built-in defaults, open to whoever can reach it.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claudia_ai import DEFAULT_DEVICE, ModelError, ModelRunner, OpenVinoModel
from claudia_core import DocumentModel
from claudia_core.clock import utc_now
from claudia_creates import ShapeLibrary
from claudia_fonts import builtin_folder
from claudia_render import RenderService, ToolRegistry, builtin_registry

from . import __version__, redirect
from .admin import AdminDirectory
from .admin_api import AdminContext, AiRuntime, any_lens, assistants_for
from .admin_sessions import AdminSessions
from .admin_start import AdminOptions, AdminStart, prepare_administrators
from .ai_desk import ProviderDesk
from .app import DEFAULT_MAX_WAITING, DEFAULT_MAX_WAITING_PER_ADDRESS, MIN_ACCESS_SECRET, create_app
from .apps import methods_for
from .assistant import Assistant
from .auth import ScryptDirectory, UserDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .containers import RenderDesk
from .filestore import FileDirectory, FileProvider
from .folder_lock import FolderLock, FolderLocked
from .fonts import FontService
from .hosts import LOCALHOST, AllowedHosts, is_exposed, is_loopback, is_unspecified, machine_names
from .hub import DEFAULT_MAX_DOCUMENTS, DocumentProvider, Hub, MemoryProvider
from .hyphenation import HyphenationService
from .idle import IdleWatch
from .kdf_policy import KdfPolicy
from .protocol import Limits
from .rasterise import svg_rasteriser
from .sealed import SealedDocuments
from .server_settings import CLAUDE, LOCAL, STAND_IN, AiSettings, ServerSettings, load_admins, load_settings
from .state import default_state_dir
from .suite import APP_MODELS, Module, Suite


class UsageError(Exception):
    """A combination of options that cannot work; the message is shown to the person running the server."""


@dataclass
class Plan:
    """Everything needed to start: the application, how uvicorn should run it, and what to tell the operator."""

    app: Any
    uvicorn_options: dict[str, Any]
    banner: list[str] = field(default_factory=list)
    redirect_from: int | None = None
    closers: list[Callable[[], None]] = field(default_factory=list)  # what to stop when the server has stopped
    idle: IdleWatch | None = None  # with --exit-when-idle: told how to stop the server once it runs (main)
    kdf: KdfPolicy | None = None  # what hashing costs for new sealed documents: measured once the server runs (D1267)

    def start(self) -> None:
        """Begin what only makes sense while the server runs: measuring the machine for the hashing cost, in the
        background, so that the server is up at once."""
        if self.kdf is not None:
            self.kdf.start()

    def close(self) -> None:
        """Stop what the server started besides itself (the language model's worker, the lock on its folder)."""
        for close in self.closers:
            close()


def build_parser() -> argparse.ArgumentParser:
    """The options of the command line."""
    parser = argparse.ArgumentParser(prog="python3 -m claudia_server", description="Run a Claudia server.")
    parser.add_argument("--version", action="version", version=f"claudia-server {__version__}")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    apps = parser.add_mutually_exclusive_group()
    apps.add_argument(
        "--apps",
        metavar="APPS",
        help=f"the apps to serve, separated by commas (default: all of them, {','.join(APP_MODELS)})",
    )
    apps.add_argument(
        "--model",
        help="serve one app only, by its document model (module:Class), with its documents directly in --dir",
    )
    parser.add_argument(
        "--dir",
        metavar="DIR",
        help="keep documents in DIR as sealed (encrypted) files, each app's in DIR/APP (default: in memory, lost on "
        "exit)",
    )
    parser.add_argument(
        "--plain-dir",
        metavar="DIR",
        help="keep documents and users in DIR as plain files, NOT encrypted (the store of the early demos)",
    )
    parser.add_argument(
        "--exit-when-idle",
        type=float,
        metavar="SECONDS",
        help="stop once nothing has used the server for SECONDS: no open socket, no request (the desktop apps' "
        "local server)",
    )
    parser.add_argument("--web", metavar="DIR", help="serve the built web app from DIR")
    parser.add_argument(
        "--shapes",
        action="append",
        default=[],
        metavar="DIR",
        help="presentations: offer the shapes (JSON files) in DIR besides the built-in ones; can be repeated",
    )
    parser.add_argument("--no-list", action="store_true", help="do not serve the list of documents (/api/docs)")
    parser.add_argument(
        "--fonts",
        action="append",
        default=[],
        metavar="DIR",
        help="font collections to hand to clients for layout and PDF export (/api/fonts), besides the open fonts "
        "every server has (D500): a collection folder or a folder of them; repeatable. STATE_DIR/fonts, where the "
        "server settings add fonts, is read after them",
    )
    parser.add_argument(
        "--hyphenation",
        metavar="DIR",
        default=None,
        help="the folder of hyphenation patterns to hand to clients (/api/hyphenation). Default: "
        "STATE_DIR/hyphenation. Fill it with python -m claudia_server.hyphenation fetch DIR",
    )
    parser.add_argument(
        "--no-assistant", action="store_true", help="do not give workbooks the scripted stand-in for the AI"
    )
    ai = parser.add_argument_group("AI assistant")
    ai.add_argument(
        "--ai",
        metavar="MODEL_DIR",
        help="the AI user answers with the language model in MODEL_DIR (converted for OpenVINO), not the stand-in",
    )
    ai.add_argument(
        "--anthropic-key-file",
        metavar="FILE",
        help="the file that holds the key for Claude (without it the environment variable ANTHROPIC_API_KEY is used if "
        "it is set); it wins over a key saved in the server settings",
    )
    ai.add_argument("--anthropic-base-url", default=None, help=argparse.SUPPRESS)  # for tests: never a field of a page
    ai.add_argument(
        "--ai-device", default=DEFAULT_DEVICE, metavar="DEVICE", help="where the model runs: CPU, GPU, NPU or AUTO"
    )
    ai.add_argument("--ai-max-tokens", type=int, default=512, metavar="N", help="longest answer, in tokens")
    ai.add_argument(
        "--ai-timeout", type=float, default=180.0, metavar="SECONDS", help="longest time one answer may take"
    )
    parser.add_argument("--allow-origin", action="append", default=[], metavar="ORIGIN")
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NAME",
        help="a host name the server answers to besides localhost, IP addresses and this computer's name: the name "
        "people type in the address bar (behind a proxy: the name the proxy passes on); can be repeated",
    )
    parser.add_argument("--no-create", action="store_true", help="documents cannot be created over the network")
    parser.add_argument("--max-connections", type=int, default=200)
    abuse = parser.add_argument_group("limits and access")
    abuse.add_argument(
        "--max-documents",
        type=int,
        default=None,
        metavar="N",
        help="the most documents the server holds; past it nobody can make another (default: "
        f"{DEFAULT_MAX_DOCUMENTS}, or whatever an administrator last set on the settings pages — giving this "
        "option pins the cap for this run and leaves what is saved there untouched)",
    )
    abuse.add_argument(
        "--max-waiting",
        type=int,
        default=DEFAULT_MAX_WAITING,
        metavar="N",
        help="the most connections that may wait to be let in at the same time (default: %(default)s)",
    )
    abuse.add_argument(
        "--max-waiting-per-address",
        type=int,
        default=DEFAULT_MAX_WAITING_PER_ADDRESS,
        metavar="N",
        help="the most of them from one address (default: %(default)s)",
    )
    abuse.add_argument(
        "--access-secret-file",
        metavar="FILE",
        help=f"only those who know the secret in FILE (at least {MIN_ACCESS_SECRET} characters) can make documents or "
        "read the list; without this option the environment variable CLAUDIA_ACCESS_SECRET is used if it is set",
    )
    parser.add_argument(
        "--state-dir", help="where the certificate and the admin settings are kept (default: a per-user folder)"
    )
    admins = parser.add_argument_group("administrators (SEC-12)")
    admins.add_argument(
        "--reset-administrators",
        action="store_true",
        help="forget every administrator (they are kept aside in the state folder); settings, fonts and documents "
        "stay. The next administrator is named with a new setup code, or with --admin",
    )
    admins.add_argument(
        "--admin",
        metavar="NAME",
        default=os.environ.get("CLAUDIA_ADMIN"),
        help="name NAME the first administrator at start if there is none, with the password in "
        "--admin-password-file; never changes an administrator who exists (default: CLAUDIA_ADMIN)",
    )
    admins.add_argument(
        "--admin-password-file",
        metavar="FILE",
        default=os.environ.get("CLAUDIA_ADMIN_PASSWORD_FILE"),
        help="the password of --admin: the first line of FILE (default: CLAUDIA_ADMIN_PASSWORD_FILE)",
    )
    tls = parser.add_argument_group("encryption")
    tls.add_argument("--no-tls", action="store_true", help="do not encrypt (only for this computer, or behind a proxy)")
    tls.add_argument(
        "--behind-proxy",
        action="store_true",
        help="with --no-tls: a proxy in front of this server encrypts the traffic; needed to listen on any address "
        "other than this computer's",
    )
    tls.add_argument(
        "--proxy-hops",
        type=int,
        metavar="N",
        help="with --behind-proxy: how many proxies in front of this server set X-Forwarded-For (default 1). A "
        "person is counted by the address the nearest of them appended, not by the proxy's own, so a wait or a cap "
        "for one address does not hit everybody. 0 counts by the socket and ignores the header",
    )
    tls.add_argument("--tls-cert", metavar="FILE")
    tls.add_argument("--tls-key", metavar="FILE")
    tls.add_argument(
        "--tls-name", action="append", default=[], metavar="NAME", help="a name the certificate must cover"
    )
    tls.add_argument("--redirect-port", type=int, metavar="PORT", help="a plain-HTTP port that sends people to https")
    return parser


def load_model(spec: str) -> type[DocumentModel]:
    """The document model class named ``module:Class``."""
    module_name, _, class_name = spec.partition(":")
    if not (module_name and class_name):
        raise UsageError(f"--model must look like module:Class, not {spec!r}")
    try:
        return getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError) as exc:
        raise UsageError(f"cannot load the model {spec}: {exc}") from exc


def _tls(args: argparse.Namespace) -> tuple[Certificate | None, dict[str, str]]:
    if args.no_tls and (args.tls_cert or args.tls_key):
        raise UsageError("--no-tls and --tls-cert/--tls-key contradict each other")
    if args.proxy_hops is not None and not args.behind_proxy:
        raise UsageError("--proxy-hops goes with --behind-proxy: without a proxy there is no header to trust")
    if args.proxy_hops is not None and args.proxy_hops < 0:
        raise UsageError("--proxy-hops cannot be negative")
    if args.behind_proxy and not args.no_tls:
        raise UsageError("--behind-proxy says that a proxy encrypts instead of this server, so it goes with --no-tls")
    if args.no_tls:
        if args.redirect_port:
            raise UsageError("--redirect-port needs TLS (there is nothing to redirect to with --no-tls)")
        if not (is_loopback(args.host) or args.behind_proxy):
            raise UsageError(
                f"--no-tls on {args.host} would send passwords in clear text over the network. Put a proxy that "
                "encrypts in front of the server and add --behind-proxy, or leave --no-tls out."
            )
        return None, {}
    try:
        certificate = ensure_certificate(args.state_dir, tuple(args.tls_name), args.tls_cert, args.tls_key)
    except CertificateError as exc:
        raise UsageError(str(exc)) from exc
    return certificate, {"ssl_certfile": str(certificate.cert_file), "ssl_keyfile": str(certificate.key_file)}


_CAPS = (
    ("--max-documents", "max_documents"),
    ("--max-waiting", "max_waiting"),
    ("--max-waiting-per-address", "max_waiting_per_address"),
)


def _check_caps(args: argparse.Namespace) -> None:
    for option, name in _CAPS:
        value = getattr(args, name)
        if value is not None and value < 1:  # --max-documents may be None: left to the server's own settings
            raise UsageError(f"{option} must be at least 1")
    if args.exit_when_idle is not None and args.exit_when_idle <= 0:
        raise UsageError("--exit-when-idle must be a positive number of seconds")


def _hosts(args: argparse.Namespace) -> AllowedHosts:
    """The names the server answers to: those it was told about, the one it listens on and this computer's own."""
    try:
        return AllowedHosts([*args.allow_host, *args.tls_name, args.host, *machine_names()])
    except ValueError as exc:
        raise UsageError(f"the host names (--allow-host, --tls-name, --host): {exc}") from exc


def _operator_access_secret(args: argparse.Namespace) -> str | None:
    """The secret given on the command line or in the environment: from the file the option names, else from the
    environment, else none (there is no operator override).

    A secret that is asked for but empty or short stops the server: an empty variable is what an unset value in a
    compose file looks like, and it must not leave the server open without a word."""
    if args.access_secret_file:
        try:
            secret = Path(args.access_secret_file).expanduser().read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            raise UsageError(f"--access-secret-file: cannot read {args.access_secret_file}: {exc}") from exc
    elif "CLAUDIA_ACCESS_SECRET" in os.environ:
        secret = os.environ["CLAUDIA_ACCESS_SECRET"].strip()
    else:
        return None
    if len(secret) < MIN_ACCESS_SECRET:
        raise UsageError(f"the access secret needs at least {MIN_ACCESS_SECRET} characters")
    return secret


def _access_secret(args: argparse.Namespace, settings: ServerSettings) -> str | None:
    """The secret that lets people make documents, for this run: the operator's own (``--access-secret-file`` or
    ``CLAUDIA_ACCESS_SECRET``) if given, else whatever was last saved through the settings pages.

    An operator override is used exactly as given and is never written back to the saved settings (see the module
    docstring on precedence): the next run without it goes back to what the settings pages hold."""
    given = _operator_access_secret(args)
    return given if given is not None else settings.access_secret


def _state_dir(args: argparse.Namespace) -> Path:
    """Where this server's own state lives: ``--state-dir``, else the per-user place ``certs.py`` already uses."""
    return Path(args.state_dir).expanduser() if args.state_dir else default_state_dir()


def _models(args: argparse.Namespace) -> tuple[list[type[DocumentModel]], bool]:
    """The document models of the apps to serve, in order, and whether the server is the old kind with one app
    whose documents sit directly in ``--dir`` (``--model``, D433)."""
    if args.model:
        return [load_model(args.model)], True
    names = [name.strip() for name in (args.apps or ",".join(APP_MODELS)).split(",") if name.strip()]
    unknown = [name for name in names if name not in APP_MODELS]
    if unknown or not names:
        raise UsageError(f"--apps: choose from {', '.join(APP_MODELS)}, not {', '.join(unknown) or 'nothing'}")
    if len(set(names)) != len(names):
        raise UsageError("--apps: each app once")
    return [load_model(APP_MODELS[name]) for name in names], False


def _shapes(args: argparse.Namespace, models: list[type[DocumentModel]]) -> ShapeLibrary | None:
    """The shape library of the presentations (``None`` on a server without creates: the other apps have no
    shapes)."""
    if all(model.app != "creates" for model in models):
        if args.shapes:
            raise UsageError("--shapes: only servers of presentations use shapes")
        return None
    for folder in args.shapes:
        if not Path(folder).is_dir():
            raise UsageError(f"--shapes: {folder} is not a folder")
    return ShapeLibrary.load([Path(folder) for folder in args.shapes])


def _fonts(args: argparse.Namespace, state_dir: Path) -> FontService:
    """The fonts this server hands to its clients: the starter set that ships with ``claudia_fonts`` (D500, so that
    printing never finds a server without fonts), then the folders of ``--fonts``, then ``STATE_DIR/fonts``, where
    Server settings ▸ Fonts adds collections (D1041); a font of the same family and style in a later one replaces an
    earlier one. ``UsageError`` for a folder given on the command line that does not exist."""
    for folder in args.fonts:
        if not Path(folder).is_dir():
            raise UsageError(f"--fonts: {folder} is not a folder")
    return FontService.from_folders(
        [Path(f) for f in args.fonts],
        state_dir / "webfonts",
        shipped=[builtin_folder()],
        added_root=state_dir / "fonts",
    )


def _program_of(entry: object) -> str | None:
    """The path of a tool entry, which is a path or a mapping with one."""
    return entry.get("path") if isinstance(entry, dict) else entry  # type: ignore[return-value]


def _tool_table(settings: ServerSettings) -> dict[str, object]:
    """The tools of the settings *as they are now*: the LaTeX programs of ``typeset`` and the ``render`` tools. Asked
    for again on every use, so what an administrator changes in Server settings takes effect without a restart."""
    tools: dict[str, object] = {"xelatex": settings.typeset.xelatex, "pdftocairo": settings.typeset.pdftocairo}
    tools.update(settings.render.tools)
    return {name: path for name, path in tools.items() if path is not None}


def _renderings(settings: ServerSettings, state_dir: Path, fonts: FontService) -> tuple[RenderDesk, list[str]]:
    """What makes containers (D395): the built-in types, the manifests of the plugins folder and the tools the
    administrator registered (the LaTeX programs are those of the typeset settings). The lines are for the start-up
    report: what is offered, and each manifest that could not be taken, with the reason."""
    work = state_dir / "render"
    registry = builtin_registry(lambda: fonts.catalogue, work / "plugins")
    folder = Path(settings.render.plugins_dir) if settings.render.plugins_dir else state_dir / "plugins"
    reports = registry.load_directory(folder, work / "plugins")
    tools = _tool_table(settings)
    service = RenderService(registry, ToolRegistry(lambda: _tool_table(settings)), work)
    lines = ["containers: " + ", ".join(plugin.manifest.type for plugin in registry.plugins())]
    lines += [f"  not used, {folder.name}/{r.file}: {r.error}" for r in reports if r.error]
    draw = svg_rasteriser(_program_of(tools.get("rsvg_convert")))
    lines.append(
        "office files draw containers as pictures"
        if draw
        else "office files get containers as SVG only (no rsvg-convert; help topic render.configure-tools)"
    )
    return RenderDesk(service, draw), lines


def _hyphenation(args: argparse.Namespace, state_dir: Path) -> HyphenationService:
    """The hyphenation patterns this server hands to its clients: from ``--hyphenation``, else
    ``STATE_DIR/hyphenation``. ``UsageError`` for a folder given on the command line that does not exist."""
    if args.hyphenation and not Path(args.hyphenation).is_dir():
        raise UsageError(f"--hyphenation: {args.hyphenation} is not a folder")
    return HyphenationService.from_folder(Path(args.hyphenation) if args.hyphenation else state_dir / "hyphenation")


def _what_is_loaded(library: ShapeLibrary | None, desk: ProviderDesk) -> list[str]:
    """The lines of the start-up report about the shapes (and the files skipped) and the AI providers."""
    lines: list[str] = []
    if library is not None:
        lines.append("shapes: " + ", ".join(shape.id for shape in library))
        lines += [f"  not used, {name}: {message}" for name, message in library.problems]
    if desk.local is not None:
        lines.append(f'AI assistant: user "ai", model {desk.local.name}')
    if desk.claude is not None:
        lines.append(f'AI assistant: user "ai", {desk.claude.name} where the document owners allow it')
    return lines


def _load_runner(model_dir: str, device: str, max_tokens: int, timeout: float) -> ModelRunner:
    """Load the model of ``model_dir`` onto ``device``. ``UsageError`` if it cannot be loaded."""
    print(f"loading the AI model from {model_dir} on {device} (this can take a while) ...", flush=True)
    try:
        return ModelRunner(OpenVinoModel(model_dir, device), max_new_tokens=max_tokens, timeout=timeout)
    except ModelError as exc:
        raise UsageError(f"--ai: {exc}") from exc


def _operator_anthropic_key(args: argparse.Namespace) -> str | None:
    """The provider key given on the command line or in the environment (``--anthropic-key-file``, else
    ``ANTHROPIC_API_KEY``), or none. Like the access secret: asked for but empty stops the server, and it is never
    written back to the saved settings (D154)."""
    if args.anthropic_key_file:
        try:
            key = Path(args.anthropic_key_file).expanduser().read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            raise UsageError(f"--anthropic-key-file: cannot read {args.anthropic_key_file}: {exc}") from exc
    elif "ANTHROPIC_API_KEY" in os.environ:
        key = os.environ["ANTHROPIC_API_KEY"].strip()
    else:
        return None
    if not key:
        raise UsageError("the Anthropic key is empty")
    return key


def _build_assistant(
    args: argparse.Namespace, models: list[type[DocumentModel]], settings: ServerSettings
) -> tuple[dict[str, Callable[[], Assistant] | None], AiRuntime]:
    """The assistant factory of each app to start with, by app, and the ``AiRuntime`` the admin API changes them
    through afterwards. Every document's assistant asks the runtime's ``ProviderDesk`` for each question who answers:
    the scripted stand-in, the one language model of the server (D432) or Claude (E7.11).

    ``--ai`` is an operator override (see the module docstring on precedence): given, it is used exactly as before
    this existed, and the saved AI settings are not even consulted. Without it, the settings last saved through the
    settings pages are used instead (if any), so that a provider chosen there survives a restart; with neither, a
    document gets the scripted stand-in, unless ``--no-assistant`` says it gets nothing — an operator's own
    decision that the settings pages must not be able to undo (``AiRuntime.enabled``)."""
    enabled = not args.no_assistant
    ai = AiRuntime(
        models=tuple(models),
        enabled=enabled,
        anthropic_key=_operator_anthropic_key(args),
        anthropic_url=args.anthropic_base_url,
    )
    if args.ai:
        if args.no_assistant:
            raise UsageError("--ai and --no-assistant contradict each other")
        if args.ai_max_tokens < 1 or args.ai_timeout <= 0:
            raise UsageError("--ai-max-tokens and --ai-timeout must be positive")
        runner = _load_runner(args.ai, args.ai_device, args.ai_max_tokens, args.ai_timeout)
        if not any_lens(models):
            runner.close()
            raise UsageError("--ai: the AI assistant does not know documents of this kind yet")
        ai.desk.install(provider=LOCAL, local=runner)
    elif enabled:
        _start_saved_provider(ai, settings.ai)
    return assistants_for(models, ai.desk) if enabled else dict.fromkeys((m.app for m in models), None), ai


def _start_saved_provider(ai: AiRuntime, saved: AiSettings) -> None:
    """Start with the providers last saved through the settings pages. What cannot be started is said on stderr and
    the stand-in answers until the administrator fixes it; the server itself always starts."""
    if saved.provider == STAND_IN:
        return
    local = None
    if saved.model_dir:
        try:
            local = _load_runner(saved.model_dir, saved.device, saved.max_tokens, saved.timeout)
        except UsageError as exc:
            print(f"warning: the AI model saved in the server settings could not be loaded: {exc}", file=sys.stderr)
            print("starting without it; open the server settings to fix or change it", file=sys.stderr)
        else:
            if not any_lens(ai.models):  # the saved model_dir does not match this server's document models any more
                local.close()
                local = None
    claude = None
    if saved.provider == CLAUDE:
        try:
            claude = ai.claude_runner(saved)
        except ValueError as exc:
            print(f"warning: Claude, saved in the server settings, cannot be used: {exc}", file=sys.stderr)
    ai.desk.install(provider=saved.provider, local=local, claude=claude, approved=saved.claude.confirmed is not None)


def _storage(
    args: argparse.Namespace, model: type[DocumentModel], one_app: bool, kdf: KdfPolicy | None = None
) -> tuple[DocumentProvider, UserDirectory]:
    """Where an app's documents (and, for ``--plain-dir``, their own users) live: sealed files, plain files, or
    memory. Each app has its own place, ``DIR/<app>`` (D431); a server of the old kind (``--model``) keeps them
    directly in ``DIR`` (D433)."""
    if args.dir:
        sealed = SealedDocuments(
            Path(args.dir) if one_app else Path(args.dir) / model.app, model, kdf=None if kdf is None else kdf.current
        )
        return sealed, sealed
    if args.plain_dir:
        folder = Path(args.plain_dir) if one_app else Path(args.plain_dir) / model.app
        return FileProvider(folder, model), FileDirectory(folder)
    return MemoryProvider(model), ScryptDirectory()


def _lock_folder(args: argparse.Namespace) -> FolderLock | None:
    """The lock on the document folder (D435), taken; ``None`` for documents in memory."""
    folder = args.dir or args.plain_dir
    if not folder:
        return None
    lock = FolderLock(folder)
    try:
        lock.acquire()
    except FolderLocked as exc:
        raise UsageError(str(exc)) from exc
    return lock


def _server_state(args: argparse.Namespace) -> tuple[Path, ServerSettings, AdminDirectory]:
    """What this server remembers between runs: where it lives, its settings and its administrators."""
    state_dir = _state_dir(args)
    settings = load_settings(state_dir, default_max_documents=DEFAULT_MAX_DOCUMENTS)
    admins = AdminDirectory()
    load_admins(state_dir, admins)
    return state_dir, settings, admins


def _bracketed(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def _settings_link(args: argparse.Namespace, certificate: Certificate | None) -> str | None:
    """The address of the settings pages for the banner's link to the setup code (D1372); ``None`` without the web
    app. The first name the server was given (``--allow-host``, then ``--tls-name``) or the address it listens on;
    behind a proxy https and no port, since the proxy's port is not known here."""
    if not args.web:
        return None
    given = [*args.allow_host, *args.tls_name]
    if given:
        host = given[0]
    elif is_unspecified(args.host):
        host = next(iter(machine_names()), LOCALHOST)
    else:
        host = args.host
    if args.behind_proxy:
        return f"https://{_bracketed(host)}/admin"
    scheme = "http" if certificate is None else "https"
    return f"{scheme}://{_bracketed(host)}:{args.port}/admin"


def _admin_options(args: argparse.Namespace) -> AdminOptions:
    if args.admin_password_file and not args.admin:
        raise UsageError("--admin-password-file needs --admin NAME (or CLAUDIA_ADMIN)")
    return AdminOptions(
        reset=args.reset_administrators,
        name=args.admin,
        password_file=Path(args.admin_password_file) if args.admin_password_file else None,
    )


def _administrators(
    args: argparse.Namespace, state_dir: Path, admins: AdminDirectory, certificate: Certificate | None
) -> AdminStart:
    """Reset, name at start and make the setup code (``admin_start.py``); ``UsageError`` for options that fail."""
    try:
        return prepare_administrators(
            state_dir, admins, _admin_options(args), link_base=_settings_link(args, certificate), now=utc_now()
        )
    except ValueError as exc:
        raise UsageError(str(exc)) from exc


def _proxy_hops(args: argparse.Namespace) -> int:
    """How many proxies in front of the server set ``X-Forwarded-For`` (D1275): none without ``--behind-proxy``, one by
    default with it."""
    if not args.behind_proxy:
        return 0
    return 1 if args.proxy_hops is None else args.proxy_hops


def _proxy_banner_lines(args: argparse.Namespace) -> list[str]:
    """Say how people are counted behind a proxy, so that nobody wonders why one wait hits everybody."""
    if not args.behind_proxy:
        return []
    hops = _proxy_hops(args)
    if hops:
        return [f"people are counted by the X-Forwarded-For entry of the nearest of {hops} proxy(ies)"]
    return ["people are counted by the proxy's address (--proxy-hops 0): one wait or cap for everybody"]


def _tls_banner_lines(certificate: Certificate | None, *, behind_proxy: bool) -> list[str]:
    """What the start-up banner says about encryption."""
    if certificate is None:
        return [
            "WARNING: no TLS (--no-tls --behind-proxy): this server does not encrypt, so only a proxy that does "
            "may stand between it and the network"
            if behind_proxy
            else "WARNING: no TLS (--no-tls): connections are not encrypted"
        ]
    origin = (
        "made by this server: browsers warn once, desktop clients ask to trust it"
        if certificate.self_signed_by_us
        else "given with --tls-cert"
    )
    return [f"connections are encrypted (TLS), certificate {origin}", f"  fingerprint {certificate.fingerprint}"]


def _check_places(args: argparse.Namespace) -> None:
    """The folders and files the options name must fit together and exist."""
    if args.web and not (Path(args.web) / "index.html").is_file():
        raise UsageError(f"{args.web} does not contain a built web app (index.html); run `npm run build` in web/")
    if args.dir and args.plain_dir:
        raise UsageError("--dir (sealed documents) and --plain-dir (plain files) cannot be used together")


def _suite(
    args: argparse.Namespace,
    models: list[type[DocumentModel]],
    one_app: bool,
    *,
    library: ShapeLibrary | None,
    assistants: dict[str, Callable[[], Assistant] | None],
    hub_options: dict[str, Any],
    kdf: KdfPolicy | None = None,
) -> Suite:
    """The server's apps (D430): for each document model its store, its methods, its assistant and its hub."""
    modules = []
    for model in models:
        provider, directory = _storage(args, model, one_app, kdf)
        methods = methods_for(model, shapes=library)
        hub = Hub(provider, methods=methods, assistant=assistants[model.app], **hub_options)
        modules.append(Module(hub, directory))
    return Suite(modules, max_documents=hub_options["max_documents"])


def _kdf_policy(args: argparse.Namespace, settings: ServerSettings) -> KdfPolicy | None:
    """What hashing costs for new sealed documents, measured once the server runs (D1267); none for documents that are
    not sealed."""
    return KdfPolicy(settings.security.kdf_target_seconds) if args.dir else None


def _kdf_banner_lines(kdf: KdfPolicy | None) -> list[str]:
    """What the start-up banner says about the hashing of new documents."""
    if kdf is None:
        return []
    seconds = kdf.describe()["target_seconds"]
    return [
        f"password hashing for new documents: measured at start, about {seconds:g} s each"
        " (Server settings > Security); existing documents keep theirs"
    ]


def _storage_banner_line(args: argparse.Namespace, one_app: bool) -> str:
    """What the start-up banner says about where the documents are kept."""
    if args.dir:
        where = args.dir if one_app else f"{args.dir}, one folder per app,"
        return f"documents are kept in {where} each sealed (encrypted) by its people's passwords"
    if args.plain_dir:
        return f"documents and users are kept in {args.plain_dir} (NOT encrypted: use --dir for sealed documents)"
    return "documents are kept in memory and are gone when the server stops (use --dir DIR to keep them)"


def make_plan(argv: list[str] | None = None) -> Plan:
    """Read the command line and prepare the server; ``UsageError`` if it cannot be started as asked."""
    args = build_parser().parse_args(argv)
    if not 0 < args.port < 65536 or args.max_connections < 1:
        raise UsageError("--port must be 1-65535 and --max-connections at least 1")
    _check_caps(args)
    models, one_app = _models(args)
    certificate, tls_options = _tls(args)
    hosts = _hosts(args)
    state_dir, settings, admins = _server_state(args)
    secret = _access_secret(args, settings)
    _check_places(args)
    limits = Limits()
    library = _shapes(args, models)
    fonts = _fonts(args, state_dir)
    hyphenation = _hyphenation(args, state_dir)
    assistants, ai = _build_assistant(args, models, settings)
    renderings, rendering_lines = _renderings(settings, state_dir, fonts)
    lock = _lock_folder(args)  # before any store touches the folder
    administrators = _administrators(args, state_dir, admins, certificate)  # before anybody can reach the server
    hub_options = {
        "limits": limits,
        "allow_create": not args.no_create,
        "max_documents": args.max_documents if args.max_documents is not None else settings.max_documents,
        "max_connections": args.max_connections,
        "renderings": renderings,
        "font_catalogue": lambda: fonts.catalogue,
    }
    kdf = _kdf_policy(args, settings)
    suite = _suite(args, models, one_app, library=library, assistants=assistants, hub_options=hub_options, kdf=kdf)
    idle = IdleWatch(args.exit_when_idle) if args.exit_when_idle else None
    exposed = is_exposed(args.host, behind_proxy=args.behind_proxy)
    admin = AdminContext(
        admins=admins,
        sessions=AdminSessions(),
        settings=settings,
        state_dir=state_dir,
        ai=ai,
        exposed=exposed,
        fonts=fonts,
        kdf=kdf,
        setup_code=administrators.code,
        reset_note=administrators.reset,
    )
    app = create_app(
        suite,
        allowed_origins=args.allow_origin,
        allowed_hosts=hosts.names,
        access_secret=secret,
        max_waiting=args.max_waiting,
        max_waiting_per_address=args.max_waiting_per_address,
        proxy_hops=_proxy_hops(args),
        web_dir=args.web,
        list_documents=not args.no_list,
        admin=admin,
        fonts=fonts,
        hyphenation=hyphenation,
        idle=idle,
    )
    scheme, ws_scheme = ("http", "ws") if certificate is None else ("https", "wss")
    banner = [
        f"serving {', '.join(suite.apps)} on {ws_scheme}://{args.host}:{args.port}/api/<app>/docs/<id>/ws",
    ]
    banner += _tls_banner_lines(certificate, behind_proxy=args.behind_proxy)
    banner += _proxy_banner_lines(args)
    banner.append(f"answers to {', '.join(hosts.names)} and IP addresses; more names with --allow-host NAME")
    if secret:
        banner.append("access secret set: making documents and reading the list need it")
    banner += administrators.banner
    banner.append(
        f"web app: {scheme}://{args.host}:{args.port}/ (from {args.web})"
        if args.web
        else f"no web app: {scheme}://{args.host}:{args.port}/ explains how to build and serve it"
    )
    banner.append(_storage_banner_line(args, one_app))
    banner += _kdf_banner_lines(kdf)
    banner.append(fonts.summary())
    banner += [f"  not used, {problem.path}: {problem.reason}" for problem in fonts.catalogue.problems]
    banner += rendering_lines
    banner.append(hyphenation.summary())
    banner += [f"  not used, {problem}" for problem in hyphenation.problems if hyphenation.languages]
    banner += _what_is_loaded(library, ai.desk)
    if idle is not None:
        banner.append(f"stops once nothing has used it for {args.exit_when_idle:g} seconds (--exit-when-idle)")
    options = {
        "host": args.host,
        "port": args.port,
        "ws_max_size": limits.max_message_bytes,
        "log_level": "info",
        **tls_options,
    }

    closers = [ai.desk.close] if lock is None else [ai.desk.close, lock.release]
    return Plan(app, options, banner, args.redirect_port, closers, idle, kdf)


def main(argv: list[str] | None = None) -> int:
    """Start the server; the exit status of the process."""
    try:
        plan = make_plan(argv)
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # a folder or file the server may not read, a state folder it may not write
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if plan.redirect_from is not None:
        try:
            redirect.start(plan.uvicorn_options["host"], plan.redirect_from, plan.uvicorn_options["port"])
        except OSError as exc:
            print(f"error: cannot listen for the redirect: {exc}", file=sys.stderr)
            return 2
    import uvicorn

    plan.start()
    for line in plan.banner:
        print(line, flush=True)
    server = uvicorn.Server(uvicorn.Config(plan.app, **plan.uvicorn_options))
    if plan.idle is not None:
        plan.idle.on_idle = lambda: setattr(server, "should_exit", True)  # as Ctrl+C does: documents are packed
    try:
        server.run()
    finally:
        plan.close()
    return 0
