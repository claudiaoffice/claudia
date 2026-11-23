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
    """Every script starts its browser through ``web/e2e/browser.cjs``, so that one variable, ``$CLAUDIA_CHROMIUM``,
    names a browser already on the computer for the Python tests and the scripts alike (CODE-17, D1453)."""
    scripts = sorted((Path(__file__).parent.parent / "web" / "e2e").glob("*.cjs"))
    own_way = [
        script.name
        for script in scripts
        if script.name != "browser.cjs"
        and re.search(r"\.launch\w*\(|process\.env\.(CHROME|CHROMIUM)\b", script.read_text())
    ]
    assert not own_way, f"these start a browser their own way, not through web/e2e/browser.cjs: {own_way}"


def test_a_failed_pytest_run_names_the_tests_that_failed(run_e2e, tmp_path, capsys):
    """CI shows only what the runner prints. A run of the specs that ended "1 failed, 140 passed" printed its last 20
    lines, all of them skipped scenarios, and not which test failed (PROC-52)."""
    specs = tmp_path / "test_some_specs.py"
    specs.write_text(
        "import pytest\n\n"
        "def test_this_one_fails():\n    assert False\n\n"
        + "".join(f"@pytest.mark.skip(reason='not yet {i}')\ndef test_skipped_{i}():\n    pass\n\n" for i in range(30))
    )
    runner = run_e2e.Runner(argparse.Namespace(shots=None, dry_run=False))
    try:
        assert not runner._record("proc-52-check", run_e2e.pytest_command(str(specs)))
    finally:
        (runner.logs / "proc-52-check.log").unlink(missing_ok=True)  # the runner keeps its logs in the repo's state
    assert "test_some_specs.py::test_this_one_fails" in capsys.readouterr().out
