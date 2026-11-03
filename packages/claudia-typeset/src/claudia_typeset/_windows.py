"""Windows Job Objects for the sandbox (E3.10, E8.1).

A Job Object is the Windows way to keep a process and everything it starts under limits: when the job is
terminated or closed, nothing of it survives (``KILL_ON_JOB_CLOSE``), and the system itself enforces a memory
limit, a CPU time limit and a limit on how many processes there may be. The structures are described with
fixed-size field types, so their layout is the same on any machine and can be checked without Windows.

This module has been written from the Windows documentation and checked there only through the tests that run
on a Windows machine (``test_typeset_sandbox_windows``).
"""

import ctypes
import math
from dataclasses import dataclass

from .job import Limits

LIMIT_PROCESS_TIME = 0x00000002
LIMIT_ACTIVE_PROCESS = 0x00000008
LIMIT_PROCESS_MEMORY = 0x00000100
LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

#: xelatex starts xdvipdfmx, and MiKTeX starts its engine through a launcher: a handful of processes, no swarm.
ACTIVE_PROCESSES = 16

#: Creation flags of the process: a group of its own, and no console window flashing up.
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_HUNDRED_NANOSECONDS = 10_000_000
_CPU_MARGIN_SECONDS = 2  # after the wall clock, so that the clock reports first

_DWORD = ctypes.c_uint32  # not wintypes.DWORD: that is 8 bytes on Linux and would change the layout
_SIZE_T = ctypes.c_size_t


class BasicLimits(ctypes.Structure):
    """JOBOBJECT_BASIC_LIMIT_INFORMATION."""

    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", _DWORD),
        ("MinimumWorkingSetSize", _SIZE_T),
        ("MaximumWorkingSetSize", _SIZE_T),
        ("ActiveProcessLimit", _DWORD),
        ("Affinity", _SIZE_T),
        ("PriorityClass", _DWORD),
        ("SchedulingClass", _DWORD),
    )


class IoCounters(ctypes.Structure):
    """IO_COUNTERS."""

    _fields_ = tuple((name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    ))  # fmt: skip


class ExtendedLimits(ctypes.Structure):
    """JOBOBJECT_EXTENDED_LIMIT_INFORMATION."""

    _fields_ = (
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", _SIZE_T),
        ("JobMemoryLimit", _SIZE_T),
        ("PeakProcessMemoryUsed", _SIZE_T),
        ("PeakJobMemoryUsed", _SIZE_T),
    )


@dataclass(frozen=True)
class JobLimitValues:
    """What the limits of a job come to in the units Windows uses."""

    flags: int
    process_memory: int  # bytes
    process_time: int  # 100 ns units of user-mode CPU time per process
    active_processes: int


def job_limit_values(limits: Limits) -> JobLimitValues:
    """The Job Object limits for ``limits``: everything switched on."""
    return JobLimitValues(
        flags=LIMIT_PROCESS_TIME | LIMIT_ACTIVE_PROCESS | LIMIT_PROCESS_MEMORY | LIMIT_KILL_ON_JOB_CLOSE,
        process_memory=limits.memory_mb * 1024 * 1024,
        process_time=(math.ceil(limits.seconds) + _CPU_MARGIN_SECONDS) * _HUNDRED_NANOSECONDS,
        active_processes=ACTIVE_PROCESSES,
    )


def fill_limits(info: ExtendedLimits, values: JobLimitValues) -> None:
    """Write ``values`` into the structure that ``SetInformationJobObject`` reads."""
    basic = info.BasicLimitInformation
    basic.LimitFlags = values.flags
    basic.PerProcessUserTimeLimit = values.process_time
    basic.ActiveProcessLimit = values.active_processes
    info.ProcessMemoryLimit = values.process_memory


def _kernel32():  # noqa: ANN202 - a ctypes library handle, which only exists on Windows
    from ctypes import wintypes  # noqa: PLC0415 - handle types, only needed here

    library = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only
    handle = wintypes.HANDLE  # explicit types: a 64-bit handle must never be squeezed into a 32-bit int
    library.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    library.CreateJobObjectW.restype = handle
    library.SetInformationJobObject.argtypes = (handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    library.SetInformationJobObject.restype = wintypes.BOOL
    library.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    library.OpenProcess.restype = handle
    library.AssignProcessToJobObject.argtypes = (handle, handle)
    library.AssignProcessToJobObject.restype = wintypes.BOOL
    library.TerminateJobObject.argtypes = (handle, ctypes.c_uint)
    library.TerminateJobObject.restype = wintypes.BOOL
    library.CloseHandle.argtypes = (handle,)
    library.CloseHandle.restype = wintypes.BOOL
    return library


class WindowsJob:
    """A Job Object with the limits of ``limits``; processes assigned to it cannot outlive it."""

    def __init__(self, limits: Limits) -> None:
        self._kernel = _kernel32()
        self._handle = self._kernel.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows only
        info = ExtendedLimits()
        fill_limits(info, job_limit_values(limits))
        if not self._kernel.SetInformationJobObject(
            self._handle, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        ):
            error = ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows only
            self.close()
            raise error

    def assign(self, pid: int) -> None:
        """Put the process ``pid`` (and so everything it starts from now on) into the job."""
        process = self._kernel.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows only
        try:
            if not self._kernel.AssignProcessToJobObject(self._handle, process):
                raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows only
        finally:
            self._kernel.CloseHandle(process)

    def terminate(self) -> None:
        """Kill every process of the job."""
        if self._handle:
            self._kernel.TerminateJobObject(self._handle, 1)

    def close(self) -> None:
        """Release the job; whatever is still in it is killed."""
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
