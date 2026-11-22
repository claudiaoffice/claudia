"""``./run-e2e.sh`` (``scripts/run_e2e.py``): the parts that decide whether a run can go on."""

from __future__ import annotations

import argparse
import os
import socket


def _runner(run_e2e):
    return run_e2e.Runner(argparse.Namespace(shots=None, dry_run=True))


def test_a_port_a_stopped_server_has_just_closed_is_free(run_e2e):
    """A server that closed its connections first leaves them in TIME_WAIT; the next server binds its port anyway
    (SO_REUSEADDR), so the runner must not call the port busy. It did, and every run stopped after the shared servers
    with "port 8766 is in use" (PROC-49)."""
    with socket.socket() as server:
        if os.name != "nt":
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # as uvicorn's asyncio server does
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        client = socket.create_connection(("127.0.0.1", port))
        accepted, _ = server.accept()
        accepted.close()  # the server's side closes first: its end of the connection waits in TIME_WAIT
        client.close()
    assert _runner(run_e2e)._free(port)


def test_a_port_someone_listens_on_is_busy(run_e2e):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        assert not _runner(run_e2e)._free(server.getsockname()[1])
