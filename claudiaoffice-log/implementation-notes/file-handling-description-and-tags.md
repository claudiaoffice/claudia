# File handling on the front page: description, tags, the way back from a collection (branch `file-handling`)

Decisions D530–D532; story E5.18; mock-ups in `notes/mockups/` (approved 2026-11-15).

## What was built

* **Container** (`claudia-container` 0.6.0): `Manifest.description` and `Manifest.tags` in the plain `manifest.json`;
  `set_details`, `clean_details`, limits `MAX_DESCRIPTION` 2000, `MAX_TAGS` 10, `MAX_TAG` 30. Tags are lower case, spaces
  collapse, no comma, no repeat. A file without the keys reads as empty, so no format change is needed.
* **Server** (`claudia-server` 0.35.0): the list carries `description` and `tags`; the method `set_details(password,
  description, tags)` is for editors and owners (amended: first owner-only) and checked with the person's own password, like `delete_document`, and runs over the
  short connection the front page opens like any login (so it passes the gateway's login rules); `SealedDocuments.describe`
  sets them for a document just made (used by import, where the keys are still held); `formats.file_details` reads the
  properties of Office and OpenDocument files; the upload answer and `hello` carry description and tags.
* **Web:** `lib/open.ts` (search over id, tags and description; tag counts, filter, `addTags`, `summaryOf`,
  `saveDetails`), `DocDetails.vue` (row: one line, chips), `DetailsFields.vue` (shared by import and Details…),
  `DetailsDialog.vue`, the tag filter next to the app filter, the import fields, "← All documents" / Esc.
* Tests: container, `test_server_listing.py`, `test_server_details_import.py`, `details.test.ts`, `protocol.test.ts`,
  `mine.test.ts`, and `web/e2e/details.cjs` (a real browser against a real sealed server).

## Why it looks like this

* **Plain, not sealed, not logged.** The owner asked for a property of the file readable by anyone with access to the
  server. The sheet drew it as a logged command; a value that must be readable without keys cannot live only in the
  sealed log, and two copies (plain and logged) can disagree. So it is a manifest property only (D530). The manifest is not
  authenticated, as the title is not.
* **The edit goes through the session protocol**, not a new HTTP endpoint: the front page already opens a socket per
  login, the throttling and the "same refusal for missing and wrong" rules (SEC-04) apply unchanged, and no new public
  route needs its own abuse analysis.
* **Reading the file's own properties** uses the standard library's XML parser after refusing parts that are larger than
  64 kB or hold a DOCTYPE, so there is no entity expansion to defend against. The properties are offered, never forced.
* **The description is read by the speaker-notes Markdown reader** (D347) and drawn from spans: no HTML in a list that
  every visitor sees.
* **Bug found by the browser test:** assigning to a `defineModel` ref inside a loop reads the stale prop, so typing
  "a, b" kept only "b". The logic lives in `addTags` now, which builds the whole array and assigns once.

## Not done, and open

* Dragging documents and collections between places and collections (sheets "move and copy", "collection to server").
  A page talks only to its own server (D170); a copy needs another name because the name is sealed into the file (D443);
  moving needs each document's owner password. Needs a decision before it is built.
* Writing description and tags into the files on export (Word `dc:description`/`cp:keywords`, OpenDocument
  `dc:description`/`meta:keyword`); an exported file loses them today.
* Details… inside the document (File ▸ Properties…) and the GTK and neutralino shells; their menus need the entry and a
  key shortcut when it comes.
* The list does not know who owns a document (D103), so Details… is offered on every row and the server refuses
  a viewer with a sentence; editors and owners may edit (D530, amended).
* The docx and pptx writers leave their template's author fields in core properties ("python-docx", "Steve Canny").
* Observed, not mine: `check_debt.py` "layout types" and "layout tests" fail here for want of installed node modules.

## Addendum: the document's uid, lookup and placing (D533–D535)

Built on top of the above, on the same branch (`claudia-container` 0.7.0, `claudia-server` 0.36.0).

* **Manifest:** `id` is `name`, `title` is gone, and every new document has a `uid` (random UUID v4). The sealed parts
  are bound to `name:uid` (`Manifest.binding`): a plain manifest with another name or uid opens nothing. No
  migration (pre-release). `new_uid`, `is_uid` are exported.
* **Server:** `SealedDocuments.find(uid)` / `uid_of(doc_id)`; `Hub.find`, `Hub.uid_of`, `Suite.find` (every app of the
  server); the welcome carries `uid`; `POST /api/docs/lookup` (exact match, throttled by `Throttle`, same 404 for
  malformed and missing, follows the list rules); `place` refuses a uid that is here already with the name of the
  document in the sentence; the upload answer has `same_document` and no `title`.
* **Web:** the import dialog says in words that the document is here already and offers to open the one that is
  here, whatever it is called; `Uploaded.title` is gone.
* **Not built (asked to wait):** the links between documents (source uid, server hints, who accepted), pulling as a logged
  export, credentials, the switch of owner, an index for the lookup.
* **Follow-ups:** call the key `name` on the wire and `name` in the Python API of the server (it is `id`/`doc_id`
  there); decide whether `--no-list` hides the lookup (it does now) and what `unlisted` is for; the Office exports
  do not carry the uid (nothing to carry it in that survives editing); a copy that should be another document needs a
  new uid and name (no function yet).
