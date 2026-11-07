"""Going back to a checkpoint, or back to a line, with the agreement of a live session (E3.7).

The kernel allows a restore or a switch outright (``Document.restore_checkpoint``, ``Document.switch_to``): nothing
here changes what it does or how the result is stored, and once one happens it is ordinary kernel history, same as
any other command. What this module adds is the question that comes before it, which is a decision of the *live
session*, not of the document's stored state: an owner or editor may *suggest* going back; everybody who is
connected now as an owner or editor must agree before it happens, unless the one suggesting it is the only such
person, in which case it happens at once.

Anybody in the group may decline outright, which ends the suggestion. At most one is open at a time. What silence
at the deadline means is the document's own choice (``policy``): ``"consensus"`` reads it as a decline, ``"veto"``
as agreement. Nothing here is persisted: an open suggestion, and who has left since a line they were on stopped
being the active one, live only as long as the document is held open in memory (``HostedDocument``); there is
nothing to recover if the server restarts, same as presence and locks.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

DEFAULT_TIMEOUT = 15 * 60.0  # minutes an open suggestion waits for everybody to answer
POLICIES = ("consensus", "veto")


class RestoreError(Exception):
    """A request about suggesting, answering or withdrawing could not be carried out; the message is for the person
    who asked (not a kernel error: nothing about the document's stored state is wrong)."""


@dataclass
class Proposal:
    """One open suggestion to restore a checkpoint or switch to a line."""

    id: int
    kind: str  # "restore" | "switch"
    by: str
    checkpoint: int | None  # set when kind == "restore"
    line: str | None  # set when kind == "switch"
    label: str  # a sentence for the banner, e.g. 'checkpoint "good"' or 'line "main"'
    opened_at: float
    expires_at: float
    policy: str
    group: set[str]  # everybody who must be asked (grows and shrinks as people connect and disconnect)
    agreed: set[str]

    def to_data(self) -> dict:
        """As sent to clients in the ``restore_proposed`` event and in a reconnecting client's welcome."""
        return {
            "id": self.id,
            "kind": self.kind,
            "by": self.by,
            "checkpoint": self.checkpoint,
            "line": self.line,
            "label": self.label,
            "opened_at": self.opened_at,
            "expires_at": self.expires_at,
            "policy": self.policy,
            "group": sorted(self.group),
            "agreed": sorted(self.agreed),
        }


@dataclass
class Resolution:
    """What happened to a line that stopped being active, for the notice a returning person gets (E3.7)."""

    by: str
    kind: str
    label: str
    agreed: list[str]

    def to_data(self) -> dict:
        """As sent to a returning person in their welcome's ``returned`` field."""
        return {"by": self.by, "kind": self.kind, "label": self.label, "agreed": self.agreed}


@dataclass
class _Record:
    kind: str
    by: str
    checkpoint: int | None
    line: str | None
    label: str
    agreed: list[str] = field(default_factory=list)


class RestoreCoordinator:
    """One document's open restore/switch suggestion, if any, and the bookkeeping around it.

    ``apply`` carries out an agreed suggestion: given ``{kind, by, checkpoint, line}`` it calls the kernel
    (``Document.restore_checkpoint`` or ``switch_to``) and, if that line's head actually moved, records the
    resolution (``record_resolution``) under the branch name that was active just before — the caller knows that
    name and this module does not, since it is the kernel's, not a concept of its own."""

    def __init__(self, apply: Callable[[dict], None], *, clock: Callable[[], float], timeout: float = DEFAULT_TIMEOUT):
        self._apply = apply
        self._clock = clock
        self.timeout = timeout
        self.policy = "consensus"
        self._proposal: Proposal | None = None
        self._next_id = 0
        self._left_on: dict[str, str] = {}  # user -> the line they were on when their last window closed
        self._resolutions: dict[str, Resolution] = {}  # old line name -> what happened to it

    @property
    def open_proposal(self) -> Proposal | None:
        """The suggestion waiting for answers, or ``None``."""
        return self._proposal

    # ------------------------------------------------------------------ opening and answering
    def propose(
        self, *, kind: str, by: str, checkpoint: int | None, line: str | None, label: str, group: Iterable[str]
    ) -> tuple[Proposal | None, bool]:
        """Open a suggestion, or carry it out at once if ``by`` is the only one who must agree.

        ``group`` is everybody else currently connected as an owner or editor; ``by`` is added to it (and counts as
        having already agreed). Returns ``(proposal, False)`` once it is open, or ``(None, True)`` if it was carried
        out immediately. ``RestoreError`` if one is open already."""
        if self._proposal is not None:
            raise RestoreError("there is already an open suggestion for this document; answer or withdraw it first")
        everybody = set(group)
        everybody.add(by)
        if len(everybody) <= 1:
            self._carry_out(_Record(kind, by, checkpoint, line, label, [by]))
            return None, True
        now = self._clock()
        self._next_id += 1
        self._proposal = Proposal(
            self._next_id, kind, by, checkpoint, line, label, now, now + self.timeout, self.policy, everybody, {by}
        )
        return self._proposal, False

    def answer(self, *, user: str, agree: bool) -> str | None:
        """``user`` agrees or declines the open suggestion. Returns the outcome (``"agreed"``, ``"declined"``) once
        this answer resolves it, else ``None``. A decline always resolves it; agreeing does only once everybody in
        the group has. ``RestoreError`` if nothing is open."""
        p = self._require()
        p.group.add(user)
        if not agree:
            return self._resolve(p, "declined")
        p.agreed.add(user)
        if p.agreed >= p.group:
            return self._resolve(p, "agreed")
        return None

    def withdraw(self, *, user: str, is_owner: bool) -> None:
        """Take back the open suggestion: only the person who made it, or an owner. ``RestoreError`` otherwise, or
        if nothing is open."""
        p = self._require()
        if user != p.by and not is_owner:
            raise RestoreError("only the person who suggested this, or an owner, can withdraw it")
        self._proposal = None

    # ------------------------------------------------------------------ the people around it
    def joined(self, user: str, can_write: bool) -> None:
        """A window of ``user`` connected. If they may write and a suggestion is open, they join its group (and so
        are asked for their answer); a viewer, or the assistant (which never calls this), does not."""
        if can_write and self._proposal is not None:
            self._proposal.group.add(user)

    def left(self, user: str, current_line: str) -> str | None:
        """The last window of ``user`` closed, while the document was on ``current_line``. Drops them from an open
        vote (the proposer leaving withdraws it outright: nobody is left to carry it out for them); returns the
        outcome if that resolves it. Also remembers where they were, for the notice they get on return."""
        self._left_on[user] = current_line
        p = self._proposal
        if p is None or user not in p.group:
            return None
        if user == p.by:
            self._proposal = None
            return "withdrawn"
        p.group.discard(user)
        p.agreed.discard(user)
        if p.group and p.agreed >= p.group:
            return self._resolve(p, "agreed")
        return None

    def sweep(self) -> str | None:
        """Called periodically: resolve an open suggestion whose deadline has passed. Returns the outcome, if any."""
        p = self._proposal
        if p is None or self._clock() < p.expires_at:
            return None
        return self._resolve(p, "agreed" if p.policy == "veto" else "declined")

    # ------------------------------------------------------------------ the returning-person notice
    def notice_for(self, user: str, current_line: str) -> dict | None:
        """The one-time notice ``user`` should see on return: what happened to the line they were on, if it is not
        the active one any more. Delivered once — calling this again before they leave on the (new) current line
        again gives ``None``."""
        left_on = self._left_on.get(user)
        if left_on is None or left_on == current_line:
            return None
        resolution = self._resolutions.get(left_on)
        self._left_on[user] = current_line
        return None if resolution is None else resolution.to_data()

    def record_resolution(self, old_line: str, resolution: Resolution) -> None:
        """Note what happened to ``old_line`` (called by whoever carries out ``apply``, once it actually moved)."""
        self._resolutions[old_line] = resolution

    # ------------------------------------------------------------------ internals
    def _require(self) -> Proposal:
        if self._proposal is None:
            raise RestoreError("there is no open suggestion to answer")
        return self._proposal

    def _resolve(self, p: Proposal, outcome: str) -> str:
        self._proposal = None
        if outcome == "agreed":
            self._carry_out(_Record(p.kind, p.by, p.checkpoint, p.line, p.label, sorted(p.agreed)))
        return outcome

    def _carry_out(self, record: _Record) -> None:
        self._apply(
            {
                "kind": record.kind,
                "by": record.by,
                "checkpoint": record.checkpoint,
                "line": record.line,
                "label": record.label,
                "agreed": record.agreed,
            }
        )
