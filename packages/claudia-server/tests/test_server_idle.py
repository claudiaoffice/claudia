"""A server that stops when nobody uses it (D434): the watch, the presence socket, and a real process."""

import asyncio
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from claudia_core.testing import FakeClock, ListModel
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app
from claudia_server.idle import IdleWatch


def test_the_server_is_idle_only_when_no_socket_is_open_and_no_request_came_for_long_enough():
    clock = FakeClock()
    fired = []
    watch = IdleWatch(60, on_idle=lambda: fired.append(True), clock=clock.lock_time)
    clock.advance(59)
    assert not watch.check()
    watch.opened()
    clock.advance(600)
    assert watch.idle_for() == 0 and not watch.check(), "an open socket keeps it in use however long"
    watch.closed()
    clock.advance(30)
    watch.touched()
    clock.advance(59)
    assert not watch.check() and not fired
    clock.advance(1)
    assert watch.check() and watch.check()
    assert fired == [True], "told once"


def test_the_idle_time_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        IdleWatch(0)


def app_with(watch, **options):
    return create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4), idle=watch, **options)


def test_requests_and_sockets_are_reported_to_the_watch():
    clock = FakeClock()
    watch = IdleWatch(60, clock=clock.lock_time)
    with TestClient(app_with(watch)) as client:
        clock.advance(50)
        client.get("/api/health")
        assert watch.idle_for() == 0
        with client.websocket_connect("/api/presence"):
            assert watch.open_sockets == 1
            clock.advance(500)
            assert watch.idle_for() == 0
        assert watch.open_sockets == 0


def test_the_presence_socket_needs_no_login_and_keeps_the_origin_rule():
    with TestClient(app_with(IdleWatch(60))) as client:
        with client.websocket_connect("/api/presence") as ws:
            ws.send_text("anything at all")  # ignored
        with (
            pytest.raises(WebSocketDisconnect) as refused,
            client.websocket_connect("/api/presence", headers={"origin": "https://evil.example"}),
        ):
            pass
    assert refused.value.code == 4403


def test_only_so_many_presence_sockets_are_held_at_once():
    with TestClient(app_with(None, max_waiting=1)) as client, client.websocket_connect("/api/presence"):
        with client.websocket_connect("/api/presence") as second, pytest.raises(WebSocketDisconnect) as full:
            second.receive_text()
        assert full.value.code == 1013


def test_the_watch_runs_with_the_server_and_asks_it_to_stop():
    stopped = asyncio.Event()

    async def scenario():
        watch = IdleWatch(0.05, on_idle=stopped.set, interval=0.01)
        await watch.start()
        await asyncio.wait_for(stopped.wait(), 2)
        await watch.stop()

    asyncio.run(scenario())


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_a_real_server_stops_by_itself_once_nobody_uses_it(tmp_path):
    port = _free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "claudia_server",
            "--no-tls",
            "--port",
            str(port),
            "--state-dir",
            str(tmp_path / "state"),
            "--dir",
            str(tmp_path / "docs"),
            "--exit-when-idle",
            "2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as answer:
                    assert answer.status == 200
                    break
            except OSError:
                time.sleep(0.2)
        assert server.wait(timeout=30) == 0
    finally:
        if server.poll() is None:
            server.kill()
    output = server.stdout.read()
    assert "nobody has used the server" in output or "Shutting down" in output
    assert not (tmp_path / "docs" / ".lock").read_text(), "the lock file stays; the lock went with the process"
