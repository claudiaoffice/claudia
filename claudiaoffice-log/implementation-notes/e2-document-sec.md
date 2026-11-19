# E2 second round: viewers, back-off, hashing cost, key renewal, exports and their record (D1261–D1278, branch `e2-document-sec`)

The design is `notes/e2-document-sec-architecture.md`; the mock-ups are in `notes/mockups/e2-*.svg`. The work goes in three
slices (A viewers, back-off and hashing cost; B what leaves; C keys and people), each a patch against the branch.

## First code, 2026-11-19: the sealed Download (E2.12, D110, D1270) and the address behind a proxy (D1275)

**The sealed copy.** `claudia_container.container.sealed_copy(path, name, password)` returns the bytes of a complete, still
sealed document file for one person. It derives the login material once (the slow part), finds the slot, and writes a new
zip with the same `_fill_zip` as the document writer: an owner gets every entry and every slot; anybody else gets only the
slot whose locator is theirs (the recovery slot goes too); a person whose slot does not hold the history key (a viewer) gets
no `head.bin`, no `history/` and no `chat/` entries, and keeps `content/snapshot.bin` and `people.bin` (sealed with the
content key). The file at `path` is not touched, and the journal is not read: the caller packs first.

**The server.** `SealedDocuments.sealed_copy` packs an open document (so the file has what was said so far and a fresh
snapshot) and then copies. The wire method `download_claudia` (`password`) is for every role. The password is asked again
because it is what finds the slot; the server does not keep passwords. The answer carries the file base64 (as the Office
export does), its name (`<document>.claudia`), a content type and `parts`.

**The clients.** `DownloadDialog.vue` replaces `ExportDialog.vue`; the dialog id `export` became `download`. The GTK and
Neutralino shells show the web app, and their Save dialogs derive the file type from the name, so they need no change. The
strings are in `po/` (German and pseudo-locale), the workbook cells are updated.

**The address.** `client_address.ClientAddress` is the one place that decides who a connection is. With `--behind-proxy`
the entry `--proxy-hops` places from the right of `X-Forwarded-For` (default 1), only if it is an IP address; otherwise the
proxy's own address, and a line in the log once. `/api/health` keeps the raw socket address on purpose.

## Assumptions about behaviour (for the owner to veto)

- The dialog asks for the password for every role, also for an owner, although an owner's file contains every slot: it is one
  rule and one dialog.
- A viewer's Download works while an editor has the document open. A viewer's file has the content snapshot; whether it is
  as fresh as the last change depends on the packing done just before.
- The file name is the document's id plus `.claudia`.
- Until E2.9 there is no unencrypted export in the menus (the owner accepted this).

## What was not run

- No real proxy (Caddy, nginx) in front of a server; only the header logic and the app with a test client.
- The Firefox run of the scenarios, the Windows and macOS shells and the GTK client by hand: the shells show the web app and
  have no code of their own for this, but nobody has pressed the menu in them. The GTK and Neutralino unit tests ran in the gate.
- The `layout` package's own type check and tests (its `node_modules` are not installed in this workspace).
- The two-person and the round-trip scenarios of `specs/container/download.feature` have no step code.
- The Download scenarios were written together with the code, not first; they have not been seen failing against the old
  Download.

## Slice A (second round), 2026-11-19: viewers, waits, the hashing cost, SEC-21 (D1261–D1263, D1266, D1267, D1275–D1278)

**What a viewer gets (D1261).** `audience.py` has two tables: `EVENT_RULES` (every pushed event: its domain and what a
viewer keeps of it) and `EPHEMERAL_RULES` (the kinds of the `ephemeral` event), and `shape_for(role, event, data)`.
`Connection.deliver` applies it to every frame that has an `"event"` key. Unknown events go to owners and editors only,
and a test fails until a new one is listed. `MethodTable.method(..., reads=)` marks the methods that read the history
(12) or the chat (1); `dispatch` refuses a viewer them. `tests/method_reads.json` pins the whole table (192 methods), so a
new method is a content method until someone decides otherwise and the diff shows it. On the web, `BaseSession.reload`
does not ask a viewer for what she cannot have and the side panel says so in one sentence.

**A viewer at a sealed document (D1262).** `open()` catches `sealed`, says the sentence of D1262 and runs the same
reconnect loop as a lost connection (status `waiting`, `DocumentFrame.vue`); Close is always there.

**Waits (D1266, D1275, D1276).** `LoginThrottle` (in memory, injected clock, bounded table). The gateway asks it before
`Hub.check_id` and before any hashing. The administrator's sign-in shares the address counter and has a counter of its own
under the key `"\x00admin"`. A success clears the address count only, so one's own success does not erase what others
tried against a name. The web counts the seconds down (`login-wait.ts`; the spoken text changes twice only).

**SEC-21 (D1277).** `Method.hashes`, `MethodTable.hashes_of` (cheap prefilter on the bytes `password`),
`Connection.hashing_for`, `Gateway.prepare` (thread, behind the cap), `SealedDocuments.warm`, and the cache in
`claudia_container.crypto.warm_login_material`.

**The hashing cost (D1267, D1278).** `claudia_container.kdf.calibrate`, `KdfPolicy` (measures in the background at
start; `Plan.start()` calls it, so planning in a test measures nothing), `SecuritySettings`, `PUT /api/admin/settings/security`,
`AdminSecurity.vue`.

**PROC-35.** The browser of the spec runner is per file.

### Assumptions about behaviour (for the owner to veto)

- Names are normalised (NFKC, case folded, spaces) before they are counted for the per-document wait, so "Ann" and "ann " are
  one name.
- A viewer sees who wrote which stretch (SEC-22, not decided). The AI lens has no way to be reached by a viewer: she cannot
  post to the chat.
- A viewer learns the document's revision with `ping`, and her window refreshes by asking for content only.
- The wait is counted per address first; behind a proxy that is the address of D1275.
- The decoy hash for a missing document uses the cost of a new document.
- The target of the hashing cost has a range of 0.1 to 30 seconds; there is no memory ceiling setting yet.
- The Security page is a sidebar page without a shortcut (UX-54).

### What was not run

- The sealed-first viewer's overlay in a browser: its scenario needs a server restart between two windows, so its first step
  has no code (the web session tests and the server tests cover the behaviour).
- The administrator's sign-in wait in a browser (unit tests only).
- The calibration on real server hardware; the number here (about 0.6 s for 256 MiB, 4 passes) is from this workspace.
- Firefox, and the GTK, Windows and macOS shells by hand: they show the web app and have no code of their own for these
  changes.
- `argon2`'s timing in `test_server_password_methods.py` is time-based (50 ms for a ping while another window hashes); on a
  heavily loaded machine it could be flaky.
