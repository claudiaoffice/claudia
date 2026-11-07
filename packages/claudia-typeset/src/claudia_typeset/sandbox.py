"""Running an engine as a process that cannot do harm (E3.10).

This is the v1 runner behind a small interface; the worker pool of E3.5 replaces it later. A process
gets a clean environment, no input, a folder of its own, limits on time, memory and what it writes, and a
way to be killed together with everything it started. How that is done depends on the system:

* Linux and macOS: resource limits set in the child, and a process group that is killed as a whole
  (macOS does not enforce an address-space limit).
* Windows: a Job Object (``_windows``) with a memory limit, a CPU limit, a limit on the number of
  processes, and kill-on-close.

On every system a watchdog also watches the size of the job folder, because a limit on single files does
not stop many files.
"""

import asyncio
import contextlib
import math
import os
import signal
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._environment import base_environment
from .job import Limits

_CHUNK = 65_536
_MB = 1024 * 1024
_OPEN_FILES = 256
_WATCH_INTERVAL = 0.2  # seconds between looks at the job folder
_MAX_ENTRIES = 10_000  # files and folders a job may leave behind
_REAP_SECONDS = 10.0  # how long a killed process may take to be gone


class SandboxError(Exception):
    """The process was stopped because it went past one of its limits."""


class Timeout(SandboxError):
    """The process took longer than its wall-clock (or CPU) limit and was killed."""


class OutputTooLarge(SandboxError):
    """The process wrote more than its limit, to the output or to its folder, and was killed."""


@dataclass(frozen=True)
class Completed:
    """A process that ended by itself: its exit code and everything it wrote, both streams together."""

    returncode: int
    output: str


class _PosixGuard:
    """Resource limits in the child and a process group of its own."""

    def __init__(self, limits: Limits) -> None:
        self._limits = limits

    @property
    def options(self) -> dict[str, Any]:
        return {"start_new_session": True, "preexec_fn": self._apply}  # noqa: PLW1509 - the only way to set rlimits

    def _apply(self) -> None:
        import resource  # noqa: PLC0415 - not available on Windows, which never gets here

        limits = self._limits
        cpu = math.ceil(limits.seconds) + 2  # later than the wall clock, so that reports first
        file_size = limits.output_mb * _MB
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))  # type: ignore[attr-defined] # POSIX only, not on Windows
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))  # type: ignore[attr-defined]
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))  # type: ignore[attr-defined]
        resource.setrlimit(resource.RLIMIT_NOFILE, (_OPEN_FILES, _OPEN_FILES))  # type: ignore[attr-defined]
        if sys.platform.startswith("linux"):  # macOS does not enforce RLIMIT_AS
            memory = limits.memory_mb * _MB
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))  # type: ignore[attr-defined]

    def attach(self, pid: int) -> None:
        """Nothing to do: the limits are already in the child."""

    def kill(self, pid: int) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):  # nothing of the group may be left
            os.killpg(pid, signal.SIGKILL)  # type: ignore[attr-defined] # POSIX only, not on Windows

    def close(self) -> None:
        """Nothing to release."""


class _WindowsGuard:
    """A Job Object that the process is put into right after it starts."""

    def __init__(self, limits: Limits) -> None:
        from ._windows import WindowsJob  # noqa: PLC0415 - Windows only

        self._job = WindowsJob(limits)

    @property
    def options(self) -> dict[str, Any]:
        from ._windows import CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW  # noqa: PLC0415 - Windows only

        return {"creationflags": CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}

    def attach(self, pid: int) -> None:
        try:
            self._job.assign(pid)
        except OSError as error:
            raise SandboxError(
                f"the process could not be put under limits ({error}); it was not allowed to run"
            ) from error

    def kill(self, pid: int) -> None:
        self._job.terminate()

    def close(self) -> None:
        self._job.close()


def _guard(limits: Limits) -> _PosixGuard | _WindowsGuard:
    return _WindowsGuard(limits) if sys.platform == "win32" else _PosixGuard(limits)


async def _collect(stream: asyncio.StreamReader, cap: int) -> bytes:
    data = bytearray()
    while chunk := await stream.read(_CHUNK):
        data += chunk
        if len(data) > cap:
            raise OutputTooLarge(f"more than {cap // _MB} MB of output")
    return bytes(data)


def _check_folder(folder: Path, cap: int) -> None:
    """Raise `OutputTooLarge` if ``folder`` holds more than ``cap`` bytes or too many entries (links: not followed)."""
    total = entries = 0
    pending = [folder]
    while pending:
        try:
            with os.scandir(pending.pop()) as scan:
                for entry in scan:
                    entries += 1
                    if entries > _MAX_ENTRIES:
                        raise OutputTooLarge(f"the job left more than {_MAX_ENTRIES} files behind")
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
                        if total > cap:
                            raise OutputTooLarge(f"the job wrote more than {cap // _MB} MB to its folder")
        except FileNotFoundError:
            continue  # something was removed while we looked


async def _watch_folder(folder: Path, cap: int) -> None:
    while True:
        await asyncio.sleep(_WATCH_INTERVAL)
        _check_folder(folder, cap)


async def _drain(process: asyncio.subprocess.Process, folder: Path, limits: Limits) -> bytes:
    assert process.stdout is not None
    cap = limits.output_mb * _MB
    collecting = asyncio.create_task(_collect(process.stdout, cap))
    watching = asyncio.create_task(_watch_folder(folder, cap))
    try:
        async with asyncio.timeout(limits.seconds):
            await asyncio.wait({collecting, watching}, return_when=asyncio.FIRST_COMPLETED)
            if watching.done():
                watching.result()  # raises OutputTooLarge
            output = collecting.result()
            await process.wait()
            _check_folder(folder, cap)  # what was written after the last look
    except TimeoutError as error:
        raise Timeout(f"took longer than {limits.seconds:g} s") from error
    finally:
        for task in (collecting, watching):
            task.cancel()
        await asyncio.gather(collecting, watching, return_exceptions=True)
    return output


async def _reap(process: asyncio.subprocess.Process) -> None:
    """Wait for a killed process to be gone.

    The pipe is read to its end first: when we stopped reading because of a limit, the pipe never reports its
    end and ``wait()`` would wait for ever.
    """
    assert process.stdout is not None
    try:
        async with asyncio.timeout(_REAP_SECONDS):
            while await process.stdout.read(_CHUNK):
                pass
            await process.wait()
    except TimeoutError:
        pass  # reported by the caller: the process has no exit code


async def run_sandboxed(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    limits: Limits,
    search_path: Sequence[str | Path] = (),
) -> Completed:
    """Run ``argv`` in ``cwd`` with only ``env`` (plus a PATH) and the given limits; wait for it.

    The PATH is the system's own after the directories in ``search_path`` (where a LaTeX installation keeps the
    helper programs of the one that is run). Raises `Timeout` or `OutputTooLarge` when a limit is passed, and
    `SandboxError` if the process cannot be put under limits. However this ends, including when the caller is
    cancelled, the process and everything it started is killed.
    """
    guard = _guard(limits)
    environment = {**base_environment(sys.platform, os.environ, cwd, search_path), **env}
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=environment,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **guard.options,
        )
    except BaseException:
        guard.close()
        raise
    try:
        guard.attach(process.pid)
        output = await _drain(process, cwd, limits)
    finally:
        guard.kill(process.pid)
        await _reap(process)
        guard.close()
    returncode = process.returncode
    if returncode is None:
        raise SandboxError("the process could not be stopped")
    if sys.platform != "win32" and returncode == -signal.SIGXFSZ:
        raise OutputTooLarge(f"wrote a file larger than {limits.output_mb} MB")
    if sys.platform != "win32" and returncode == -signal.SIGXCPU:
        raise Timeout(f"used more than its CPU time ({limits.seconds:g} s)")
    return Completed(returncode, output.decode("utf-8", errors="replace"))
