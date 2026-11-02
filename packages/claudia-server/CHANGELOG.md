# Changelog of claudia-server

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.4.0] - 2026-11-02

### Added
- `SealedDocuments`: documents and their people in the encrypted container (`claudia-container`). It is the
  `DocumentProvider` and the `UserDirectory` in one, because the people of a document are the key slots in its file. A
  document is `docs/<id>.claudia` and a sealed journal next to it; the names, roles, passwords and content are not in
  any file in readable form. Keys live in memory only: a login by an owner or editor leaves them waiting for `open`
  (`key_ttl`, 60 s), and they are forgotten when the hub unloads the document. A viewer holds only the content key, so a
  viewer who logs in first after a restart is told that the document is sealed and an editor has to open it.
- `--plain-dir DIR`: the old unencrypted store of the early demos, by name, with a banner that says so.
- `replay(items, model_cls)` in `claudia_server.filestore`: rebuilds log and chat from journal items, shared by the plain
  and the sealed store.
- `Gateway(max_hashing=2)`: at most two password hashings run at once.

### Changed
- **Breaking:** `--dir DIR` now keeps sealed documents. Folders made by earlier versions are not read (use
  `--plain-dir` to keep using them).
- **Breaking:** `DocumentProvider` has a new method `release(doc_id)`, called when the hub unloads a document from
  memory. A provider of your own must have it (it may do nothing).
- Passwords are checked in a thread and not on the event loop (SEC-03), and an unknown document costs as much time as a
  wrong password (SEC-04). Creating a document adds its owner in a thread too.
- A password must have 8 characters, a capital letter, a small letter and a digit (in the sealed store).
- claudia-server now depends on claudia-container, and on `cryptography>=44`.

## [0.3.0] - 2026-11-02

### Added
- `chat_log` method: the chat an account may read. `log` method: the newest entries of the visible history with a sentence for each (`summary`).
- `claudia_server.computes.computes_methods`: `sheets`, `cells` (a window), `set_cells` (what people type),
  `add_sheet` and `structure` for workbooks; `claudia_server.apps.methods_for` picks the table of a model, and the
  command line uses it.
- The `command` event has a `summary`.
- `add_user` method: the owner of a document lets a person in with a name and a password (editor or viewer). `Hub(directory=...)`
  (`create_app` fills it in), `Context.directory` and `Context.doc_id`.
- The AI as a participant: `Assistant` (a connection named `ai`, one per document, in the colour Iris) with a pluggable
  `Engine` (`Task`, `Say`, `Call`); it answers `@ai` messages to the asker and edits through the same methods as
  everybody, so locks and roles apply. `ScriptedEngine` is a stand-in for a real model; `Hub(assistant=...)`,
  `stand_in_assistant_for` and `--no-assistant`.

### Changed
- claudia-server now depends on claudia-computes.

## [0.2.0] - 2026-11-02

### Added
- `GET /api/docs` and `Hub.listing()`: the documents on the server (`id`, `app`, `modified`, `online`), most recently
  changed first; no names, no content. `create_app(..., list_documents=False)` and `--no-list` switch it off.
- `DocumentProvider.documents()` and `StoredInfo`.
- `FileProvider` and `FileDirectory`: documents (a journal per document) and users (`users.json`, hashes only) in a
  folder, for a demo server (`--dir DIR`). Not encrypted; the container (E2) replaces it.
- `ScryptDirectory.dump()` and `load()`.

### Changed
- `MemoryProvider.open` now also restores the chat of the document.

## [0.1.0] - 2026-11-02

First version (E3.1).

### Added
- The protocol (version 1): JSON frames over one WebSocket per person and document; `MethodTable` (extensible per
  app), `core_methods` (ping, snapshot, lines, changes_since, history, checkpoints, users, apply, undo, redo,
  save_checkpoint, presence, lock, unlock, chat), error codes including `locked`, `conflict` and `stale`.
- `Hub`, `HostedDocument`, `Connection` over a `DocumentProvider` (`MemoryProvider` for now): who receives which event,
  lock sweeping, idle unloading, connection limits.
- `create_app`: the WebSocket `/api/docs/{doc}/ws` with a `hello` handshake (name and password per document, creating
  a document makes its creator the owner), `/api/health`, `/api/protocol`, the web app and a landing page.
- `ScryptDirectory` (users per document; stand-in for the directory in the document file, E2.3).
- TLS by default: `ensure_certificate` makes and keeps a self-signed certificate; an optional plain-HTTP port redirects
  to https.
- `python3 -m claudia_server` (see `claudia_server.cli`).
