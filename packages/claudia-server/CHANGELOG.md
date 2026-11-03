# Changelog of claudia-server

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.6.0] - 2026-11-03

Security release: three findings of the first QA review (SEC-01, SEC-02, SEC-07).

### Added
- **The server answers only to its own names (SEC-01).** `create_app(allowed_hosts=...)`, `--allow-host NAME` (repeatable)
  and the module `claudia_server.hosts` (`AllowedHosts`, `HostGuard`, `host_name`, `is_loopback`, `machine_names`; internal for now, not in `__all__`). A request whose
  `Host` header is not `localhost`, an IP address (not `0.0.0.0` or `::`) or a configured name is refused: 403 for HTTP,
  close code 4403 for a WebSocket, before any other part of the application sees it. Before, the Origin check trusted
  the `Host` the page itself sent, so a page that had pointed its own name at 127.0.0.1 (DNS rebinding) could list,
  create and try passwords on the documents of a server on its visitor's computer. `--tls-name`, the name given with
  `--host` and this computer's host name are answered without further options; the start-up report lists the names.
- **Limits against abuse (SEC-02).** `Hub(max_documents=1000)` / `--max-documents N`: past it nobody can make a document
  (`HubError('unavailable')`, close code 1013) and nothing is hashed or written for the refused one. `Hub.ensure_room()`.
  `create_app(max_waiting=256, max_waiting_per_address=64)` / `--max-waiting`, `--max-waiting-per-address`: only so many
  connections may wait to be let in (they are turned away with 1013), so a flood of `hello` frames no longer queues behind
  the password hashing without end.
- **Access secret (SEC-02, optional).** `create_app(access_secret=...)` / `--access-secret-file FILE` or the environment
  variable `CLAUDIA_ACCESS_SECRET` (at least 16 characters): only those who know it can make documents (`"access"` in
  `hello`) or read `GET /api/docs` (`Authorization: Bearer ...`). A refused creation is answered like a missing document
  and costs nothing (D50, SEC-04). Without a secret nothing changes. `Gateway.accepts_secret()`.
- `--behind-proxy` (SEC-07), see below.

### Changed
- **Breaking:** a server only answers to the names above. A server that was reached by another name (a proxy that passes
  the name people typed, a name in DNS, `http://myserver:8765` from another computer) now answers 403 until the name is
  added with `--allow-host` (or `allowed_hosts=`). The 403 page and the log (once per name) say so.
- **Breaking:** `--no-tls` on any address other than this computer's (`127.0.0.0/8`, `::1`, `localhost`) is refused,
  because the passwords would cross the network in clear text (SEC-07). Behind a proxy that encrypts, add
  `--behind-proxy`. The Docker image is not affected (it encrypts by default).
- `Gateway.admit(..., access=None)` takes the access secret the person gave. `Gateway(max_waiting=..., max_waiting_per_address=...,
  access_secret=...)`.
- CORS answers `Authorization` as an allowed header (the Bearer token of the access secret) for the configured origins.
- `scripts/start.py` refuses `--host` with an address other than this computer's unless `--tls` is given.

## [0.5.0] - 2026-11-03

### Added
- Presentations (E10.1): `claudia_server.creates.creates_methods` offers `slides`, `slide`, `shapes`, `styles`,
  `add_slide`, `add_object`, `move_object`, `resize_object`, `set_text` and `remove_object` besides the core methods.
  `creates_methods_with(library)` makes the table for a server with more shapes than the built-in ones. A shape comes
  from the library by its id and is copied into the document with the first object that uses it, in one history step.
- `python3 -m claudia_server --shapes DIR` (repeatable) adds the shape files (JSON) in DIR to a presentation server; the
  start-up report names the shapes and every file that was skipped, with the reason.
- `GET /api/docs` also tells which `app` the server hosts, so that a client knows what kind of document to create.
- `Hub.app`; `DocumentProvider.app` (a provider tells which kind of documents it holds; `MemoryProvider`, `FileProvider` and `SealedDocuments` do).
- `scripts/start.py --app creates` starts the presentation server (documents in `demo-docs-creates`).

### Changed
- `methods_for(model_cls, *, shapes=None)` picks the presentation table for `creates` documents.
- claudia-server now depends on claudia-creates.
- **Breaking for custom providers:** a `DocumentProvider` must have an `app` property.

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
- The text app (composes): `claudia_server.composes.composes_methods` adds `blocks`, `suggestions`, `replace_text`
  (one request, one step in the history; a line break starts a paragraph), `set_style`, `look`, `hold` (locks the
  ± n words around the cursor, D11), `suggest` (assistant only), `accept_suggestion` and `reject_suggestion` (D63).
  The assistant has no direct write path into the text: `replace_text` and `set_style` refuse it.
- `TextEngine` (`claudia_server.standin_text`): the scripted stand-in assistant for texts. It reviews and only suggests.
- `methods_for` and `stand_in_assistant_for` know the text app; `--model claudia_composes:TextModel` serves texts.

### Changed
- claudia-server now depends on claudia-composes.
- The AI user can answer with a language model (E7.1): `python3 -m claudia_server --ai MODEL_DIR` loads a model converted
  for OpenVINO (`--ai-device`, default GPU; `--ai-max-tokens`; `--ai-timeout`) before the server starts listening.
  `ModelEngine` asks the shared `claudia_ai.ModelRunner` (one model for the server, one question at a time, off the event
  loop) and turns the answer into something to say and requests to make (`set_cells`, `add_sheet`, `structure`); the
  assistant makes them like anybody, so roles, limits and locks apply. `model_assistant_for` makes such assistants.
- `AsyncEngine`: an engine that is awaited (`plan_async`), for anything slow. `Assistant(max_waiting=...)` refuses
  questions that would wait behind too many others.
- Optional dependency `claudia-server[openvino]` (installs `openvino-genai`).

### Changed
- claudia-server now depends on claudia-ai.
- `Assistant` accepts an `AsyncEngine` as well as an `Engine`.

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
