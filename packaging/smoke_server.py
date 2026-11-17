"""Does an installed Claudia server work? The check of the installers' tests (D732), against a server that is running.

    uv run --no-project --with websockets python packaging/smoke_server.py http://127.0.0.1:8765
        [--expect-version 0.36.0]

For each of the three apps it opens a new document over the server's own protocol, asks for the app's help topics
(they are data files of the packages, which a frozen or packaged server easily loses) and closes it. It leaves no
document behind that matters: the documents are named ``smoke-<app>`` and the server may be a throw-away one.
Exit code 0 when everything worked, 1 with the reason on standard error when not.
"""

import argparse
import json
import sys
import urllib.request

from websockets.sync.client import connect

APPS = ("composes", "computes", "creates")
PASSWORD = "Installer-Test-Passw0rd"  # nothing secret: the documents are named smoke-* and thrown away


def health(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/api/health", timeout=10) as response:
        return json.load(response)


def call(ws, request_id: int, method: str, **params):
    ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
    while True:
        reply = json.loads(ws.recv(timeout=30))
        if reply.get("id") == request_id:
            if not reply.get("ok"):
                raise RuntimeError(f"{method} failed: {reply.get('error')}")
            return reply.get("result")


def check_app(base: str, app: str) -> None:
    url = base.replace("http", "ws", 1) + f"/api/{app}/docs/smoke-{app}/ws"
    with connect(url, open_timeout=30) as ws:
        call(ws, 1, "hello", user="smoke", password=PASSWORD, create=True)
        topics = call(ws, 2, "help_search")
        if not topics:
            raise RuntimeError(f"{app} has no help topics: its data files did not come along")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base", help="http://127.0.0.1:8765")
    parser.add_argument("--expect-version", help="the version the server must report")
    args = parser.parse_args(argv)
    base = args.base.rstrip("/")
    try:
        found = health(base)
        missing = sorted(set(APPS) - set(found.get("apps", [])))
        if missing:
            raise RuntimeError(f"the server does not serve {', '.join(missing)} (it serves {found.get('apps')})")
        if args.expect_version and found.get("version") != args.expect_version:
            raise RuntimeError(f"the server is version {found.get('version')}, not {args.expect_version}")
        for app in APPS:
            check_app(base, app)
    except Exception as problem:
        print(f"smoke test failed: {problem}", file=sys.stderr)
        return 1
    print(f"smoke test passed: {', '.join(APPS)} (server {found.get('version')})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
