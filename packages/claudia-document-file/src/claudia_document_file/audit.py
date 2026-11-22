"""The audit record (E2.9, D1271): what left the document in a form that can be read outside Claudia.

One :class:`AuditRecord` per export, print or PDF: who, when, what kind, which format, which parts, and for a print or a
PDF how many pages (not what was on them). The records are kept in a chain of blocks of their own
(``audit/NNNNNN.blk``), sealed with the history key and covered by the head, so a block that is taken out, swapped or
changed is noticed like any other. The chain is not part of the command log and adds no revision; neither a redaction
nor the rewrite of the journal touches it, and nothing in this package removes a record.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .slots import Part

KINDS = ("export", "print", "pdf")
"""What can leave: an export in any format, a print, a PDF."""

PARTS = tuple(part.value for part in Part)
"""Which parts of the document a record can name: all of them (content, history, chat)."""

MAX_FIELD = 200
"""Longest a name or a format may be: the record must not become a place to store things."""


@dataclass(frozen=True)
class AuditRecord:
    """One thing that left the document."""

    kind: str
    """``export``, ``print`` or ``pdf``."""
    who: str
    """The account that did it, as the server authenticated it (never taken from what a client says)."""
    when: str
    """ISO 8601 time, UTC."""
    format: str
    """The format of an export (``docx``, ``claudia-unencrypted``, ...); for a print ``print``."""
    parts: tuple[str, ...]
    """Which parts left, ``content`` and for owners also ``history`` and ``chat``."""
    pages: int | None = None
    """For a print or a PDF, the number of pages of the document."""

    def check(self) -> None:
        """``ValueError`` if the record could not be a sound one."""
        if self.kind not in KINDS:
            raise ValueError(f"the kind of a record is one of {', '.join(KINDS)}")
        if not all(isinstance(text, str) and 0 < len(text) <= MAX_FIELD for text in (self.who, self.when, self.format)):
            raise ValueError("a record needs a name, a time and a format of at most 200 characters")
        if not self.parts or not all(part in PARTS for part in self.parts) or len(set(self.parts)) != len(self.parts):
            raise ValueError(f"the parts of a record are some of {', '.join(PARTS)}")
        pages = self.pages
        if pages is not None and (not isinstance(pages, int) or isinstance(pages, bool) or pages < 0):
            raise ValueError("pages is a number of pages")

    def to_bytes(self) -> bytes:
        """The payload that goes into a block."""
        self.check()
        data = {
            "kind": self.kind,
            "who": self.who,
            "when": self.when,
            "format": self.format,
            "parts": list(self.parts),
            "pages": self.pages,
        }
        return json.dumps(data, separators=(",", ":")).encode()

    @classmethod
    def from_bytes(cls, payload: bytes) -> AuditRecord:
        """Read a record from a block; ``ValueError`` if it is not one. A block that opened is authentic, so this is
        a bug or a newer writer, not an attack."""
        try:
            data = json.loads(payload)
            record = cls(data["kind"], data["who"], data["when"], data["format"], tuple(data["parts"]), data["pages"])
        except (KeyError, TypeError) as error:
            raise ValueError(f"not an audit record: {error}") from error
        record.check()
        return record
