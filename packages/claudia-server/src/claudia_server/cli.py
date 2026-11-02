"""Command line of the server: ``python3 -m claudia_server``.

Local use (the default) binds to 127.0.0.1:

    python3 -m claudia_server

Secure by default: the connection is encrypted (https:// and wss://). The server makes itself a certificate the first
time (browsers warn about it once; the desktop client asks the person to trust its fingerprint, which is printed at
start-up), or it is given one:

    python3 -m claudia_server --tls-cert fullchain.pem --tls-key privkey.pem
    python3 -m claudia_server --tls-name claudia.example.org      # the name people will type
    python3 -m claudia_server --no-tls                           # behind a TLS-terminating proxy, say

The web app (built in ``web/``) is served from the same address with ``--web``. A page served from another origin (the
Nuxt dev server on :3000, say) must be named with ``--allow-origin``. Documents live in memory unless ``--dir`` names
a folder: there every document is a sealed (encrypted) file that only its people can open. ``--plain-dir`` keeps the
old unencrypted store of the early demos; it has to be asked for by name.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__, redirect
from .app import create_app
from .apps import methods_for, stand_in_assistant_for
from .auth import ScryptDirectory, UserDirectory
from .certs import Certificate, CertificateError, ensure_certificate
from .filestore import FileDirectory, FileProvider
from .hub import DocumentProvider, Hub, MemoryProvider
from .protocol import Limits
from .sealed import SealedDocuments

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
    parser.add_argument("--no-list", action="store_true", help="do not serve the list of documents (/api/docs)")
    parser.add_argument(
        "--no-assistant", action="store_true", help="do not give workbooks the scripted stand-in for the AI"
    )
    parser.add_argument("--allow-origin", action="append", default=[], metavar="ORIGIN")
    parser.add_argument("--no-create", action="store_true", help="documents cannot be created over the network")
    parser.add_argument("--max-connections", type=int, default=200)
    parser.add_argument("--state-dir", help="where the server keeps its certificate (default: a per-user folder)")
    tls = parser.add_argument_group("encryption")
    tls.add_argument("--no-tls", action="store_true", help="do not encrypt (use behind a TLS proxy)")
    tls.add_argument("--tls-cert", metavar="FILE")
    tls.add_argument("--tls-key", metavar="FILE")
    tls.add_argument(
        "--tls-name", action="append", default=[], metavar="NAME", help="a name the certificate must cover"
    )
    tls.add_argument("--redirect-port", type=int, metavar="PORT", help="a plain-HTTP port that sends people to https")
    return parser


def load_model(spec: str) -> type:
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
    if args.no_tls:
        if args.redirect_port:
            raise UsageError("--redirect-port needs TLS (there is nothing to redirect to with --no-tls)")
        return None, {}
    try:
        certificate = ensure_certificate(args.state_dir, tuple(args.tls_name), args.tls_cert, args.tls_key)
    except CertificateError as exc:
        raise UsageError(str(exc)) from exc
    return certificate, {"ssl_certfile": str(certificate.cert_file), "ssl_keyfile": str(certificate.key_file)}


def make_plan(argv: list[str] | None = None) -> Plan:
    """Read the command line and prepare the server; ``UsageError`` if it cannot be started as asked."""
    args = build_parser().parse_args(argv)
    if not 0 < args.port < 65536 or args.max_connections < 1:
        raise UsageError("--port must be 1-65535 and --max-connections at least 1")
    model = load_model(args.model)
    certificate, tls_options = _tls(args)
    if args.web and not (Path(args.web) / "index.html").is_file():
        raise UsageError(f"{args.web} does not contain a built web app (index.html); run `npm run build` in web/")
    if args.dir and args.plain_dir:
        raise UsageError("--dir (sealed documents) and --plain-dir (plain files) cannot be used together")
    limits = Limits()
    provider: DocumentProvider
    directory: UserDirectory
    if args.dir:
        sealed = SealedDocuments(args.dir, model)
        provider, directory = sealed, sealed
    elif args.plain_dir:
        provider, directory = FileProvider(args.plain_dir, model), FileDirectory(args.plain_dir)
    else:
        provider, directory = MemoryProvider(model), ScryptDirectory()
    hub = Hub(
        provider,
        methods=methods_for(model),
        assistant=None if args.no_assistant else stand_in_assistant_for(model),
        limits=limits,
        allow_create=not args.no_create,
        max_connections=args.max_connections,
    )
    app = create_app(
        hub, directory, allowed_origins=args.allow_origin, web_dir=args.web, list_documents=not args.no_list
    )
    scheme = "http" if certificate is None else "https"
    ws_scheme = "ws" if certificate is None else "wss"
    banner = [f"serving on {ws_scheme}://{args.host}:{args.port}/api/docs/<id>/ws"]
    if certificate is None:
        banner.append("WARNING: no TLS (--no-tls): connections are not encrypted")
    else:
        origin = (
            "made by this server: browsers warn once, desktop clients ask to trust it"
            if (certificate.self_signed_by_us)
            else "given with --tls-cert"
        )
        banner += [f"connections are encrypted (TLS), certificate {origin}", f"  fingerprint {certificate.fingerprint}"]
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
    options = {
        "host": args.host,
        "port": args.port,
        "ws_max_size": limits.max_message_bytes,
        "log_level": "info",
        **tls_options,
    }
    return Plan(app, options, banner, args.redirect_port)


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
    uvicorn.run(plan.app, **plan.uvicorn_options)
    return 0
