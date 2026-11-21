"""The command log: the source of truth of a document (D15, E1.2).

An ``Step`` is one executed command with its place in the order. The log is append-only except for
redaction (E1.8), which replaces the *content* of an entry and nothing else: revision, parent, author, time,
kind and ids stay.

Branches: every entry has a ``Revision(branch, seq)`` and a ``parent`` (the previous entry on the path, which for the
first entry of a branch is its fork point). ``path(rev)`` walks from the root to ``rev`` through forks.
Version 1 of the product uses only ``main``; the structure is here so that what-if branches and scrubbing back
in time need no format change.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .errors import KernelError, RevisionMismatch
from .revision import MAIN, Branch, Revision, check_branch

if TYPE_CHECKING:
    from .commands import Command, CommandRegistry

ORIGINS = ("do", "undo", "redo")


@dataclass(frozen=True)
class Step:
    rev: Revision
    parent: Revision | None
    author: str | None
    time: str  # ISO 8601 UTC, stamped by the server; every replica logs the same time
    command: Command
    origin: str = "do"
    of: Revision | None = None  # for undo/redo: the revision this entry reverses
    redacted: bool = False
    via: str | None = None  # by what the author made the step, when not by hand ("ai": accepted from a proposal, D1308)

    def to_data(self) -> dict:
        """The plain-data form of the entry, as stored and sent to replicas."""
        from .commands import encode

        data: dict = {
            "rev": self.rev.to_data(),
            "parent": self.parent.to_data() if self.parent else None,
            "author": self.author,
            "time": self.time,
            "command": encode(self.command),
        }
        if self.origin != "do":
            data["origin"] = self.origin
        if self.of is not None:
            data["of"] = self.of.to_data()
        if self.redacted:
            data["redacted"] = True
        if self.via is not None:
            data["via"] = self.via
        return data

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> Step:
        """Inverse of ``to_data``; the registry decodes the command."""
        parent, of = data.get("parent"), data.get("of")
        origin = data.get("origin", "do")
        if origin not in ORIGINS:
            raise KernelError(f"unknown origin {origin!r} in the log")
        return cls(
            Revision.parse(data["rev"]),
            Revision.parse(parent) if parent else None,
            data.get("author"),
            data["time"],
            registry.decode(data["command"]),
            origin,
            Revision.parse(of) if of else None,
            bool(data.get("redacted", False)),
            data.get("via"),
        )


class CommandLog:
    """All entries of a document, grouped in lines (``main`` and the lines a restore forks), plus the active line.

    The log only stores and orders entries; applying them is ``replay``'s and ``Document``'s job."""

    def __init__(self):
        self._branch_steps: dict[str, list[Step]] = {MAIN: []}
        self._first: dict[str, int] = {MAIN: 1}  # seq of the first entry of each line
        self._branches: dict[str, Branch] = {MAIN: Branch(MAIN)}
        self.active = MAIN  # the line the document works on; the others are side lines (E1.7)

    # -- reading -------------------------------------------------------------
    @property
    def branches(self) -> dict[str, Branch]:
        """Every line by name (a copy)."""
        return dict(self._branches)

    def head(self, branch: str = MAIN) -> Revision | None:
        """The newest revision on ``branch``; for a branch without entries yet, its fork point."""
        line = self._branch_steps[branch]
        return line[-1].rev if line else self._branches[branch].fork_point

    def steps_of(self, name: str) -> tuple[Step, ...]:
        """The steps that belong to the branch ``name`` itself, not those it shares with the branch it forked from."""
        return tuple(self._branch_steps[name])

    def has(self, rev: Revision) -> bool:
        """Is there an entry with this revision?"""
        line = self._branch_steps.get(rev.branch)
        if line is None:
            return False
        index = rev.seq - self._first[rev.branch]
        return 0 <= index < len(line)

    def get(self, rev: Revision) -> Step:
        """The entry with this revision; ``KeyError`` if there is none."""
        if not self.has(rev):
            raise KeyError(f"no such revision {rev}")
        return self._branch_steps[rev.branch][rev.seq - self._first[rev.branch]]

    def path(self, rev: Revision | None) -> list[Step]:
        """All entries from the root to ``rev``, following forks. ``None`` -> empty (the empty document)."""
        out: list[Step] = []
        while rev is not None:
            line = self._branch_steps[rev.branch]
            first = self._first[rev.branch]
            upto = rev.seq - first + 1
            if upto > len(line) or upto < 0:
                raise KeyError(f"no such revision {rev}")
            out[:0] = line[:upto]
            rev = self._branches[rev.branch].fork_point
        return out

    def on_path(self, rev: Revision, head: Revision | None) -> bool:
        """Is ``rev`` an entry on the path from the root to ``head``? Walks forks, not entries."""
        while head is not None:
            if head.branch == rev.branch:
                return self.has(rev) and rev.seq <= head.seq
            head = self._branches[head.branch].fork_point
        return False

    def since(self, rev: Revision | None, branch: str = MAIN) -> list[Step]:
        """The entries of ``branch`` after ``rev`` (which must be on its path), to bring a replica up to date.

        Costs as much as the answer is long, not as much as the history: it walks back from the head only as far as
        the line that holds ``rev``."""
        head = self.head(branch)
        if rev is None:
            return self.path(head)
        parts: list[list[Step]] = []
        cur = head
        while cur is not None:
            first = self._first[cur.branch]
            upto = cur.seq - first + 1  # how many entries of this line are on the path
            if rev.branch == cur.branch:
                index = rev.seq - first
                if not 0 <= index < upto:
                    break
                parts.append(self._branch_steps[cur.branch][index + 1 : upto])
                return [entry for part in reversed(parts) for entry in part]
            parts.append(self._branch_steps[cur.branch][:upto])
            cur = self._branches[cur.branch].fork_point
        raise KeyError(f"{rev} is not on the path of {branch}")

    def __iter__(self) -> Iterator[Step]:
        return iter(self.path(self.head(MAIN)))

    def __len__(self) -> int:
        return sum(len(line) for line in self._branch_steps.values())

    # -- writing -------------------------------------------------------------
    def next_revision(self, branch: str = MAIN) -> Revision:
        """The revision the next entry of ``branch`` will get."""
        line = self._branch_steps[branch]
        if line:
            return Revision(branch, line[-1].rev.seq + 1)
        fork = self._branches[branch].fork_point
        return Revision(branch, fork.seq + 1 if fork else 1)

    def append(self, entry: Step) -> None:
        """Add an entry at the end of its line; it must be exactly the next one (``RevisionMismatch`` otherwise)."""
        branch = entry.rev.branch
        if branch not in self._branch_steps:
            raise RevisionMismatch(f"unknown branch {branch!r}")
        if entry.rev != self.next_revision(branch) or entry.parent != self.head(branch):
            raise RevisionMismatch(
                f"expected {self.next_revision(branch)} after {self.head(branch)}, got {entry.rev} after {entry.parent}"
            )
        self._branch_steps[branch].append(entry)

    def fork(self, name: str, at: Revision) -> Branch:
        """Start a new line that continues after the existing revision ``at``."""
        check_branch(name)
        if name in self._branches:
            raise KernelError(f"branch {name!r} exists")
        if not self.has(at):
            raise KeyError(f"no such revision {at}")
        branch = Branch(name, at)
        self._branches[name] = branch
        self._branch_steps[name] = []
        self._first[name] = at.seq + 1
        return branch

    def activate(self, name: str) -> None:
        """Make ``name`` the line the document works on."""
        if name not in self._branches:
            raise KeyError(f"no such branch {name!r}")
        self.active = name

    def discard_off_path(self, keep: Revision | None) -> list[Revision]:
        """Remove every entry that is not on the path to ``keep`` (and the branches that only held such entries).

        This is the owner's permanent act of forgetting the abandoned future after a restore.
        Returns the removed revisions."""
        kept = {e.rev for e in self.path(keep)}
        removed: list[Revision] = []
        forked_from = {b.fork_point.branch for b in self._branches.values() if b.fork_point}
        for name in list(self._branch_steps):
            line = self._branch_steps[name]
            survivors = [e for e in line if e.rev in kept]
            removed += [e.rev for e in line if e.rev not in kept]
            self._branch_steps[name] = survivors
            gone = not survivors and name not in (MAIN, self.active) and name not in forked_from
            if gone:
                del self._branch_steps[name], self._branches[name], self._first[name]
        return sorted(removed, key=lambda r: (r.branch, r.seq))

    def replace_command(self, rev: Revision, command: Command) -> Step:
        """Redaction: swap the content of one entry, keep everything else."""
        entry = self.get(rev)
        new = replace(entry, command=command, redacted=True)
        self._branch_steps[rev.branch][rev.seq - self._first[rev.branch]] = new
        return new

    def restore_entry(self, entry: Step) -> None:
        """Put an entry back exactly as it was (undoing a failed redaction)."""
        self._branch_steps[entry.rev.branch][entry.rev.seq - self._first[entry.rev.branch]] = entry

    # -- (de)serialisation ----------------------------------------------------
    def to_data(self) -> dict:
        """The plain-data form of the whole log: active line, lines and entries."""
        return {
            "active": self.active,
            "branches": [b.to_data() for b in self._branches.values()],
            "entries": [e.to_data() for line in self._branch_steps.values() for e in line],
        }

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> CommandLog:
        """Inverse of ``to_data``."""
        log = cls()
        forks = {b.name: b for b in map(Branch.from_data, data.get("branches", [])) if b.name != MAIN}
        for item in data["entries"]:
            entry = Step.from_data(item, registry)
            name = entry.rev.branch
            if name != MAIN and name not in log._branches:  # its fork point is an earlier entry
                log.fork(name, forks[name].fork_point)  # type: ignore[arg-type]
            log.append(entry)
        for name, branch in forks.items():  # branches that have no entries of their own yet
            if name not in log._branches:
                log.fork(name, branch.fork_point)  # type: ignore[arg-type]
        log.activate(data.get("active", MAIN))
        return log
