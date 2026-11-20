"""Choosing the cost of password hashing for new documents from what this machine can do (D1267).

The measuring is injected, so these tests are about the decision and not about the speed of the machine that runs them.
"""

import pytest

from claudia_container import KdfParams, calibrate
from claudia_container.crypto import MAX_ITERATIONS

FLOOR = KdfParams(iterations=3, memory_kib=64 * 1024, lanes=4)
MIB = 1024


def machine(seconds_per_pass_per_mib: float):
    """A pretend machine: a pass over ``m`` MiB takes ``m * rate`` seconds, whatever the lanes."""

    def measure(params: KdfParams) -> float:
        return params.iterations * (params.memory_kib / MIB) * seconds_per_pass_per_mib

    return measure


def test_a_fast_machine_gets_the_most_memory_and_the_passes_that_fill_the_target():
    chosen = calibrate(0.75, max_memory_kib=256 * MIB, floor=FLOOR, measure=machine(0.75 / 4 / 256))
    assert chosen == KdfParams(iterations=4, memory_kib=256 * MIB, lanes=4)


def test_the_result_takes_about_the_target_time():
    measure = machine(0.002)
    chosen = calibrate(0.75, max_memory_kib=256 * MIB, floor=FLOOR, measure=measure)
    assert measure(chosen) == pytest.approx(0.75, rel=0.4)


def test_a_slow_machine_gets_less_memory_before_it_gets_fewer_passes_than_the_floor():
    measure = machine(0.01)  # 64 MiB × 3 passes already take 1.92 s
    chosen = calibrate(0.75, max_memory_kib=256 * MIB, floor=FLOOR, measure=measure)
    assert chosen == FLOOR, "never weaker than the floor, even if that is slower than the target"


def test_a_machine_in_between_trades_memory_for_time():
    chosen = calibrate(0.75, max_memory_kib=256 * MIB, floor=FLOOR, measure=machine(0.003))
    assert FLOOR.memory_kib <= chosen.memory_kib < 256 * MIB
    assert chosen.iterations >= FLOOR.iterations


def test_the_memory_never_goes_over_what_the_server_may_use():
    chosen = calibrate(5.0, max_memory_kib=128 * MIB, floor=FLOOR, measure=machine(0.0001))
    assert chosen.memory_kib == 128 * MIB


def test_the_passes_never_go_over_what_a_file_may_ask_for():
    chosen = calibrate(5.0, max_memory_kib=64 * MIB, floor=FLOOR, measure=machine(0.00001))
    assert chosen.iterations == MAX_ITERATIONS


def test_a_cap_below_the_floor_is_still_the_floor():
    chosen = calibrate(0.75, max_memory_kib=16 * MIB, floor=FLOOR, measure=machine(0.0001))
    assert chosen.memory_kib == FLOOR.memory_kib


def test_the_lanes_stay_those_of_the_floor():
    chosen = calibrate(0.75, max_memory_kib=256 * MIB, floor=KdfParams(3, 64 * MIB, 2), measure=machine(0.001))
    assert chosen.lanes == 2


def test_the_default_measuring_really_hashes():
    params = KdfParams(iterations=1, memory_kib=1024, lanes=1)
    from claudia_container.kdf import measure_once

    assert 0 < measure_once(params) < 5
