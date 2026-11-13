"""The stream of uniform numbers behind ``RAND``, ``RANDBETWEEN`` and ``RANDOM`` (D291).

A draw is a pure function of five things: the document's seed, the cell it is for, the document's draw number and
the index of the call inside the cell. The algorithm is fixed and written down here so that any other implementation
(a second server, a script that checks a result) gets the same numbers: BLAKE2b with an 8-byte digest of the text
``seed:sheet:row:col:draw:index``, the top 53 bits of it as an integer, divided by 2**53. The numbers lie in [0, 1).

Nothing here depends on the machine or on what else was calculated before, which is what makes every person in a
document see the same values, and what lets the alternatives of an input see the same draw (common random numbers).
"""

from __future__ import annotations

from hashlib import blake2b

_SCALE = float(1 << 53)


def uniform(seed: int, sheet: str, row: int, col: int, draw: int, index: int) -> float:
    """The number in [0, 1) that the document's ``seed`` and ``draw`` number give to call ``index`` of cell
    (``row``, ``col``) on ``sheet``."""
    digest = blake2b(f"{seed}:{sheet}:{row}:{col}:{draw}:{index}".encode(), digest_size=8).digest()
    return (int.from_bytes(digest, "big") >> 11) / _SCALE
