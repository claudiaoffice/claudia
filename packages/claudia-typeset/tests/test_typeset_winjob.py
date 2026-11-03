"""What is asked of a Windows Job Object, checked on any machine; the real thing is in test_typeset_sandbox_windows.

The sizes are those the Windows documentation gives for 64-bit systems, so a wrong field type would show here.
"""

import ctypes

import pytest

from claudia_typeset import Limits
from claudia_typeset._windows import (
    ACTIVE_PROCESSES,
    LIMIT_ACTIVE_PROCESS,
    LIMIT_KILL_ON_JOB_CLOSE,
    LIMIT_PROCESS_MEMORY,
    LIMIT_PROCESS_TIME,
    BasicLimits,
    ExtendedLimits,
    IoCounters,
    fill_limits,
    job_limit_values,
)

pytestmark = pytest.mark.skipif(ctypes.sizeof(ctypes.c_void_p) != 8, reason="sizes are those of 64-bit Windows")


def test_the_structures_have_the_sizes_windows_expects():
    assert ctypes.sizeof(BasicLimits) == 64
    assert ctypes.sizeof(IoCounters) == 48
    assert ctypes.sizeof(ExtendedLimits) == 144


def test_the_limits_are_the_documented_flags():
    assert LIMIT_PROCESS_TIME == 0x2
    assert LIMIT_ACTIVE_PROCESS == 0x8
    assert LIMIT_PROCESS_MEMORY == 0x100
    assert LIMIT_KILL_ON_JOB_CLOSE == 0x2000


def test_every_protection_is_switched_on():
    values = job_limit_values(Limits(seconds=7, memory_mb=1024))
    assert values.flags == LIMIT_PROCESS_TIME | LIMIT_ACTIVE_PROCESS | LIMIT_PROCESS_MEMORY | LIMIT_KILL_ON_JOB_CLOSE


def test_the_memory_limit_is_in_bytes():
    assert job_limit_values(Limits(memory_mb=1024)).process_memory == 1024 * 1024 * 1024


def test_the_cpu_limit_is_in_hundreds_of_nanoseconds_and_a_little_after_the_clock():
    assert job_limit_values(Limits(seconds=7)).process_time == (7 + 2) * 10_000_000


def test_a_fraction_of_a_second_is_rounded_up_before_the_margin():
    assert job_limit_values(Limits(seconds=0.5)).process_time == (1 + 2) * 10_000_000


def test_a_job_may_run_a_few_programs_but_no_swarm():
    assert 4 <= job_limit_values(Limits()).active_processes <= ACTIVE_PROCESSES <= 32


def test_the_values_end_up_in_the_structure_windows_reads():
    values = job_limit_values(Limits(seconds=5, memory_mb=512))
    info = ExtendedLimits()
    fill_limits(info, values)
    assert info.BasicLimitInformation.LimitFlags == values.flags
    assert info.BasicLimitInformation.PerProcessUserTimeLimit == values.process_time
    assert info.BasicLimitInformation.ActiveProcessLimit == values.active_processes
    assert info.ProcessMemoryLimit == values.process_memory
