# Changelog of claudia-server

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.4.0] - 2026-11-02

### Added
- The text app (composes): `claudia_server.composes.composes_methods` adds `blocks`, `suggestions`, `replace_text`
  (one request, one step in the history; a line break starts a paragraph), `set_style`, `look`, `hold` (locks the
  ± n words around the cursor, D11), `suggest` (assistant only), `accept_suggestion` and `reject_suggestion` (D63).
  The assistant has no direct write path into the text: `replace_text` and `set_style` refuse it.
- `TextEngine` (`claudia_server.standin_text`): the scripted stand-in assistant for texts. It reviews and only suggests.
- `methods_for` and `stand_in_assistant_for` know the text app; `--model claudia_composes:TextModel` serves texts.

### Changed
- claudia-server now depends on claudia-composes.

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
