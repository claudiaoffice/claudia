"""Document: a model, its command log, and everything common to composes, computes and creates.

This is the one class a doc server holds per open document. It owns

* the **command log** (source of truth, D15) and the model built by applying it,
* **per-author undo** (E1.4), **checkpoints** (E1.7) and **redaction** (E1.8),
* **presence and locks** over Regions (E1.5), **chat** and **ephemeral** messages (E1.6),
* the **manifest** check (E1.9),
* an **event bus** that tells views and network layers what happened.

It does no I/O. Storage is an injected ``DocumentStore`` (E2); clocks are injected; sockets, roles and
passwords belong to other layers. Threading rule (D16): all calls come from one thread.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace

from .clock import monotonic, utc_now
from .commands import Batch, Checkpoint, Command, Import, Redaction, Restore, Switch, tombstone
from .commands import Redacted as RedactedCommand
from .context import Context
from .errors import (
    KernelError,
    ProposalOutdated,
    RedactionError,
    RegionHeld,
    ReplayError,
    RevisionMismatch,
    StaleEdit,
    UndoConflict,
    UndoRefused,
)
from .events import (
    BranchSwitched,
    ChatPosted,
    CheckpointSaved,
    CommandApplied,
    EphemeralPublished,
    EventBus,
    HistoryChanged,
    Rebuilt,
    Redacted,
    ResultsStale,
)
from .history import History
from .log import CommandLog, Step
from .manifest import Environment, Manifest, RequirementReport, check
from .messages import ChatRecord, Ephemeral, parse_chat
from .model import DocumentModel, Snapshot
from .presence import Presence
from .region import Region, transform
from .replay import replay, replay_collecting
from .revision import Branch, Revision
from .store import DocumentStore
from .what_if import Proposal, WhatIf, places


@dataclass(frozen=True)
class Applied:
    """Result of ``execute``."""

    revision: Revision
    command: Command
    inverse: Command
    entry: Step


@dataclass(frozen=True)
class Look:
    """What ``Document.peek_revision`` shows of one step of the history (D551)."""

    revision: Revision
    model: DocumentModel  # the state after the step, on a scratch model
    entry: Step  # the step itself: who, when, what
    focus: tuple[Region, ...]  # where the step touched the document, the places a view brings into sight


@dataclass(frozen=True)
class Changes:
    """What ``Document.changes_since`` found: the places changed after a step, each once, and whether more were
    left out."""

    regions: tuple[Region, ...]
    truncated: bool


@dataclass(frozen=True)
class BranchInfo:
    """One branch of the history (``main``, or ``restore-N`` after a restore), as it is now: its head and whether it is
    the active one (a view of :class:`~claudia_core.revision.Branch`)."""

    name: str
    head: Revision | None
    active: bool
    forked_from: Revision | None  # ``None`` for the first line


@dataclass(frozen=True)
class CheckpointInfo:
    number: int  # from 1
    label: str
    author: str | None
    marks: Revision  # the state revision it labels
    entry: Revision  # where the label itself sits in the log
    time: str


#: The most places a redaction plan names for a preview to mark.
REDACTION_PLACES = 500


@dataclass(frozen=True)
class RedactionPlan:
    """What a redaction does, worked out before anything changes (``Document.plan_redaction``, D721).

    ``targets`` are the steps asked for, ``dependents`` the later steps that stop working without the content and are
    blanked with it (D722), ``chat`` the numbers of the chat messages. ``imports`` are the targets that imported a
    file, whose kept original the server forgets too (D723). ``changes_now`` says whether the document as people see
    it changes (D721: it may, and is shown first); ``after`` is that state, on a scratch model, and ``regions`` the
    places in it that the blanked steps touch, for a preview to mark (empty when nothing people see changes)."""

    targets: tuple[Revision, ...]
    dependents: tuple[Revision, ...]
    chat: tuple[int, ...]
    imports: tuple[Revision, ...]
    changes_now: bool
    after: DocumentModel = field(repr=False, compare=False)
    replacements: Mapping[Revision, Command] = field(repr=False, compare=False)
    basis: tuple = field(repr=False, compare=False)
    regions: tuple[Region, ...] = ()

    @property
    def revisions(self) -> tuple[Revision, ...]:
        """The steps that are blanked, the targets and their dependents together, in order."""
        return tuple(sorted({*self.targets, *self.dependents}, key=lambda r: (r.branch, r.seq)))


class Document:
    """A model with its command log: the one object a doc server holds per open document (see the module text)."""

    def __init__(
        self,
        model: DocumentModel,
        *,
        log: CommandLog | None = None,
        store: DocumentStore | None = None,
        branch: str | None = None,
        clock: Callable[[], str] = utc_now,
        lock_clock: Callable[[], float] = monotonic,
        chat: Iterable[ChatRecord] = (),
    ):
        self.model = model
        self.log = log if log is not None else CommandLog()
        self.store = store
        self.branch = branch if branch is not None else self.log.active
        self.bus = EventBus()
        self._lock_clock = lock_clock
        self.presence = Presence(lock_clock)
        self.chat: list[ChatRecord] = list(chat)
        self._clock = clock
        self._histories: dict[str | None, History] = {}
        self._checkpoints: list[CheckpointInfo] = []
        self._state_head: Revision | None = None
        self._snapshots: dict[Revision, Snapshot] = {}
        self._origin: dict | None = None  # a scratch copy's own state at the start: its log starts there, not empty
        self._purge_hooks: list[Callable[[tuple[Revision, ...]], None]] = []
        self._reindex()

    # ------------------------------------------------------------------ opening
    @classmethod
    def open(
        cls,
        model_cls: type[DocumentModel],
        log: CommandLog,
        *,
        snapshot: Snapshot | None = None,
        branch: str | None = None,
        **options,
    ) -> Document:
        """Build a document from its log. A snapshot only shortens the replay; a stale or foreign one is ignored."""
        branch = branch if branch is not None else log.active
        path = log.path(log.head(branch))
        start = 0
        model: DocumentModel | None = None
        if snapshot is not None and _usable(snapshot, model_cls):
            for index, entry in enumerate(path):
                if entry.rev == snapshot.rev:
                    model, start = model_cls.restore(snapshot.state), index + 1
                    break
        if model is None:
            model = model_cls.empty()
        # The replay itself touches only `model` and the log's own entries -- no live Document needed yet
        # (groundwork for dispatching it to a worker in a future round, D1315). `doc` is built afterward, and
        # recording each author's undo stack from the pairs that come back is the cheap part that stays here.
        applied = replay_collecting(model, path[start:])
        doc = cls(model, log=log, branch=branch, **options)
        for entry, inverse in applied:
            doc._record_history(entry, inverse)
        return doc

    # ------------------------------------------------------------------ state
    @property
    def revision(self) -> Revision | None:
        """The newest revision of this document's branch (``None``: nothing happened yet)."""
        return self.log.head(self.branch)

    @property
    def state_revision(self) -> Revision | None:
        """The newest revision that changed state (checkpoints and redaction records do not count)."""
        return self._state_head

    def subscribe(self, callback: Callable[[object], None]) -> Callable[[], None]:
        """Call ``callback`` for every event; returns the function that unsubscribes."""
        return self.bus.subscribe(callback)

    def subscribe_batches(self, callback: Callable[[list], None]) -> Callable[[], None]:
        """Like ``subscribe``, but called once per command with all of its events."""
        return self.bus.subscribe_batches(callback)

    # ------------------------------------------------------------------ the one entry point for changes
    def execute(
        self,
        command: Command,
        *,
        author: str | None = None,
        time: str | None = None,
        base: Revision | None = None,
        via: str | None = None,
    ) -> Applied:
        """Apply ``command`` atomically as ``author``. On any error the document is unchanged.

        ``base`` is the revision the author's view was at. If it is not on the active line (a checkpoint was restored
        or the line switched while the edit was on its way) the edit is refused with ``StaleEdit``. ``None`` skips
        the check. Refuses (``RegionHeld``) a command that touches a region somebody else holds: the rule is enforced
        here, once, for people and the AI alike. Replaying entries the server already accepted (``apply_entry``) is
        not checked. ``via`` says by what the author made the step when not by hand (``"ai"``), and is kept in the entry
        (D1308)."""
        if base is not None and not self.log.on_path(base, self.revision):
            raise StaleEdit(base, self.branch)
        self.check_free(author, command)
        return self._commit(command, author, time, "do", None, via=via)

    def apply_entry(self, entry: Step, *, persist: bool = True) -> Applied:
        """Replay an entry made elsewhere (a replica following the server). Must be exactly the next one."""
        expected = self.log.next_revision(self.branch)
        if entry.rev != expected or entry.parent != self.revision:
            raise RevisionMismatch(f"expected {expected} after {self.revision}, got {entry.rev} after {entry.parent}")
        return self._commit(
            entry.command,
            entry.author,
            entry.time,
            entry.origin,
            entry.of,
            persist=persist,
            redacted=entry.redacted,
            via=entry.via,
        )

    def entries_since(self, revision: Revision | None) -> list[Step]:
        """What a replica that has everything up to ``revision`` still needs."""
        return self.log.since(revision, self.branch)

    def _commit(
        self,
        command: Command,
        author: str | None,
        time: str | None,
        origin: str,
        of: Revision | None,
        *,
        persist: bool = True,
        redacted: bool = False,
        via: str | None = None,
    ) -> Applied:
        rev = self.log.next_revision(self.branch)
        parent = self.revision
        when = time or self._clock()
        ctx = Context(self.model, author, when, rev, origin)
        try:
            inverse = self.model.apply(command, ctx)
        except BaseException:
            ctx.failed = True
            self.model.settle(ctx)  # a rolled-back command may leave derived state to recompute
            raise
        self.model.settle(ctx)
        entry = Step(rev, parent, author, when, command, origin, of, redacted, via)
        if persist and self.store is not None:
            try:
                self.store.append_entry(entry)
            except BaseException:
                self._undo_quietly(inverse, author, when, origin)  # not durable, so it did not happen
                raise
        self.log.append(entry)
        self._index(entry)
        self.presence.on_command(command)
        changed = self._record_history(entry, inverse)
        with self.bus.batching():
            for event in ctx.events:
                self.bus.emit(event)
            self.bus.emit(CommandApplied(entry, inverse))
            if changed:
                self.bus.emit(self._history_event(author))
            if isinstance(command, Checkpoint):
                self.bus.emit(CheckpointSaved(len(self._checkpoints), command.label_text, author, command.marks))
        return Applied(rev, command, inverse, entry)

    def _undo_quietly(self, inverse: Command, author: str | None, when: str, origin: str) -> None:
        ctx = Context(self.model, author, when, None, origin)
        inverse.apply(ctx)
        self.model.settle(ctx)

    def _reindex(self) -> None:
        """Checkpoint list and state revision follow the active line."""
        self._checkpoints.clear()
        self._state_head = None
        for entry in self.log.path(self.revision):
            self._index(entry)

    def _index(self, entry: Step) -> None:
        if not entry.command.meta:
            self._state_head = entry.rev
        command = entry.command
        if isinstance(command, Checkpoint):
            self._checkpoints.append(
                CheckpointInfo(
                    len(self._checkpoints) + 1, command.label_text, entry.author, command.marks, entry.rev, entry.time
                )
            )

    def _record_history(self, entry: Step, inverse: Command) -> bool:
        return self.history_for(entry.author).record(entry, inverse)

    # ------------------------------------------------------------------ undo / redo (E1.4)
    def history_for(self, author: str | None) -> History:
        """The undo and redo stacks of one author (created on first use)."""
        if author not in self._histories:
            self._histories[author] = History(author)
        return self._histories[author]

    def _history_event(self, author: str | None) -> HistoryChanged:
        h = self.history_for(author)
        return HistoryChanged(author, h.can_undo, h.can_redo, h.undo_label, h.redo_label)

    def undo(self, author: str | None) -> Applied | None:
        """Undo ``author``'s last step. ``None`` if there is nothing to undo.

        Raises UndoRefused if the step would touch a region somebody else holds."""
        return self._step(author, redo=False)

    def redo(self, author: str | None) -> Applied | None:
        """Redo ``author``'s last undone step. Same rules as ``undo``."""
        return self._step(author, redo=True)

    def _step(self, author: str | None, *, redo: bool) -> Applied | None:
        history = self.history_for(author)
        step = history.next_redo() if redo else history.next_undo()
        if step is None:
            return None
        command = step.command
        for entry in _standing(e for e in self.log.since(step.rev, self.branch) if not e.command.meta):
            # The step was written for the state right after step.rev. Everything that ran since moved things; so
            # follow all of it, our own undone steps too. A step undone right away is left out with its undo: the
            # pair changed nothing, and following it can lose a place (a delete takes a span's start with it, and
            # putting the words back cannot tell where inside them the span began). Only a colleague's change may
            # make the step meaningless; that refuses the undo.
            for leaf in entry.command.leaves():
                shifted = command.shifted_by(leaf)
                if shifted is None and entry.author != author:
                    raise UndoConflict(
                        f"{entry.author or 'Somebody'} changed this after you ({entry.command.label}). "
                        f"Undoing “{step.label}” would overwrite their work."
                    )
                command = shifted if shifted is not None else command
        held = self.presence.conflicts(author, self.model.describe_regions(command))
        if held:
            raise UndoRefused(held)
        try:
            return self._commit(command, author, None, "redo" if redo else "undo", step.rev)
        except KernelError:
            raise
        except Exception as exc:  # the command validated and refused: nothing changed
            raise UndoConflict(f"“{step.label}” can no longer be undone: {exc}") from exc

    # ------------------------------------------------------------------ presence and locks (E1.5, E1.6)
    def check_free(self, author: str | None, command: Command) -> None:
        """For the layer that accepts edits: refuse a command that touches somebody else's lock."""
        held = self.presence.conflicts(author, self.model.describe_regions(command))
        if held:
            raise RegionHeld(held)

    def show_presence(self, owner: str, regions: Iterable[Region]) -> Ephemeral:
        """Where ``owner`` is looking (replaces their previous presence); also published as an ephemeral message."""
        regions = tuple(regions)
        self.presence.show(owner, regions)
        return self.publish("presence", owner, {"regions": [r.to_data() for r in regions]})

    def lock(self, owner: str, regions: Iterable[Region], ttl: float) -> Ephemeral:
        """``owner`` holds these regions for ``ttl`` seconds; ``RegionHeld`` if a colleague holds any of them."""
        regions = tuple(regions)
        held = self.presence.conflicts(owner, regions)
        if held:
            raise RegionHeld(held)
        self.presence.lock(owner, regions, ttl)
        return self.publish("presence", owner, {"regions": [r.to_data() for r in regions], "locked": True})

    def publish(self, kind: str, sender: str | None, data: dict | None = None) -> Ephemeral:
        """An ephemeral message: delivered to subscribers, stored nowhere (there is no path to a store)."""
        message = Ephemeral(kind, sender, data or {})
        self.bus.emit(EphemeralPublished(message))
        return message

    # ------------------------------------------------------------------ chat (E1.6)
    def post_chat(self, author: str, raw: str, *, users: Iterable[str] = ()) -> ChatRecord:
        """``@name message`` or a message for everybody. Chat is not part of the command log."""
        to, text = parse_chat(raw, users)
        record = ChatRecord(len(self.chat) + 1, author, to, text, self._clock(), self.revision)
        if self.store is not None:
            self.store.append_chat(record)
        self.chat.append(record)
        self.bus.emit(ChatPosted(record))
        return record

    # ------------------------------------------------------------------ snapshots (cache, E1.2)
    def snapshot(self) -> Snapshot | None:
        """The state right now as a cache entry; ``None`` for an empty document."""
        head = self.revision
        if head is None:
            return None
        return Snapshot(head, self.model.app, self.model.state_schema, self.model.serialize())

    def cache_snapshot(self) -> Snapshot | None:
        """Take a snapshot and keep it (and hand it to the store) to shorten later replays."""
        snap = self.snapshot()
        if snap is not None:
            self._snapshots[snap.rev] = snap
            if self.store is not None:
                self.store.write_snapshot(snap)
        return snap

    def materialize(self, rev: Revision | None) -> DocumentModel:
        """The state at ``rev`` (on any branch), rebuilt on a scratch model; the live model is untouched."""
        path = self.log.path(rev)
        model: DocumentModel | None = None
        start = 0
        for index in range(len(path) - 1, -1, -1):
            snap = self._snapshots.get(path[index].rev)
            if snap is not None and _usable(snap, type(self.model)):
                model, start = type(self.model).restore(snap.state), index + 1
                break
        if model is None:
            model = type(self.model).empty() if self._origin is None else type(self.model).restore(self._origin)
        return replay(model, path[start:])

    def scratch(self, at: Revision | None = None) -> Document:
        """A throwaway document that starts from the state now (or at ``at``) and goes nowhere (E7.8, D263).

        It runs commands like any document (``execute``, ``undo``, its own events and locks) on a copy of the model,
        with a log of its own that starts empty and no store, so nothing it does reaches the live document, the live
        log, the disk or anybody's undo steps, and nothing the live document does afterwards reaches it. This is how an
        AI proposal is previewed and how the AI checks the effect of a change it has only proposed: apply the commands
        here, read the result, drop the copy. ``at`` is any revision on any line; ``KernelError`` for one that does not
        exist. Building the copy costs the size of the state (the current state is copied, not replayed); for an older
        revision it costs the replay since the nearest cached snapshot, as ``materialize`` does."""
        if at is None:
            model = type(self.model).restore(self.model.serialize())
        else:
            try:
                model = self.materialize(at)
            except KeyError as exc:
                raise KernelError(f"there is no revision {at}") from exc
        copy = Document(model, clock=self._clock, lock_clock=self._lock_clock)
        copy._origin = model.serialize()  # its log starts here: what it can show of its own beginning (D1308)
        return copy

    # ------------------------------------------------------------------ what-ifs and proposals (D1308)
    def what_if(self, at: Revision | None = None, *, author: str | None = None) -> WhatIf:
        """A :class:`~claudia_core.WhatIf` that starts from the state now (or at ``at``, any revision on any line):
        a private copy that remembers what it is asked to do, to be handed back as a :class:`~claudia_core.Proposal`.
        ``KernelError`` for a revision that does not exist."""
        return WhatIf(self, at, author)

    def footprint(self, proposal: Proposal) -> tuple[Region, ...]:
        """The places ``proposal`` would change, read against the state it was made on."""
        return places(self.materialize(proposal.base), proposal.commands, self._clock(), proposal.author)

    def apply_proposal(self, proposal: Proposal, *, author: str | None = None, via: str | None = None) -> Applied:
        """Carry out ``proposal`` on the document as one step by ``author`` (one entry, one undo step), tagged ``via``.

        Refused with :class:`~claudia_core.ProposalOutdated`, and nothing changed, when a step after the one the
        proposal was made on touches a place it touches or moves one of them, or when that step is not on the line the
        document is on; never rebased (D263). A place somebody holds refuses it whole (``RegionHeld``). ``KernelError``
        for a proposal that does nothing."""
        if not proposal.commands:
            raise KernelError("a proposal that does nothing has nothing to carry out")
        base = proposal.base
        if base is not None and not self.log.on_path(base, self.revision):
            raise ProposalOutdated(())
        later = self.log.since(base, self.branch)
        if later:
            footprint = self.footprint(proposal)
            state = self.materialize(base)
            conflicts: list[Region] = []

            def look(entry: Step, inverse: Command) -> None:
                touched = [r for each in (entry.command, inverse) for r in _regions_of(each, state)]
                for region in footprint:
                    moved = transform(region, entry.command)
                    if region not in conflicts and (
                        any(region.overlaps(other) for other in touched)
                        or moved is None
                        or moved.to_data() != region.to_data()
                    ):
                        conflicts.append(region)

            replay(state, later, look)
            if conflicts:
                raise ProposalOutdated(conflicts)
        command = proposal.commands[0] if len(proposal.commands) == 1 else Batch(proposal.commands)
        return self.execute(command, author=author, via=via)

    # ------------------------------------------------------------------ checkpoints (E1.7)
    @property
    def checkpoints(self) -> tuple[CheckpointInfo, ...]:
        """The checkpoints on the visible line, in order."""
        return tuple(self._checkpoints)

    def save_checkpoint(self, author: str | None = None, label: str | None = None) -> CheckpointInfo | None:
        """File > Save. Labels the current state. ``None`` if nothing changed since the last checkpoint."""
        head = self._state_head
        if head is None or (self._checkpoints and self._checkpoints[-1].marks == head):
            return None
        number = len(self._checkpoints) + 1
        self._commit(Checkpoint(label or f"Checkpoint {number}", head), author, None, "do", None)
        return self._checkpoints[-1]

    def restore_checkpoint(self, number: int, author: str | None = None) -> Applied | None:
        """Go back to a checkpoint by **forking**: the document continues from that state on a new line.

        What came after stays in the log, unchanged and readable, on a side line (``side_revisions``) until an owner
        discards it (``discard_side_history``); no revision id changes. The first entry of the new line records who
        restored what. Everybody's undo steps and checkpoints are those of the new line; locks and presence are
        cleared. Returns ``None`` if the document is already in that state."""
        if not 1 <= number <= len(self._checkpoints):
            raise KernelError(f"no checkpoint number {number}")
        info = self._checkpoints[number - 1]
        if info.marks == self._state_head:
            return None
        return self._fork_back(info.label, info.marks, info.entry, author)

    def restore_revision(self, rev: Revision, author: str | None = None) -> Applied | None:
        """Go back to the state after any one step of the line the document is on (D553), the way
        ``restore_checkpoint`` goes back to a labelled one: by forking, so what came after stays on a side line and
        nothing is lost.

        The step is named in the first entry of the new line by what it did. ``KernelError`` for a revision that is not
        on the active line (a side line's steps are reached by switching to it). ``None`` if the document is in that
        state already."""
        if rev not in self.history_revisions():
            raise KernelError(f"there is no step {rev} on this line")
        if rev == self._state_head:
            return None
        label = f"{self.log.get(rev).command.label} ({rev.seq})"
        return self._fork_back(label, rev, rev, author)

    def _fork_back(self, label: str, marks: Revision, at: Revision, author: str | None) -> Applied | None:
        if self.materialize(marks).serialize() == self.model.serialize():
            return None
        old = self.branch
        # fork at the step itself, so it stays in the visible history
        self._enter(Branch(self._new_restore_name(), at), new=True)
        return self._commit(Restore(label, marks, old), author, None, "do", None)

    # ------------------------------------------------------------------ lines: the way back
    def branches(self) -> list[BranchInfo]:
        """Every branch of the history: the active one, and the ones a restore left behind."""
        return [
            BranchInfo(name, self.log.head(name), name == self.branch, branch.fork_point)
            for name, branch in self.log.branches.items()
        ]

    def peek_branch(self, branch: str) -> DocumentModel:
        """A read-only look at ``line`` without switching to it (E3.8): the state at its head, on a scratch model.

        Like ``materialize`` the live model, the active line and everybody's undo steps are untouched; this is how a
        person previews a hidden line (or the active one) before asking to make it current. ``KernelError`` for a
        name that is not a line of this document."""
        if branch not in self.log.branches:
            raise KernelError(f"there is no branch called {branch!r}")
        return self.materialize(self.log.head(branch))

    def peek_revision(self, rev: Revision) -> Look:
        """A read-only look at the document after one step of its history, on any line (D551): the state at ``rev``, the
        step itself, and the regions the step touched. This is what replaying the history shows, one step at a time.

        The regions are the command's own, read against the state before the step and then against the state after it,
        each place once: a removed thing is found in the first, a new one in the second. A command that cannot say
        where it acts on one of the two states (the thing is not there) adds nothing from it. Like ``materialize`` it
        touches neither the live model, the active line nor anybody's undo steps. ``KernelError`` for a revision the
        document does not have."""
        if not self.log.has(rev):
            raise KernelError(f"there is no revision {rev}")
        entry = self.log.get(rev)
        after = self.materialize(rev)
        before = self.materialize(entry.parent)
        focus: list[Region] = []
        seen: set[str] = set()
        for model in (before, after):
            try:
                found = entry.command.regions(model)
            except (KeyError, ValueError, IndexError):
                continue  # the thing it acts on is not in this state
            for region in found:
                key = json.dumps(region.to_data(), sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    focus.append(region)
        return Look(rev, after, entry, tuple(focus))

    def changes_since(self, rev: Revision, limit: int = 500) -> Changes:
        """Every place that changed after the step ``rev``, on the line the document is on (D553): what "show the
        differences from now" tints in the view of an earlier step.

        The steps after ``rev`` are replayed once on a scratch model, starting from the state at ``rev``; each
        step's own places are read against the state after it and its inverse's against the same state, so a thing that
        was taken away is named where it was. A step that cannot say where it acts adds nothing. Each place is named
        once, in order of first change; after ``limit`` places the rest are left out and ``truncated`` says so.
        ``KernelError`` for a revision that is not on the active line."""
        path = self.log.path(self.revision)
        position = next((i for i, e in enumerate(path) if e.rev == rev), None)
        if position is None:
            raise KernelError(f"there is no step {rev} on this line")
        found: list[Region] = []
        seen: set[str] = set()
        truncated = False
        model = self.materialize(rev)

        def look(entry: Step, inverse: Command) -> None:
            nonlocal truncated
            for command in (entry.command, inverse):
                try:
                    places = command.regions(model)
                except (KeyError, ValueError, IndexError):
                    continue
                for region in places:
                    key = json.dumps(region.to_data(), sort_keys=True)
                    if key in seen:
                        continue
                    if len(found) >= limit:
                        truncated = True
                        return
                    seen.add(key)
                    found.append(region)

        replay(model, path[position + 1 :], look)
        return Changes(tuple(found), truncated)

    def last_seen(self, present: Callable[[DocumentModel], bool]) -> Revision | None:
        """The last step of the line the document is on after which ``present(model)`` was true, or ``None`` if it never
        was (D551). What a tag to something that has since been deleted needs: the replay goes to the last moment it was
        there. The history is replayed once, forwards, on a scratch model; nothing live is touched."""
        model = type(self.model).empty()
        seen: Revision | None = None

        def look(entry: Step, _inverse: Command) -> None:
            nonlocal seen
            if present(model):
                seen = entry.rev

        replay(model, self.log.path(self.revision), look)
        return seen

    def switch_to(self, line: str, author: str | None = None) -> Applied | None:
        """Make an existing line the one the document continues on (the way back after a restore).

        Like a restore this moves everybody: model, undo steps and checkpoints are those of ``line``; locks and
        presence are cleared; views get ``BranchSwitched`` and ``Rebuilt``. Nothing is lost and no id changes. The
        first new entry on ``line`` (``core.Switch``) records who came back from where. ``None`` if the document is
        on that line already. Who may do this, and the confirmation, are decisions of the layer above."""
        if line not in self.log.branches:
            raise KernelError(f"there is no line called {line!r}")
        if line == self.branch:
            return None
        old = self.branch
        self._enter(self.log.branches[line], new=False)
        return self._commit(Switch(old), author, None, "do", None)

    def _enter(self, branch: Branch, *, new: bool) -> None:
        """Continue on ``branch`` (created now if ``new``): stored first, then the state is rebuilt from its path."""
        old, old_path = self.branch, self.log.path(self.revision)
        if self.store is not None:
            self.store.write_branch(branch, True)
        if new:
            assert branch.fork_point is not None
            self.log.fork(branch.name, branch.fork_point)
        self.log.activate(branch.name)
        self.branch = branch.name
        self._rebuild()
        self._reindex()
        shared = None  # the last revision both paths have in common: where views can keep what they have
        for before, after in zip(old_path, self.log.path(self.revision), strict=False):
            if before.rev != after.rev:
                break
            shared = after.rev
        with self.bus.batching():
            self.bus.emit(BranchSwitched(old, branch.name, shared))
            self.bus.emit(Rebuilt())

    def _new_restore_name(self) -> str:
        taken = {n for n in self.log.branches if n.startswith("restore-")}
        number = len(taken) + 1
        while f"restore-{number}" in taken:
            number += 1
        return f"restore-{number}"

    def history_revisions(self) -> list[Revision]:
        """The revisions of the visible history: the path of the active line."""
        return [e.rev for e in self.log.path(self.revision)]

    def side_revisions(self) -> list[Revision]:
        """Everything in the log that is not part of the visible history (abandoned futures, what-if lines)."""
        visible = set(self.history_revisions())
        return sorted(
            (
                e.rev
                for branch in self.log.branches
                for e in self.log.path(self.log.head(branch))
                if e.rev not in visible
            ),
            key=lambda r: (r.branch, r.seq),
        )

    def discard_side_history(self) -> list[Revision]:
        """Permanently forget everything outside the visible history (the owner's act; permission is E2.3).

        Returns the revisions removed. Chat records keep their ``at`` revision even if it is gone."""
        removed = self.log.discard_off_path(self.revision)
        if removed:
            if self.store is not None:
                self.store.discard_entries(removed)
            for rev in removed:
                self._snapshots.pop(rev, None)
        return removed

    # ------------------------------------------------------------------ redaction (E1.8, D229, D720–D726)
    def on_purge(self, hook: Callable[[tuple[Revision, ...]], None]) -> None:
        """Register a cache (AI memory, asset index, search index, ...) that must forget redacted content."""
        self._purge_hooks.append(hook)

    def plan_redaction(
        self,
        revisions: Iterable[Revision] = (),
        *,
        chat: Iterable[int] = (),
        parts: Mapping[Revision, Iterable[str]] | None = None,
    ) -> RedactionPlan:
        """Work out what redacting these steps and chat messages does, without changing anything (D721).

        A step may be on any line, a hidden one too (D724). Each is replaced by its blanked form (D720); ``parts``
        blanks only some things of an import (D723). Every line that holds a replaced step is replayed, and a later
        step that no longer applies is blanked as well and named in ``dependents`` (D722), until every line replays; one
        whose blank of the same shape still does not apply becomes a no-op tombstone. ``RedactionError`` for a request
        that names nothing, something the document does not have, something that holds no content or is redacted
        already, and for the last resort: a history that does not replay before any blanked step."""
        targets = self._redactable(revisions)
        numbers = self._redactable_chat(chat)
        wanted = {rev: frozenset(things) for rev, things in (parts or {}).items()}
        if not set(wanted) <= set(targets):
            raise RedactionError("parts can only be given for a step that is redacted")
        if not targets and not numbers:
            raise RedactionError("nothing to redact")
        replacements = {rev: self._blanked(rev, wanted.get(rev)) for rev in targets}
        dependents: list[Revision] = []
        while (failing := self._first_failure(replacements)) is not None:
            rev, cause = failing
            entry = self.log.get(rev)
            if rev in replacements and not isinstance(replacements[rev], RedactedCommand):
                # its same-shape blank does not apply either: it becomes a no-op tombstone (D722)
                replacements[rev] = tombstone(entry.command)
                continue
            if rev in replacements or entry.redacted or entry.command.meta:
                raise RedactionError(
                    f"Redacting this would stop step {rev} ({entry.command.label}) from working, even if it were "
                    f"blanked too ({cause}). Nothing was redacted."
                )
            replacements[rev] = self._blanked(rev, None)
            dependents.append(rev)
        after, places = self._replayed(replacements, self.revision)
        imports = tuple(rev for rev in targets if isinstance(self.log.get(rev).command, Import))
        changes_now = after.serialize() != self.model.serialize()
        return RedactionPlan(
            targets,
            tuple(dependents),
            numbers,
            imports,
            changes_now,
            after,
            dict(replacements),
            self._redaction_basis(),
            places if changes_now else (),
        )

    def redact(self, what: RedactionPlan | Iterable[Revision], *, author: str | None = None) -> Applied:
        """Remove the *content* of steps and chat messages from the document and from its store (D229).

        ``what`` is a plan from :meth:`plan_redaction`, shown to the person first, or a bare list of steps, which is
        refused if any later step would have to be blanked with them: nobody's work goes without being named first.
        Each entry keeps its revision, author, time, kind and shape; each message its number, author, recipient and
        time. The redaction itself is logged (without content); the store is rewritten so that no copy of the content
        is left in it (D725); snapshots and undo steps derived from the content are dropped, purge hooks run, and the
        state is rebuilt from the redacted log. ``RedactionError`` if the document changed since the plan was made.
        Copies and backups made earlier keep the content (D21)."""
        plan = what if isinstance(what, RedactionPlan) else self._plan_alone(what)
        if plan.basis != self._redaction_basis():
            raise RedactionError("The document changed since this redaction was worked out. Look at it again.")
        originals = [self.log.get(rev) for rev in plan.replacements]
        chat_before = list(self.chat)
        for rev, command in plan.replacements.items():
            self.log.replace_command(rev, command)
        self.chat = [record.blanked() if record.number in plan.chat else record for record in self.chat]
        if self.store is not None:
            try:
                self.store.rewrite(self.log, self.chat)
            except BaseException:
                for original in originals:
                    self.log.restore_entry(original)
                self.chat = chat_before
                raise
        self._snapshots.clear()
        applied = self._commit(Redaction(plan.revisions, plan.chat), author, None, "do", None)
        for hook in self._purge_hooks:
            hook(plan.revisions)
        if plan.revisions:
            self._rebuild()
            for history in self._histories.values():  # undoing blanked content makes no sense
                history.purge(set(plan.revisions))
        with self.bus.batching():
            self.bus.emit(Redacted(plan.revisions, plan.chat))
            if plan.revisions:
                self.bus.emit(Rebuilt())
        return applied

    def _plan_alone(self, revisions: Iterable[Revision]) -> RedactionPlan:
        plan = self.plan_redaction(revisions)
        if plan.dependents:
            later = ", ".join(map(str, plan.dependents))
            raise RedactionError(
                f"Redacting this would also blank {later}, which needs what it takes away. Ask for a plan, show it, "
                "then redact that."
            )
        return plan

    def _redactable(self, revisions: Iterable[Revision]) -> tuple[Revision, ...]:
        revs = tuple(sorted(set(revisions), key=lambda r: (r.branch, r.seq)))
        for rev in revs:
            if not self.log.has(rev):
                raise RedactionError(f"{rev} is not part of this document's history")
            entry = self.log.get(rev)
            if entry.command.meta:
                raise RedactionError(f"{rev} is a {entry.command.kind} record and holds no content")
            if entry.redacted:
                raise RedactionError(f"{rev} is already redacted")
        return revs

    def _redactable_chat(self, numbers: Iterable[int]) -> tuple[int, ...]:
        wanted = tuple(sorted(set(numbers)))
        by_number = {record.number: record for record in self.chat}
        for number in wanted:
            if number not in by_number:
                raise RedactionError(f"there is no chat message {number}")
            if by_number[number].redacted:
                raise RedactionError(f"chat message {number} is already redacted")
        return wanted

    def _blanked(self, rev: Revision, parts: frozenset[str] | None) -> Command:
        command = self.log.get(rev).command
        try:
            if parts is None:
                return command.redacted_in(type(self.model))
            if not isinstance(command, Import):
                raise RedactionError(f"{rev} is not an import: only an import is redacted in parts")
            return command.blanked(type(self.model), parts)
        except KernelError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            raise RedactionError(f"{rev} cannot be blanked: {exc}") from exc

    def _with(self, replacements: Mapping[Revision, Command], head: Revision | None) -> list[Step]:
        return [
            replace(e, command=replacements[e.rev], redacted=True) if e.rev in replacements else e
            for e in self.log.path(head)
        ]

    def _replayed(
        self, replacements: Mapping[Revision, Command], head: Revision | None
    ) -> tuple[DocumentModel, tuple[Region, ...]]:
        """The state at ``head`` with the replacements, and the places the blanked steps on that line touch, read as
        ``changes_since`` reads them: each step's own regions against the state after it, once each, at most 500."""
        model = type(self.model).empty()
        places: dict[str, Region] = {}

        def look(entry: Step, _inverse: Command) -> None:
            if entry.rev not in replacements or len(places) >= REDACTION_PLACES:
                return
            for command in (entry.command, self.log.get(entry.rev).command):
                try:
                    found = command.regions(model)
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                for region in found:
                    places.setdefault(json.dumps(region.to_data(), sort_keys=True), region)

        replay(model, self._with(replacements, head), look)
        return model, tuple(places.values())[:REDACTION_PLACES]

    def _first_failure(self, replacements: Mapping[Revision, Command]) -> tuple[Revision, Exception] | None:
        """The first step that no longer applies on a line that holds one of the replaced steps, and why."""
        for name in sorted(self.log.branches):
            path = self._with(replacements, self.log.head(name))
            first = next((i for i, e in enumerate(path) if e.rev in replacements), None)
            if first is None:
                continue
            done = 0

            def count(_entry: Step, _inverse: Command) -> None:
                nonlocal done
                done += 1

            try:
                replay(type(self.model).empty(), path, count)
            except Exception as exc:  # noqa: BLE001  (any refusal of a step is what the plan looks for)
                if done < first:  # the steps before any replaced one were never changed
                    raise RedactionError(f"the history of the line {name!r} does not replay ({exc})") from exc
                cause = exc.__cause__ if isinstance(exc, ReplayError) and exc.__cause__ is not None else exc
                return path[done].rev, cause  # type: ignore[return-value]
        return None

    def _redaction_basis(self) -> tuple:
        """What a plan was made against: the head of every line and the chat."""
        heads = tuple((name, self.log.head(name)) for name in sorted(self.log.branches))
        return heads, tuple((record.number, record.redacted) for record in self.chat)

    def _rebuild(self) -> None:
        """Throw the state away and build it again from the log (undo stacks and holds go with it)."""
        self.model = type(self.model).empty()
        for history in self._histories.values():
            history.clear()
        for hold in list(self.presence.holds()):
            self.presence.release(hold.owner)
        # Same shape as `open` (D1315): the replay itself needs nothing of `self` but `self.model`.
        for entry, inverse in replay_collecting(self.model, self.log.path(self.revision)):
            self._record_history(entry, inverse)

    # ------------------------------------------------------------------ manifest (E1.9)
    def manifest(self) -> Manifest:
        """What this document requires: app, schemas of the commands in its log, functions and fonts."""
        used: dict[str, int] = {}
        for entry in self.log.path(self.revision):
            for leaf in entry.command.leaves():
                used[leaf.kind] = max(used.get(leaf.kind, 0), leaf.schema)
        return Manifest(self.model.app, self.model.state_schema, used, self.model.requirements())

    def check_requirements(self, env: Environment) -> RequirementReport:
        """Compare the manifest with what this installation offers."""
        return check(self.manifest(), env)

    def apply_report(self, report: RequirementReport) -> None:
        """Mark results of changed functions stale; the model recomputes them when the function is available."""
        names = report.stale_names
        if names:
            self.model.mark_stale(names)
            self.bus.emit(ResultsStale(names))


def _regions_of(command: Command, model: DocumentModel) -> tuple[Region, ...]:
    """Where ``command`` acts in ``model``; nowhere when it cannot say."""
    try:
        return command.regions(model)
    except (KeyError, ValueError, IndexError):
        return ()


def _usable(snapshot: Snapshot, model_cls: type[DocumentModel]) -> bool:
    return snapshot.app == model_cls.app and snapshot.state_schema == model_cls.state_schema


def environment_of(model_cls: type[DocumentModel], *, functions=None, fonts=(), providable_fonts=()) -> Environment:
    """What this installation offers for a manifest check (the server adds its function folder and fonts)."""
    return Environment(
        model_cls.app,
        model_cls.state_schema,
        model_cls.registry.schemas(),
        dict(functions or {}),
        frozenset(fonts),
        frozenset(providable_fonts),
    )


def _standing(entries: Iterable[Step]) -> Iterator[Step]:
    """The entries in order, without each step that was undone (or redone) by the very next entry, nor that entry: the
    two together changed nothing."""
    pending: Step | None = None
    for entry in entries:
        if (
            pending is not None
            and entry.origin in ("undo", "redo")
            and entry.of == pending.rev
            and entry.author == pending.author
        ):
            pending = None
            continue
        if pending is not None:
            yield pending
        pending = entry
    if pending is not None:
        yield pending
