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
(``admin.py``): on an address beyond this computer, the first person to open the settings pages names its
administrator, and after that administrators manage it (and each other) from there, at ``/api/admin/*``. What they
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
from claudia_creates import ShapeLibrary
from claudia_render import RenderService, ToolRegistry, builtin_registry

from . import __version__, redirect
from .admin import AdminDirectory, needs_administrator
from .admin_api import AdminContext, AiRuntime
from .admin_sessions import AdminSessions
from .app import DEFAULT_MAX_WAITING, DEFAULT_MAX_WAITING_PER_ADDRESS, MIN_ACCESS_SECRET, create_app
from .apps import methods_for, model_assistant_for, stand_in_assistant_for
from .assistant import Assistant
from .auth import ScryptDirectory, UserDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .filestore import FileDirectory, FileProvider
from .fonts import FontService
from .hosts import AllowedHosts, is_loopback, machine_names
from .hub import DEFAULT_MAX_DOCUMENTS, DocumentProvider, Hub, MemoryProvider
from .hyphenation import HyphenationService
from .protocol import Limits
from .rasterise import svg_rasteriser
from .rendered import RenderDesk
from .sealed import SealedDocuments
from .server_settings import ServerSettings, load_admins, load_settings
from .state import default_state_dir

DEFAULT_MODEL = "claudia_computes.model:WorkbookModel"


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

    def close(self) -> None:
        """Stop what the server started besides itself (the language model's worker)."""
        for close in self.closers:
            close()


def build_parser() -> argparse.ArgumentParser:
    """The options of the command line."""
    parser = argparse.ArgumentParser(prog="python3 -m claudia_server", description="Run a Claudia server.")
    parser.add_argument("--version", action="version", version=f"claudia-server {__version__}")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="the document model, as module:Class")
    parser.add_argument(
        "--dir",
        metavar="DIR",
        help="keep documents in DIR as sealed (encrypted) files (default: in memory, lost on exit)",
    )
    parser.add_argument(
        "--plain-dir",
        metavar="DIR",
        help="keep documents and users in DIR as plain files, NOT encrypted (the store of the early demos)",
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
        help="font collections to hand to clients for layout and PDF export (/api/fonts): a collection folder or a "
        "folder of them; repeatable. Default: STATE_DIR/fonts if it exists. "
        "Fill one with python -m claudia_fonts fetch",
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
    tls = parser.add_argument_group("encryption")
    tls.add_argument("--no-tls", action="store_true", help="do not encrypt (only for this computer, or behind a proxy)")
    tls.add_argument(
        "--behind-proxy",
        action="store_true",
        help="with --no-tls: a proxy in front of this server encrypts the traffic; needed to listen on any address "
        "other than this computer's",
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


def _shapes(args: argparse.Namespace, model: type[DocumentModel]) -> ShapeLibrary | None:
    """The shape library of a presentation server (``None`` for the other apps, which have no shapes)."""
    if model.app != "creates":
        if args.shapes:
            raise UsageError("--shapes: only servers of presentations use shapes")
        return None
    for folder in args.shapes:
        if not Path(folder).is_dir():
            raise UsageError(f"--shapes: {folder} is not a folder")
    return ShapeLibrary.load([Path(folder) for folder in args.shapes])


def _fonts(args: argparse.Namespace, state_dir: Path) -> FontService:
    """The fonts this server hands to its clients: the folders of ``--fonts``, else ``STATE_DIR/fonts`` if there is
    one. ``UsageError`` for a folder given on the command line that does not exist."""
    for folder in args.fonts:
        if not Path(folder).is_dir():
            raise UsageError(f"--fonts: {folder} is not a folder")
    folders = [Path(f) for f in args.fonts] or [state_dir / "fonts"]
    return FontService.from_folders(folders, state_dir / "webfonts")


def _program_of(entry: object) -> str | None:
    """The path of a tool entry, which is a path or a mapping with one."""
    return entry.get("path") if isinstance(entry, dict) else entry  # type: ignore[return-value]


def _renderings(settings: ServerSettings, state_dir: Path, fonts: FontService) -> tuple[RenderDesk, list[str]]:
    """What makes rendered containers (D395): the built-in types, the manifests of the plugins folder and the tools the
    administrator registered (the LaTeX programs are those of the typeset settings). The lines are for the start-up
    report: what is offered, and each manifest that could not be taken, with the reason."""
    work = state_dir / "render"
    registry = builtin_registry(fonts.catalogue, work / "plugins")
    folder = Path(settings.render.plugins_dir) if settings.render.plugins_dir else state_dir / "plugins"
    reports = registry.load_directory(folder, work / "plugins")
    tools: dict[str, object] = {"xelatex": settings.typeset.xelatex, "pdftocairo": settings.typeset.pdftocairo}
    tools.update(settings.render.tools)
    service = RenderService(registry, ToolRegistry({k: v for k, v in tools.items() if v is not None}), work)
    lines = ["rendered containers: " + ", ".join(plugin.manifest.type for plugin in registry.plugins())]
    lines += [f"  not used, {folder.name}/{r.file}: {r.error}" for r in reports if r.error]
    draw = svg_rasteriser(_program_of(tools.get("rsvg_convert")))
    lines.append(
        "office files draw rendered containers as pictures"
        if draw
        else "office files get rendered containers as SVG only (no rsvg-convert; help topic render.configure-tools)"
    )
    return RenderDesk(service, draw), lines


def _hyphenation(args: argparse.Namespace, state_dir: Path) -> HyphenationService:
    """The hyphenation patterns this server hands to its clients: from ``--hyphenation``, else
    ``STATE_DIR/hyphenation``. ``UsageError`` for a folder given on the command line that does not exist."""
    if args.hyphenation and not Path(args.hyphenation).is_dir():
        raise UsageError(f"--hyphenation: {args.hyphenation} is not a folder")
    return HyphenationService.from_folder(Path(args.hyphenation) if args.hyphenation else state_dir / "hyphenation")


def _what_is_loaded(library: ShapeLibrary | None, runner: ModelRunner | None) -> list[str]:
    """The lines of the start-up report about the shapes (and the files skipped) and the AI model."""
    lines: list[str] = []
    if library is not None:
        lines.append("shapes: " + ", ".join(shape.id for shape in library))
        lines += [f"  not used, {name}: {message}" for name, message in library.problems]
    if runner is not None:
        lines.append(f'AI assistant: user "ai", model {runner.name}')
    return lines


def _load_runner(model_dir: str, device: str, max_tokens: int, timeout: float) -> ModelRunner:
    """Load the model of ``model_dir`` onto ``device``. ``UsageError`` if it cannot be loaded."""
    print(f"loading the AI model from {model_dir} on {device} (this can take a while) ...", flush=True)
    try:
        return ModelRunner(OpenVinoModel(model_dir, device), max_new_tokens=max_tokens, timeout=timeout)
    except ModelError as exc:
        raise UsageError(f"--ai: {exc}") from exc


def _build_assistant(
    args: argparse.Namespace, model: type[DocumentModel], settings: ServerSettings
) -> tuple[Callable[[], Assistant] | None, AiRuntime]:
    """The assistant factory to start with, and the ``AiRuntime`` the admin API changes it through afterwards.

    ``--ai`` is an operator override (see the module docstring on precedence): given, it is used exactly as before
    this existed, and the saved AI settings are not even consulted. Without it, the settings last saved through the
    settings pages are used instead (if any), so that a model chosen there survives a restart; with neither, a
    document gets the scripted stand-in, unless ``--no-assistant`` says it gets nothing — an operator's own
    decision that the settings pages must not be able to undo (``AiRuntime.enabled``)."""
    enabled = not args.no_assistant
    if args.ai:
        if args.no_assistant:
            raise UsageError("--ai and --no-assistant contradict each other")
        if args.ai_max_tokens < 1 or args.ai_timeout <= 0:
            raise UsageError("--ai-max-tokens and --ai-timeout must be positive")
        runner = _load_runner(args.ai, args.ai_device, args.ai_max_tokens, args.ai_timeout)
        factory = model_assistant_for(model, runner)
        if factory is None:
            runner.close()
            raise UsageError("--ai: the AI assistant does not know documents of this kind yet")
        return factory, AiRuntime(model=model, enabled=enabled, runner=runner)
    model_dir = settings.ai.model_dir
    if enabled and model_dir:
        ai = settings.ai
        try:
            runner = _load_runner(model_dir, ai.device, ai.max_tokens, ai.timeout)
        except UsageError as exc:
            print(f"warning: the AI model saved in the server settings could not be loaded: {exc}", file=sys.stderr)
            print("starting without it; open the server settings to fix or change it", file=sys.stderr)
        else:
            factory = model_assistant_for(model, runner)
            if factory is not None:
                return factory, AiRuntime(model=model, enabled=enabled, runner=runner)
            runner.close()  # the saved model_dir does not match this server's document model any more
    return (stand_in_assistant_for(model) if enabled else None), AiRuntime(model=model, enabled=enabled)


def _storage(args: argparse.Namespace, model: type[DocumentModel]) -> tuple[DocumentProvider, UserDirectory]:
    """Where documents (and, for ``--plain-dir``, their own users) live: sealed files, plain files, or memory."""
    if args.dir:
        sealed = SealedDocuments(args.dir, model)
        return sealed, sealed
    if args.plain_dir:
        return FileProvider(args.plain_dir, model), FileDirectory(args.plain_dir)
    return MemoryProvider(model), ScryptDirectory()


def _server_state(args: argparse.Namespace) -> tuple[Path, ServerSettings, AdminDirectory]:
    """What this server remembers between runs: where it lives, its settings and its administrators."""
    state_dir = _state_dir(args)
    settings = load_settings(state_dir, default_max_documents=DEFAULT_MAX_DOCUMENTS)
    admins = AdminDirectory()
    load_admins(state_dir, admins)
    return state_dir, settings, admins


def _administrator_banner_line(admins: AdminDirectory, exposed: bool) -> str | None:
    """Who may configure this server, for the start-up banner; ``None`` on loopback, where nobody needs to be one."""
    if admins:
        return f"administrators: {', '.join(a.name for a in admins.list_admins())}"
    if needs_administrator(exposed, len(admins)):
        return "no administrator yet: open the server settings on this address to name one (/api/admin)"
    return None


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


def make_plan(argv: list[str] | None = None) -> Plan:
    """Read the command line and prepare the server; ``UsageError`` if it cannot be started as asked."""
    args = build_parser().parse_args(argv)
    if not 0 < args.port < 65536 or args.max_connections < 1:
        raise UsageError("--port must be 1-65535 and --max-connections at least 1")
    _check_caps(args)
    model = load_model(args.model)
    certificate, tls_options = _tls(args)
    hosts = _hosts(args)
    state_dir, settings, admins = _server_state(args)
    secret = _access_secret(args, settings)
    max_documents = args.max_documents if args.max_documents is not None else settings.max_documents
    _check_places(args)
    limits = Limits()
    provider, directory = _storage(args, model)
    assistant, ai = _build_assistant(args, model, settings)
    library = _shapes(args, model)
    fonts = _fonts(args, state_dir)
    hyphenation = _hyphenation(args, state_dir)
    renderings, rendering_lines = _renderings(settings, state_dir, fonts)
    hub = Hub(
        provider,
        methods=methods_for(model, shapes=library),
        assistant=assistant,
        limits=limits,
        allow_create=not args.no_create,
        max_documents=max_documents,
        max_connections=args.max_connections,
        renderings=renderings,
    )
    exposed = not is_loopback(args.host)
    admin = AdminContext(
        admins=admins, sessions=AdminSessions(), settings=settings, state_dir=state_dir, ai=ai, exposed=exposed
    )
    app = create_app(
        hub,
        directory,
        allowed_origins=args.allow_origin,
        allowed_hosts=hosts.names,
        access_secret=secret,
        max_waiting=args.max_waiting,
        max_waiting_per_address=args.max_waiting_per_address,
        web_dir=args.web,
        list_documents=not args.no_list,
        admin=admin,
        fonts=fonts,
        hyphenation=hyphenation,
    )
    scheme = "http" if certificate is None else "https"
    ws_scheme = "ws" if certificate is None else "wss"
    banner = [f"serving on {ws_scheme}://{args.host}:{args.port}/api/docs/<id>/ws"]
    banner += _tls_banner_lines(certificate, behind_proxy=args.behind_proxy)
    banner.append(f"answers to {', '.join(hosts.names)} and IP addresses; more names with --allow-host NAME")
    if secret:
        banner.append("access secret set: making documents and reading the list need it")
    if (admin_line := _administrator_banner_line(admins, exposed)) is not None:
        banner.append(admin_line)
    banner.append(
        f"web app: {scheme}://{args.host}:{args.port}/ (from {args.web})"
        if args.web
        else f"no web app: {scheme}://{args.host}:{args.port}/ explains how to build and serve it"
    )
    if args.dir:
        banner.append(f"documents are kept in {args.dir}, each sealed (encrypted) by its people's passwords")
    elif args.plain_dir:
        banner.append(
            f"documents and users are kept in {args.plain_dir} (NOT encrypted: use --dir for sealed documents)"
        )
    else:
        banner.append("documents are kept in memory and are gone when the server stops (use --dir DIR to keep them)")
    banner.append(fonts.summary())
    banner += [f"  not used, {problem.path}: {problem.reason}" for problem in fonts.catalogue.problems]
    banner += rendering_lines
    banner.append(hyphenation.summary())
    banner += [f"  not used, {problem}" for problem in hyphenation.problems if hyphenation.languages]
    banner += _what_is_loaded(library, ai.runner)
    options = {
        "host": args.host,
        "port": args.port,
        "ws_max_size": limits.max_message_bytes,
        "log_level": "info",
        **tls_options,
    }

    # a closure, not ai.runner.close itself: the settings pages may swap it for another one while the server runs
    # (AiRuntime.apply, which closes whatever it replaces), and it is the one running when the server stops that
    # must be closed then, not the one that happened to be running at start-up.
    def _close_ai() -> None:
        if ai.runner is not None:
            ai.runner.close()

    return Plan(app, options, banner, args.redirect_port, [_close_ai])


def main(argv: list[str] | None = None) -> int:
    """Start the server; the exit status of the process."""
    try:
        plan = make_plan(argv)
        if plan.redirect_from is not None:
            redirect.start(plan.uvicorn_options["host"], plan.redirect_from, plan.uvicorn_options["port"])
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot listen for the redirect: {exc}", file=sys.stderr)
        return 2
    import uvicorn

    for line in plan.banner:
        print(line, flush=True)
    try:
        uvicorn.run(plan.app, **plan.uvicorn_options)
    finally:
        plan.close()
    return 0
