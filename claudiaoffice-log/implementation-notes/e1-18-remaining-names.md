# Implementation notes: the remaining renames of E1.18

Branch `e1-18-remaining-names`, decisions from D1434 (range D1430–D1449). The owner's order, 2026-11-22: the parts of
a document, then a deep dive into chart and diagram, then ai, then proposal. This file keeps what the code does not say.
The earlier slices are in `architecture-improvements.md`.

## The parts of a document (D1434), 2026-11-22

- **Two meanings of `domain` were found.** One holds a part (typed `Domain`): it became `part`. The other is the name of
  a chain of blocks (`str`), which is a part's value, `"audit"` or `"private/<id>"`; calling it a part would call the
  exit record and private notes parts, which the glossary does not. The owner chose `stream`, the word `_STREAMS` and
  `_STREAM_BYTE` already used. Before the general rename, the `domain` locals of `blocks._aad`, `_private_entries`,
  `read_private`, `_load_chains`, `_extend` and `_sealed_chain` were renamed by position in the syntax tree (so no
  string and no attribute could be hit), and `Place.domain` by hand; then every remaining word `domain` was a part.
- **No name collided.** A syntax-tree check found no function that already had a `part` or `parts` beside its `domain`
  or `domains`.
- **Prose about the private domain was written sentence by sentence**, not by a rule, because "private notes" takes the
  verb in the plural ("the private notes do not open"). The exception messages change wording; none is translated or
  shown in the UI.
- `audit.PARTS` is `tuple(part.value for part in Part)`; `audit.py` now imports `slots` (no cycle: `slots` imports only
  `crypto`).
- `claudia_core.messages`' table column "key domain" is "part".
- **Left as history:** the changelog entries before this one, `notes/e2-document-sec-architecture.md` (a record of
  slices A to C, which also still names `container.py`), and the stories E2.4 "Key domains and visibility", E1.6, E2.2,
  E2.9 and E16.8, whose wording is the owner's.

**Assumptions** (said in the patch): an exception's English wording may change freely (no test, client or translation
reads it); the backlog's story titles are not renamed by this slice.

## CI of `main` after the merge of `architecture-improvements` (PROC-45)

The job "Linux client (Python 3.12, GTK 4)" was red: the GTK client's end-to-end test asked the page for
`[data-block]`, which the paragraph slice had renamed. Fixed on `main` (`31fe94a9`). The agent's environment now has
GTK 4, libadwaita and WebKitGTK from the distribution, as in CI, so the GTK client's tests run before delivery:
`cd clients/linux && xvfb-run -a /usr/bin/python3.12 -m pytest` (the distribution's `python3-gi` is built for 3.12,
and the web frontend must be built first: `cd web && npm run build`).
