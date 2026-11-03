"""Start the Claudia demo: build the web app if needed, run the server(s), open the browser.

    ./start.sh                  # computes (tables) at http://127.0.0.1:8765/, documents in ./demo-docs
    ./start.sh composes         # composes (text) at port 8765, documents in ./demo-docs-composes
    ./start.sh creates          # creates (presentations) at port 8765, documents in ./demo-docs-creates
    ./start.sh all              # all three at once: computes 8765, composes 8766, creates 8767
    ./start.sh all --dir ~/claudia-docs --port 9000 --no-browser
    ./start.sh --rebuild        # build the web app again first
    ./start.sh --tls            # encrypt (the browser warns once about the own certificate)

``./start.sh`` is ``start.cmd`` on Windows. ``--app composes`` is the same as the word ``composes``.
One server serves one app, so ``all`` runs three servers side by side; each prints how to find it in the browser.

The wrappers ``start.sh`` (Linux, macOS) and ``start.cmd`` (Windows) call this through ``uv``. Only the standard
library is used here, so it also runs with a plain ``python3``.
"""

from __future__ import annotations

import argparse
import copy
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
BUILT = WEB / ".output" / "public"
# The server's default model is the workbook.
MODELS = {"computes": "", "composes": "claudia_composes:TextModel", "creates": "claudia_creates:SlideModel"}
WAIT_SECONDS = 30.0
APPS = tuple(MODELS)
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
    dir: str
    url: str
    args: argparse.Namespace


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """The options of the launcher. ``args.app`` is one app or ``all``."""
    parser = argparse.ArgumentParser(description="Start the Claudia demo server and open it in the browser.")
    parser.add_argument(
        "which",
        nargs="?",
        choices=[*APPS, "all"],
        metavar="{" + ",".join([*APPS, "all"]) + "}",
        help="which app to serve (default: computes); all starts one server for each app, on consecutive ports",
    )
    parser.add_argument("--app", choices=[*APPS, "all"], help="the same as the word above")
    parser.add_argument(
        "--dir", help="where the sealed (encrypted) documents are kept (default: demo-docs, one folder per app)"
    )
    parser.add_argument(
        "--shapes", action="append", default=[], metavar="DIR", help="creates: more shapes (JSON files); repeatable"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="the port (with all: the first of three)")
    parser.add_argument("--tls", action="store_true", help="encrypt the connection (default: plain, localhost only)")
    parser.add_argument("--rebuild", action="store_true", help="build the web app again before starting")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    if not (args.tls or is_this_computer(args.host)):
        parser.error(
            f"--host {args.host} can be reached from the network, and a plain connection would send passwords in "
            "clear text: add --tls"
        )
    args.app = args.which or args.app or "computes"
    if args.dir is None and args.app != "all":  # one directory holds the documents of one app
        args.dir = str(ROOT / ("demo-docs" if args.app == "computes" else f"demo-docs-{args.app}"))
    return args


def app_servers(args: argparse.Namespace) -> list[AppServer]:
    """The servers to run for these options: one for an app, one per app (consecutive ports) for ``all``."""
    if args.app != "all":
        return [AppServer(args.app, args.port, str(args.dir), page_url(args), args)]
    servers = []
    for offset, app in enumerate(APPS):
        own = copy.copy(args)
        own.app, own.port = app, args.port + offset
        if args.dir is None:
            own.dir = str(ROOT / ("demo-docs" if app == "computes" else f"demo-docs-{app}"))
        else:
            own.dir = str(Path(args.dir) / app)
        servers.append(AppServer(app, own.port, own.dir, page_url(own), own))
    return servers


def needs_build(args: argparse.Namespace, built: Path = BUILT) -> bool:
    """Must the web app be built before the server can serve it?"""
    return args.rebuild or not (built / "index.html").exists()


def server_command(args: argparse.Namespace, python: str = sys.executable, built: Path = BUILT) -> list[str]:
    """The command line that runs the server for these options."""
    command = [python, "-m", "claudia_server", "--dir", str(args.dir), "--web", str(built)]
    command += ["--host", args.host, "--port", str(args.port)]
    if MODELS[args.app]:
        command += ["--model", MODELS[args.app]]
    for folder in args.shapes:
        command += ["--shapes", folder]
    if not args.tls:
        command.append("--no-tls")
    return command


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
    lines += ["", "Ctrl+C stops the server."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the launcher; returns the exit code of the first server that stops."""
    args = parse_args(argv)
    if needs_build(args):
        build_web()
    servers = app_servers(args)
    processes: list[subprocess.Popen] = []
    try:
        for server in servers:
            Path(server.dir).mkdir(parents=True, exist_ok=True)
            processes.append(subprocess.Popen(server_command(server.args)))
        if all(wait_for_port(s.args.host, s.port, p) for s, p in zip(servers, processes, strict=True)):
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
