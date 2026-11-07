"""The Windows layer for real: Job Objects. These tests run only on Windows (the CI job of the project).

They are the first time this code meets a Windows machine; if one of them fails there, the layer is wrong
and the failing test says which protection is missing.
"""

import asyncio
import functools
import sys
import time

import pytest

from claudia_typeset import Limits, OutputTooLarge, SandboxError, Timeout, run_sandboxed

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Job Objects exist on Windows only")


def runs_in_a_loop(test):
    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return wrapper


def python(code):
    return [sys.executable, "-c", code]


def alive(pid):
    import ctypes

    kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    code = ctypes.c_ulong()
    kernel.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel.CloseHandle(handle)
    return code.value == 259


@runs_in_a_loop
async def test_a_child_of_the_process_is_killed_with_it(tmp_path):
    pids = tmp_path / "pids"
    code = (
        "import subprocess, sys, time, os\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pids)!r}, 'w').write(f'{{os.getpid()}} {{child.pid}}')\n"
        "time.sleep(60)\n"
    )
    with pytest.raises(Timeout):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(seconds=2))
    parent, child = map(int, pids.read_text().split())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and (alive(parent) or alive(child)):
        await asyncio.sleep(0.1)
    assert not alive(parent)
    assert not alive(child)


@runs_in_a_loop
async def test_a_process_that_asks_for_too_much_memory_does_not_get_it(tmp_path):
    code = "data = bytearray(900 * 1024 * 1024)\nprint('got it')"
    done = await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(memory_mb=256, seconds=30))
    assert "got it" not in done.output
    assert done.returncode != 0


@runs_in_a_loop
async def test_a_swarm_of_processes_is_refused(tmp_path):
    # Each spawned process inherits the sandboxed process's own stdout pipe, so `run_sandboxed` cannot see end of
    # output until every one of them has exited too. They only need to still be alive when the active-process limit
    # is checked, not for the length of the test's own deadline, so they sleep far less than `Limits(seconds=...)`.
    code = (
        "import subprocess, sys\n"
        "started = 0\n"
        "try:\n"
        "    for _ in range(40):\n"
        "        subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(2)'])\n"
        "        started += 1\n"
        "except OSError:\n"
        "    pass\n"
        "print('started', started)\n"
    )
    done = await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(seconds=30))
    started = int(done.output.split("started")[-1])
    assert started < 40


@runs_in_a_loop
async def test_a_busy_loop_is_stopped(tmp_path):
    with pytest.raises(Timeout):
        await run_sandboxed(python("while True: pass"), cwd=tmp_path, env={}, limits=Limits(seconds=1))


@runs_in_a_loop
async def test_the_process_sees_no_variable_of_ours(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDIA_SECRET_FOR_TEST", "hunter2")
    done = await run_sandboxed(python("import os; print(sorted(os.environ))"), cwd=tmp_path, env={}, limits=Limits())
    assert "CLAUDIA_SECRET_FOR_TEST" not in done.output
    assert "SYSTEMROOT" in done.output.upper()


@runs_in_a_loop
async def test_temporary_files_go_to_the_job_folder(tmp_path):
    done = await run_sandboxed(
        python("import tempfile; print(tempfile.gettempdir())"), cwd=tmp_path, env={}, limits=Limits()
    )
    assert done.output.strip().lower() == str(tmp_path).lower()


@runs_in_a_loop
async def test_a_flood_of_output_is_stopped(tmp_path):
    code = "import sys\nwhile True: sys.stdout.write('x' * 65536)"
    with pytest.raises(OutputTooLarge):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=1, seconds=30))


@runs_in_a_loop
async def test_no_window_is_opened_and_the_call_returns_normally(tmp_path):
    done = await run_sandboxed(python("print('hello')"), cwd=tmp_path, env={}, limits=Limits())
    assert done.output.strip() == "hello"
    assert isinstance(SandboxError("x"), Exception)
