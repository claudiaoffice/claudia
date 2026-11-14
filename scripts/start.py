"""Start Claudia: build the web app if needed, run the server, open the browser.

    ./start.sh                  # the server of all three apps at http://127.0.0.1:8765/
    ./start.sh composes         # the same server; the browser opens composes (text)
    ./start.sh creates          # the same server; the browser opens creates (presentations)
    ./start.sh all              # the same as ./start.sh (it once meant three servers on 8765-8767)
    ./start.sh --dir ~/claudia-data --port 9000 --no-browser
    ./start.sh --rebuild        # build the web app again first
    ./start.sh --tls            # encrypt (the browser warns once about the own certificate)
    ./start.sh --ai             # the AI user answers with the language model in ai-models/ (computes, creates)
    ./start.sh --ai ~/models/qwen2.5-7b-instruct-int4-ov --ai-device CPU

``./start.sh`` is ``start.cmd`` on Windows. ``--app composes`` is the same as the word ``composes``.
One server serves all three apps (D430); naming an app only chooses the page the browser opens (D433).

Where things are kept: one folder per checkout, ``.claudia/`` (or ``--dir DIR``)::

    .claudia/documents/<app>      each app's sealed documents (D431)
    .claudia/state                the server's own state: certificate, administrators, settings
    .claudia/fonts                the fonts the server hands to its clients for print and PDF (fetched once)
    .claudia/hyphenation          the hyphenation patterns it hands out, the same way (fetched once)

The installed desktop apps keep theirs elsewhere, in the system's place for user data, so a development checkout
never touches them. Folders of the earlier layouts (``.claudia/<app>/``, ``docs-<app>``, ``demo-docs*``) are not used
any more (D437); the guide names them once so that they can be deleted, and this script never touches them.

The wrappers ``start.sh`` (Linux, macOS) and ``start.cmd`` (Windows) call this through ``uv``. Only the standard
library is used here, so it also runs with a plain ``python3``.
"""

from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
#: Where a checkout keeps its documents and its server's state (ignored by git).
DATA = ROOT / ".claudia"
#: Folders of earlier layouts, relative to the checkout: before D430 each app had ``.claudia/<app>/``, and before that
#: ``docs-<app>`` or ``demo-docs*`` (until 2938f0a). Named once in the guide, never used, never moved (D437).
LEGACY = ("docs-computes", "docs-composes", "docs-creates", "demo-docs", "demo-docs-composes", "demo-docs-creates")
BUILT = WEB / ".output" / "public"
APPS = ("computes", "composes", "creates")
WAIT_SECONDS = 30.0
#: Where ``--ai`` without a folder looks for a model: one folder per model, converted for OpenVINO (ignored by git).
MODELS_DIR = ROOT / "ai-models"
#: Loading a model of several GB before the server listens takes minutes on a slow disk, not seconds.
AI_WAIT_SECONDS = 900.0
#: How a model folder is made, for the message when there is none.
CONVERT_HINT = (
    "convert one with `optimum-cli export openvino --model Qwen/Qwen2.5-7B-Instruct --weight-format int4 "
    "ai-models/qwen2.5-7b-instruct-int4-ov`, or download one of huggingface.co/OpenVINO into ai-models/"
)
#: What installs OpenVINO GenAI into the environment the server runs in, without removing anything else.
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """The options of the launcher. ``args.app`` is the app whose page the browser opens, ``None`` for the start page
    of all of them."""
    parser = argparse.ArgumentParser(description="Start the Claudia server and open it in the browser.")
    parser.add_argument(
        "which",
        nargs="?",
        choices=[*APPS, "all"],
        metavar="{" + ",".join([*APPS, "all"]) + "}",
        help="the app to open in the browser (default: the start page of all three); the server serves them all",
    )
    parser.add_argument("--app", choices=[*APPS, "all"], help="the same as the word above")
    parser.add_argument(
        "--dir",
        help="where documents and server state are kept: DIR/documents/<app> and DIR/state (default: .claudia)",
    )
    parser.add_argument(
        "--shapes", action="append", default=[], metavar="DIR", help="creates: more shapes (JSON files); repeatable"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
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
    chosen = args.which or args.app
    args.app = None if chosen in (None, "all") else chosen
    args.root = str(DATA if args.dir is None else Path(args.dir).expanduser())
    args.documents, args.state = folders(args.root)
    if args.ai_device and args.ai is None:
        parser.error("--ai-device names where the model of --ai runs: add --ai")
    if args.ai == "":
        try:
            args.ai = str(find_model())
        except LookupError as problem:
            parser.error(str(problem))
    return args


def folders(root: str | Path) -> tuple[str, str]:
    """Where the server keeps its documents (one folder per app inside, D431) and its own state, under ``root``."""
    return str(Path(root) / "documents"), str(Path(root) / "state")


def old_folders(root: str | Path = DATA, checkout: Path = ROOT) -> list[Path]:
    """Folders of earlier layouts that still hold something (D437): ``ROOT/<app>`` of the three-server layout and the
    older ``docs-<app>`` and ``demo-docs*`` in the checkout."""
    candidates = [Path(root) / app for app in APPS] + [checkout / name for name in LEGACY]
    return [folder for folder in candidates if folder.is_dir() and any(folder.iterdir())]


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


def needs_build(args: argparse.Namespace, built: Path = BUILT) -> bool:
    """Must the web app be built before the server can serve it?"""
    return args.rebuild or not (built / "index.html").exists()


def server_command(args: argparse.Namespace, python: str = sys.executable, built: Path = BUILT) -> list[str]:
    """The command line that runs the server of all three apps for these options."""
    # `--web` stays forward-slash even on Windows (Path.as_posix(), not str()): it is echoed back by callers and
    # compared verbatim, and the OS itself accepts either separator when the server opens files under it.
    command = [python, "-m", "claudia_server", "--dir", str(args.documents), "--state-dir", str(args.state)]
    command += ["--web", Path(built).as_posix()]
    command += ["--host", args.host, "--port", str(args.port)]
    command += ["--fonts", fonts_folder(args.root).as_posix()]
    command += ["--hyphenation", hyphenation_folder(args.root).as_posix()]
    for folder in args.shapes:
        command += ["--shapes", folder]
    if not args.tls:
        command.append("--no-tls")
    if args.ai:
        command += ["--ai", args.ai]
        if args.ai_device:
            command += ["--ai-device", args.ai_device]
    return command


def fonts_folder(root: str | Path) -> Path:
    """The fonts the server of a checkout hands out: ``ROOT/fonts`` (D905)."""
    return Path(root) / "fonts"


def ensure_fonts(root: str | Path, fetch=None) -> bool:
    """Fetch the starter set of open fonts into :func:`fonts_folder` once, the first time it is missing; print preview
    and PDF export lay out with them (D901, D905). A failed fetch (no network) is reported and the server starts
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


def hyphenation_folder(root: str | Path) -> Path:
    """The hyphenation patterns the server of a checkout hands out: ``ROOT/hyphenation`` (D913)."""
    return Path(root) / "hyphenation"


def ensure_hyphenation(root: str | Path, fetch=None) -> bool:
    """Fetch the pinned hyphenation patterns into :func:`hyphenation_folder` once (D913). As with the fonts, a failed
    fetch is reported and the server starts anyway; its pages are then not hyphenated. ``True`` when the patterns
    are there afterwards."""
    from claudia_server.hyphenation import FetchError, HyphenationService
    from claudia_server.hyphenation import fetch as fetch_patterns

    folder = hyphenation_folder(root)
    if folder.is_dir() and HyphenationService.from_folder(folder).languages:
        return True
    folder.mkdir(parents=True, exist_ok=True)  # the server is given the folder either way
    print(f"Fetching the hyphenation patterns into {folder} (once; about 400 kB) …", flush=True)
    try:
        (fetch or fetch_patterns)(folder)
    except (FetchError, OSError) as problem:
        print(
            f"Could not fetch the hyphenation patterns ({problem}); pages are not hyphenated until they are there. "
            f"Run `uv run python -m claudia_server.hyphenation fetch {folder}`.",
            flush=True,
        )
        return False
    return True


def server_url(args: argparse.Namespace) -> str:
    """The address of the server."""
    return f"{'https' if args.tls else 'http'}://{args.host}:{args.port}/"


def page_url(args: argparse.Namespace) -> str:
    """The address to open in the browser: the page of the app asked for, else the start page."""
    return server_url(args) + (f"?app={args.app}" if args.app else "")


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
    """Can the server's interpreter (this one) load the language model?"""
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


def guide(args: argparse.Namespace, command: str = "./start.sh") -> str:
    """What to do in the browser: the address of each app and the way into a document."""
    lines = [f"Claudia is running at {server_url(args)} with all three apps:", ""]
    lines += [f"  {app:<9} {server_url(args)}?app={app}   {WHAT_TO_DO[app]}" for app in APPS]
    lines += ["", f"Documents are kept in {args.documents}, one folder per app."]
    if args.ai:
        lines.append(f"The AI user answers with the language model {Path(args.ai).name} (computes, creates).")
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
    old = old_folders(args.root)
    if old:
        lines += ["", "Folders of an earlier version are not used any more; delete them when you like:"]
        lines += [f"  {folder}" for folder in old]
    lines += ["", f"Ctrl+C stops the server. ({command} composes opens composes, and so on.)"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the launcher; returns the exit code of the server."""
    args = parse_args(argv)
    if needs_build(args):
        build_web()
    if args.ai and not has_openvino():
        install_openvino()
    ensure_fonts(args.root)
    ensure_hyphenation(args.root)
    Path(args.documents).mkdir(parents=True, exist_ok=True)  # (the state folder: the server makes it private)
    process = subprocess.Popen(server_command(args))
    try:
        if args.ai:
            print(f"Loading the AI model {Path(args.ai).name}; this can take a few minutes…")
        if wait_for_port(args.host, args.port, process, AI_WAIT_SECONDS if args.ai else WAIT_SECONDS):
            print("\n" + guide(args) + "\n")
            if not args.no_browser:
                webbrowser.open(page_url(args))
        return process.wait()
    except KeyboardInterrupt:
        return 0
    finally:
        _stop([process])


def _stop(processes: Sequence[subprocess.Popen]) -> None:
    """Stop the server if it still runs."""
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        process.wait()


if __name__ == "__main__":
    sys.exit(main())
