"""Start the Claudia demo: build the web app if needed, run the server(s), open the browser.

    ./start.sh                  # computes (tables) at http://127.0.0.1:8765/
    ./start.sh composes         # composes (text) at port 8765
    ./start.sh creates          # creates (presentations) at port 8765
    ./start.sh all              # all three at once: computes 8765, composes 8766, creates 8767
    ./start.sh all --dir ~/claudia-data --port 9000 --no-browser
    ./start.sh --rebuild        # build the web app again first
    ./start.sh --tls            # encrypt (the browser warns once about the own certificate)
    ./start.sh all --ai         # the AI user answers with the language model in ai-models/ (computes)
    ./start.sh --ai ~/models/qwen2.5-7b-instruct-int4-ov --ai-device CPU

``./start.sh`` is ``start.cmd`` on Windows. ``--app composes`` is the same as the word ``composes``.
One server serves one app, so ``all`` runs three servers side by side; each prints how to find it in the browser.

Where things are kept: one folder per checkout, ``.claudia/`` (or ``--dir DIR``), and in it one folder per app with the
app's sealed documents and its server's own state (certificate, administrators, settings)::

    .claudia/computes/documents   .claudia/computes/state
    .claudia/composes/documents   .claudia/composes/state
    .claudia/creates/documents    .claudia/creates/state
    .claudia/fonts                the fonts every app hands to its clients for print and PDF (fetched once)

``--dir DIR`` means the same for one app and for ``all``: ``DIR/<app>/documents``. The installed desktop apps keep
theirs elsewhere, in the system's place for user data, so a development checkout never touches them. Folders that
earlier versions of this script used (``docs-<app>``, ``demo-docs*``) are reported at start, never moved.

The wrappers ``start.sh`` (Linux, macOS) and ``start.cmd`` (Windows) call this through ``uv``. Only the standard
library is used here, so it also runs with a plain ``python3``.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import ipaddress
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
#: Where a checkout keeps its documents and its servers' state, one folder per app (ignored by git).
DATA = ROOT / ".claudia"
#: Where earlier versions of this script kept each app's documents, newest first (``demo-docs*`` until 2938f0a).
LEGACY = {
    "computes": ("docs-computes", "demo-docs"),
    "composes": ("docs-composes", "demo-docs-composes"),
    "creates": ("docs-creates", "demo-docs-creates"),
}
BUILT = WEB / ".output" / "public"
# The server's default model is the workbook.
MODELS = {"computes": "", "composes": "claudia_composes:TextModel", "creates": "claudia_creates:SlideModel"}
WAIT_SECONDS = 30.0
APPS = tuple(MODELS)
#: Where ``--ai`` without a folder looks for a model: one folder per model, converted for OpenVINO (ignored by git).
MODELS_DIR = ROOT / "ai-models"
#: The apps whose server can answer with a language model: an app needs a lens for that (``claudia_server.apps``).
#: composes keeps its scripted stand-in and is not given the model. Each server loads a copy of its own (one AI server
#: for all apps, D2, is not built yet), so ``all --ai`` needs the memory of the model twice.
AI_APPS = ("computes", "creates")
#: Loading a model of several GB before the server listens takes minutes on a slow disk, not seconds.
AI_WAIT_SECONDS = 900.0
#: How a model folder is made, for the message when there is none.
CONVERT_HINT = (
    "convert one with `optimum-cli export openvino --model Qwen/Qwen2.5-7B-Instruct --weight-format int4 "
    "ai-models/qwen2.5-7b-instruct-int4-ov`, or download one of huggingface.co/OpenVINO into ai-models/"
)
#: What installs OpenVINO GenAI into the environment the servers run in, without removing anything else.
INSTALL_OPENVINO = ("sync", "--locked", "--inexact", "--package", "claudia-server", "--extra", "openvino")
# What a person does in the browser, per app.
WHAT_TO_DO = {
    "computes": "tables: sheets, cells, formulas",
    "composes": "text: paragraphs, styles, suggestions",
    "creates": "presentations: slides, text boxes, shapes",
}


def is_this_computer(host: str) -> bool:
    """Does ``host``, an address to listen on, mean this computer only? (The same rule as ``claudia_server.hosts``,
    repeated here because this script runs with a plain ``python3``, without the packages.)"""
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return host.lower().rstrip(".") == "localhost"


@dataclass(frozen=True)
class AppServer:
    """One server of one app: where it listens, where its documents are and how it is started."""

    app: str
    port: int
    dir: str  # the sealed documents
    state: str  # the server's own state: certificate, administrators, settings
    url: str
    args: argparse.Namespace


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """The options of the launcher. ``args.app`` is one app or ``all``."""
    parser = argparse.ArgumentParser(description="Start the Claudia server and open it in the browser.")
    parser.add_argument(
        "which",
        nargs="?",
        choices=[*APPS, "all"],
        metavar="{" + ",".join([*APPS, "all"]) + "}",
        help="which app to serve (default: computes); all starts one server for each app, on consecutive ports",
    )
    parser.add_argument("--app", choices=[*APPS, "all"], help="the same as the word above")
    parser.add_argument(
        "--dir",
        help="where documents and server state are kept: DIR/<app>/documents and DIR/<app>/state (default: .claudia)",
    )
    parser.add_argument(
        "--shapes", action="append", default=[], metavar="DIR", help="creates: more shapes (JSON files); repeatable"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="the port (with all: the first of three)")
    parser.add_argument("--tls", action="store_true", help="encrypt the connection (default: plain, localhost only)")
    parser.add_argument("--rebuild", action="store_true", help="build the web app again before starting")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ai = parser.add_argument_group("AI model (computes and creates; composes keeps the scripted stand-in)")
    ai.add_argument(
        "--ai",
        nargs="?",
        const="",
        metavar="MODEL_DIR",
        help="the AI user answers with the language model in MODEL_DIR (converted for OpenVINO); without "
        "MODEL_DIR, the one model folder in ai-models/. OpenVINO GenAI is installed the first time",
    )
    ai.add_argument(
        "--ai-device", choices=("GPU", "CPU", "NPU", "AUTO"), help="where the model runs (the server's default: GPU)"
    )
    args = parser.parse_args(argv)
    if not (args.tls or is_this_computer(args.host)):
        parser.error(
            f"--host {args.host} can be reached from the network, and a plain connection would send passwords in "
            "clear text: add --tls"
        )
    args.app = args.which or args.app or "computes"
    args.root = str(DATA if args.dir is None else Path(args.dir).expanduser())
    if args.app != "all":
        args.documents, args.state = folders(args.root, args.app)
    if args.ai_device and args.ai is None:
        parser.error("--ai-device names where the model of --ai runs: add --ai")
    if args.ai is not None:
        if args.app not in (*AI_APPS, "all"):
            parser.error(f"--ai: only {', '.join(AI_APPS)} can answer with a language model so far")
        if not args.ai:
            try:
                args.ai = str(find_model())
            except LookupError as problem:
                parser.error(str(problem))
    return args


def folders(root: str | Path, app: str) -> tuple[str, str]:
    """Where the server of ``app`` keeps its documents and its own state, under ``root``. One app's server never sees
    another's documents, and no two servers share a certificate or administrators."""
    base = Path(root) / app
    return str(base / "documents"), str(base / "state")


def legacy_folders(app: str, root: Path = ROOT) -> list[Path]:
    """Folders of ``app``'s documents left by earlier versions of this script that still hold something."""
    return [root / name for name in LEGACY[app] if (root / name).is_dir() and any((root / name).iterdir())]


def find_model(folder: Path | None = None) -> Path:
    """The one model in ``folder`` (``ai-models/``): a folder of its own holding ``openvino_model.xml``.
    ``LookupError``, saying what to do, when there is none or more than one."""
    folder = MODELS_DIR if folder is None else folder
    found = sorted(p for p in folder.glob("*/") if (p / "openvino_model.xml").is_file()) if folder.is_dir() else []
    if not found:
        raise LookupError(f"--ai: there is no model in {folder}; {CONVERT_HINT}, or name a folder: --ai MODEL_DIR")
    if len(found) > 1:
        names = ", ".join(p.name for p in found)
        raise LookupError(f"--ai: {folder} holds more than one model ({names}); name one: --ai MODEL_DIR")
    return found[0]


def app_servers(args: argparse.Namespace) -> list[AppServer]:
    """The servers to run for these options: one for an app, one per app (consecutive ports) for ``all``."""
    if args.app != "all":
        return [AppServer(args.app, args.port, args.documents, args.state, page_url(args), args)]
    servers = []
    for offset, app in enumerate(APPS):
        own = copy.copy(args)
        own.app, own.port = app, args.port + offset
        own.ai = args.ai if app in AI_APPS else None
        own.documents, own.state = folders(args.root, app)
        servers.append(AppServer(app, own.port, own.documents, own.state, page_url(own), own))
    return servers


def needs_build(args: argparse.Namespace, built: Path = BUILT) -> bool:
    """Must the web app be built before the server can serve it?"""
    return args.rebuild or not (built / "index.html").exists()


def server_command(args: argparse.Namespace, python: str = sys.executable, built: Path = BUILT) -> list[str]:
    """The command line that runs the server for these options."""
    # `--web` stays forward-slash even on Windows (Path.as_posix(), not str()): it is echoed back by callers and
    # compared verbatim, and the OS itself accepts either separator when the server opens files under it.
    command = [python, "-m", "claudia_server", "--dir", str(args.documents), "--state-dir", str(args.state)]
    command += ["--web", Path(built).as_posix()]
    command += ["--host", args.host, "--port", str(args.port)]
    command += ["--fonts", fonts_folder(args.root).as_posix()]
    if MODELS[args.app]:
        command += ["--model", MODELS[args.app]]
    for folder in args.shapes:
        command += ["--shapes", folder]
    if not args.tls:
        command.append("--no-tls")
    if getattr(args, "ai", None):
        command += ["--ai", args.ai]
        if args.ai_device:
            command += ["--ai-device", args.ai_device]
    return command


def fonts_folder(root: str | Path) -> Path:
    """The fonts all the servers of a checkout share: ``ROOT/fonts`` (D905)."""
    return Path(root) / "fonts"


def ensure_fonts(root: str | Path, fetch=None) -> bool:
    """Fetch the starter set of open fonts into :func:`fonts_folder` once, the first time it is missing; print preview
    and PDF export lay out with them (D901, D905). A failed fetch (no network) is reported and the servers start
    anyway, with whatever fonts are there. ``True`` when the folder holds fonts afterwards."""
    from claudia_fonts import FetchError, collection_folders
    from claudia_fonts import fetch as fetch_starter

    folder = fonts_folder(root)
    if collection_folders(folder):
        return True
    print(f"Fetching the starter fonts into {folder} (once; about 6 MB) …", flush=True)
    try:
        (fetch or fetch_starter)(folder)
    except (FetchError, OSError) as problem:
        print(
            f"Could not fetch the fonts ({problem}); print preview needs them. Try again later, or run "
            f"`uv run python -m claudia_fonts fetch {folder}`.",
            flush=True,
        )
        return False
    return True


def page_url(args: argparse.Namespace) -> str:
    """The address to open in the browser."""
    return f"{'https' if args.tls else 'http'}://{args.host}:{args.port}/"


def build_web() -> None:
    """Install the web dependencies if needed and build the web app. Exits with a message if npm is missing."""
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("The web app is not built yet and npm was not found. Install Node.js (22 or newer), then run again.")
    if not (WEB / "node_modules").exists():
        print("Installing the web dependencies (once)…")
        subprocess.run([npm, "ci"], cwd=WEB, check=True)
    print("Building the web app…")
    subprocess.run([npm, "run", "build"], cwd=WEB, check=True)


def has_openvino() -> bool:
    """Can the servers' interpreter (this one) load the language model?"""
    return importlib.util.find_spec("openvino_genai") is not None


def install_openvino() -> None:
    """Add OpenVINO GenAI to the environment with ``uv``, keeping everything else. Exits with a message if uv is
    missing. (A later plain ``uv sync`` removes it again; the next ``--ai`` puts it back.)"""
    uv = shutil.which("uv")
    if uv is None:
        command = " ".join(("uv", *INSTALL_OPENVINO))
        sys.exit(f"--ai needs OpenVINO GenAI, which is not installed, and uv was not found to install it: {command}")
    print("Installing OpenVINO GenAI for the AI model (once)…")
    subprocess.run([uv, *INSTALL_OPENVINO], cwd=ROOT, check=True)


def wait_for_port(host: str, port: int, server: subprocess.Popen, seconds: float = WAIT_SECONDS) -> bool:
    """Wait until something listens on ``host:port``; ``False`` if the server stopped or the time ran out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and server.poll() is None:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def guide(servers: Sequence[AppServer], command: str = "./start.sh") -> str:
    """What to do in the browser: the address of each app and the way into a document."""
    lines = ["Claudia is running. Open the address of the app you want in your browser:", ""]
    for server in servers:
        lines.append(f"  {server.app:<9} {server.url}   {WHAT_TO_DO[server.app]}")
        lines.append(f"  {'':<9} documents are kept in {server.dir}")
        if getattr(server.args, "ai", None):
            lines.append(f"  {'':<9} the AI user answers with the language model {Path(server.args.ai).name}")
    lines += [
        "",
        "In the browser:",
        "  1. Choose a document from the list, or type a new name in 'Document'.",
        "  2. Type your name and a password (8 characters or more, with a capital letter, a small letter and a digit).",
        "  3. 'Create document' makes a new one (you become its owner), 'Open' opens an existing one.",
        "  4. Share it: others open the same address, choose the document and log in with their own name.",
        "  5. The panel next to the document has the history of every step, the chat and the AI user:",
        "     write @ai and your wish in the chat.",
    ]
    served = {server.app for server in servers}
    if served != set(APPS):
        lines += ["", "Other apps (each in its own terminal, or all at once):"]
        lines += [f"  {command} {app:<9} {WHAT_TO_DO[app]}" for app in APPS if app not in served]
        lines.append(f"  {command} all")
    for server in servers:
        for old in legacy_folders(server.app):
            lines += [
                "",
                f"Documents of {server.app} from an earlier version are in {old}; they are not used any more.",
                f"  To keep using them, stop the server and move the files in it to {server.dir}",
            ]
    lines += ["", "Ctrl+C stops the server."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the launcher; returns the exit code of the first server that stops."""
    args = parse_args(argv)
    if needs_build(args):
        build_web()
    if args.ai and not has_openvino():
        install_openvino()
    ensure_fonts(args.root)
    servers = app_servers(args)
    processes: list[subprocess.Popen] = []
    try:
        for server in servers:
            Path(server.dir).mkdir(parents=True, exist_ok=True)  # (the state folder: the server makes it private)
            processes.append(subprocess.Popen(server_command(server.args)))
        if args.ai:
            print(f"Loading the AI model {Path(args.ai).name}; this can take a few minutes…")
        if all(
            wait_for_port(s.args.host, s.port, p, AI_WAIT_SECONDS if s.args.ai else WAIT_SECONDS)
            for s, p in zip(servers, processes, strict=True)
        ):
            print("\n" + guide(servers) + "\n")
            if not args.no_browser:
                webbrowser.open(servers[0].url)
        return _wait_for_first(processes)
    except KeyboardInterrupt:
        return 0
    finally:
        _stop(processes)


def _wait_for_first(processes: Sequence[subprocess.Popen]) -> int:
    """Block until one server stops; returns its exit code."""
    while True:
        for process in processes:
            if process.poll() is not None:
                return process.returncode
        time.sleep(0.5)


def _stop(processes: Sequence[subprocess.Popen]) -> None:
    """Stop the servers that still run."""
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        process.wait()


if __name__ == "__main__":
    sys.exit(main())
