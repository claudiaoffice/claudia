"""A person's private server (E8.5, D1620, D1621; before: the desktop's one shared server, D445): her three apps share
it, it is on a port of her own, and her apps use a server they find there only when it proves to be hers -- so another
person's server, a shared one, or a program on her port is never taken for it (CODE-99, CODE-100).

The twin of ``clients/neutralino/tests/private-server.test.ts``. Everything outside the server's process is faked by a
small computer that knows which port holds what; the real health check, the port check, the presence socket and the
setup code are covered at the bottom.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import socket
import stat
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from claudia_shell_gtk import private_server
from claudia_shell_gtk.owner_key import OWNER_KEY_FILE
from claudia_shell_gtk.private_server import (
    IDLE_SECONDS,
    STATE_FILE,
    Health,
    PrivateServer,
    is_port_free,
    probe_health,
    read_instead,
)
from claudia_shell_gtk.server import ServerStartError

VERSION = "0.40.0"
APPS = ("composes", "computes", "creates")
ANNA = 501  # her port: 20501
BEN = 502  # his port: 20502


def wait_for(condition: Callable[[], bool], seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


class FakeSocket:
    """A presence connection that the test drops by hand."""

    def __init__(self) -> None:
        self.closed = False
        self._ended = threading.Event()

    def wait_closed(self) -> None:
        self._ended.wait()

    def close(self) -> None:
        self.closed = True
        self._ended.set()

    def drop(self) -> None:
        self._ended.set()


@dataclass
class FakeServer:
    owner: str | None  # None: a shared server
    version: str = VERSION
    apps: tuple[str, ...] = APPS
    documents: str = ""


class FakeComputer:
    """What runs on which port: Claudia servers (a person's, or a shared one), programs that answer but are not Claudia
    (``other``), and ports held by something that says nothing (``silent``)."""

    def __init__(self) -> None:
        self.servers: dict[int, FakeServer] = {}
        self.other: set[int] = set()
        self.silent: set[int] = set()
        self.starts: list[tuple[str, int, list[str], Path]] = []

    def health(self, port: int) -> Health:
        server = self.servers.get(port)
        if server is not None:
            return Health("claudia", server.apps, server.version)
        return Health("other") if port in self.other else Health("none")

    def free(self, port: int) -> bool:
        return port not in self.servers and port not in self.other and port not in self.silent


def _port(url: str) -> int:
    return urlsplit(url).port or 0


class Window:
    """A window of ``person``: a ``PrivateServer`` with her own state folder and account number."""

    def __init__(
        self,
        computer: FakeComputer,
        person: str,
        uid: int,
        state: Path,
        *,
        app: str = "computes",
        version: str | None = VERSION,
        port: int | None = None,
        start_fails: Exception | None = None,
    ) -> None:
        self.state = state
        self.probed: list[int] = []
        self.sockets: list[FakeSocket] = []
        window = self

        class Process:
            def __init__(self, command: list[str], url: str, log: Path) -> None:
                self.command, self.url, self.log = command, url, log

            def start(self) -> str:
                port_ = _port(self.url)
                computer.starts.append((person, port_, self.command, self.log))
                if start_fails is not None:
                    raise start_fails
                if not computer.free(port_):
                    raise ServerStartError(f"port {port_} is in use", exited=True)
                documents = self.command[self.command.index("--dir") + 1]
                # The server's own lock on its folder (D435): a second server of the same documents exits at start-up.
                if any(running.documents == documents for running in computer.servers.values()):
                    raise ServerStartError(
                        "the server stopped at start-up (exit code 2)\nerror: another Claudia server uses "
                        f"{documents}; stop it first, or give this one another folder",
                        exited=True,
                    )
                computer.servers[port_] = FakeServer(person, documents=documents)
                return self.url

            def stop(self) -> None: ...

        def probe(url: str) -> Health:
            window.probed.append(_port(url))
            return computer.health(_port(url))

        def connect(_url: str) -> FakeSocket:
            made = FakeSocket()
            window.sockets.append(made)
            return made

        server = computer.servers.get
        self.server = PrivateServer(
            app=app,
            python="/repo/.venv/bin/python",
            web=Path("/frontend"),
            documents=Path(f"/home/{person}/documents"),
            state=state,
            uid=uid,
            port=port,
            race_wait=0.05,
            probe=probe,
            is_mine=lambda url: (found := server(_port(url))) is not None and found.owner == person,
            make_server=Process,
            port_free=computer.free,
            version=lambda: version,
            connect=connect,
            sleep=lambda _seconds: time.sleep(0.001),  # work: the code's own pause between tries, made short
        )


@pytest.fixture
def computer() -> FakeComputer:
    return FakeComputer()


@pytest.fixture
def windows() -> Iterator[list[Window]]:
    made: list[Window] = []
    yield made
    for window in made:
        window.server.stop()


@pytest.fixture
def open_window(tmp_path: Path, computer: FakeComputer, windows: list[Window]):
    def open_(person: str, uid: int, *, state: Path | None = None, **options: object) -> Window:
        folder = state or tmp_path / person / "state"
        folder.mkdir(parents=True, exist_ok=True)
        window = Window(computer, person, uid, folder, **options)  # type: ignore[arg-type]
        windows.append(window)
        return window

    return open_


def test_starts_her_server_on_her_own_port_with_the_key_that_makes_it_hers(open_window, computer) -> None:
    window = open_window("anna", ANNA)
    assert window.server.start() == "http://127.0.0.1:20501"
    _person, port, command, log = computer.starts[0]
    assert port == 20501
    assert command[command.index("--owner-key-file") + 1] == str(window.state / OWNER_KEY_FILE)
    assert command[command.index("--exit-when-idle") + 1] == str(IDLE_SECONDS)
    assert "--model" not in command  # all three apps (D445)
    assert log == window.state / "server.log"
    key_file = window.state / OWNER_KEY_FILE
    assert len(key_file.read_text(encoding="utf-8").strip()) == 64
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_her_three_apps_share_her_private_place(open_window, computer) -> None:
    first = open_window("anna", ANNA, app="composes")
    first.server.start()
    second = open_window("anna", ANNA, app="computes", state=first.state)
    assert second.server.start() == "http://127.0.0.1:20501"
    assert len(computer.starts) == 1


def test_keeps_her_key_and_makes_a_new_one_when_the_file_holds_none(open_window, computer) -> None:
    first = open_window("anna", ANNA)
    first.server.start()
    first.server.stop()
    key_file = first.state / OWNER_KEY_FILE
    key = key_file.read_text(encoding="utf-8")
    computer.servers.clear()
    open_window("anna", ANNA, state=first.state).server.start()
    assert key_file.read_text(encoding="utf-8") == key
    key_file.write_text("not a key", encoding="utf-8")
    computer.servers.clear()
    open_window("anna", ANNA, state=first.state).server.start()
    assert len(key_file.read_text(encoding="utf-8").strip()) == 64


# CODE-99
def test_two_people_of_one_computer_each_get_their_own_server(open_window, computer) -> None:
    open_window("anna", ANNA, app="composes").server.start()
    assert open_window("ben", BEN, app="composes").server.start() == "http://127.0.0.1:20502"
    assert computer.servers[20502].owner == "ben"
    assert computer.servers[20502].documents == "/home/ben/documents"
    assert computer.servers[20501].documents == "/home/anna/documents"


# CODE-99
def test_his_server_is_still_his_after_the_other_person_has_logged_out(open_window, computer) -> None:
    open_window("anna", ANNA).server.start()
    ben = open_window("ben", BEN)
    before = ben.server.start()
    del computer.servers[20501]  # Anna logged out
    del computer.servers[20502]  # Ben's server stopped while idle
    assert open_window("ben", BEN, state=ben.state).server.start() == before
    assert computer.servers[20502].documents == "/home/ben/documents"


# CODE-99
def test_a_claudia_server_that_is_not_hers_on_her_port_is_not_taken_for_hers(open_window, computer, caplog) -> None:
    computer.servers[20501] = FakeServer("mallory")
    window = open_window("anna", ANNA)
    with caplog.at_level("INFO"):
        assert window.server.start() == "http://127.0.0.1:20502"
    assert computer.servers[20502].owner == "anna"
    assert read_instead(window.state / STATE_FILE) == 20502
    assert "20501" in caplog.text


# CODE-100
def test_a_shared_server_of_another_version_does_not_keep_her_apps_from_opening(open_window, computer) -> None:
    computer.servers[8765] = FakeServer(None, version="0.31.0")
    window = open_window("anna", ANNA)
    assert window.server.start() == "http://127.0.0.1:20501"
    assert 8765 not in window.probed


# CODE-100
def test_a_shared_server_of_another_version_on_her_port_is_not_hers_either(open_window, computer) -> None:
    computer.servers[20501] = FakeServer(None, version="0.31.0")
    assert open_window("anna", ANNA).server.start() == "http://127.0.0.1:20502"


def test_her_own_older_server_still_running_after_an_update_says_it_stops_by_itself(open_window, computer) -> None:
    computer.servers[20501] = FakeServer("anna", version="0.39.0")
    window = open_window("anna", ANNA)
    with pytest.raises(ServerStartError, match=r"0\.39\.0") as raised:
        window.server.start()
    assert "stops by itself ten minutes after its last window has closed" in str(raised.value)


def test_her_own_server_from_before_holding_her_documents_says_it_stops_by_itself(open_window, computer) -> None:
    computer.servers[8765] = FakeServer(None, version="0.39.0", documents="/home/anna/documents")  # no key, on 8765
    with pytest.raises(ServerStartError, match="older version") as raised:
        open_window("anna", ANNA).server.start()
    assert "stops by itself ten minutes after its last window has closed" in str(raised.value)


def test_does_not_insist_on_a_version_it_could_not_find_out(open_window, computer) -> None:
    computer.servers[20501] = FakeServer("anna", version="0.39.0")
    assert open_window("anna", ANNA, version=None).server.start() == "http://127.0.0.1:20501"


def test_refuses_her_own_server_when_it_does_not_serve_this_app(open_window, computer) -> None:
    computer.servers[20501] = FakeServer("anna", apps=("composes",))
    with pytest.raises(ServerStartError, match="does not serve computes"):
        open_window("anna", ANNA).server.start()


# --------------------------------------------------------------------- a program that is not her server on her port


def test_her_server_goes_elsewhere_for_this_start_and_her_other_apps_find_it(open_window, computer) -> None:
    computer.other.add(20501)
    first = open_window("anna", ANNA, app="composes")
    assert first.server.start() == "http://127.0.0.1:20502"
    assert open_window("anna", ANNA, app="creates", state=first.state).server.start() == "http://127.0.0.1:20502"
    assert len(computer.starts) == 1


def test_the_next_start_tries_her_usual_address_again(open_window, computer) -> None:
    computer.other.add(20501)
    first = open_window("anna", ANNA)
    first.server.start()
    computer.other.discard(20501)
    del computer.servers[20502]  # her server stopped while idle
    assert open_window("anna", ANNA, state=first.state).server.start() == "http://127.0.0.1:20501"
    assert read_instead(first.state / STATE_FILE) is None


def test_something_that_holds_her_port_and_says_nothing_counts_as_well(open_window, computer) -> None:
    computer.silent.add(20501)
    assert open_window("anna", ANNA).server.start() == "http://127.0.0.1:20502"


def test_her_server_still_running_on_the_other_port_is_used_also_once_her_port_is_free(open_window, computer) -> None:
    computer.other.add(20501)
    first = open_window("anna", ANNA, app="composes")
    assert first.server.start() == "http://127.0.0.1:20502"
    computer.other.discard(20501)  # the program went; her server still runs where it went, with her documents
    assert open_window("anna", ANNA, app="computes", state=first.state).server.start() == "http://127.0.0.1:20502"
    assert len(computer.starts) == 1


def test_two_of_her_windows_starting_at_once_while_her_port_is_held_share_one_server(open_window, computer) -> None:
    computer.other.add(20501)
    first = open_window("anna", ANNA, app="composes")
    second = open_window("anna", ANNA, app="creates", state=first.state)
    urls: list[str] = []
    threads = [threading.Thread(target=lambda w=w: urls.append(w.server.start())) for w in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert urls == ["http://127.0.0.1:20502", "http://127.0.0.1:20502"]
    assert [server.owner for server in computer.servers.values()].count("anna") == 1


def test_the_walk_stays_in_her_range(open_window, computer) -> None:
    computer.other.add(29999)
    assert open_window("anna", 9999).server.start() == "http://127.0.0.1:20000"  # her port: 29999


def test_a_server_on_the_other_port_that_is_not_hers_is_not_used_either(open_window, computer) -> None:
    computer.other.add(20501)
    window = open_window("anna", ANNA)
    (window.state / STATE_FILE).write_text(json.dumps({"instead": 20502}), encoding="utf-8")
    computer.servers[20502] = FakeServer("ben")
    assert window.server.start() == "http://127.0.0.1:20503"
    assert read_instead(window.state / STATE_FILE) == 20503


def test_claudia_server_port_takes_the_place_of_her_usual_port(open_window) -> None:
    assert open_window("anna", ANNA, port=18765).server.start() == "http://127.0.0.1:18765"


# --------------------------------------------------------------------------------- two of her windows at once


def test_a_start_that_lost_to_another_one_uses_the_winner_when_it_is_hers(open_window, computer) -> None:
    lost = ServerStartError("the server stopped at start-up (exit code 2)", exited=True)
    window = open_window("anna", ANNA, start_fails=lost)
    threading.Timer(0.01, lambda: computer.servers.setdefault(20501, FakeServer("anna"))).start()
    assert window.server.start() == "http://127.0.0.1:20501"


def test_does_not_take_a_winner_that_is_not_hers(open_window, computer) -> None:
    lost = ServerStartError("the server stopped at start-up (exit code 2)", exited=True)
    window = open_window("anna", ANNA, start_fails=lost)
    threading.Timer(0.01, lambda: computer.servers.setdefault(20501, FakeServer("mallory"))).start()
    with pytest.raises(ServerStartError) as raised:
        window.server.start()
    assert raised.value is lost


def test_does_not_wait_for_another_server_when_its_own_simply_never_answered(open_window) -> None:
    slow = ServerStartError("the server did not answer")
    window = open_window("anna", ANNA, start_fails=slow)
    with pytest.raises(ServerStartError) as raised:
        window.server.start()
    assert raised.value is slow
    assert window.probed == [20501]  # the one look before starting, none after


# ------------------------------------------------------------------------------------- as the window uses it


def test_spawn_finds_the_server_without_blocking_and_check_ready_says_when(open_window) -> None:
    window = open_window("anna", ANNA)
    window.server.spawn()
    wait_for(window.server.check_ready)
    assert window.server.url == "http://127.0.0.1:20501"


def test_check_ready_raises_what_went_wrong(open_window, computer) -> None:
    computer.servers[20501] = FakeServer("anna", apps=("composes",))
    window = open_window("anna", ANNA)
    window.server.spawn()
    with pytest.raises(ServerStartError):
        wait_for(lambda: window.server.check_ready())


# ------------------------------------------------------------------------------------------------- presence


def test_keeps_a_presence_connection_and_lets_go_of_it_not_of_the_server(open_window, computer) -> None:
    window = open_window("anna", ANNA)
    window.server.start()
    wait_for(lambda: len(window.sockets) == 1)
    window.server.stop()
    assert window.sockets[0].closed
    assert 20501 in computer.servers  # closing a window does not stop the server


def test_starts_her_server_again_on_the_same_port_when_it_has_gone(open_window, computer) -> None:
    window = open_window("anna", ANNA)
    window.server.start()
    wait_for(lambda: len(window.sockets) == 1)
    del computer.servers[20501]  # the server stopped
    window.sockets[0].drop()
    wait_for(lambda: len(computer.starts) == 2)
    assert [start[1] for start in computer.starts] == [20501, 20501]
    wait_for(lambda: len(window.sockets) == 2)


def test_starts_her_server_again_where_the_page_is_also_when_her_port_has_come_free(open_window, computer) -> None:
    computer.other.add(20501)
    window = open_window("anna", ANNA)
    assert window.server.start() == "http://127.0.0.1:20502"
    wait_for(lambda: len(window.sockets) == 1)
    computer.other.discard(20501)
    del computer.servers[20502]  # her server stopped
    window.sockets[0].drop()
    wait_for(lambda: len(computer.starts) == 2)
    assert [start[1] for start in computer.starts] == [20502, 20502]
    assert window.server.url == "http://127.0.0.1:20502"


def test_connects_again_without_starting_anything_when_her_server_is_still_there(open_window, computer) -> None:
    window = open_window("anna", ANNA)
    window.server.start()
    wait_for(lambda: len(window.sockets) == 1)
    window.sockets[0].drop()
    wait_for(lambda: len(window.sockets) == 2)
    assert len(computer.starts) == 1


# ------------------------------------------------------------------------------------------- the real pieces


def test_the_state_file_reads_the_other_port_and_nothing_from_a_missing_broken_silly_or_older_file(tmp_path) -> None:
    file = tmp_path / STATE_FILE
    assert read_instead(file) is None
    file.write_text('{"instead": 41233}', encoding="utf-8")
    assert read_instead(file) == 41233
    older = '{"port": 41233}'  # before E8.5: the port the one shared server went to
    nonsense = ['{"instead": "41233"}', '{"instead": 0}', '{"instead": 70000}', '{"instead": true}']
    for bad in ["", "x", "[]", older, *nonsense]:
        file.write_text(bad, encoding="utf-8")
        assert read_instead(file) is None


def test_a_port_is_not_free_while_something_listens_on_it() -> None:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        assert not is_port_free(port)
    assert is_port_free(port)


class _Answering:
    """An HTTP server on loopback that answers every GET with ``status`` and ``body``."""

    def __init__(self, status: int, body: str) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (the standard library's name)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())

            def log_message(self, *_args: object) -> None: ...

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            200,
            '{"ok": true, "apps": ["composes", "creates"], "version": "0.32.0"}',
            Health("claudia", ("composes", "creates"), "0.32.0"),
        ),
        (200, '{"ok": true, "apps": ["composes"]}', Health("claudia", ("composes",), None)),
        (200, '{"ok": true}', Health("other")),  # a server from before D444 has no apps
        (200, "<html>", Health("other")),
        (500, '{"ok": true, "apps": []}', Health("other")),
    ],
)
def test_probe_health_knows_a_claudia_server_by_its_answer(status: int, body: str, expected: Health) -> None:
    answering = _Answering(status, body)
    try:
        assert probe_health(answering.url) == expected
    finally:
        answering.close()


def test_probe_health_says_none_when_nobody_answers() -> None:
    answering = _Answering(200, "{}")
    url = answering.url
    answering.close()
    assert probe_health(url) == Health("none")


class _PresenceServer:
    """A WebSocket server that accepts one connection, pings it, and closes it when told to; it records the pong."""

    def __init__(self) -> None:
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.url = f"ws://127.0.0.1:{self.listener.getsockname()[1]}/api/presence"
        self.pong = threading.Event()
        self.path = ""
        self.connection: socket.socket | None = None
        self.accepted = threading.Event()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        connection, _ = self.listener.accept()
        self.connection = connection
        head = b""
        while b"\r\n\r\n" not in head:
            head += connection.recv(1024)
        lines = head.decode().split("\r\n")
        self.path = lines[0].split()[1]
        key = next(line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1((key + private_server._GUID).encode()).digest()).decode()  # noqa: S324
        connection.sendall(
            f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode()
        )
        connection.sendall(bytes([0x89, 4]) + b"ping")  # a ping, unmasked as from a server
        self.accepted.set()
        first = connection.recv(2)
        if first and first[0] & 0x0F == 0xA:
            length = first[1] & 0x7F
            mask = connection.recv(4)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(connection.recv(length)))
            if payload == b"ping":
                self.pong.set()

    def end(self) -> None:
        assert self.connection is not None
        self.connection.sendall(bytes([0x88, 2]) + (1001).to_bytes(2, "big"))
        self.connection.close()
        self.listener.close()


def _wait_then_set(socket_: private_server._WebSocket, done: threading.Event) -> None:
    socket_.wait_closed()
    done.set()


def test_the_presence_socket_answers_pings_and_notices_the_end() -> None:
    server = _PresenceServer()
    socket_ = private_server._WebSocket(server.url)
    done = threading.Event()
    threading.Thread(target=_wait_then_set, args=(socket_, done), daemon=True).start()
    assert server.pong.wait(5), "the ping was not answered"
    assert server.path == "/api/presence"
    assert not done.is_set()
    server.end()
    assert done.wait(5)


def test_closing_the_presence_socket_ends_the_wait() -> None:
    server = _PresenceServer()
    socket_ = private_server._WebSocket(server.url)
    done = threading.Event()
    threading.Thread(target=_wait_then_set, args=(socket_, done), daemon=True).start()
    server.accepted.wait(5)
    socket_.close()
    assert done.wait(5)


# ------------------------------------------------------------------------------------- the setup code (D1373)
def test_the_setup_code_is_read_from_the_servers_state_folder_each_time(tmp_path: Path) -> None:
    from claudia_shell_gtk.private_server import read_setup_code

    assert read_setup_code(tmp_path) is None
    (tmp_path / "admin").mkdir()
    code = tmp_path / "admin" / "setup-code"
    code.write_text("K7QM-4TXR-92HB\n", encoding="utf-8")
    assert read_setup_code(tmp_path) == "K7QM-4TXR-92HB"
    code.write_text("2W9C-HQ4M-7KXA\n", encoding="utf-8")  # the server restarted
    assert read_setup_code(tmp_path) == "2W9C-HQ4M-7KXA"
    code.write_text("not a code at all\n", encoding="utf-8")
    assert read_setup_code(tmp_path) is None
    code.unlink()  # an administrator was named
    assert read_setup_code(tmp_path) is None


def test_only_a_page_of_the_shells_own_server_gets_the_code() -> None:
    from claudia_shell_gtk.private_server import setup_code_for_page

    def read() -> str:
        return "K7QM-4TXR-92HB"

    assert setup_code_for_page("http://127.0.0.1:8765", "http://127.0.0.1:8765", read) == "K7QM-4TXR-92HB"
    assert setup_code_for_page("http://127.0.0.1:8765/admin/", "http://127.0.0.1:8765", read) == "K7QM-4TXR-92HB"
    assert setup_code_for_page("https://claudia.example.org", "http://127.0.0.1:8765", read) is None
    assert setup_code_for_page("http://127.0.0.1:8766", "http://127.0.0.1:8765", read) is None
    assert setup_code_for_page(None, "http://127.0.0.1:8765", read) is None
    assert setup_code_for_page("http://127.0.0.1:8765", None, read) is None
