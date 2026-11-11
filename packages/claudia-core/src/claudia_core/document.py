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

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .clock import monotonic, utc_now
from .commands import Checkpoint, Command, Redaction, Restore, Switch
from .context import Context
from .errors import (
    KernelError,
    RedactionError,
    RegionHeld,
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
from .log import CommandLog, Entry
from .manifest import Environment, Manifest, RequirementReport, check
from .messages import ChatRecord, Ephemeral, parse_chat
from .model import DocumentModel, Snapshot
from .presence import Presence
from .region import Region
from .replay import replay
from .revision import Branch, Revision
from .store import DocumentStore


@dataclass(frozen=True)
class Applied:
    """Result of ``execute``."""

    revision: Revision
    command: Command
    inverse: Command
    entry: Entry


@dataclass(frozen=True)
class Line:
    """One line of the log (``main``, or ``restore-N`` after a restore)."""

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
        doc = cls(model, log=log, branch=branch, **options)
        replay(model, path[start:], doc._record_history)
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
        self, command: Command, *, author: str | None = None, time: str | None = None, base: Revision | None = None
    ) -> Applied:
        """Apply ``command`` atomically as ``author``. On any error the document is unchanged.

        ``base`` is the revision the author's view was at. If it is not on the active line (a checkpoint was restored
        or the line switched while the edit was on its way) the edit is refused with ``StaleEdit``. ``None`` skips
        the check. Refuses (``RegionHeld``) a command that touches a region somebody else holds: the rule is enforced
        here, once, for people and the AI alike. Replaying entries the server already accepted (``apply_entry``) is
        not checked."""
        if base is not None and not self.log.on_path(base, self.revision):
            raise StaleEdit(base, self.branch)
        self.check_free(author, command)
        return self._commit(command, author, time, "do", None)

    def apply_entry(self, entry: Entry, *, persist: bool = True) -> Applied:
        """Replay an entry made elsewhere (a replica following the server). Must be exactly the next one."""
        expected = self.log.next_revision(self.branch)
        if entry.rev != expected or entry.parent != self.revision:
            raise RevisionMismatch(f"expected {expected} after {self.revision}, got {entry.rev} after {entry.parent}")
        return self._commit(
            entry.command, entry.author, entry.time, entry.origin, entry.of, persist=persist, redacted=entry.redacted
        )

    def entries_since(self, revision: Revision | None) -> list[Entry]:
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
        entry = Entry(rev, parent, author, when, command, origin, of, redacted)
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

    def _index(self, entry: Entry) -> None:
        if not entry.command.meta:
            self._state_head = entry.rev
        command = entry.command
        if isinstance(command, Checkpoint):
            self._checkpoints.append(
                CheckpointInfo(
                    len(self._checkpoints) + 1, command.label_text, entry.author, command.marks, entry.rev, entry.time
                )
            )

    def _record_history(self, entry: Entry, inverse: Command) -> bool:
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
        for entry in self.log.since(step.rev, self.branch):
            if entry.command.meta:
                continue
            # The step was written for the state right after step.rev. Everything that ran since moved things; so
            # follow all of it, our own undone steps too (they cancel out only if followed in order). Only a
            # colleague's change may make the step meaningless; that refuses the undo.
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
            model = type(self.model).empty()
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
        return Document(model, clock=self._clock, lock_clock=self._lock_clock)

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
        if self.materialize(info.marks).serialize() == self.model.serialize():
            return None
        old = self.branch
        # fork at the label itself, so the checkpoint stays in the visible history
        self._enter(Branch(self._new_restore_name(), info.entry), new=True)
        return self._commit(Restore(info.label, info.marks, old), author, None, "do", None)

    # ------------------------------------------------------------------ lines: the way back
    def lines(self) -> list[Line]:
        """Every line of the log: the active one, and the side lines a restore left behind."""
        return [
            Line(name, self.log.head(name), name == self.branch, branch.fork_point)
            for name, branch in self.log.branches.items()
        ]

    def peek_line(self, line: str) -> DocumentModel:
        """A read-only look at ``line`` without switching to it (E3.8): the state at its head, on a scratch model.

        Like ``materialize`` the live model, the active line and everybody's undo steps are untouched; this is how a
        person previews a hidden line (or the active one) before asking to make it current. ``KernelError`` for a
        name that is not a line of this document."""
        if line not in self.log.branches:
            raise KernelError(f"there is no line called {line!r}")
        return self.materialize(self.log.head(line))

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

    # ------------------------------------------------------------------ redaction (E1.8)
    def on_purge(self, hook: Callable[[tuple[Revision, ...]], None]) -> None:
        """Register a cache (AI memory, asset index, search index, ...) that must forget redacted content."""
        self._purge_hooks.append(hook)

    def redact(self, revisions: Iterable[Revision], *, author: str | None = None) -> Applied:
        """Remove the *content* of these commands from the history.

        Each entry keeps its revision, author, time, kind and ids; its command becomes ``command.redacted()``.
        The redaction itself is logged (without content), snapshots and undo steps derived from the content are
        dropped, purge hooks run, and the state is rebuilt from the redacted log, so replaying the stored log from now
        on gives exactly the state shown here. Copies and backups made earlier keep the content (D21)."""
        revs = tuple(sorted(set(revisions), key=lambda r: (r.branch, r.seq)))
        if not revs:
            raise RedactionError("nothing to redact")
        on_path = {e.rev for e in self.log.path(self.revision)}
        for rev in revs:
            if rev not in on_path:
                raise RedactionError(f"{rev} is not part of this document's history")
            entry = self.log.get(rev)
            if entry.command.meta:
                raise RedactionError(f"{rev} is a {entry.command.kind} record and holds no content")
            if entry.redacted:
                raise RedactionError(f"{rev} is already redacted")
        originals = [self.log.get(rev) for rev in revs]
        changed = [self.log.replace_command(e.rev, e.command.redacted()) for e in originals]
        try:  # the redacted log must still replay; if not, nothing was redacted
            replay(type(self.model).empty(), self.log.path(self.revision))
        except KernelError as exc:
            for original in originals:
                self.log.restore_entry(original)
            raise RedactionError(
                f"Redacting {', '.join(map(str, revs))} would break later commands ({exc}). "
                "The model must keep what other commands refer to when it redacts a command."
            ) from exc
        if self.store is not None:
            self.store.replace_entries(changed)
            self.store.drop_snapshots()
        self._snapshots.clear()
        applied = self._commit(Redaction(revs), author, None, "do", None)
        for hook in self._purge_hooks:
            hook(revs)
        self._rebuild()
        for history in self._histories.values():  # undoing blanked content makes no sense
            history.purge(set(revs))
        with self.bus.batching():
            self.bus.emit(Redacted(revs))
            self.bus.emit(Rebuilt())
        return applied

    def _rebuild(self) -> None:
        """Throw the state away and build it again from the log (undo stacks and holds go with it)."""
        self.model = type(self.model).empty()
        for history in self._histories.values():
            history.clear()
        for hold in list(self.presence.holds()):
            self.presence.release(hold.owner)
        replay(self.model, self.log.path(self.revision), self._record_history)

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
