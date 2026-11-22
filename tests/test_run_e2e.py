"""``./run-e2e.sh`` (``scripts/run_e2e.py``): the parts that decide whether a run can go on."""

from __future__ import annotations

import argparse
import os
import re
import socket
from pathlib import Path


def _runner(run_e2e):
    return run_e2e.Runner(argparse.Namespace(shots=None, dry_run=True))


def test_a_port_a_stopped_server_has_just_closed_is_free(run_e2e):
    """A server that closed its connections first leaves them in TIME_WAIT; the next server binds its port anyway
    (SO_REUSEADDR), so the runner must not call the port busy. It did, and every run stopped after the shared servers
    with "port 8766 is in use" (PROC-51)."""
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


def test_every_browser_script_starts_its_browser_one_way():
    """One variable names a browser already on the computer, ``$CLAUDIA_CHROMIUM``, for the Python tests and the
    scripts alike. The scripts read ``CHROME``, ``CHROMIUM``, ``CLAUDIA_CHROMIUM`` or nothing (PROC-52): on a computer
    that cannot download Playwright's browser, most could not run. They start it through ``web/e2e/browser.cjs``."""
    scripts = sorted((Path(__file__).parent.parent / "web" / "e2e").glob("*.cjs"))
    own_way = [
        script.name
        for script in scripts
        if script.name != "browser.cjs" and re.search(r"\.launch\w*\(|process\.env\.(CHROME|CHROMIUM)\b", script.read_text())
    ]
    assert not own_way, f"these start a browser their own way, not through web/e2e/browser.cjs: {own_way}"
