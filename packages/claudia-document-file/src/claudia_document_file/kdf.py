"""The cost of password hashing for new documents, chosen from what the machine can do (D1267).

A password is as hard to guess offline as the hashing is slow, so the cost should be as high as the server can bear
without making a login feel broken. What a fixed number means differs a lot between a laptop and a small server, so a
server measures itself once at start (:func:`calibrate`) and uses what it finds for the documents it makes from then on.
A document keeps the cost it was made with (``KdfParams``), so this changes nothing about existing ones.

The measuring is a parameter, so the decision can be tested without depending on the speed of the machine.
"""

import time
from collections.abc import Callable

from .crypto import MAX_ITERATIONS, MAX_MEMORY_KIB, KdfParams, argon2id

DEFAULT_TARGET_SECONDS = 0.75
"""How long hashing a password should take for new documents: slow enough to hurt a guesser, quick enough to log in."""
DEFAULT_MAX_MEMORY_KIB = 256 * 1024
"""The most memory a calibrated cost asks for (256 MiB): a few logins at once must still fit on a small server."""


def measure_once(params: KdfParams) -> float:
    """The seconds one real hash with ``params`` takes here (the better of two runs, to leave out a hiccup)."""
    password, salt = b"calibration", b"claudia-calibrate"
    best = float("inf")
    for _ in range(2):
        started = time.perf_counter()
        argon2id(password, salt, params, 32)
        best = min(best, time.perf_counter() - started)
    return best


def calibrate(
    target_seconds: float = DEFAULT_TARGET_SECONDS,
    *,
    max_memory_kib: int = DEFAULT_MAX_MEMORY_KIB,
    floor: KdfParams | None = None,
    measure: Callable[[KdfParams], float] = measure_once,
) -> KdfParams:
    """The cost whose hash takes about ``target_seconds`` here: all the memory allowed, then the passes that fill it.

    Memory is what makes guessing expensive on special hardware, so it comes first: the result starts at
    ``max_memory_kib`` and gives memory up (halving it) only while even the passes of ``floor`` would take longer than
    the target. It is never weaker than ``floor`` in any respect, so a slow machine gets the floor, which may take
    longer than the target; a security minimum is not traded for speed. The lanes are the floor's.
    """
    floor = floor or KdfParams.default()
    lanes = floor.lanes
    memory = max(floor.memory_kib, min(max_memory_kib, MAX_MEMORY_KIB))
    memory -= memory % (8 * lanes)
    one_pass = measure(KdfParams(iterations=1, memory_kib=memory, lanes=lanes))
    while memory > floor.memory_kib and one_pass * floor.iterations > target_seconds:
        memory = max(floor.memory_kib, memory // 2)
        memory -= memory % (8 * lanes)
        memory = max(memory, floor.memory_kib)
        one_pass = measure(KdfParams(iterations=1, memory_kib=memory, lanes=lanes))
    passes = round(target_seconds / one_pass) if one_pass > 0 else MAX_ITERATIONS
    return KdfParams(iterations=min(MAX_ITERATIONS, max(floor.iterations, passes)), memory_kib=memory, lanes=lanes)
