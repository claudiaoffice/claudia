"""How a person wants the AI to treat her requests: *act* or *suggest* (D262, E7.7).

The choice is hers, per document, and lives on her client; each ``@ai`` request carries it (``chat``'s ``ai_mode``) and
the server stores nothing. *Suggest* is the default everywhere (D262): a request that names no mode, from a client that
has no switch yet or from a script, is treated as *suggest* too.
"""

from __future__ import annotations

from typing import Literal

AiMode = Literal["act", "suggest"]

ACT: AiMode = "act"
SUGGEST: AiMode = "suggest"

DEFAULT_MODE: AiMode = SUGGEST  # what a client starts with, and what a request with no mode means (D262)


def parse_mode(raw: object) -> AiMode:
    """The mode a request names; ``None`` (not sent) is the default. ``ValueError`` for anything else."""
    if raw is None:
        return DEFAULT_MODE
    if raw == ACT:
        return ACT
    if raw == SUGGEST:
        return SUGGEST
    raise ValueError(f"ai_mode must be {ACT!r} or {SUGGEST!r}")
