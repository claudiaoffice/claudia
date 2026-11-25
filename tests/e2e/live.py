"""Real servers for the end-to-end tests that need no browser: a ``python -m claudia_server`` process each, spoken to
over HTTP and the WebSocket protocol exactly as a client does.

The unit tests of ``claudia-server`` run the app in-process with Starlette's ``TestClient``; what they cannot see is
the command line, the folders a real server lays out, two servers that do not share memory, and the process boundary
a file crosses when it goes from one place to another. These helpers start the real thing on a free port and stop it
afterwards. A server here serves every app (D430), with sealed documents (``--dir``) and no web app: nothing in these
tests opens a page.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hashing import lower_hashing_cost
from websockets.sync.client import ClientConnection, connect

ROOT = Path(__file__).resolve().parent.parent.parent
START_SECONDS = 90.0
PASSWORD = "Correct-Horse-9"


def free_port() -> int:
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@dataclass
class Live:
    """One running server: where it answers and where it keeps its documents."""

    url: str
    documents: Path
    process: subprocess.Popen

    def get(self, path: str) -> tuple[int, Any]:
        return _http(f"{self.url}{path}")

    def post(self, path: str, body: bytes, headers: dict[str, str] | None = None) -> tuple[int, Any]:
        return _http(f"{self.url}{path}", body, headers or {})

    def file_of(self, app: str, name: str) -> bytes:
        """The document file as it lies in the server's folder: what a person copies to move it elsewhere."""
        found = sorted((self.documents / app).rglob(f"{name}.claudia"))
        assert found, f"no file of {app}/{name} under {self.documents}"
        return found[0].read_bytes()

    @contextmanager
    def socket(self, app: str, name: str) -> Iterator[Session]:
        with connect(f"{self.url.replace('http', 'ws', 1)}/api/{app}/docs/{name}/ws", open_timeout=30) as ws:
            yield Session(ws)


class Session:
    """A connection to one document: ``hello`` first, then requests, with pushed events set aside."""

    def __init__(self, ws: ClientConnection):
        self.ws = ws
        self.events: list[dict] = []
        self._next = 1

    def call(self, method: str, **params: Any) -> dict:
        """The whole answer frame: ``{"ok": true, "result": …}`` or ``{"ok": false, "error": …}``."""
        request_id = self._next
        self._next += 1
        self.ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
        while True:
            frame = json.loads(self.ws.recv(timeout=60))
            if frame.get("id") == request_id:
                return frame
            self.events.append(frame)

    def ok(self, method: str, **params: Any) -> Any:
        """The result of a request that must succeed."""
        frame = self.call(method, **params)
        assert frame.get("ok"), f"{method} {params} was refused: {frame}"
        return frame["result"]

    def hello(self, user: str = "ann", password: str = PASSWORD, **extra: Any) -> dict:
        return self.ok("hello", user=user, password=password, **extra)


def _http(url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    request = urllib.request.Request(
        url, data=body, headers=headers or {}, method="POST" if body is not None else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            status, raw = answer.status, answer.read()
    except urllib.error.HTTPError as refused:
        status, raw = refused.code, refused.read()
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw.decode(errors="replace")


@contextmanager
def server(folder: Path, *extra: str) -> Iterator[Live]:
    """A server of every app on a free port of this computer, with its documents sealed in ``folder/documents``, that
    hashes passwords at the lowest cost (``hashing.lower_hashing_cost``)."""
    port = free_port()
    lower_hashing_cost(folder / "state")
    documents = folder / "documents"
    command = [
        sys.executable,
        "-m",
        "claudia_server",
        "--no-tls",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--dir",
        str(documents),
        "--state-dir",
        str(folder / "state"),
        *extra,
    ]
    # The output goes to a file, not to a pipe nobody reads: a full pipe (about 64 KiB) blocks the server's next write,
    # and with it the whole event loop (PROC-39).
    log = folder / "server.log"
    with log.open("wb") as output:
        process = subprocess.Popen(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + START_SECONDS
        while True:
            if process.poll() is not None:
                raise AssertionError(f"the server stopped early:\n{log.read_text(errors='replace')}")
            try:
                if _http(f"{url}/api/health")[0] == 200:
                    break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise AssertionError(f"the server did not answer in {START_SECONDS:.0f}s")
            time.sleep(0.2)
        yield Live(url, documents, process)
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
