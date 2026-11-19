# E2 second round: viewers, back-off, hashing cost, key renewal, exports and their record (D1261–D1276, branch `e2-document-sec`)

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
