"""How a person wants the AI to treat her requests: *act* or *suggest* (D262, E7.7).

The choice is hers, per document, and lives on her client; each ``@ai`` request carries it (``chat``'s ``ai_mode``) and
the server stores nothing. *Suggest* is what a client starts with (D262, ``DEFAULT_MODE``). A request that names no mode
comes from a client that has no switch yet, or from a script, and gets *act* (``UNSAID_MODE``, E7.7): that is how the AI
worked before modes existed, and treating it as *suggest* left the AI unable to do anything in computes, which cannot
propose yet (E7.8), with an answer pointing at a switch no client had (QA 2026-11-12).
"""

from __future__ import annotations

from typing import Literal

AiMode = Literal["act", "suggest"]

ACT: AiMode = "act"
SUGGEST: AiMode = "suggest"

DEFAULT_MODE: AiMode = SUGGEST  # what a client starts with (D262)
UNSAID_MODE: AiMode = ACT  # what a request that names no mode gets: a client without the switch (E7.7)


def parse_mode(raw: object) -> AiMode:
    """The mode a request names; ``None`` (not sent) is ``UNSAID_MODE``. ``ValueError`` for anything else."""
    if raw is None:
        return UNSAID_MODE
    if raw == ACT:
        return ACT
    if raw == SUGGEST:
        return SUGGEST
    raise ValueError(f"ai_mode must be {ACT!r} or {SUGGEST!r}")
