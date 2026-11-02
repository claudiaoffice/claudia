"""The only place the kernel reads a clock.

Everything else gets a clock injected, so tests and replay are deterministic."""

from __future__ import annotations

import time as _time
from datetime import UTC, datetime


def utc_now() -> str:
    """The time as the log keeps it: ISO 8601, UTC, milliseconds ("2026-11-01T12:34:56.789Z")."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def monotonic() -> float:
    """Seconds, for lock timeouts (never stored)."""
    return _time.monotonic()
