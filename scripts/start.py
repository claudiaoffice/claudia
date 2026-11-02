"""Start the Claudia demo: build the web app if needed, run the server, open the browser.

    uv run python scripts/start.py                 # documents are kept in ./demo-docs
    uv run python scripts/start.py --dir ~/claudia-docs --port 9000 --no-browser
    uv run python scripts/start.py --rebuild       # build the web app again first
    uv run python scripts/start.py --tls           # encrypt (the browser warns once about the own certificate)

The wrappers ``start.sh`` (Linux, macOS) and ``start.cmd`` (Windows) call this through ``uv``. Only the standard
library is used here, so it also runs with a plain ``python3``.
"""

from __future__ import annotations

import argparse
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
BUILT = WEB / ".output" / "public"
WAIT_SECONDS = 30.0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """The options of the launcher."""
    parser = argparse.ArgumentParser(description="Start the Claudia demo server and open it in the browser.")
    parser.add_argument("--dir", default=str(ROOT / "demo-docs"), help="where documents and users are kept")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tls", action="store_true", help="encrypt the connection (default: plain, localhost only)")
    parser.add_argument("--rebuild", action="store_true", help="build the web app again before starting")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    return parser.parse_args(argv)


def needs_build(args: argparse.Namespace, built: Path = BUILT) -> bool:
    """Must the web app be built before the server can serve it?"""
    return args.rebuild or not (built / "index.html").exists()


def server_command(args: argparse.Namespace, python: str = sys.executable, built: Path = BUILT) -> list[str]:
    """The command line that runs the server for these options."""
    command = [python, "-m", "claudia_server", "--dir", str(args.dir), "--web", str(built)]
    command += ["--host", args.host, "--port", str(args.port)]
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the launcher; returns the exit code of the server."""
    args = parse_args(argv)
    if needs_build(args):
        build_web()
    Path(args.dir).mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(server_command(args))
    try:
        if wait_for_port(args.host, args.port, server):
            print(f"\nClaudia is running at {page_url(args)}  (Ctrl+C stops it; documents are in {args.dir})\n")
            if not args.no_browser:
                webbrowser.open(page_url(args))
        return server.wait()
    except KeyboardInterrupt:
        server.terminate()
        return server.wait()


if __name__ == "__main__":
    sys.exit(main())
