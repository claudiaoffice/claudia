"""What password hashing costs for the documents this server makes from now on (D1267).

A server measures what it can bear once at start, in a background thread so that it is up at once (``calibrate`` in
``claudia_document_file.kdf``), and an administrator can change the target time in Server settings ▸ Security, which
measures again. Until a measuring is done the floor (claudia-document-file's default) is used, so a document made in the
first seconds is never made with less than the minimum. A document keeps the cost it was made with: this applies to new
ones.
"""

import logging
import math
import threading
from collections.abc import Callable

from claudia_document_file import KdfParams, calibrate
from claudia_document_file.kdf import DEFAULT_MAX_MEMORY_KIB, DEFAULT_TARGET_SECONDS

from .i18n import msg

log = logging.getLogger("claudia_server")

MIN_TARGET_SECONDS = 0.1
MAX_TARGET_SECONDS = 30.0


def check_target(value: object) -> float:
    """``value`` as a target time in seconds; ``ValueError`` with a sentence for anything that makes no sense."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or not MIN_TARGET_SECONDS <= value <= MAX_TARGET_SECONDS
    ):
        raise ValueError(
            msg(
                "the target must be a number of seconds from {low} to {high}",
                low=MIN_TARGET_SECONDS,
                high=f"{MAX_TARGET_SECONDS:g}",
            )
        )
    return float(value)


class KdfPolicy:
    """The current cost for new documents, measured in the background. ``current`` is what a document store asks."""

    def __init__(
        self,
        target_seconds: float = DEFAULT_TARGET_SECONDS,
        *,
        max_memory_kib: int = DEFAULT_MAX_MEMORY_KIB,
        floor: KdfParams | None = None,
        calibrate: Callable[..., KdfParams] = calibrate,
    ):
        self._target = check_target(target_seconds)
        self._max_memory_kib = max_memory_kib
        self._floor = floor or KdfParams.default()
        self._calibrate = calibrate
        self._params = self._floor
        self._measured = False
        self._started = False
        self._generation = 0  # one per measuring asked for: an older one that ends late is not used
        self._finished = 0
        self._changed = threading.Condition()

    def current(self) -> KdfParams:
        """The cost for a document made now."""
        with self._changed:
            return self._params

    def describe(self) -> dict:
        """What the settings page shows: the target, the cost in force and whether it was measured yet."""
        with self._changed:
            return {"target_seconds": self._target, **self._params.to_dict(), "measured": self._measured}

    def start(self) -> None:
        """Measure in the background (once; later calls do nothing)."""
        with self._changed:
            if self._started:
                return
            self._started = True
        self._measure()

    def retarget(self, target_seconds: object) -> None:
        """Aim at another time from now on and measure again. ``ValueError`` if the time makes no sense."""
        target = check_target(target_seconds)
        with self._changed:
            self._target = target
            self._started = True
        self._measure()

    def wait(self, timeout: float) -> bool:
        """Block until the latest measuring asked for is done (``True``) or ``timeout`` seconds passed (for tests)."""
        with self._changed:
            return self._changed.wait_for(lambda: self._finished >= self._generation, timeout)

    def _set(self, params: KdfParams) -> None:
        with self._changed:
            self._params, self._measured = params, True

    def _measure(self) -> None:
        with self._changed:
            self._generation += 1
            generation, target = self._generation, self._target
        calibrate_now = self._calibrate

        def run() -> None:
            result = None
            try:
                result = calibrate_now(target, max_memory_kib=self._max_memory_kib, floor=self._floor)
            except Exception:  # a machine that cannot measure keeps the floor: a login must never fail for it
                log.warning("could not measure the cost of password hashing; keeping the minimum", exc_info=True)
            with self._changed:
                if result is not None and generation == self._generation:
                    self._params, self._measured = result, True
                    log.info("password hashing for new documents: %s", result)
                self._finished = max(self._finished, generation)
                self._changed.notify_all()

        threading.Thread(target=run, name="claudia-kdf", daemon=True).start()
