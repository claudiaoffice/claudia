"""The owners' consent (E7.11, D264): which remote AI provider may be sent the content of this document.

One :class:`ConsentRecord` per decision, in the order they were made: who allowed or withdrew it, and when. The latest
record of a provider says where it stands now; no record means *not allowed*. The records are kept in a chain of blocks
of their own (``consent/NNNNNN.blk`` with a head of its own), sealed with the **content** key, so a viewer can read
whether a remote provider is allowed here, and a block that is taken out, swapped or changed is noticed like any other.

It is not the record of what left the document (:mod:`audit`, from which nothing is ever removed: a consent can be
withdrawn) and not history: it adds no revision and no undo step, and neither a redaction nor the rewrite of the journal
touches it. An honest limit: owners and editors both hold the content key, so that only the owners may change it is the
server's rule, not cryptography. What the seal guarantees is what D264 is for: whoever administers the server holds no
key, and cannot give the owners' consent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

MAX_FIELD = 200
"""Longest a provider or a name may be: the record must not become a place to store things."""


@dataclass(frozen=True)
class ConsentRecord:
    """One decision of the owner about one remote provider."""

    provider: str
    """Which provider the decision is about (``claude``)."""
    allowed: bool
    """``True`` for allowed, ``False`` for withdrawn."""
    who: str
    """The owner who decided, as the server authenticated her (never taken from what a client says)."""
    when: str
    """ISO 8601 time, UTC."""

    def check(self) -> None:
        """``ValueError`` if the record could not be a sound consent."""
        if not all(
            isinstance(text, str) and 0 < len(text) <= MAX_FIELD for text in (self.provider, self.who, self.when)
        ):
            raise ValueError("a consent needs a provider, a name and a time of at most 200 characters")
        if not isinstance(self.allowed, bool):
            raise ValueError("a consent is allowed or withdrawn")

    def to_bytes(self) -> bytes:
        """The payload that goes into a block."""
        self.check()
        data = {"provider": self.provider, "allowed": self.allowed, "who": self.who, "when": self.when}
        return json.dumps(data, separators=(",", ":")).encode()

    @classmethod
    def from_bytes(cls, payload: bytes) -> ConsentRecord:
        """Read a record from a block; ``ValueError`` if it is not one. A block that opened is authentic, so this is
        a bug or a newer writer, not an attack."""
        try:
            data = json.loads(payload)
            record = cls(data["provider"], data["allowed"], data["who"], data["when"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"not a consent record: {error}") from error
        record.check()
        return record
