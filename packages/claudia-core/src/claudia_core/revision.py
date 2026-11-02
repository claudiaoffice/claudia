"""Revision identifiers.

A revision is ``(branch, seq)``. It is *not* derived from the content of the command, so redacting a
command (E1.8) never changes any identifier. Sequence numbers continue along a branch from its fork
point: a branch ``alt`` forked at ``main:10`` gets ``alt:11`` as its first entry, so ``seq`` grows
strictly along the path from the root to any revision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAIN = "main"
_BRANCH = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def check_branch(name: str) -> str:
    if not _BRANCH.fullmatch(name):
        raise ValueError(f"not a valid branch name: {name!r}")
    return name


@dataclass(frozen=True, slots=True)
class Revision:
    branch: str
    seq: int

    def __post_init__(self):
        check_branch(self.branch)
        if self.seq < 1:
            raise ValueError("a revision number starts at 1")

    def __str__(self) -> str:
        return f"{self.branch}:{self.seq}"

    @classmethod
    def parse(cls, text: str) -> Revision:
        """Read ``"branch:seq"``; raises ``ValueError`` for anything else."""
        branch, sep, seq = text.rpartition(":")
        if not sep or not seq.isdigit():
            raise ValueError(f"not a revision: {text!r}")
        return cls(branch, int(seq))

    def to_data(self) -> str:
        """``"branch:seq"``."""
        return str(self)

    @classmethod
    def from_data(cls, data: str) -> Revision:
        """Inverse of ``to_data``."""
        return cls.parse(data)


@dataclass(frozen=True, slots=True)
class Branch:
    """A line of history. ``fork_point`` is the last revision it shares with its parent line."""

    name: str
    fork_point: Revision | None = None

    def to_data(self) -> dict:
        """The plain-data form of the branch."""
        return {"name": self.name, "fork": self.fork_point.to_data() if self.fork_point else None}

    @classmethod
    def from_data(cls, data: dict) -> Branch:
        """Inverse of ``to_data``."""
        fork = data.get("fork")
        return cls(data["name"], Revision.parse(fork) if fork else None)
