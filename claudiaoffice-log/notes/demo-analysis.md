# claudia computes demo — reference analysis

Written 2026-11-01 from `gtk_sheet_docker_security.zip`, read statically; the tests were not run. Moved here
2026-11-05. This is the analysis of the **original demo**, which the current repository replaced. It is kept because
the "worth keeping" and "gaps" sections are the reasoning behind much of the kernel's design, and because the two
signature features it names (Python extensibility and SQL in cells) are still unbuilt stories.

## What the demo was

| Part | Size (approx.) | What it holds |
|---|---|---|
| `sheetcore/` | 9,500 lines Python | UI-free model: refs, typed values, formula parser and evaluator, a pandas cell store, layout, drawing objects, commands, undo, track log, SQL, LaTeX formulas, Python plugins |
| `sheetserver/` | 2,900 lines | FastAPI and WebSocket server: hub, protocol table, auth, TLS, AES-256-GCM at rest, AI participant |
| `sheetclient/` | 1,200 lines | `RemoteSession`: a replica of a server document, reconnect, TLS fingerprint trust |
| `gtk_sheet.py` | 3,263 lines in one file | The GTK 4 window |
| `web/` | 5,100 lines TS/Vue | Nuxt 4 SPA client |
| `tests/` | 13,400 lines | README's claim: 1,319 Python tests and 85 web unit tests |

Signature features beyond the core: complete Python extensibility (`UserFunction`) and SQL in cells (`SELECT` over
named ranges, SQLite in memory, read-only, a 1 s limit).

## What the kernel did that was worth keeping

- Every change is a serializable, **invertible command**; `execute()` returns the inverse. Undo is a new command, so
  replicas just see one more change.
- Commands carry **final values**, never "parse this again" — RANDOM's draws are stored in the command — so replay is
  deterministic.
- Revision numbers, an in-memory change log, `changes_since()` for replicas, one undo history per author.
- A connection is a `send` callable plus `handle(text)`, transport-free, so a socket, a test list and the in-process
  AI all look the same.
- A protocol table that validates parameters, checks roles and is published at `/api/protocol`.
- Presence and per-cell edit locks with a timeout; the lock moves or ends when structure changes.
- Cells filled by a SQL query are owned by the query — "results, not cells" — and cannot be typed over. This is the
  precedent for the output range of any function that returns an array.

## The proposed split for claudia-core

| Part | Verdict | Notes |
|---|---|---|
| `history.py` (undo per author from inverse commands) | core as is | 122 lines, no spreadsheet in it |
| Command base, registry, `Batch`, `Context`/`Changes`, revision log, `apply_change`, `changes_since`, event batching | core after extraction | The kernel is entangled with `Workbook`; needs a `DocumentModel` interface each app implements |
| `tracking.py` (track log, chat, time helpers) | core, minus `command_sheets` | |
| `hub.py`, `protocol.py`, `auth.py`, `app.py`, `certs.py`, `redirect.py`, `state.py` | core after extraction | Cell-specific locks, `Limits` and the method table content stay in computes |
| `vault.py` | core, but see D15/D19 | Whole-file AES-GCM; the new format needs key slots and per-block encryption |
| `sheetclient/remote.py`, `tls.py` | core after extraction | Reconnect, heartbeat and replica rebuild are generic; the cell API is not |
| `ai/` | core after change | Must become remote (D8); `agent.py` is a placeholder |
| `refs.py`, `values.py`, `formula.py`, `cells.py`, `layout.py`, `sql.py`, `latex.py`, `clipboard.py`, `selection.py`, `plugins.py` | computes only | The plugin loader is generic, its contract is cell-specific |
| `drawing.py`, `assets.py`, `figure.py` | candidates for creates | The object layer; assets are content-addressed |
| `fileformat.py` | pattern only | The atomic write and migrations are reusable; the format is not |

*What actually happened:* the network layer became its own package rather than going into the kernel, and
`drawing.py` was not reused — `claudia-creates` has a new model.

## Gaps between the demo and the decisions

1. **Log versus snapshot (D15).** The file was a JSON snapshot; the change log lived in memory and the undo history
   was dropped when the user left. Only the optional track log was saved, capped at 20,000 entries, and chat was kept
   only while tracking was on. With the log as truth, "tracking" can no longer decide whether history exists; it can
   only be about visibility.
2. **Encryption (D15, D19).** The vault re-encrypted the whole file at each save, which does not fit an append-only
   log or per-role visibility.
3. **AI in process (D8).** `AssistantConnection.call()` was synchronous. A remote AI makes every call asynchronous and
   needs its own replica; the demo's `RemoteSession` is the right model, but reversed — the doc server dials and the
   AI server acts as the client on that socket.
4. **GTK client (D3, D4).** Plain GTK 4, no libadwaita, one 3,263-line window class. Charts and the LaTeX pop-up ran
   in a WebKitGTK web view, which is not realistically available on Windows and macOS. The grid created one widget per
   cell and showed at most about 120,000 cells.
5. **Menus (D4).** File, Edit, Insert, Tools, Help. Insert and the long Edit menu do not fit the four-menu skeleton,
   and the structure was written twice, once in the GTK window and once in the web menu bar. *The second half of that
   problem is still with us: the structure is still written twice, now as six web menus and a mapping table in the
   Linux shell (UX-09).*
6. **Excel exactness (D12).** Only 15 built-ins existed. The typed INT and "division is always float" differ from
   Excel's doubles. `UserFunction` was pure and scalar-by-argument, could not read other cells, return arrays or take
   lazy arguments, so it could not express VLOOKUP/INDEX/OFFSET/INDIRECT, FILTER/SORT/UNIQUE, IFERROR/IFS/CHOOSE or
   volatile functions. *Solved: the current engine has all of those as core forms, and 69 library functions.*
7. **File formats (D5).** No xlsx or ODF reading or writing anywhere. *Still true.*
8. **Locks and regions (D11, D17).** One lock per connection, per cell. Presence positions were plain coordinates and
   stayed put when rows were inserted. `refs.py` already rewrote references through structural edits, which was the
   prototype for Region mapping.
9. **Threading (D16).** All sessions of a document ran on one event-loop thread, so formulas, SQL queries and plugin
   functions all ran on that thread and one slow calculation blocked every user. *Still true, and now the root of
   PERF-01, PERF-02 and PERF-05.*
10. **Duplicated logic.** `selection.ts` was a hand port of `selection.py`. The protocol table is machine-readable, so
    the TypeScript types can be generated. *Still not done: E3.2.*
11. **Plugins.** Trusted code with full privileges, loaded from a folder, needing a server restart to reload. Fine for
    an operator, but the AI must never be able to add one, and there was no time limit for a function that never
    returns.
12. **Deployment.** The Dockerfile defaulted to Python 3.13 while the app targeted 3.14. No installer or bundling.
13. **Recalculation was complete, not incremental.** `Workbook._recalculate()` ran after every command, rebuilding the
    whole dependency graph and re-evaluating every formula and query. Finding the edges looped, for each formula and
    each range it reads, over all other formulas on the referenced sheet, so the worst case was quadratic in the
    number of formulas. Read from the code, not measured. *Solved by `calc.py`, which is incremental and indexed.*
14. **Every client calculated.** The GTK client kept a replica and recalculated the whole document itself, so it
    needed the same plugin files as the server. *Solved by D36: calculation is on the server and clients display.*
