"""Presence and locks, written once against Region (E1.5, D11, D17).

One hold per person: the regions they are looking at (presence) and, optionally, regions they hold with a
timeout (lock). Holds are *ephemeral* (E1.6): they live here and on the wire, never in the log or on disk.
Whenever a command runs, every hold is moved through it, so a hold follows the text or cells it was on
and disappears when they do.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .commands import Command
from .region import Region, transform


@dataclass(frozen=True)
class Hold:
    owner: str
    regions: tuple[Region, ...]
    expires: float | None  # None: presence only, nothing is locked


class Presence:
    """Who is looking at or holding which regions (E1.5). Holds move with the edits; locks run out after a time."""

    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._holds: dict[str, Hold] = {}

    def show(self, owner: str, regions: Iterable[Region]) -> Hold:
        """Where ``owner`` is looking. Replaces their previous hold (and releases a lock they had)."""
        hold = Hold(owner, tuple(regions), None)
        self._store(hold)
        return hold

    def lock(self, owner: str, regions: Iterable[Region], ttl: float) -> Hold:
        """``owner`` holds these regions for ``ttl`` seconds (renew by locking again)."""
        hold = Hold(owner, tuple(regions), self._clock() + ttl)
        self._store(hold)
        return hold

    def release(self, owner: str) -> None:
        """Remove everything ``owner`` shows or holds."""
        self._holds.pop(owner, None)

    def _store(self, hold: Hold) -> None:
        if hold.regions:
            self._holds[hold.owner] = hold
        else:
            self._holds.pop(hold.owner, None)

    def holds(self) -> list[Hold]:
        """All current holds, locks and presence alike."""
        self.expire()
        return list(self._holds.values())

    def of(self, owner: str) -> Hold | None:
        """The hold of ``owner``, if any."""
        self.expire()
        return self._holds.get(owner)

    def expire(self) -> None:
        """Turn locks whose time ran out into plain presence."""
        now = self._clock()
        for owner, hold in list(self._holds.items()):
            if hold.expires is not None and hold.expires <= now:
                self._holds[owner] = Hold(owner, hold.regions, None)  # the lock ran out, the presence stays

    def conflicts(self, owner: str | None, regions: Iterable[Region]) -> list[tuple[str, Region]]:
        """Locks of *other* people that overlap ``regions``."""
        self.expire()
        wanted = list(regions)
        found: list[tuple[str, Region]] = []
        for hold in self._holds.values():
            if hold.owner == owner or hold.expires is None:
                continue
            found.extend((hold.owner, mine) for mine in hold.regions if any(mine.overlaps(w) for w in wanted))
        return found

    def on_command(self, command: Command) -> None:
        """Move every hold through ``command``; holds that lose all their regions end."""
        for owner, hold in list(self._holds.items()):
            moved = tuple(r for r in (transform(region, command) for region in hold.regions) if r is not None)
            self._store(Hold(owner, moved, hold.expires))
