"""How a person wants the AI to treat her requests: *act* or *suggest* (D262, E7.7).

The choice is hers, per document, and lives on her client; each ``@ai`` request carries it (``chat``'s ``ai_mode``) and
the server stores nothing. A client that sends none is one from before the switch existed, which could not choose, and
gets what it always got: *act*. The default a client starts with is *suggest*, in all three apps.
"""

from __future__ import annotations

from typing import Literal

AiMode = Literal["act", "suggest"]

ACT: AiMode = "act"
SUGGEST: AiMode = "suggest"

DEFAULT_MODE: AiMode = SUGGEST  # what a client starts with (D262)
LEGACY_MODE: AiMode = ACT  # what a request with no mode means: an older client


def parse_mode(raw: object) -> AiMode:
    """The mode a request names; ``None`` (not sent) is the legacy one. ``ValueError`` for anything else."""
    if raw is None:
        return LEGACY_MODE
    if raw == ACT:
        return ACT
    if raw == SUGGEST:
        return SUGGEST
    raise ValueError(f"ai_mode must be {ACT!r} or {SUGGEST!r}")
