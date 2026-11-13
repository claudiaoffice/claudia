"""The local server that the shell starts for its window (E0.2): start, wait for it, stop, never leave it behind.

The shell shows the web frontend served by a Claudia server on this computer's loopback address. The server is a
separate process on its own interpreter (3.14); the shell runs on the distribution's Python and must never ask for a
newer one. Nothing here imports GTK.

Three rules keep the server from outliving the window:

* it is started in its own process group, and :meth:`LocalServer.stop` ends the whole group (a worker that the server
  started is not left behind);
* it asks Linux to send it ``SIGTERM`` when the shell dies, however the shell dies (``prctl(PR_SET_PDEATHSIG)``): a
  crash or a ``kill -9`` of the shell cannot orphan it;
* start-up problems are reported with what the server said, not with a bare time-out.

Call :meth:`LocalServer.spawn` from the thread that lives as long as the application (the main thread): Linux ties the
death signal to the thread that started the process, not to the process.
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from .i18n import translate as _
from .paths import default_repo

__all__ = ["LocalServer", "ServerStartError", "find_server_python", "free_port", "server_command"]

LOOPBACK = "127.0.0.1"
HEALTH_PATH = "/api/health"
_LOG_TAIL = 2000
# The server is started through a few lines of Python that first ask for the death signal and then become the server
# (exec keeps the setting). `preexec_fn` would do the same but is unsafe in a process with threads, and GTK has some.
_LAUNCH = (
    "import ctypes, os, signal, sys\n"
    "ctypes.CDLL(None, use_errno=True).prctl(1, int(signal.SIGTERM))\n"  # PR_SET_PDEATHSIG
    "if os.getppid() != int(sys.argv[1]):\n"  # the shell died before the call took effect
    "    os._exit(1)\n"
    "os.execvp(sys.argv[2], sys.argv[2:])\n"
)


class ServerStartError(RuntimeError):
    """The server did not come up. The message says why and quotes the end of what the server printed."""


def free_port(host: str = LOOPBACK) -> int:
    """A port on ``host`` that nobody is listening on right now."""
    with socket.socket() as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def find_server_python(*, repo: Path | None = None) -> str | None:
    """The interpreter that runs the server: ``$CLAUDIA_SERVER_PYTHON``, else the repository's ``.venv``, else ``None``.

    There is no guess beyond that: the server needs Python 3.14 and the Claudia packages, and the Python the shell
    itself runs on has neither.
    """
    explicit = os.environ.get("CLAUDIA_SERVER_PYTHON")
    if explicit:
        return explicit
    candidate = (repo or default_repo()) / ".venv" / "bin" / "python"
    return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None


def server_command(python: str, *, model: str, port: int, documents: Path, web: Path, state: Path) -> list[str]:
    """The command line of a server for one person on this computer, hosting the document ``model`` (``module:Class``,
    ``AppIdentity.model``).

    It listens on the loopback address only, so the connection is plain (as in ``start.sh``); it serves the bundled web
    frontend itself, so the page and its WebSocket have the same origin and no ``--allow-origin`` is needed.
    """
    return [
        python,
        "-m",
        "claudia_server",
        "--model",
        model,
        "--host",
        LOOPBACK,
        "--port",
        str(port),
        "--no-tls",
        "--dir",
        str(documents),
        "--state-dir",
        str(state),
        "--web",
        str(web),
    ]


class LocalServer:
    """One server process: :meth:`spawn` it, ask :meth:`check_ready` until it answers, :meth:`stop` it."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        url: str,
        log: Path | None = None,
        startup_timeout: float = 30.0,
    ) -> None:
        self.url = url
        """Where the server will answer, for example ``http://127.0.0.1:41233``."""
        self._command = list(command)
        self._log = log
        self._timeout = startup_timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._spawned_at = 0.0
        self._ready = False

    @property
    def pid(self) -> int | None:
        """The process id of the server, or ``None`` before :meth:`spawn`."""
        return self._process.pid if self._process else None

    @property
    def running(self) -> bool:
        """Is the server process alive?"""
        return self._process is not None and self._process.poll() is None

    @property
    def log_path(self) -> Path | None:
        """The file the server writes its output to."""
        return self._log

    def spawn(self) -> None:
        """Start the process and return at once (the server is not ready yet: see :meth:`check_ready`)."""
        if self._process is not None:
            raise RuntimeError("the server was started already")
        if self._log is None:
            handle, name = tempfile.mkstemp(prefix="claudia-server-", suffix=".log")
            os.close(handle)
            self._log = Path(name)
        self._log.parent.mkdir(parents=True, exist_ok=True)
        with self._log.open("ab") as output:
            self._process = subprocess.Popen(
                [sys.executable, "-I", "-c", _LAUNCH, str(os.getpid()), *self._command],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # its own process group: stop() ends the group
            )
        self._spawned_at = time.monotonic()
        self._ready = False

    def check_ready(self) -> bool:
        """Does the server answer yet? Never blocks for long.

        Raises :class:`ServerStartError` (and stops the server) when it has exited or has not answered in time.
        """
        process = self._process
        if process is None:
            raise RuntimeError("the server was not started")
        if self._ready:
            return True
        code = process.poll()
        if code is not None:
            self.stop()
            raise ServerStartError(
                _("The server stopped at start-up (exit code {code}).").format(code=code) + self._what_it_said()
            )
        if self._answers():
            self._ready = True
            return True
        if time.monotonic() - self._spawned_at > self._timeout:
            self.stop()
            raise ServerStartError(
                _("The server did not answer at {url} within {seconds} seconds.").format(
                    url=self.url, seconds=f"{self._timeout:g}"
                )
                + self._what_it_said()
            )
        return False

    def start(self) -> str:
        """:meth:`spawn`, then wait until the server answers. Returns its address. (For tools and tests: a window
        must not block, so the application polls :meth:`check_ready` from its main loop instead.)"""
        self.spawn()
        while not self.check_ready():
            time.sleep(0.05)
        return self.url

    def stop(self, grace: float = 3.0) -> None:
        """End the server and everything it started: ``SIGTERM`` to the group, ``SIGKILL`` after ``grace`` seconds.
        Safe to call before :meth:`spawn`, twice, and after the server died on its own."""
        process = self._process
        if process is None:
            return
        self._signal_group(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self._signal_group(process.pid, signal.SIGKILL)  # type: ignore[attr-defined] # POSIX only, not on Windows
            process.wait()
        self._signal_group(process.pid, signal.SIGKILL)  # type: ignore[attr-defined] # whatever is left in the group
        self._process = None

    # ------------------------------------------------------------------------------------------- internals

    @staticmethod
    def _signal_group(pgid: int, sig: signal.Signals) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pgid, sig)  # type: ignore[attr-defined] # POSIX only, not on Windows

    def _answers(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + HEALTH_PATH, timeout=0.5) as answer:  # noqa: S310 (our own http URL)
                return bool(answer.status == 200)
        except (urllib.error.URLError, OSError):
            return False

    def _what_it_said(self) -> str:
        if self._log is None or not self._log.exists():
            return ""
        tail = self._log.read_text(encoding="utf-8", errors="replace")[-_LOG_TAIL:].strip()
        if not tail:
            return ""
        return "\n" + _("--- What the server printed ({log}) ---").format(log=self._log) + f"\n{tail}"
