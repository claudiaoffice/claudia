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

## Slice B, 2026-11-19: what leaves the document (D1269–D1272, D1279, E2.9)

**The record (D1271).** `claudia_container.audit.AuditRecord` is one JSON object (kind `export`, `print` or `pdf`; who; when;
format; parts; pages) and the chain `audit/NNNNNN.blk` holds them, sealed with the history key and listed in the head
(`Head.audit`; a head without it reads as an empty chain, D1279). `record_audit` appends under the held keys; `_write_blocks`,
`rewrite_journal` and `pack_journal` carry the blocks over byte for byte, so a redaction cannot touch a record; `sealed_copy`
leaves the chain out of a viewer's file. A removed, added or swapped block is found like any other.

**The server.** A method says it takes something out with `leaves="export"`; after it answered, `MethodTable.dispatch` calls
`Context.record_leaving(kind, format, parts)`, which uses the account of the connection for "who". `report_output` is for what
a browser does (print, PDF): the name is the connection's, the page count is checked, 20 reports a minute per person (a
`Throttle` per connection). `audit_log` and the ephemeral event `audit_recorded` are history, so a viewer has neither; the
sender of an event is not sent it (the web session reads the record again after its own export). `tests/method_reads.json` is
the golden list of what each method reads.

**The export (D1270) and the import (D1272).** `export_file.write_export`/`read_export` (`claudia-export 2`); `export_claudia`
is the wire method; an upload recognises `claudia-export ` by the first entry and answers `kind: "Claudia export"`, `made_by`,
`made_at`; the import makes a new document of one `core.Import` step in the app of the export and nothing is kept as an
original. A state of another `state_schema` is refused with a sentence.

**The web app.** `lib/audit.ts` (the sentences and where a row belongs in the history), `ExportFormatDialog.vue` (the format,
the checkbox for owners, the question "Save without protection?"), `ImportDialog.vue` ("A Claudia export, made by … on …", no
box to keep the original), `PrintPreview.vue` (reports after the PDF is saved or the page sent, and says so in a note),
`SidePanel.vue` (a muted line, `data-testid=audit-row`). GTK and Neutralino show these screens and have no code of their own
for them; the Save dialog of a desktop window takes the file's name (`.claudia-export.zip`).

**The format specification** is `docs/container-format.md` (D1268's sentence is in it: an older copy of the whole file is
not detected). **The measurement of D1269** is in the story E2.5: 12 to 13 times smaller than sealing each change alone, on
typing-like logs, not on "real logs of the test documents" (importing those makes a log of one step).

### Assumptions about behaviour (for the owner to veto)

- The format number stays 1 in this slice (D1279); slice C moves it to 2.
- The import dialog says "Nobody else is given access." and not what the mock-up said about names in the history, because the
  history of an export is not read back (PROC-37).
- A viewer's export is recorded in her name, and she may export the content only; the box for history and chat is for owners
  and an editor is told in a sentence.
- A print is reported when the print dialog's page is sent; where a desktop window hands the PDF to a viewer ("open in your
  PDF viewer"), it is recorded as a PDF, not as a print.
- 20 reports a minute per person is a number made for this round, not decided.
- The unencrypted zip is offered to every role that can open the Export dialog, because D1270 says editors and viewers may
  export the content; what a viewer's content holds is already what she may see.
- The upload's `suggested_id` for an export drops `.claudia-export.zip`.
- The German texts of the new strings are mine and have not been read by a native speaker (the formal "Sie" is used).

### What was not run

- Printing to a real printer, and the browser's print dialog: the automated run saves a PDF; the "printed" row is covered by
  the web session test and the server test only.
- The three `@extended` scenarios are run by the unit tests they name, not in a browser.
- The import of an export made by an older or newer version of Claudia (only the refusal sentences are tested).
- Firefox, and the GTK, Windows and macOS shells by hand.
- The performance of the record with thousands of rows (the history panel sorts all of them on every change).

### Bugs found in this slice

UX-55 (fixed in this slice), PROC-37 (history and chat of an export are not read back; needs a decision), CODE-74
(`export_content` is a third export nobody asked for), PROC-36 fixed.

## Slice C, 2026-11-19: keys and people (D1263–D1265, D1274, D1281–D1285, E2.2–E2.4)

**Keys (D1274).** `inbox.py`: an X25519 key pair per person (`new_key_pair`) and `seal_to`/`open_inbox` (an ephemeral key, HKDF,
AES-256-GCM; the authenticated data names the document and the slot locator). A slot now holds the person's private key and
the key of her private domain; `people.bin` lists her public key. The head has a recovery locator and public key, so the
recovery key receives letters like a person. Login is one resolver in `container.py` (`_resolve`): slot → private key →
letter → checks (the content key opens `people.bin`, the list names the same role for her, the history key opens the head) →
a replacement slot. A letter that fails a check is ignored, not an error. `unlock` and `unlock_with_recovery` write the
catch-up under the write lock (the manifest does not change).

**Renewal (D1263, D1282).** `renewal.py`: `change_role` and `remove_person` decide which domains to renew (removal: the ones
she held; editor→viewer: history and chat; upgrades and owner↔editor: none, but she gets a letter) and replace the file once.
Everything under a renewed key is re-sealed with a new key and the same payloads (chains, the record, the head, the people
list, the original); the snapshot is dropped unless passed (D1285); pending journal records are folded in first and a new
journal starts at generation+1 under the new keys. Letters are written for everybody who stays and for the recovery key. If
the journal step fails after the file was written, `RenewalInterrupted(keys)` carries the new keys so the server can go on.

**The private domain (D1265, D1283).** `private/<id>/NNNNNN.blk` and `head.bin`; `read_private` and `write_private`
(stand-in; E16.8 fills it). Recovery makes a new key pair and a new chain; removal deletes it.

**The server.** `change_role` and `remove_person` (D1284) in `protocol.py`, `PeopleDirectory` in `auth.py`, the work in
`SealedDocuments` (`_change_people`: renewal under the lock, then the open document's keys and the account's role are
replaced, then the hub is told). `hub.py` replaces the role of a person's open connections before the event is delivered and
marks removed ones (no more events; requests answered `forbidden`). Events `role_changed` and `person_removed` are ephemeral
with the CONTENT audience, so a viewer sees them too.

**The web app.** `ShareDialog.vue` has a People section for owners (name, role select, Remove), a question before lowering
or removing that says what is protected and what is not, and a "Renewing the keys…" state. `BaseSession.changeRole` and
`removePerson`; the notices for the person concerned and for the others. (`setRole` is the text session's style-role method,
which caused one wrong turn: the people method is `changeRole` on the client and `change_role` on the wire.) GTK and
Neutralino show the same Share dialog and have no code of their own for it. No new menu entry; `File ▸ Manage ▸ Share…` keeps
its shortcut in `claudia-menus.xlsx`.

### Assumptions about behaviour (for the owner to veto)

- "only look" is what the viewer role is called to a person in the dialog (E2.3's mock-up); the wire and the file say viewer.
- Raising a viewer to editor (the select) happens at once, without a question: it gives away nothing that was not meant.
- Lowering and removing ask first, and say that what was seen and any saved copy stay with the person.
- The owner cannot lower or remove another owner; the way is the handover (`propose_owner`).
- A removed person's windows close with a sentence; she cannot reopen the document with her old password (the login says the
  usual "wrong name or password").
- A person who was away while her role changed gets the new keys at her next login; until then her old slot still opens the
  document with the keys of the old role.
- The renewal runs on the event loop (D1282); the dialog says it takes "about as long as writing the file once".
- Format 2 (D1281): files made before this slice are refused, not upgraded.
- The German texts are mine and have not been read by a native speaker (the formal "Sie" is used).

### What was not run

- A renewal of a document of hundreds of MiB (timed on the test documents only; the claim "about as long as writing the file
  once" is argued, not measured on a large one).
- A second server process or a crash in the middle of a renewal (the order of the two file replacements is tested by making the
  second fail, not by killing the process).
- Firefox, and the GTK, Windows and macOS shells by hand.
- The `@extended` scenarios are run by the unit tests they name, not in a browser.

### Bugs found in this slice

PROC-39 (fixed: the e2e server's output pipe was never read, so a long enough run froze the server; found because the six new
scenarios made the run long enough), PROC-38 (a timing test of `test_server_password_methods.py` fails on a fast machine under load: the hashing took 0.1499 s
against a floor of 0.15 s). The earlier list stands: SEC-22, PROC-37, CODE-74, UX-54.
