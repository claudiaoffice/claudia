"""A person's private server, which her three desktop apps share ("Private on this computer"; E8.5, D1620, D1621;
before E8.5: the desktop's one server, D445). No GTK in here.

The twin of ``clients/neutralino/src/private-server.ts`` (macOS and Windows), in Python:

* **One server for her three apps.** It serves all three (no ``--model``), keeps her folder of documents and her folder
  of state, and stops by itself (``--exit-when-idle``, D434) ten minutes after nothing was connected. Her first window
  that needs it starts it; her others find it.
* **On a port of her own** (``private_port.py``): from her account number, the same at every start, so the address --
  and what the page keeps for it -- stays hers; never 8765, the port of every shared server (D1621).
* **Hers, proven.** Her apps start it with a key from her state folder (``owner_key.py``) and use a server they find on
  her port only when it answers a fresh challenge with that key: another person's server, a shared one, or a program on
  her port is never taken for hers (CODE-99), and its version is no business of hers (CODE-100).
* **Her port held by something else** (a program, or a Claudia server that is not hers): her server goes to the next
  free port of her range (``walk_from``, the same order for every window of hers) for as long as that lasts, written
  down as ``instead`` in ``desktop-server.json`` so that her other apps find it. A start uses her server where it is,
  and starts one on her own port again (and forgets ``instead``) once her server is gone and her port is free.
* **Two windows starting at once** both start a server on the same port; the one that loses (the port, or the server's
  own lock on its folder, D435) exits at start-up, and its window then uses the one that won, when it is hers.
* **A window never ends the server.** Closing it only lets go of the connection it keeps (``/api/presence``), so the
  server is never taken for idle while a window is open. A window that finds the server gone (it stopped, or somebody
  ended it) starts it again, where the page reconnects.

A window must never block (E0.2), and finding the server can take seconds (a version check, a start, a race with
another window), so :meth:`PrivateServer.spawn` does it on a thread of its own and the application polls
:meth:`PrivateServer.check_ready` from its main loop, as it did with a server of its own. The presence connection is a
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
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

from .i18n import translate as _
from .owner_key import OwnerKey, is_owned_by, owner_key
from .private_port import PRIVATE_PORTS, private_port, walk_from
from .server import LOOPBACK, LocalServer, ServerStartError, server_command
from .urls import is_internal

__all__ = [
    "IDLE_SECONDS",
    "STATE_FILE",
    "Health",
    "PresenceSocket",
    "PrivateServer",
    "is_port_free",
    "probe_health",
    "read_instead",
    "read_setup_code",
    "server_version",
    "setup_code_for_page",
    "write_instead",
]

log = logging.getLogger(__name__)

IDLE_SECONDS = 600
"""``--exit-when-idle``: ten minutes (D445). The clock starts only when the last page has closed."""
STATE_FILE = "desktop-server.json"
"""The file in the server's state folder that holds ``{"instead": N}``, the port her server went to while her own port
is held by something else; there is no file while it is not. (A file from before E8.5 says ``{"port": N}`` and is not
read.)"""
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


def read_instead(file: Path) -> int | None:
    """The port her server went to instead of her own, or ``None`` for a missing, broken, nonsensical or older file."""
    try:
        port = json.loads(file.read_text(encoding="utf-8")).get("instead")
    except (OSError, ValueError, AttributeError):
        return None
    return port if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535 else None


def write_instead(file: Path, port: int | None) -> None:
    """Write down where her server went instead (written whole under another name first, so that her other windows
    never read half a file), or, with ``None``, that it is on her own port again. The folder is made."""
    if port is None:
        file.unlink(missing_ok=True)
        return
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(f"{file.name}.{os.getpid()}")
    temporary.write_text(json.dumps({"instead": port}) + "\n", encoding="utf-8")
    temporary.replace(file)


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


def _url(port: int) -> str:
    return f"http://{LOOPBACK}:{port}"


def _port(url: str) -> int:
    return urlsplit(url).port or 0


_FOLDER_HELD = "another Claudia server uses "
"""What a server says when another one holds its folder of documents (``claudia_server/folder_lock.py``, D435)."""


def _make_server(command: list[str], url: str, log_path: Path) -> ServerProcess:
    return LocalServer(command, url=url, log=log_path, outlives_shell=True)


class PrivateServer:
    """Her private server, as one window uses it: :meth:`spawn`, then :meth:`check_ready` until it answers; :meth:`stop`
    lets go of it."""

    def __init__(
        self,
        *,
        app: str,
        python: str,
        web: Path,
        documents: Path,
        state: Path,
        uid: int | None = None,
        port: int | None = None,
        idle_seconds: int = IDLE_SECONDS,
        race_wait: float = 30.0,
        # What the tests replace:
        probe: Callable[[str], Health] = probe_health,
        is_mine: Callable[[str], bool] | None = None,
        make_server: Callable[[list[str], str, Path], ServerProcess] = _make_server,
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
        # Her port: by her account number (``uid``, this process's by default), unless told otherwise (``port``,
        # ``CLAUDIA_SERVER_PORT``).
        self._usual = port if port is not None else private_port(os.getuid() if uid is None else uid)
        self._probe = probe
        self._is_mine = is_mine or self._proves_hers
        self._key: OwnerKey | None = None
        self._make_server = make_server
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

    def _ensure(self, stay: int | None = None) -> str:
        """Find her server or start it. ``stay``: the port the page is on, tried first when her server has gone
        (:meth:`_keep_presence`), so that it comes back where the page reconnects."""
        if stay is not None:
            there = self._find_on(stay)
            if there == "hers":
                return _url(stay)
            if there == "free":
                return self._start_server(stay)
        usual = self._usual
        at_usual = self._find_on(usual)
        if at_usual == "hers":
            self._gone_back()
            return _url(usual)
        # Her server may still run where it went while her port was held, and it keeps her documents (D435): use it.
        instead = read_instead(self._state_file)
        if instead is not None and instead != usual and self._find_on(instead) == "hers":
            return _url(instead)
        if at_usual == "free":
            self._gone_back()
            return self._start_server(usual)
        log.info(
            "port %s, hers, is held by %s; her server uses another port of her range while that lasts",
            usual,
            "something that is not a Claudia server" if at_usual == "held" else "a Claudia server that is not hers",
        )
        for port in walk_from(usual):
            there = self._find_on(port)
            if there in ("hers", "free"):
                self._write(port)
                return _url(port) if there == "hers" else self._start_server(port)
        raise ServerStartError(
            _("No port from {first} to {last} is free for your Claudia server on this computer.").format(
                first=PRIVATE_PORTS[0], last=PRIVATE_PORTS[1]
            )
        )

    def _find_on(self, port: int) -> Literal["hers", "free", "not hers", "held"]:
        """What is on ``port``: ``hers`` (checked to serve this app at this version), ``free``, ``not hers`` (a Claudia
        server that is not hers) or ``held`` (something else holds it)."""
        found = self._probe(_url(port))
        if found.kind == "claudia":
            if not self._is_mine(_url(port)):
                return "not hers"
            self._check_is_ours(found, port)
            return "hers"
        return "free" if found.kind == "none" and self._port_free(port) else "held"

    def _gone_back(self) -> None:
        """Her server is on her own port: ``instead`` is no longer needed."""
        if read_instead(self._state_file) is not None:
            self._write(None)

    def _write(self, instead: int | None) -> None:
        try:
            write_instead(self._state_file, instead)
        except OSError as problem:
            log.warning("%s could not be written: %s", self._state_file, problem)

    def _owner_key(self) -> OwnerKey:
        if self._key is None:
            self._key = owner_key(self._state)
        return self._key

    def _proves_hers(self, url: str) -> bool:
        """Does the Claudia server at ``url`` prove to be hers (``owner_key.is_owned_by`` with her key)?"""
        return is_owned_by(_port(url), self._owner_key().key)

    def _check_is_ours(self, found: Health, port: int) -> None:
        hint = self._hint()
        if self._app not in found.apps:
            raise ServerStartError(
                _("Your Claudia server on this computer (port {port}) does not serve {app}; it serves {apps}.").format(
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
                    "Your Claudia server of another version ({running}, this app belongs to {own}) is still running "
                    "on this computer (port {port})."
                ).format(running=found.version, own=own, port=port)
                + "\n"
                + hint
            )

    @staticmethod
    def _hint() -> str:
        return _(
            "It stops by itself ten minutes after its last window has closed. Or end its python process "
            "(System Monitor). Then start again."
        )

    def _start_server(self, port: int) -> str:
        url = _url(port)
        command = server_command(
            self._python,
            port=port,
            documents=self._documents,
            web=self._web,
            state=self._state,
            idle_seconds=self._idle,
            owner_key_file=self._owner_key().file,
        )
        server = self._make_server(command, url, self.log_path)
        try:
            return server.start()
        except ServerStartError as problem:
            # Another of her windows may have started it a moment before: its server holds the folder's lock (D435), and
            # ours exited. Then that one is the server -- when it proves to be hers.
            if problem.exited and self._winner_answers(url):
                log.info("another start was first; using its server at %s", url)
                return url
            # Her documents are held by a server that is not on her port and cannot prove to be hers: her own from
            # before E8.5 (on 8765, with no key), still running after an update.
            if problem.exited and _FOLDER_HELD in str(problem):
                raise ServerStartError(
                    _(
                        "Your documents are in use by another Claudia server on this computer: most likely your "
                        "own, of an older version, which is still running."
                    )
                    + "\n"
                    + self._hint()
                ) from problem
            raise

    def _winner_answers(self, url: str) -> bool:
        until = time.monotonic() + self._race_wait
        while True:
            found = self._probe(url)
            if found.kind == "claudia" and self._app in found.apps:
                return self._is_mine(url)
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
                # gone? then up again, where the page is; there, nothing happens
                self._origin = self._ensure(_port(self._origin) if self._origin else None)
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
