# claudia-core and claudia-server — Epic 1 and E3.1

State: kernel `claudia-core` 0.3.0 (draft 3), server `claudia-server` 0.1.0, client trust `claudia-client` 0.1.0. 443 tests green on Python 3.14.6; ruff, mypy, vulture, the Sphinx build and the performance guards are clean (`uv run python scripts/check_debt.py`). Kernel: Locks are enforced in `execute`, restoring forks, the way back exists (`switch_to`), edits in flight are refused (`StaleEdit`), and the project hygiene is in place (Sphinx docs, versioned API, debt checks, CI). The network layer is described in the section "Server (E3.1)" below. Written 2026-11-02.
Scope agreed: kernel only (E1.1–E1.9), proven by a mini-computes port plus composes/creates stubs.
No sockets, encryption or container in the kernel (E2); no formulas (E6.1). The hub, protocol and authentication are in the separate package `claudia-server` (E3.1).

## What is where

| Story | Module | State |
|---|---|---|
| E1.1 DocumentModel | `model.py`, `commands.py`, `context.py`, `document.py` | done. Toy `ListModel` in `testing.py`; a purity test proves no I/O and no app words in the kernel |
| E1.2 Log as truth | `log.py`, `replay.py`, `revision.py`, `Document.open/materialize/snapshot` | done. Randomized replay equals live state, including undo stacks. Snapshots are caches, ignored if foreign or stale |
| E1.3 Schema versions | `commands.py` (`CommandRegistry.upcaster`, envelope `{k,s,d}`), `errors.py` | thin, tested with fixture logs v1 (upcast) and v3 (refused) |
| E1.4 Per-author undo | `history.py`, `Document.undo/redo` | done, see "Undo" below |
| E1.5 Region | `region.py`, `presence.py`; `CellRegion` (computes), `TextRange` (composes), `ObjectSet` (creates), `Interval` (toy) | done |
| E1.6 Message classes | `messages.py`, `store.py`, `Document.publish/post_chat` | done. The store interface has no method for ephemeral messages |
| E1.7 Checkpoints | `Document.save_checkpoint/restore_checkpoint`, `core.Checkpoint` | done |
| E1.8 Redaction | `Document.redact`, `Command.redacted()`, purge hooks | thin, tested including a rolled-back unsafe redaction |
| E1.9 Manifest | `manifest.py`, `Document.manifest/check_requirements/apply_report` | thin, data model and check only |

Mini-computes (`claudia-computes`): `refs.py` from the demo unchanged; sheets, typed cells, `SetCells`, `Structure` (insert/delete rows and columns), `CellRegion`. Composes and creates stubs are about 150 lines each.

## Design points (decided D45–D49 unless marked open)

1. **Revision ids** are `Revision(branch, seq)`; seq continues along a branch from its fork point. No content hash, so redaction never changes an id. (D45.)
2. **Undo follows the log, not the caller.** Undo stacks are rebuilt from log entries (`origin` do/undo/redo/restore, `of` = revision reversed). Reopening a document restores everybody's stacks; live use and replay cannot disagree.
3. **Collaborative undo is not blind.** The demo executes the stored inverse as is; with two authors an index-based inverse then hits the wrong element. New hook `Command.shifted_by(other)`: the inverse is moved through everything that ran since. Returning `None` means "a colleague changed this after you": undo is refused with `UndoConflict`, nothing consumed. **Decided (D46):** if a colleague wrote the same cell after me, my undo is refused; it never overwrites their work.
4. **`execute` enforces locks** (D47): a command that touches a region a colleague holds raises `RegionHeld` and changes nothing, for people and the `ai` user alike. Undo checks the same rule. Replicas replaying accepted entries (`apply_entry`) are not checked. `check_free` stays public for the UI to ask in advance.
5. **Restoring a checkpoint forks** (D48). The document continues on a new line `restore-N`, forked at the checkpoint's own log entry; its first entry (`core.Restore`) records who restored what. The old future stays in the log under its old, unchanged revision ids on a side line, hidden from the visible history (`history_revisions`, `side_revisions`). `discard_side_history()` forgets it permanently (the owner's act; the permission check is E2.3). **The way back:** `switch_to(line)` makes any line the active one again (same effects as a restore: everybody moves, undo steps and checkpoints are those of that line, locks cleared, `BranchSwitched` + `Rebuilt`; the act is recorded as a `core.Switch` entry). `lines()` lists the lines. Who may restore or switch, and the confirmation, are the rules of the live session and not decided yet (the owner is thinking about them). Everybody's undo steps, checkpoints and the model are those of the new line; locks and presence are cleared; views get `BranchSwitched` + `Rebuilt`. Restoring costs one replay, with no growth of the log. Chat records keep their `at` revision even after a discard. The `diff_to` hook of draft 1 is gone.
6. **Redaction contract (still open, the owner is thinking about it).** A command's `redacted()` must keep what later commands depend on (a sheet, an object, text length) and blank only the content. The default is a no-op tombstone. If the redacted log no longer replays, the redaction is rolled back and explained. After redaction the state is rebuilt from the redacted log, snapshots are dropped, undo steps derived from the content are dropped, presence is cleared, purge hooks run (`Document.on_purge`).
7. **Tracking is no longer a switch.** The demo's `track.on` decided whether history existed. With the log as truth it always exists; who may see it is E2.4.
8. **Chat is not a command.** The demo logged `ChatMessage` as a command; it now lives in the chat store with the revision it was written at.
9. **`settle(ctx)`** is the single place a model recomputes after a command (once per command, also after a rolled-back one). It must not fail; failing after a successful apply leaves the model inconsistent. Worker results (D37) will arrive as commands with final values.

10. **Edits in flight** (D49). `execute(command, author=..., base=revision)`: `base` is the revision the author's view was at. If it is not on the path of the active line (somebody restored a checkpoint or switched the line while the edit was on its way) the edit is refused with `StaleEdit` and nothing happens. A base on the shared part of the old and the new line is fine. The server (E3.1) passes the base of every edit it receives, and the client reloads on `BranchSwitched`.

## Project hygiene (the rules added 2026-11-02)

* **Docs from the code.** `docs/` is a Sphinx project (autodoc, napoleon, MyST). The API reference is generated from the docstrings; every public class, function and method must have one (a test checks it, inherited descriptions count). `sphinx-build -W` makes any unresolved reference an error.
* **Versioned API.** `claudia_core.__all__` is the public API; `__version__` (semantic versioning, `_version.py`); `CHANGELOG.md`; `docs/versioning.md` is the policy. `tests/api/<package>.json` snapshots names and signatures, so an API change is a visible diff that comes with a version bump and a changelog entry (a test checks both).
* **Debt checks.** `uv run python scripts/check_debt.py` runs ruff, mypy, vulture, the tests, the docs build and the performance guards; `.github/workflows/ci.yml` runs it on Linux, Windows and macOS on every push and weekly. Exceptions are written down with their reason (`pyproject.toml`, `vulture_whitelist.py`).
* **What the first run found.** Unused code in the ported `refs.py` (`CellMove`, `RangeRef.contains`, `of_cell`, `shape`): removed, the demo has it back for E6.7. The performance guards found that `log.since()` and therefore every undo cost as much as the whole history; both now cost only the entries involved. Opening a document is linear in its history by design until snapshots (E4); a guard keeps it linear.
* `CONTRIBUTING.md` states the rules: test first, clean code, docs from code, versioned APIs, regular debt checks, a pure kernel.

## Server (E3.1): packages `claudia-server` and `claudia-client` (see also server.md)

Built after the kernel as separate packages (the backlog first said "in claudia-core"; the kernel stays free of network code and keeps its purity test). Run with `python3 -m claudia_server` (`--web DIR`, `--tls-cert/--tls-key/--tls-name`, `--no-tls`, `--redirect-port`, `--allow-origin`, `--no-create`, `--state-dir`). Documents are in memory until the container exists (E2).

| Part | Module | What it does |
|---|---|---|
| Protocol | `protocol.py` | JSON frames: requests `{id, method, params}`, responses `{id, ok, result \| error}`, pushed `{event, data}`. A `MethodTable` that an app extends (`core_methods.extended()`); methods: ping, snapshot, lines, changes_since, history, checkpoints, users, apply, undo, redo, save_checkpoint, presence, lock, unlock, chat. Typed parameters with limits; kernel errors become codes: `locked`, `conflict`, `stale`, `command_error`, `forbidden`, ... Served at `/api/protocol` (`PROTOCOL_VERSION` 1). |
| Hub | `hub.py` | `Hub` (documents, limits, idle unloading, lock sweeping), `HostedDocument`, `Connection`, a `DocumentProvider` (`MemoryProvider` now). Forwards kernel events with audience rules: history to its author only, private chat to sender and recipient, ephemeral messages not echoed. A dead or slow client never breaks the edit that is being broadcast. |
| Access | `auth.py`, `app.py` | `hello` handshake in the first frame (name, password, optional `create`); roles owner/editor/viewer; viewers cannot write; the name `ai` is refused; scrypt hashes with a random salt, an unknown name costs the same time as a wrong password; wrong password, unknown name and missing document give one answer; the creator of a new document is its owner. Close codes 4400/4401/4403/4404/4408/1013. Foreign browser origins are refused unless named. No endpoint lists documents (D50, proposal). |
| TLS | `certs.py`, `redirect.py`, client `trust.py` | Own self-signed certificate made once (names: localhost, 127.0.0.1, ::1, host name, `--tls-name`), renewed before expiry. Plain-HTTP redirect port. The client trusts it like an SSH host: fingerprint shown once, remembered, a different certificate refused loudly. Ported from the demo. |

**Edits in flight.** `apply` carries `base`, the revision of the view the edit was made against; after a restore or switch the edit is refused with `stale` (D49). A client reloads on the `branch` and `rebuilt` events and on `stale`.

**Not on the wire on purpose:** restore, switch and discarding side history: the rules for a live session are the owner's to decide (E3.7, D48).

**Known gaps** (each has a story): viewers still receive history and chat (E2.4); no rate limiting (E2.7); the user directory is an in-memory stand-in (E2.3); locks are per user name, not per connection; the demo's client replica `RemoteSession` was not ported (calculation is on the server, D36; the client comes with E5); no document list (D50); sessions are not persisted.

## Not done, on purpose

Container, key slots, encryption (E2); persistence of hosted documents (E2); the AI participant (E3.6/E7); formulas, recalculation, names, SQL, layout, drawing (E6.1); font and function services. Free-form what-if branches have no API yet (only the restore fork). Opening replays the whole log (snapshots shorten it, E4).

## Decision-log text

> **D45 · Revision identifiers are `(branch, seq)` with a parent link, not content hashes and not bare integers. · 2026-11-02 · Notes:** sequence numbers continue along a branch from its fork point; redaction never changes an id; no tamper evidence from the id itself (the container can add a hash chain later, E2.5).

## Running it

```
uv sync            # Python 3.14, creates .venv
uv run pytest      # all packages
```
`python3 -m claudia_server --no-tls` starts a development server on 127.0.0.1:8765. If a package directory was empty when you first ran `uv sync`, run `uv sync --reinstall`.
