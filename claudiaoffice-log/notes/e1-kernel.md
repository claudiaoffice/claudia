# claudia-core and the server base — Epic 1 and E3.1

Written 2026-11-02; moved here 2026-11-05. Scope agreed at the time: kernel only (E1.1–E1.9), proven by a
mini-computes port plus composes and creates stubs. No sockets, encryption or container in the kernel; no formulas.
The hub, protocol and authentication live in the separate package `claudia-server`.

Both of those boundaries have held since: the kernel is still standard-library only and still guarded by a purity
test, through four more epics of work.

## What is where

| Story | Module | State when written |
|---|---|---|
| E1.1 DocumentModel | `model.py`, `commands.py`, `context.py`, `document.py` | done. Toy `ListModel` in `testing.py`; a purity test proves no I/O and no app words in the kernel |
| E1.2 Log as truth | `log.py`, `replay.py`, `revision.py`, `Document.open/materialize/snapshot` | done. Randomized replay equals live state, including undo stacks. Snapshots are caches, ignored if foreign or stale |
| E1.3 Schema versions | `commands.py` (`CommandRegistry.upcaster`, envelope `{k,s,d}`), `errors.py` | thin, tested with fixture logs v1 (upcast) and v3 (refused) |
| E1.4 Per-author undo | `history.py`, `Document.undo/redo` | done |
| E1.5 Region | `region.py`, `presence.py`; `CellRegion`, `TextRange`, `ObjectSet`, `Interval` | done |
| E1.6 Message classes | `messages.py`, `store.py`, `Document.publish/post_chat` | done. The store interface has no method for ephemeral messages |
| E1.7 Checkpoints | `Document.save_checkpoint/restore_checkpoint`, `core.Checkpoint` | done |
| E1.8 Redaction | `Document.redact`, `Command.redacted()`, purge hooks | thin, tested including a rolled-back unsafe redaction |
| E1.9 Manifest | `manifest.py`, `Document.manifest/check_requirements/apply_report` | thin, data model and check only |

E1.10 (the style model) came later with the composes styling work; see `e9-composes.md`.

## Design points (D45–D49 unless marked open)

1. **Revision ids** are `Revision(branch, seq)`; `seq` continues along a branch from its fork point. No content hash,
   so redaction never changes an id. (D45.)
2. **Undo follows the log, not the caller.** Undo stacks are rebuilt from log entries (`origin` do/undo/redo/restore,
   `of` = revision reversed). Reopening a document restores everybody's stacks; live use and replay cannot disagree.
3. **Collaborative undo is not blind.** The demo executed the stored inverse as it was; with two authors an
   index-based inverse then hits the wrong element. The hook `Command.shifted_by(other)` moves the inverse through
   everything that ran since. Returning `None` means "a colleague changed this after you": the undo is refused with
   `UndoConflict` and nothing is consumed. (D46.)
4. **`execute` enforces locks** (D47): a command that touches a region a colleague holds raises `RegionHeld` and
   changes nothing, for people and the `ai` user alike. Undo checks the same rule. Replicas replaying accepted entries
   are not checked. `check_free` stays public for the UI to ask in advance.
5. **Restoring a checkpoint forks** (D48). The document continues on a new line `restore-N`, forked at the
   checkpoint's own log entry; its first entry (`core.Restore`) records who restored what. The old future stays under
   its old, unchanged revision ids on a side line, hidden from the visible history (`history_revisions`,
   `side_revisions`). `discard_side_history()` forgets it permanently. **The way back** is `switch_to(line)`, which
   makes any line active again with the same effects as a restore and is recorded as a `core.Switch` entry; `lines()`
   lists them. Everybody's undo steps, checkpoints and model are those of the new line; locks and presence are
   cleared; views get `BranchSwitched` and `Rebuilt`. Restoring costs one replay, with no growth of the log. Chat
   records keep their `at` revision even after a discard.
6. **Redaction contract (still open).** A command's `redacted()` must keep what later commands depend on (a sheet, an
   object, text length) and blank only the content. The default is a no-op tombstone. If the redacted log no longer
   replays, the redaction is rolled back and explained. After redaction the state is rebuilt from the redacted log,
   snapshots are dropped, undo steps derived from the content are dropped, presence is cleared, and purge hooks run.
7. **Tracking is no longer a switch.** The demo's `track.on` decided whether history existed. With the log as truth it
   always exists; who may see it is E2.4.
8. **Chat is not a command.** The demo logged `ChatMessage` as a command; it now lives in the chat store with the
   revision it was written at.
9. **`settle(ctx)`** is the single place a model recomputes after a command, once per command and also after a
   rolled-back one. It must not fail: failing after a successful apply leaves the model inconsistent.
10. **Edits in flight** (D49). `execute(command, author=…, base=revision)`: `base` is the revision the author's view
    was at. If it is not on the path of the active line, the edit is refused with `StaleEdit` and nothing happens. A
    base on the shared part of the old and the new line is fine. The server passes the base of every edit it receives,
    and the client reloads on `BranchSwitched`.

## Project hygiene (the rules added 2026-11-02)

- **Docs from the code.** `docs/` is a Sphinx project (autodoc, napoleon, MyST). Every public class, function and
  method must have a docstring, checked by a test, with inherited descriptions counting. `sphinx-build -W` makes any
  unresolved reference an error.
- **Versioned API.** `__all__` is the public API; `__version__` follows semantic versioning; a `CHANGELOG.md` per
  package; `docs/versioning.md` is the policy. `tests/api/<package>.json` snapshots names and signatures, so an API
  change is a visible diff that must come with a version bump and a changelog entry, checked by a test.
- **Debt checks.** `scripts/check_debt.py` runs ruff, mypy, vulture, the tests, the docs build and the performance
  guards; CI runs it on three OSes on every push and weekly. Exceptions are written down with their reason.
- **What the first run found.** Unused code in the ported `refs.py` (`CellMove`, `RangeRef.contains`, `of_cell`,
  `shape`), removed and due back with E6.7. Two real performance bugs: `log.since()` and therefore every undo cost as
  much as the whole history; both now cost only the entries involved, with scaling guards that fail if the cost ever
  grows with history again. Opening a document is linear in its history by design until snapshots, and a guard keeps
  it linear.
- `CONTRIBUTING.md` states the rules: test first, clean code, docs from code, versioned APIs, regular debt checks, a
  pure kernel.

## Server (E3.1): `claudia-server` and `claudia-client`

Built after the kernel as separate packages; the backlog first said "in claudia-core", but the kernel stays free of
network code and keeps its purity test.

| Part | Module | What it does |
|---|---|---|
| Protocol | `protocol.py` | JSON frames: requests `{id, method, params}`, responses `{id, ok, result \| error}`, pushed `{event, data}`. A `MethodTable` that an app extends. Typed parameters with limits; kernel errors become codes `locked`, `conflict`, `stale`, `command_error`, `forbidden` and so on. Served at `/api/protocol` with `PROTOCOL_VERSION` 1 |
| Hub | `hub.py` | `Hub` (documents, limits, idle unloading, lock sweeping), `HostedDocument`, `Connection`, a `DocumentProvider`. Forwards kernel events with audience rules: history to its author only, private chat to sender and recipient, ephemeral messages not echoed. A dead or slow client never breaks the edit being broadcast |
| Access | `auth.py`, `app.py` | The `hello` handshake in the first frame; roles owner/editor/viewer; viewers cannot write; the name `ai` refused; wrong password, unknown name and missing document give one answer; the creator of a new document is its owner. Close codes 4400/4401/4403/4404/4408/1013 |
| TLS | `certs.py`, `redirect.py`, client `trust.py` | A self-signed certificate made once and renewed before expiry; a plain-HTTP redirect port; the client trusts it like an SSH host, with the fingerprint shown once, remembered, and a different certificate refused loudly |

**Not on the wire on purpose:** restore, switch and discarding side history. The rules for a live session were the
owner's to decide, and became D51 and D52; the flow is E3.7 and is still not built.

## Demo v0 additions (D55–D57)

- **Server 0.2.0:** `GET /api/docs` and `Hub.listing()`; `FileProvider` and `FileDirectory` (`--dir`, not encrypted).
- **Server 0.3.0:** `log` and `chat_log`; the computes methods (`sheets`, `cells`, `set_cells`, `add_sheet`,
  `structure`), chosen per model by `methods_for`; `add_user` (owner only, D55); `summary` in the `command` event; the
  assistant as `Assistant` + pluggable `Engine` + `ScriptedEngine` (D56).
- **`claudia-computes`:** `parse_input` decides what typed text means (empty, `'` forces text, TRUE/FALSE, integers,
  floats, else text).
- **Web app:** Nuxt 4, single page, fonts bundled with no third-party requests. `Link` (protocol client with
  reconnect), `Session` (replica store, cell chunks of 64×16 loaded as the grid scrolls), virtualised grid, formula
  bar, history and chat panel, presence, menus, dialogs.
- **Found by the browser tests:** a closed socket must reject requests at once, and chunks in flight when a connection
  died must be forgotten, or the table stays empty after a server restart.

## Running it

```
uv sync            # Python 3.14, creates .venv
uv run pytest      # all packages
```

`python3 -m claudia_server --no-tls` starts a development server on 127.0.0.1:8765. If a package directory was empty
when `uv sync` first ran, use `uv sync --reinstall`.
