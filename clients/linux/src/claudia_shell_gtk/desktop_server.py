"""The one local server that the three desktop apps share (D445). No GTK in here.

The twin of ``clients/neutralino/src/desktop-server.ts`` (macOS and Windows), in Python:

* **One server for the suite.** It serves all three apps (no ``--model``), keeps one folder of documents and one of
  state, and stops by itself (``--exit-when-idle``, D434) ten minutes after nothing was connected. The first window
  that needs it starts it; the others find it.
* **Found by its port: 8765, the port of every Claudia server** (D504; ``./start.sh`` and a cloud server use it too),
  so the address — and what the page keeps for that address — stays the same. Only when something that is not a
  Claudia server holds 8765 does the suite go to another port, remembered in ``desktop-server.json`` in the state
  folder. A running server is recognised by ``/api/health`` (its apps; its version, for a request from this computer):
  nothing else is asked of it, so a Claudia server of this version on 8765 is this computer's server, whoever started
  it.
* **Two windows starting at once** both start a server on the same port; the one that loses (the port, or the server's
  own lock on its folder, D435) exits at start-up, and its window then uses the one that won.
* **A window never ends the server.** Closing it only lets go of the connection it keeps (``/api/presence``), so the
  server is never taken for idle while a window is open. A window that finds the server gone (it stopped, or somebody
  ended it) starts it again on the same port, where the page reconnects.

A window must never block (E0.2), and finding the server can take seconds (a version check, a start, a race with
another window), so :meth:`DesktopServer.spawn` does it on a thread of its own and the application polls
:meth:`DesktopServer.check_ready` from its main loop, as it did with a server of its own. The presence connection is a
plain WebSocket held on another thread: it carries nothing, and answers the server's pings.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from .i18n import translate as _
from .server import LOOPBACK, LocalServer, ServerStartError, free_port, server_command
from .urls import is_internal

__all__ = [
    "IDLE_SECONDS",
    "SERVER_PORT",
    "STATE_FILE",
    "DesktopServer",
    "Health",
    "PresenceSocket",
    "is_port_free",
    "probe_health",
    "read_port",
    "read_setup_code",
    "server_version",
    "setup_code_for_page",
    "write_port",
]

log = logging.getLogger(__name__)

IDLE_SECONDS = 600
"""``--exit-when-idle``: ten minutes (D445). The clock starts only when the last page has closed."""
STATE_FILE = "desktop-server.json"
"""The file in the server's state folder that says where the server runs, ``{"port": N}``."""
SETUP_CODE_FILE = Path("admin") / "setup-code"
"""Where the server writes its setup code while it has no administrator (D1371), readable by this user only."""
_SETUP_CODE = re.compile(r"[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}")


def read_setup_code(state: Path) -> str | None:
    """The setup code the server with this state folder wrote, or ``None`` (an administrator exists, or the file is
    not a code). Read anew at every call: the shared server may have been restarted by another window (D1373)."""
    try:
        text = (state / SETUP_CODE_FILE).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return text if _SETUP_CODE.fullmatch(text) else None


def setup_code_for_page(shown: str | None, local: str | None, read: Callable[[], str | None]) -> str | None:
    """The setup code a page may be handed (D1373): the shell's own server's, and only while the window shows that
    server (``shown`` is the address of the page, ``local`` the origin of the shell's own server)."""
    if not shown or not local or not is_internal(shown, local):
        return None
    return read()


SERVER_PORT = 8765
"""The port of every Claudia server unless told otherwise (D504), the same for ./start.sh and the desktop's own."""

_PRESENCE_PAUSE = 1.0
_PRESENCE_PAUSE_MAX = 10.0
_RACE_POLL = 0.3


@dataclass(frozen=True)
class Health:
    """What is listening where the server should be: ``none`` (nothing), ``other`` (something that is not a server of
    this suite, or one from before D444, which says no apps) or ``claudia``."""

    kind: str
    apps: tuple[str, ...] = field(default=())
    version: str | None = None


NONE = Health("none")
OTHER = Health("other")


def probe_health(url: str, timeout: float = 1.0) -> Health:
    """``/api/health`` at ``url``. A refused connection is ``none``; any other answer that is not ours is ``other``."""
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=timeout) as answer:  # noqa: S310 (our own http URL)
            status, body = answer.status, answer.read()
    except urllib.error.HTTPError:
        return OTHER
    except (urllib.error.URLError, OSError):
        return NONE
    if status != 200:
        return OTHER
    try:
        data = json.loads(body)
    except ValueError:
        return OTHER
    apps = data.get("apps") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("ok") is not True or not isinstance(apps, list):
        return OTHER
    if not all(isinstance(app, str) for app in apps):
        return OTHER
    version = data.get("version")
    return Health("claudia", tuple(apps), version if isinstance(version, str) else None)


def read_port(file: Path) -> int | None:
    """The remembered port, or ``None`` for a missing, broken or nonsensical file."""
    try:
        port = json.loads(file.read_text(encoding="utf-8")).get("port")
    except (OSError, ValueError, AttributeError):
        return None
    return port if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535 else None


def write_port(file: Path, port: int, *, exclusive: bool) -> bool:
    """Remember ``port``. ``exclusive`` writes only when there is no file yet (``False`` when somebody was first);
    otherwise the file is overwritten. The folder is made."""
    file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"port": port}) + "\n"
    if not exclusive:
        file.write_text(text, encoding="utf-8")
        return True
    # Written whole under another name and then linked into place: a second window that loses never reads a file that
    # is there but not written yet (two first starts at once are exactly when this is asked).
    handle, name = tempfile.mkstemp(prefix=".desktop-server-", dir=file.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.link(name, file)
    except FileExistsError:
        return False
    finally:
        with contextlib.suppress(OSError):
            os.unlink(name)
    return True


def is_port_free(port: int, host: str = LOOPBACK) -> bool:
    """Can a server listen on ``port`` of this computer's loopback address right now?"""
    with socket.socket() as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def server_version(python: str, timeout: float = 30.0) -> str | None:
    """The version of the server this app would start (``claudia_server --version``), or ``None`` if that cannot be
    found out."""
    try:
        done = subprocess.run(  # noqa: S603 (our own interpreter and module)
            [python, "-m", "claudia_server", "--version"], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    found = re.search(r"claudia-server\s+(\S+)", done.stdout) if done.returncode == 0 else None
    return found.group(1) if found else None


# ------------------------------------------------------------------------------------------------------ presence


class PresenceSocket(Protocol):
    """What the presence connection needs: wait until it ends, and end it."""

    def wait_closed(self) -> None: ...
    def close(self) -> None: ...


_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class _WebSocket:
    """A WebSocket client that is just enough for ``/api/presence``: it says nothing, answers pings, and notices the
    end. (The standard library has no WebSocket client, and this needs no GTK main loop.)"""

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        parts = urlsplit(url)
        host, port = parts.hostname or LOOPBACK, parts.port or 80
        self._closing = False
        self._buffer = b""  # what came with the handshake's answer: the first frames may arrive in the same read
        self._send_lock = threading.Lock()
        self._sock = socket.create_connection((host, port), timeout=timeout)
        try:
            key = base64.b64encode(os.urandom(16)).decode("ascii")
            request = (
                f"GET {parts.path or '/'} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            )
            self._sock.sendall(request.encode("ascii"))
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = self._sock.recv(1024)
                if not chunk:
                    raise OSError("the server closed the connection during the handshake")
                head += chunk
            answer, self._buffer = head.split(b"\r\n\r\n", 1)
            lines = answer.decode("latin-1").split("\r\n")
            if not lines[0].startswith("HTTP/1.1 101"):
                raise OSError(f"the server refused the presence socket: {lines[0]}")
            expected = base64.b64encode(hashlib.sha1((key + _GUID).encode("ascii")).digest()).decode("ascii")  # noqa: S324 (the protocol's own hash)
            headers = {k.strip().lower(): v.strip() for k, _sep, v in (line.partition(":") for line in lines[1:])}
            if headers.get("sec-websocket-accept") != expected:
                raise OSError("the server's answer to the presence socket was not a WebSocket handshake")
            self._sock.settimeout(None)
        except BaseException:
            self._sock.close()
            raise

    def _read(self, size: int) -> bytes:
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        while len(data) < size:
            chunk = self._sock.recv(size - len(data))
            if not chunk:
                raise EOFError
            data += chunk
        return data

    def _send(self, opcode: int, payload: bytes = b"") -> None:
        mask = os.urandom(4)
        header = bytes([0x80 | opcode, 0x80 | len(payload)])  # control frames carry at most 125 bytes
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self._send_lock:
            self._sock.sendall(header + mask + masked)

    def wait_closed(self) -> None:
        """Return when the connection has ended, however it ends."""
        try:
            while True:
                first, second = self._read(2)
                opcode, length = first & 0x0F, second & 0x7F
                if length == 126:
                    length = int.from_bytes(self._read(2), "big")
                elif length == 127:
                    length = int.from_bytes(self._read(8), "big")
                mask = self._read(4) if second & 0x80 else b""
                payload = self._read(length) if length else b""
                if mask:
                    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
                if opcode == 0x9:  # ping
                    self._send(0xA, payload[:125])
                elif opcode == 0x8:  # close
                    with contextlib.suppress(OSError):
                        self._send(0x8, payload[:2])
                    return
        except (EOFError, OSError):
            return
        finally:
            with contextlib.suppress(OSError):
                self._sock.close()

    def close(self) -> None:
        """End the connection (from any thread); :meth:`wait_closed` returns."""
        if self._closing:
            return
        self._closing = True
        with contextlib.suppress(OSError):
            self._send(0x8, (1000).to_bytes(2, "big"))
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_RDWR)


def _connect(url: str) -> PresenceSocket:
    return _WebSocket(url)


# ------------------------------------------------------------------------------------------------- the server


class ServerProcess(Protocol):
    """One server process, as ``server.LocalServer`` offers it."""

    def start(self) -> str: ...
    def stop(self) -> None: ...


def _make_server(command: list[str], url: str, log_path: Path) -> ServerProcess:
    return LocalServer(command, url=url, log=log_path, outlives_shell=True)


class DesktopServer:
    """The shared local server, as one window uses it: :meth:`spawn`, then :meth:`check_ready` until it answers;
    :meth:`stop` lets go of it."""

    def __init__(
        self,
        *,
        app: str,
        python: str,
        web: Path,
        documents: Path,
        state: Path,
        idle_seconds: int = IDLE_SECONDS,
        race_wait: float = 30.0,
        port: int = SERVER_PORT,
        # What the tests replace:
        probe: Callable[[str], Health] = probe_health,
        make_server: Callable[[list[str], str, Path], ServerProcess] = _make_server,
        pick_port: Callable[[], int] = free_port,
        port_free: Callable[[int], bool] = is_port_free,
        version: Callable[[], str | None] | None = None,
        connect: Callable[[str], PresenceSocket] = _connect,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._app = app
        self._python = python
        self._web = web
        self._documents = documents
        self._state = state
        self._idle = idle_seconds
        self._race_wait = race_wait
        self._port = port
        self._probe = probe
        self._make_server = make_server
        self._pick_port = pick_port
        self._port_free = port_free
        self._version = version or (lambda: server_version(python))
        self._connect = connect
        self._sleep = sleep
        self._state_file = state / STATE_FILE
        self._origin: str | None = None
        self._let_go = threading.Event()
        self._socket: PresenceSocket | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._result: str | BaseException | None = None

    @property
    def log_path(self) -> Path:
        """The file the server writes to (shared by every start)."""
        return self._state / "server.log"

    @property
    def url(self) -> str:
        """Where the server answers, once :meth:`check_ready` said so (empty before)."""
        return self._origin or ""

    def setup_code(self) -> str | None:
        """The server's setup code while it has no administrator (:func:`read_setup_code`)."""
        return read_setup_code(self._state)

    # ------------------------------------------------------------------------------- what the application calls

    def spawn(self) -> None:
        """Find or start the server on a thread of its own, and return at once."""
        if self._thread is not None:
            raise RuntimeError("the server was asked for already")
        self._thread = threading.Thread(target=self._find, name="claudia-desktop-server", daemon=True)
        self._thread.start()

    def check_ready(self) -> bool:
        """Has the server been found (or started)? Never blocks. Raises what went wrong (``ServerStartError``)."""
        if self._thread is None:
            raise RuntimeError("the server was not asked for")
        result = self._result
        if result is None:
            return False
        if isinstance(result, BaseException):
            raise result
        return True

    def start(self) -> str:
        """Find or start the server and keep the presence connection; its address. (Blocks: for tools and tests.)"""
        url = self._ensure()
        self._origin = url
        if not self._let_go.is_set():
            threading.Thread(target=self._keep_presence, name="claudia-presence", daemon=True).start()
        return url

    def stop(self) -> None:
        """Let go of the server: this window is gone. The server is not stopped; it stops when nothing is connected."""
        self._let_go.set()
        with self._lock:
            socket_, self._socket = self._socket, None
        if socket_ is not None:
            socket_.close()

    # ------------------------------------------------------------------------------------------- finding it

    def _find(self) -> None:
        try:
            self._result = self.start()
        except ServerStartError as problem:
            self._result = problem
        except OSError as problem:
            self._result = ServerStartError(str(problem))

    def _ensure(self) -> str:
        preferred = self._port
        remembered = read_port(self._state_file)
        # A server that runs already: on the port of every Claudia server, or where an earlier start had to go instead.
        preferred_taken = False
        for port in [preferred] if remembered in (None, preferred) else [preferred, remembered]:
            url = f"http://{LOOPBACK}:{port}"
            found = self._probe(url)
            if found.kind == "claudia":
                self._check_is_ours(found, port)
                self._remember(port)
                return url
            if port == preferred:
                preferred_taken = found.kind == "other" or not self._port_free(port)
        # None runs: start one, on the usual port unless something that is not a Claudia server holds it.
        port = preferred
        if preferred_taken:
            usable = remembered is not None and remembered != preferred and self._port_free(remembered)
            port = remembered if usable and remembered is not None else self._pick_port()
            log.info(
                "port %s is used by something that is not a Claudia server; the local server goes to port %s",
                preferred,
                port,
            )
        self._remember(port)
        return self._start_server(f"http://{LOOPBACK}:{port}", port)

    def _remember(self, port: int) -> None:
        """Write down where the server is, if that is not what the file says already."""
        if read_port(self._state_file) == port:
            return
        try:
            write_port(self._state_file, port, exclusive=False)
        except OSError as problem:
            log.warning("%s could not be written: %s", self._state_file, problem)

    def _check_is_ours(self, found: Health, port: int) -> None:
        hint = _(
            "It stops by itself ten minutes after its last window has closed. Or end its python process "
            "(System Monitor). Then start again."
        )
        if self._app not in found.apps:
            raise ServerStartError(
                _("The Claudia server on this computer (port {port}) does not serve {app}; it serves {apps}.").format(
                    port=port, app=self._app, apps=", ".join(found.apps) or _("no app")
                )
                + "\n"
                + hint
            )
        if found.version is None:
            return
        own = self._version()
        if own is not None and own != found.version:
            raise ServerStartError(
                _(
                    "A Claudia server of another version ({running}, this app belongs to {own}) is running on this "
                    "computer (port {port})."
                ).format(running=found.version, own=own, port=port)
                + "\n"
                + hint
            )

    def _start_server(self, url: str, port: int) -> str:
        command = server_command(
            self._python,
            port=port,
            documents=self._documents,
            web=self._web,
            state=self._state,
            idle_seconds=self._idle,
        )
        server = self._make_server(command, url, self.log_path)
        try:
            return server.start()
        except ServerStartError as problem:
            # Another window may have started it a moment before: its server holds the folder's lock (D435), and ours
            # exited. Then that one is the server.
            if problem.exited and self._winner_answers(url):
                log.info("another start was first; using its server at %s", url)
                return url
            raise

    def _winner_answers(self, url: str) -> bool:
        until = time.monotonic() + self._race_wait
        while True:
            found = self._probe(url)
            if found.kind == "claudia" and self._app in found.apps:
                return True
            if time.monotonic() >= until:
                return False
            self._sleep(_RACE_POLL)

    # ------------------------------------------------------------------------------------------------ presence

    def _keep_presence(self) -> None:
        """Keep a connection to the server while this window is open (D445). When it ends, the server has stopped (or
        been stopped): start it again on the same port and connect again."""
        pause = _PRESENCE_PAUSE
        while not self._let_go.is_set():
            try:
                self._hold()
                pause = _PRESENCE_PAUSE
                if self._let_go.is_set():
                    return
                self._origin = self._ensure()  # gone? then up again; there, nothing happens
            except (ServerStartError, OSError) as problem:
                log.warning("the local server is not there and could not be started again: %s", problem)
                pause = min(pause * 2, _PRESENCE_PAUSE_MAX)
            if not self._let_go.is_set():
                self._sleep(pause)

    def _hold(self) -> None:
        """Return when the presence connection ends, however it ends."""
        origin = self._origin
        if origin is None or self._let_go.is_set():
            return
        try:
            socket_ = self._connect(origin.replace("http", "ws", 1) + "/api/presence")
        except OSError:
            return
        with self._lock:
            if self._let_go.is_set():
                socket_.close()
                return
            self._socket = socket_
        socket_.wait_closed()
