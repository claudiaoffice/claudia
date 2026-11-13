"""Running an engine as a process that cannot do harm: limits, clean environment, no survivors (E3.10)."""

import asyncio
import functools
import os
import sys
import time

import pytest

from claudia_typeset import Limits, OutputTooLarge, Timeout, run_sandboxed

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="resource limits and signals are POSIX")


def runs_in_a_loop(test):
    """The repository has no async test plugin: each test drives its coroutine with asyncio.run."""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return wrapper


def python(code):
    return [sys.executable, "-c", code]


def alive(pid):
    if sys.platform == "win32":  # os.kill(pid, 0) would end the process there
        import ctypes  # noqa: PLC0415

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def gone(*pids, within=3.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if not any(alive(pid) for pid in pids):
            return True
        await asyncio.sleep(0.05)
    return False


@runs_in_a_loop
async def test_the_output_and_the_exit_code_come_back(tmp_path):
    done = await run_sandboxed(python("print('hello'); import sys; sys.exit(3)"), cwd=tmp_path, env={}, limits=Limits())
    assert done.returncode == 3
    assert done.output.strip() == "hello"


@runs_in_a_loop
async def test_the_error_stream_comes_back_in_the_same_text(tmp_path):
    code = "import sys; print('out'); sys.stdout.flush(); print('err', file=sys.stderr)"
    done = await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits())
    assert "out" in done.output
    assert "err" in done.output


@runs_in_a_loop
async def test_the_process_runs_in_the_folder_it_was_given(tmp_path):
    done = await run_sandboxed(python("import os; print(os.getcwd())"), cwd=tmp_path, env={}, limits=Limits())
    assert os.path.realpath(done.output.strip()) == os.path.realpath(tmp_path)


@runs_in_a_loop
async def test_the_process_sees_the_environment_it_was_given_and_nothing_secret_of_ours(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDIA_SECRET_FOR_TEST", "hunter2")
    code = "import os; print(sorted(os.environ))"
    done = await run_sandboxed(python(code), cwd=tmp_path, env={"FONTCONFIG_FILE": "/x/fonts.conf"}, limits=Limits())
    assert "FONTCONFIG_FILE" in done.output
    assert "PATH" in done.output
    assert "CLAUDIA_SECRET_FOR_TEST" not in done.output


@runs_in_a_loop
async def test_the_process_gets_no_input(tmp_path):
    done = await run_sandboxed(
        python("import sys; print(repr(sys.stdin.read()))"), cwd=tmp_path, env={}, limits=Limits()
    )
    assert done.output.strip() == "''"


@runs_in_a_loop
async def test_a_process_that_takes_too_long_is_killed_and_reported(tmp_path):
    started = time.monotonic()
    with pytest.raises(Timeout):
        await run_sandboxed(python("import time; time.sleep(30)"), cwd=tmp_path, env={}, limits=Limits(seconds=0.5))
    assert time.monotonic() - started < 5


@runs_in_a_loop
async def test_a_busy_loop_is_stopped_too(tmp_path):
    with pytest.raises(Timeout):
        await run_sandboxed(python("while True: pass"), cwd=tmp_path, env={}, limits=Limits(seconds=0.5))


@runs_in_a_loop
async def test_the_processes_it_started_do_not_survive_it(tmp_path):
    pids = tmp_path / "pids"
    code = (
        "import subprocess, sys, time, os\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pids)!r}, 'w').write(f'{{os.getpid()}} {{child.pid}}')\n"
        "time.sleep(60)\n"
    )
    with pytest.raises(Timeout):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(seconds=1.5))
    parent, child = map(int, pids.read_text().split())
    assert await gone(parent, child)


@runs_in_a_loop
async def test_a_cancelled_run_kills_the_process(tmp_path):
    pidfile = tmp_path / "pid"
    code = f"import os, time; open({str(pidfile)!r}, 'w').write(str(os.getpid())); time.sleep(60)"
    task = asyncio.create_task(run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(seconds=30)))
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text():
            break
        await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await gone(int(pidfile.read_text()))


@runs_in_a_loop
async def test_more_output_than_allowed_stops_the_process(tmp_path):
    code = "import sys\nwhile True: sys.stdout.write('x' * 65536)"
    with pytest.raises(OutputTooLarge):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=1, seconds=20))


@posix_only
@runs_in_a_loop
async def test_the_resource_limits_are_set_in_the_process(tmp_path):
    code = (
        "import resource\n"
        "print(resource.getrlimit(resource.RLIMIT_FSIZE)[0], resource.getrlimit(resource.RLIMIT_CORE)[0])\n"
        "print(resource.getrlimit(resource.RLIMIT_CPU)[0])\n"
    )
    done = await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=2, seconds=7))
    fsize_and_core, cpu = done.output.split("\n")[:2]
    assert fsize_and_core == f"{2 * 1024 * 1024} 0"
    assert int(cpu) >= 7  # a little more than the wall clock, so the wall clock reports first


@posix_only
@runs_in_a_loop
async def test_a_process_killed_for_writing_too_big_a_file_is_reported_as_such(tmp_path):
    """TeX dies of SIGXFSZ when its log grows past the limit (Python ignores it, so the child restores the default)."""
    code = "import os, signal; signal.signal(signal.SIGXFSZ, signal.SIG_DFL); os.kill(os.getpid(), signal.SIGXFSZ)"
    with pytest.raises(OutputTooLarge):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits())


@runs_in_a_loop
async def test_many_files_that_are_each_small_are_stopped_by_the_size_of_the_folder(tmp_path):
    code = (
        "import itertools\n"
        "for number in itertools.count():\n"
        "    open(f'part{number}.bin', 'wb').write(b'x' * 200_000)\n"
    )
    started = time.monotonic()
    with pytest.raises(OutputTooLarge, match="folder"):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=1, seconds=30))
    assert time.monotonic() - started < 15


@runs_in_a_loop
async def test_a_swarm_of_empty_files_is_stopped_too(tmp_path):
    code = "for number in range(30_000):\n    open(f'f{number}', 'w').close()\n"
    with pytest.raises(OutputTooLarge, match="files"):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=1, seconds=30))


@runs_in_a_loop
async def test_what_is_written_just_before_the_end_is_counted_too(tmp_path):
    # each file is below the limit for a single file, so only the total can stop it, and the process ends
    # long before the watchdog's first look
    code = "for n in range(3): open(f'late{n}.bin', 'wb').write(b'x' * 600_000)"
    with pytest.raises(OutputTooLarge):
        await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(output_mb=1, seconds=30))


@runs_in_a_loop
async def test_a_link_to_a_big_file_outside_does_not_count_against_the_job(tmp_path):
    if sys.platform == "win32":
        pytest.skip("links need privileges on Windows")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.bin").write_bytes(b"x" * 3_000_000)
    folder = tmp_path / "job"
    folder.mkdir()
    (folder / "link").symlink_to(outside / "big.bin")
    done = await run_sandboxed(python("print('fine')"), cwd=folder, env={}, limits=Limits(output_mb=1))
    assert done.output.strip() == "fine"


@runs_in_a_loop
async def test_directories_to_search_are_in_the_path_of_the_process(tmp_path):
    code = "import os; print(os.environ['PATH'])"
    done = await run_sandboxed(python(code), cwd=tmp_path, env={}, limits=Limits(), search_path=[tmp_path / "tex-bin"])
    assert done.output.strip().startswith(str(tmp_path / "tex-bin") + os.pathsep)


@runs_in_a_loop
async def test_a_program_that_does_not_exist_is_reported_by_python_as_usual(tmp_path):
    with pytest.raises(FileNotFoundError):
        await run_sandboxed([str(tmp_path / "nowhere")], cwd=tmp_path, env={}, limits=Limits())


@posix_only
@runs_in_a_loop
async def test_a_browser_based_tool_can_be_run_without_the_address_space_limit(tmp_path):
    """V8 and Chromium reserve far more address space than they use: a limit of it stops them at once (D342)."""
    reserve = "import mmap; m = mmap.mmap(-1, 1 << 30); print('reserved')"
    limited = await run_sandboxed(python(reserve), cwd=tmp_path, env={}, limits=Limits(memory_mb=256, seconds=10))
    assert limited.returncode != 0, "a gigabyte of address space is refused under a 256 MB limit"
    free = Limits(memory_mb=256, seconds=10, address_space=False)
    done = await run_sandboxed(python(reserve), cwd=tmp_path, env={}, limits=free)
    assert done.returncode == 0 and "reserved" in done.output


def test_the_address_space_limit_is_on_unless_asked_off():
    assert Limits().address_space is True
