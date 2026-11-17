# Changelog of claudia-server

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Added
- References (step H) in composes and creates (`claudia_server.structure_methods`): `reference_targets(query?)`
  (headings with their numbers, numbered items, named things), `insert_reference(paragraph, offset, target, show?)`,
  `set_field(paragraph, index, show)` and `fields` (what every reference reads as; a `fields` event brings changes).
  `blocks` sends a paragraph's `fields` and `shown`. Words a person writes (`replace_text`, `write_words`, the
  assistant's) make no reference: their U+FFFC are taken out.
- `write_words` in creates (step G): the words of an object as a person typed them; only what differs from the words it
  has changes, so the words that stay keep their writer (`set_text` gives all of them to whoever saved). The web app
  writes through it from its new paragraph editor.
- Tables of contents and agendas (step E, E9.31): `contents` (every table's entries) and `set_contents` in composes and
  creates (`claudia_server.structure_methods`); `insert_contents` and `remove_contents` in composes
  (`claudia_server.composes_contents`: a "Contents" paragraph in the reader's language and the table, as one step);
  `insert_agenda` in creates. `blocks` sends a table's `generated` and `entries`. `PROTOCOL_VERSION` stays: methods
  were added.
- Lists, numbered headings and numbering schemes in composes and creates, one module for both
  (`claudia_server.structure_methods`, step D, E9.22): `lists` (the lists, the schemes and every label),
  `make_list`, `indent_item`, `continue_list` and `list_start` on any paragraph id in reading order (in creates the
  objects whose words they are, so a list runs on across text boxes), `number_headings` (creates: Number All Slide
  Titles), `new_scheme`, `change_scheme`, `reset_scheme`, `remove_scheme`; `set_style_numbering` in all three apps.
  `blocks` sends the document's own schemes, each with its `levels`. `PROTOCOL_VERSION` stays: methods were added.

### Removed
- `claudia_server.composes_lists`: its methods are `structure_methods`'.


### Changed
- The server's state files (certificate, key, settings, the file store's list) and the fetched hyphenation patterns are
  written with `claudia_file_writer` (CODE-34, D701): ten attempts with waits up to a second on Windows instead of
  five, a temporary file name that two threads cannot share, and the pattern fetch is the one the fonts use.

### Added
- `set_heading_level` (E9.22), in the three apps: make a paragraph style give its paragraphs a heading level (0 the title,
  1 to 9 a section, `"body"` none, null as its parent). `styles` says the level each style gives as `heading`.
  `PROTOCOL_VERSION` stays: a method was added.
- `add_image` and `describe_object` in composes (CODE-27): a picture comes into a text from disk, hanging from a
  character (`block`, `offset`), and any object of a text can be described or marked decorative, as in the other two
  apps. `PROTOCOL_VERSION` stays 1: methods were added.
- The AI in composes (E7.10, D680, D681): a document lens (`DocumentLens`), so a server with a language model answers
  `@ai` in a text with the model-driven loop as in computes and creates; the stand-in answers without one. For a
  person who chose *act* the assistant may also call `replace_words` and `add_paragraphs`; for *suggest*,
  `suggest_words`. A model is never offered `replace_text` or `suggest`, which take offsets. New methods for the text
  by what it says, open to everyone except `suggest_words` (the assistant's): `paragraphs(first?, count=20,
  containing?)`, `outline`, `replace_words(block, find, text, occurrence=1)`, `add_paragraphs(text, after?, style?)`
  and `suggest_words(block, find, reason, replacement?, occurrence=1)`. `Lens.orient` takes `asker` and `writes`.
  `PROTOCOL_VERSION` stays 1: methods were added.
- `name_thing` (D554), in the three apps: give a thing that has no name the one it gets when first pointed at (a
  heading of a text its own words, anything else "Paragraph 1", "Text box 3" ... in the asker's language); a named
  thing keeps its name and nothing is written. `blocks` in composes says a named paragraph's `name`.
- A new document's things are named in its `Setup` entry, in the maker's language: a presentation's first slide was the
  one thing without a name (UX-40).
- `rotate_object` turns an object about its centre in all three apps (rotation-ui): any whole number of degrees (-20 is
  340); in creates a turn that would push the outline off the slide also moves the object just far enough in, in the same
  step of the history, and one that cannot fit is refused; a chart (computes) does not turn; in composes the assistant may
  not (D63). `move_object` in composes takes `dx` and `dy`, how far the object floats from the character it hangs from; left
  out, it keeps the offset it has. `PROTOCOL_VERSION` stays 1: a method and optional parameters were added.
- `changes_since` (D553), in the three apps: `{regions, truncated}`, every place that changed after a step of the line
  (`replay.MAX_CHANGES` at most), for "show differences from now" in a replay.
- `propose_restore_step` (D553): suggest going back to the state after one step of the history, with the same
  agreement as `propose_restore`. A suggestion now carries `revision` (and `checkpoint: null`) in `restore_proposed`
  and in the welcome; a checkpoint's carries `revision: null`. Not for the assistant.
- `names` in computes returns each range's `id` (D552); `rename_thing` renames a sheet (E6.24) and refuses a name a
  range has, as a range refuses the name of a thing.
- Names of things (D550): `rename_thing` and `name_unnamed` in the three apps (the assistant may not in composes,
  D63); a new object, slide or diagram gets the first free "Text box 1", "Slide 2" ... in the maker's language; `slides`
  says each slide's `name`. `PROTOCOL_VERSION` stays 1: methods and a field were added.
- `peek_revision` (D551): the document after one step of its history, with the step and the regions it touched
  (`focus`), for replaying the history in the dock; `state: false` asks for the place only.
- `as_of` (D551): any of the reads a view makes (`slides`, `cells`, `blocks`, ... the list is `replay.VIEW_READS`),
  answered for an earlier revision, so the views draw the past from the requests they already make. It never writes;
  any other method is `forbidden`. States rebuilt for it are kept for a moment, so one step costs one rebuild.
- `thing_last_seen` (D551): `{present, revision}` for an object, slide, sheet or chart tab by id: whether it is there
  now and the last step after which it was, so that a tag in the chat to something deleted can take a replay there.
- The event `thing_renamed` `{id, name}` is documented (it was sent since D550): clients update the names tags show.
- The text app (composes) places rendered containers (D563): `add_rendering` (`block`, `offset`), `move_object`,
  `resize_object` and `remove_object` hang an object from a character of a paragraph, size it and take it away. The
  assistant is refused, as it is for the words. `add_rendering_methods` takes a `guard` that says who may change
  containers. No change to `PROTOCOL_VERSION`: the methods are new.
- computes: `pivots`, `define_pivot`, `update_pivot`, `delete_pivot`, `pivot_sql`, `pivot_to_sql` (E6.30, D620, D626)
  and a pushed `pivots` event: make, change, delete and read pivot tables, and turn one into the `SQL()` query it is.
  `define_pivot` may make the sheet it starts on (`new_sheet`) in the same step of the history.

### Fixed
- `add_object` in creates refuses `rendered` and `diagram` with a sentence that says where they come from; it failed
  inside the server (CODE-24).
- A docx imported and kept stays a patch of that file when paragraphs were added or removed (D456); before, the download
  was a new file without the file's tables and pictures, with a `not-patched` loss. It also says `removed-...` for what
  went with a removed paragraph.
- A web app built again while the server runs is no longer blocked: the Content-Security-Policy's hashes of the inline
  scripts follow the files in the web folder (`WebScriptHashes`, read again when a page's name, time or size changed).
  The desktop apps' shared server (D445) outlives its windows, and the start scripts build the web app at every start,
  so the second start showed an empty window (the new build's inline script was refused).

### Changed
- **Breaking** for the assistant in composes (D640): it acts or suggests as in the other apps. In *act* mode it may
  write through `replace_text` and `set_style` (`apps.MODEL_METHODS["composes"]`), and the scripted stand-in makes its
  replacements itself, from the end of each paragraph; in *suggest* mode it suggests, as before. composes' own guard
  (`_people_only`) is gone, and with it the `guard` hooks of `add_style_methods`, `add_name_methods`,
  `add_list_methods`, `add_object_methods`, `add_rendering_methods` and `SearchApp.before_replace`, which only
  composes used: the assistant's allow-list (SEC-10) is the one rule. Page setup stays people's in every app
  (`printing.people_only`, now with the message "people set a document up, not the assistant").
- The methods that change one object (`images`, `add_image`, `describe_object`, `move_object`, `resize_object`,
  `rotate_object`, `remove_object`) are registered once for the three apps by `object_methods.add_object_methods`
  (CODE-27); an app says only where an object is, with a `Placement` that `rendered.add_rendering_methods` takes too
  (in place of its `anchor` tuple). `wire.fresh_id`, `wire.done` and `wire.current_revision` replace the per-app
  copies. The wire names and parameters are unchanged (`tests/test_server_object_methods.py` holds them); the help
  texts of these methods now share their first sentences.

## [0.36.0] - 2026-11-15

The uid of a document: found by its exact value, kept when a file is placed, never twice on a server (D533–D535).

### Added
- `POST /api/docs/lookup` `{uid}` answers `{app, id, modified}` of the document of any app with exactly that uid, or
  404; follows the list's rules (no answer with `--no-list`, the access secret when there is one) and is throttled per
  address (`Throttle`, `app.state.lookup_throttle`).
- The welcome carries `uid`; the upload answer of a Claudia file carries `same_document` (the name of the document here
  that is the same one, or `null`).
- `Hub.find`, `Hub.uid_of`, `Suite.find`, `SealedDocuments.find`, `SealedDocuments.uid_of`, `StoredInfo.uid`,
  `hub.DuplicateDocument` (what a store raises for a file whose uid it has), `hub.same_document_message`.

### Changed
- Placing a Claudia file refuses (409) one whose uid is on the server already, under any name and in any app, and says
  which document it is.
- `set_details` may be called by an editor as well as an owner (a viewer is refused with `forbidden`) (D530).
- Needs `claudia-container` 0.7.0: `SealedDocuments` makes documents by `name`.

### Removed
- The `title` of a Claudia file in the upload answer.

### Changed
- Every server has the starter set of open fonts (D500): the copy shipped with `claudia_fonts` is read first, the
  folders of `--fonts` (or `STATE_DIR/fonts`) after it, and win for the same family and style. A server started with
  no fonts (the desktop apps' local server) can print. The Docker image no longer fetches the set.

### Fixed
- On Windows the built web app's `_nuxt/` files were revalidated on every load instead of kept for good: Starlette
  hands the path over with backslashes there, and the rule looked for a slash.
- The hyphenation patterns fetched into the Docker image were readable by root only (`mkstemp` makes 0600 files), so
  the container, which runs as another user, stopped at start with "Permission denied"; fetched files are 0644 now.
  A start-up error from reading a file or folder is no longer worded as a problem with the redirect port.
- The patch of a kept odt gets the document's `info` and the times of its suggestions, as a new file does (D411, D454).

### Changed
- `export_office` of a document imported in that format and kept answers `losses` also when it patched the file: what
  the patch writer reported (`removed-...`, `stale-reference`) and the unwritten changes since the import
  (`not-written`, `layout`, `chart`, `planned-time`...) (D450, D452). The docx answer has a loss list now too, and
  opening a docx or pptx names what the model does not show of it (D451).

## [0.35.0] - 2026-11-15

Description and tags of a document (D530, D531).

### Added
- `GET /api/docs` and `GET /api/{app}/docs` list `description` and `tags` of every document (`StoredInfo.description`,
  `StoredInfo.tags`); they are read from the plain manifest, so they need no password. A store that has none lists them
  empty.
- The protocol method `set_details(password, description, tags)`: an owner replaces them, confirming with their own
  password (`unauthorized` if wrong, `forbidden` for anybody else, `command_error` with a sentence if they do not fit,
  `unavailable` on a store that cannot keep them); the people connected get `details_changed`. `DetailsDirectory`
  names the capability, `SealedDocuments.set_details` implements it.
- The upload answer has `description` and `tags`: the Dublin Core description and keywords of an Office or
  OpenDocument file (`formats.file_details`; a part that is large, not XML or has a DOCTYPE says nothing), or those of a
  Claudia file's manifest.
- `hello` with `create` and `upload` takes `description` and `tags` (checked before anything is made); the welcome's
  `imported` says `described`. `Hub.describe` and `SealedDocuments.describe` keep them for a document just made.

### Changed
- The entries of the document list have two more keys, `description` and `tags`.

## [0.34.0] - 2026-11-14

Search and replace in composes and creates (E9.28, E10.19).

### Added
- `search_find`, `search_preview` and `search_replace` in composes and in creates, with the same parameters and
  answers as in computes; each app words its own kinds (`text`, `heading`, `remark`, `object`, `description` in a
  text; `text`, `label`, `notes`, `description` in a presentation), scopes (a section or a selection; one slide) and
  places (`{block}`, `{object, source}`; `{slide, object, source}`, `{slide, source: "notes"}`). In composes the
  assistant may look but not replace.
- `leave` items may carry `said`, what the match said when the person saw it: a text typed into since is skipped
  with the reason `changed` instead of being replaced on stale numbers. Also in computes.
- `claudia_server.search_methods` (`SearchApp`): the three methods once for every app; `computes_search`,
  `composes_search` and `creates_search` are the apps' parts.

### Changed
- The deadline of a search is `claudia_server.search_methods.SEARCH_SECONDS` (it was in `computes_search`).

## [0.33.0] - 2026-11-14

### Added
- `change_password` (`old_password`, `new_password`): a person chooses a new password for the document, their own
  only, whatever their role (D448). `{changed: true}`; `unauthorized` for a wrong current password; `command_error`
  with a sentence for a weak new one. `PasswordDirectory`; `ScryptDirectory.change_password`,
  `SealedDocuments.change_password` (the container's `change_password`: the keys sealed again under the new one).

## [0.32.0] - 2026-11-14

The desktop apps on the one server (D444, D445).

### Added
- `/api/health` answers `apps` (the apps the server serves) to everyone, and `version` to a request from this
  computer to this computer's address (`127.0.0.1`, `localhost`, `[::1]`), so a desktop app that finds a running
  server can tell whether it is its own.

## [0.31.0] - 2026-11-14

Opening files from the computer (D438-D442).

### Added
- `POST /api/uploads` (body: the file; `X-Claudia-Name`: its name, percent-encoded) answers `{upload, name, format,
  app, size, hosted}` and `suggested_id`/`kind`, or for a Claudia file `id`, `title`, `exists`. `UploadDesk`,
  `formats.sniff`, `formats.import_state`.
- `hello` takes `upload` (with `create: true`) and `keep_original` (default true): the new document is the file's
  content as one `core.Import` entry, read in the worker pool, and the file is kept in it. The welcome then has
  `imported: {name, format, kept, losses}`.
- `POST /api/uploads/{token}/place`: a Claudia file goes into its app's folder as it is (`Hub.place`,
  `SealedDocuments.place`); 409 when that id is there, 422 on a server that keeps documents in memory.
- `export_office` in the imported format patches the edits into the kept file and says `patched: true`; when that
  cannot be done the new file's losses say `not-patched`. `Context.original`, `Hub.original`, `Hub.keep_original`,
  `keep_original`/`original` on `MemoryProvider` and `SealedDocuments`.

## [0.30.0] - 2026-11-14

One server for all three apps (D430-D437). The rest of this section is the work that was unreleased before it.

### Added
- `Suite` and `Module` (`claudia_server.suite`): one server hosts several apps, each with its own `Hub` and
  `UserDirectory`. `APP_MODELS` names the apps and their document models. `create_app` takes a `Suite` (a single
  `Hub` with its directory still works and is a suite of one).
- Addresses with the app (D431): `/api/<app>/docs/<id>/ws`, `/api/<app>/docs`, `/api/<app>/protocol`. `/api/docs`
  answers `apps` as well and lists the documents of every app; its `app` is `null` on a server with several.
- `/api/presence`: a socket that carries nothing and keeps a server in use while a page without a document is open.
- `--exit-when-idle SECONDS` and `IdleWatch`: the server stops by itself, gracefully, once nothing has used it for
  that long (D434). `main` runs uvicorn through `uvicorn.Server` so that it can be asked to stop.
- `--apps computes,composes,creates` (all by default). `--model` still starts a server of one app with its documents
  directly in `--dir` (D433); the two cannot be given together.
- `FolderLock`/`FolderLocked` (`claudia_server.folder_lock`): a server refuses to start on a document folder another
  process uses (D435).
- `Room`: the document cap shared by the hubs of one server (`Hub.share_room`, `Hub.count_known`).

### Changed
- **Breaking** (storage): with `--apps` (the default) each app keeps its documents in `DIR/<app>/` (D431). Nothing
  is migrated (D437).
- **Breaking**: `Gateway(suite, allowed, ...)` replaces `Gateway(hub, directory, allowed, ...)`; `admin_router` and
  `AiRuntime.apply` take the `Suite`; `AiRuntime(models=...)` replaces `AiRuntime(model=...)`. One language model
  serves every app that has a lens; the others keep their stand-in (D432).
- `max_documents` counts the documents of every app together (D432); the hubs of a suite share one worker pool.
- A sealed store lists and opens only its own app's files.
- The old address `/api/docs/<id>/ws` opens the first app that has the id, and makes a new document in the app
  `hello.app` names, else in the first app (D431).

Describing objects (BITV 1.1.1), in creates and computes (composes has no object methods yet).

### Added
- Creates methods `set_slide_notes(slide, notes, base?)` and `set_slide_time(slide, seconds, base?)` (D342, D343).
  `slides` answers each slide as `{id, objects, seconds, has_notes}` and `slide` adds `notes` and `seconds`. The AI
  may write notes (`set_slide_notes`) but not planned times.
- `describe_object(id, description, decorative?, base?)`: say what an object is to someone who cannot see it, or that it is
  only decoration (then no description). A picture needs one or the other. One history step, "Describe object" or "Mark
  as decorative".
- `add_image` takes `decorative` (optional). A decorative picture has an empty `alt`; any other still needs words, and a
  picture given both is refused.
- The objects of a slide or a sheet are listed with `description` and `decorative`.
- `number_formats` (computes): the workbook's named number formats, `{id, name, code, to_name}` each (D378). A style's
  data has `number_format` when it names one.

### Changed
- **Breaking** (network): search and replace in a workbook name every place as `at` = `{sheet, row, col}`: a match is
  `{at, kind, number, …}`, a left-out cell `{at, kind, why}`, a change `{at, kind, before, after}`, a skipped cell
  `{at, kind, reason, by}`; `leave` takes `{at, match}` (was `{sheet, row, col, match}`, now refused). The same shape
  will serve composes and creates (CODE-18). The methods moved to `claudia_server.computes_search`.
- The search runs on `claudia_search` (`regex`): one request searches for `SEARCH_SECONDS` (2 s) at most, inside a
  pattern too, and then answers `timed_out` with what it had found (SEC-18; before, the 2 s were checked only between
  cells, and one pattern on one cell could hold the server for minutes). `search_preview` answers `timed_out` as
  well; `search_replace` refuses (`command_error`) rather than replace part of what was asked (PERF-11).
- A pattern that "could backtrack without end" is no longer refused as an `error`: it runs until the deadline.
- `leave` holds at most 10000 items.

### Changed (UX-33)
- When `hello` creates a document, the server runs the app's `setup_commands` once, as one `core.Setup` entry by the
  maker: a new workbook has `Sheet1`, a new text or presentation the language of the `locale` the maker's client sent
  (or the default). None of it is an undo step. A client no longer adds the first sheet or sets the language itself.

### Fixed
- `GET /api/fonts/{sha256}` and `/api/fonts/{sha256}.woff2` no longer run on the event loop (PERF-09). Making a WOFF2
  file takes seconds (2.4 s for an ordinary 740 KB font), and every other request of every document waited for it the
  first time a page asked for a font.

## [0.29.0] - 2026-11-13

Rendered text containers on the wire (D390-D396).

### Added
- Methods `rendering_types` and `renderings` in every app; `add_rendering` and `set_rendering_source` in creates
  and computes (composes cannot place objects yet).
- The hub makes pictures in the background (`RENDER_DELAY`, `Hub(renderings=...)`, `HostedDocument.stop_rendering`)
  and sends the event `render_result` `{id, ok, diagnostics, message, unavailable}`.
- Settings `render.tools` and `render.plugins_dir`; the start-up lines say which container types are on offer and why
  one is not.
- `export_office` draws rendered pictures as PNG with `rsvg-convert` when it is installed, and returns losses for
  pptx too.
- The help library includes `claudia_render` (topic `render.configure-tools`, English and German).

## [0.28.0] - 2026-11-13

Help and function documentation in German (E13.8, D323).

### Added
- `set_locale(locale)`: the person chose another interface language in this window; what the server says to it from
  then on (errors, help, function descriptions) is in it. Any role may call it; answers `{locale}` as understood. The
  web app sends it when the language changes and after a reconnect. `Context.set_locale` is the callback behind it.
- Help topics can be translated: `<topic>.<language>.md` next to the English file, with the same `id`, its own
  `language` and a `source-hash` (the `fingerprint` of the English file it was made from). `HelpLibrary.get(id,
  language)` and `search(query, language=)` give the translation where there is one and English where not
  (`help_search` and `help_topic` use the connection's locale; `help_topic` says which `language` it answered in);
  `HelpLibrary.stale()` lists translations older than their source and `check()` refuses one without its source. A
  test fails on a stale translation. `Topic` gained `source_hash` and `fingerprint`.
- `functions` and `function_help` say the descriptions and the words of the worked examples in the connection's
  language (German first), the formulas, results and signatures unchanged.

## [0.27.0] - 2026-11-13

The server's own messages are said in the language of the connection (E5.7, D31, D322).

### Changed
- A `RequestError`'s message may be a `claudia_server.i18n.Message` (`msg("{what}: at most {limit} cells at a time",
  limit=500)`): it reads as its English text and `RequestError.to_dict(locale)` says it in the language of the
  connection it is sent to (the `locale` of `hello`, `Context.locale`). The server's own request errors, the refusals of
  `hello` and `HubError` are written that way, with German as the first catalog
  (`claudia_server/locale/<language>/LC_MESSAGES/claudia.mo`, built from `po/<language>.po`). What the document packages
  raise (`str(exc)`) and the assistant's own chat texts stay English until they carry templates too (E5.17). The wire
  protocol is unchanged: `message` is still one string, and a client that sends no `locale` gets English.

### Security
- Every HTTP answer carries a `Content-Security-Policy` (scripts from this server and the start page's inline scripts
  by hash, connections to this server and its WebSocket, `object-src 'none'`, `base-uri 'none'`, framing only by the
  server itself or a page on this computer for the desktop shells, D251), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer` and a `Permissions-Policy` (`claudia_server.security_headers`, SEC-13).

### Fixed
- `chat` without `ai_mode` gets *act* (`ai_mode.UNSAID_MODE`), as the method's own description and E7.7 say; it had got
  *suggest*, so with no client sending a mode yet the AI in computes changed nothing and pointed at a switch that no
  client had (QA 2026-11-12, UX-20). A client still starts with *suggest* (`DEFAULT_MODE`, D262) once it has the switch.

### Added
- Random numbers, alternatives and following a computation in the computes app (E6.21–E6.23): `random_state`,
  `resample` (F9, steps 1–1000), `set_random_seed`, `outcome_table` (`sheet, row, col, combine`: all or paired
  combinations) and `trace` (`sheet, row, col, reach, window`: the lit cells of a window). `cells` carries `alts`
  (the alternatives of an input) and `out` (the median and spread of an outcome). `export_office` answers `losses`
  for xlsx too. The protocol version stays 2: only methods and fields were added.
- `random_preview` (`distribution, params, low, high, draws`): what the Random generator dialog shows — the formula to
  type, the text an Excel file would hold, and up to 1000 draws of the distribution itself (E6.22).
- Lists in the text app (E9.21, `claudia_server.composes_lists`): `make_list(blocks, scheme)` (bullets, numbers or, with
  a null scheme, none; asking for what the paragraphs are takes them out, the other kind of a whole list changes its
  scheme, anything else starts a new list), `indent_item(blocks, by)` (answers how many items moved), `continue_list(block)`
  and `list_start(list, start)`; each is one history step and the assistant has no access (D63). `blocks` also
  answers `lists` and `schemes`, and gives every list item an `item` and a derived `label` (`{marker, path}`). The
  events `item`, `labels` and `lists` follow the document.
- Search and replace in workbooks (E6.20, D284-D286): `search_find`, `search_preview` and `search_replace` look in text,
  formulas and values on every sheet, one sheet or a selection; show what a replacement would change; and replace in
  one history step, skipping and naming the cells somebody else holds. A mistake in a person's pattern, or a pattern
  that could run without end, is answered as `error: {message, field, position}`, not as a failed request. A search
  stops after two seconds (`computes.SEARCH_SECONDS`; the answer says `timed_out`) and a replacement may change
  10000 cells. The AI user may call `search_replace` (`apps.MODEL_METHODS`). New methods of an app do not change
  `PROTOCOL_VERSION`.
- One style API for all three apps (`claudia_server.style_targets`, the styling-suite plan step 1.5):
  `style_model` (facets, kinds, slots with the kinds each takes, and the target keys this app accepts),
  `apply_style(targets, style, slot?)`, `deviate(parent, targets, slot?, set|text)` and `style_uses`. A target is
  `{"object": id}` in every app, `{"block": id}` in composes (and `{"sheet": id, "range": [...]}` in computes);
  without a `slot`, a style fills every slot it fits (D309, D311, D316) and a deviation every slot that held the
  parent. `add_style_methods` takes the app's `targets`; a later kind of thing is a row of the slot table and an
  adapter (D315). The narrower methods stay until every client uses these.
- computes: cells are a style target, `{"sheet": id, "range": [r0, c0, r1, c1]}` (D307, D311); a whole column,
  row or sheet goes into the layer of its shape. `cell_styles(sheet, row0, row1, col0, col1)` returns the style
  ranges of a window, cut to it, for a client to paint; `cell_style_at(sheet, row, col)` says where a cell's look
  comes from, slot by slot.
- computes: styling cells lets the last action win (D317); `clear_cell_style(sheet, range, slot?)` takes the
  cells' own style away so that the row's, column's or sheet's style shows through.
- `export_office` also writes `"odt"` for the text app (D401), and its answer then has `losses`: what the file could
  not hold, as a list of `{kind, detail, count}` codes (nothing yet puts them into words; the screen is designed
  first). A format that cannot say has no `losses` in the answer. The error for an unknown format names both.
- `export_office` of the presentation app also writes `"odp"` (D412), with `losses`, and the file says in its metadata
  when the deck was made and last changed and by whom, read from the log (D411).
- `export_office` of the spreadsheet app also writes `"ods"` (D413), with `losses` and the metadata from the log (D411).
- The text app's `export_office` takes `tracked_changes` (default `false`, a clean copy, D212): the open suggestions
  that propose a replacement are written as tracked changes, dated with when they were proposed and signed by their
  author (docx and odt); an odt's metadata is filled from the log (D411).
- computes: `names`, `define_name`, `rename_name`, `remove_name`, `sql_preview`, `define_sql` (D600–D609), and a pushed
  `names` event; `diagrams`/`define_diagram` accept a chart that reads a named `source`. They are not yet in the AI's allow-list.

### Changed
- `set_paragraph_style` is one of the shared style methods (`add_style_methods`), so computes and composes have it
  as creates did: the objects of a sheet or a text can have their words restyled too.
- A new text box's own style is `plain-box`, the box slot (D310); its words stay `body-text`.
- `set_object_style` and `set_paragraph_style` refuse, as `command_error`, a style that does not fit the slot
  (D316): a paragraph style on a shape's outline, an outline style on its words.
- A new shape's words start under `shape-label`, not under the shape's own style: a shape's outline and its words
  are two styles of two kinds (D310). A text box's words stay under `body-text`.
- `deviate_style` and `deviate_object_style` make a style of the parent's kind (D305), and refuse, as
  `command_error`, a property the kind cannot hold (changing the font of an outline, say).
- `styles` answers each style's `kind` (D305).
- The built web app is served with `Cache-Control` (D248): pages and every file not named by its content are
  revalidated on each load (`no-cache`, a cheap `304` when nothing changed), the content-hashed files under `_nuxt/`
  are kept for good (`public, max-age=31536000, immutable`). Before, a client that kept its cache between runs (the
  WebKit view of the Linux client) could show the previous web app for a long time after the server was updated.

## [0.26.0] - 2026-11-13

Printing slides (D917).

### Added
- creates: `print_setup` and `set_print_setup(setup)` (a viewer cannot change it), and `language` and
  `set_language`, as composes has them.
- `claudia_server.printing`: what the apps that print share — `add_language_methods(table)` and `people_only(ctx)`.
  composes' `language` and `set_language` are made by it now; their answers are unchanged.

## [0.25.0] - 2026-11-12

Hyphenation and SVG in the client's pages (D912–D915): the server hands out the patterns.

### Added
- `GET /api/hyphenation` and `GET /api/hyphenation/{sha256}` (`claudia_server.hyphenation`, D913): the languages the
  server can hyphenate (BCP 47 tag, other tags they stand for, name, licence, the hash and size of the pattern file
  and of the exceptions), and the files themselves under their hash, cached for good.
- `--hyphenation DIR` (default `STATE_DIR/hyphenation`) and `create_app(hyphenation=...)`; the start-up banner names
  the languages, or says that pages are not hyphenated.
- `python -m claudia_server.hyphenation fetch DIR`: the TeX hyphenation patterns of hyph-utf8 for German (1996
  spelling) and British and American English, pinned at one commit with every file's SHA-256
  (`hyphenation.lock.json`).
- composes: `language` and `set_language` (D915), the language of a text.

## [0.24.0] - 2026-11-12

Print preview and PDF in the client (D901–D907): the server hands out what the client lays out with.

### Added
- `GET /api/fonts`, `GET /api/fonts/{sha256}` and `GET /api/fonts/{sha256}.woff2` (`claudia_server.fonts`, D905): the
  font catalogue as data (family, style, weight, slant, variation axes, outline kind, hash, licence, substitutions)
  and the font files themselves under their hash, cached for good; only fonts whose collection may be redistributed.
- `--fonts DIR` (repeatable; default `STATE_DIR/fonts`) and `create_app(fonts=...)`: where those fonts come from.
- composes: `page` and `set_page` (D904), the page a text is printed on; `objects`, `images` and `shapes` (D907),
  the floating objects of a text and what they are drawn with, for the print preview.

### Security
- The Content-Security-Policy allows `'wasm-unsafe-eval'` (WebAssembly compiled from bytes the page fetched from this
  server: HarfBuzz, D903; no JavaScript `eval`) and `frame-src 'self' blob:` (the PDF a page made, handed to the
  browser's print dialog, D906).

## [0.23.0] - 2026-11-11

The AI looks, acts, checks and corrects (E7.5), and a request that names no mode is a *suggest* request (D262).

### Added
- The model's loop (`ModelEngine`): a question takes rounds on the shared runner. The model asks to look at the document
  or change it; the server makes the requests as the asker's AI under the question's account and sends back what came of
  them: what it saw, and after a change the effect report (every cell that changed, recalculated dependents included,
  and which of them show an error); the model carries on until it answers without requests. `Budget` (rounds, requests,
  characters shown) ends a model that never answers, and the asker is told what was done before it stopped.
- The lens, an app's side of the loop (`lens.Lens`, `lens.fence`, `lens.cut`): the orientation the model starts with, the
  read requests written for a model (`B2: 24 (=B1*2)`, errors marked) and the effect report. `WorkbookLens` is the one
  for computes. Everything that comes out of a document is handed to the model fenced as data.
- `Task.call`: an engine can make requests as the AI under the question's account while it plans.

### Changed
- **Breaking:** a `chat` that sends no `ai_mode` is a *suggest* request (0.22.0 treated it as *act*): `ai_mode.LEGACY_MODE`
  is gone, `DEFAULT_MODE` is what it means. A client that wants the AI to change the document must say `"act"`.
- **Breaking:** `ModelEngine(runner, tools, lens, ...)` takes a lens, not a function describing the workbook;
  `steps_of` is gone (the model's answers are no longer turned into steps once, the loop makes the requests itself);
  `tools_of(..., kind=)` and `model_assistant_for(..., budget=)` are new. `model_assistant_for` knows the apps that
  have a lens (computes); for composes it returns `None`, so `--ai` on a composes server now says so at start-up
  instead of starting an AI that failed on its first question.

## [0.22.0] - 2026-11-11

The AI works under the account of the person who asked, in the mode she chose (D261, D262; E7.4, E7.7).

### Added
- `chat` takes an optional `ai_mode` (`"act"` or `"suggest"`): how the sender wants the AI to treat this request. It is
  not stored; a client that sends none gets `"act"` (it is an older one and could not choose). Anything else is a
  `bad_request` and nothing is posted. The mode a client starts with is *suggest* (`ai_mode.DEFAULT_MODE`).
- `Account.acting_for(asker_role, writes)`: the account the AI answers one question under: the weaker of its role and
  the asker's, with the allow-list narrowed to `writes`. `Assistant.account_for(asker, mode)` builds it per question;
  `Assistant(suggest_methods=...)` is what it may write for *suggest*; `apps.SUGGEST_METHODS` lists that per app (only
  composes' `suggest` today, since computes and creates cannot propose before E7.8).
- `Task.mode` and `Task.writes`: what an engine is told about the question. `ModelEngine` offers the model only the
  tools in `writes`, and leaves the example request out of the prompt when there is none.
- `HostedDocument.role_of`, `note_ai_mode`, `ai_mode_of`.

### Changed
- In *suggest* mode in computes the AI writes nothing and says so (a chosen mode, not an error). Clients that do not send
  `ai_mode` are unaffected.

## [0.21.0] - 2026-11-10

Word, Excel and PowerPoint export, one method per app (D212).

### Added
- `export_office(format)` in composes (`"docx"`), computes (`"xlsx"`) and creates (`"pptx"`): the document as it
  stands now — no history, no chat, no open suggestions — as `{format, content_type, data}`, `data` base64. Any
  other format is `bad_request`.
- `office_export.office_export(fmt, data)`: the one place that wraps those bytes for the wire.

### Changed
- `claudia-server` now depends on `claudia-composes-io`, `claudia-computes-io` and `claudia-creates-io`.

## [0.20.0] - 2026-11-09

What the style menus in all three apps needed from the protocol (D203).

### Added
- `deviate_object_style`: "change this shape only". Makes a new style from the one an object has, differing in the
  CSS given, and points the objects at it in one step — with a provisional name, marked `to_name` until somebody
  names it (D75). The mirror of composes' `deviate_style`, which names paragraphs; this one names objects, and all
  three apps have it.
- `palette` now also answers `builtin`: the palette a document starts with, so a client can offer "the colours it
  started with" without keeping a copy of the nine roles that could drift from the server's.

## [0.19.0] - 2026-11-09

Fixes `help_search` leaking one app's topics into another's (UX-13): a topic meant for `claudia_computes` was
showing up in `claudia_composes`' Help tab and the reverse, because nothing read the `apps` front matter the topic
files already carried.

### Changed
- **`HelpLibrary.search(query, *, app=None)`**: new optional keyword. When given, keeps only topics that name `app`
  in their own `apps` front matter, or that name no app at all (shared topics still show everywhere). `query=""`
  with an `app` given now means "every topic for this app", not "every topic".
- **`core_methods.help_search`** now passes the asking document's own app (`ctx.document.model.app`) to `search`,
  so each app only ever sees its own topics plus any shared ones. `help_topic` is unchanged: an id already names
  one exact topic, the same way a direct link would from anywhere.

claudia-composes gained its own first two help topics (`composes.editing-a-style`, `composes.asking-ai-to-review`),
so its Help tab is no longer empty now that it is correctly scoped.

## [0.18.0] - 2026-11-08

A first, cross-app help system (E13): searchable help topics and, for `claudia_computes`, a searchable catalog of
every cell function, both read-only and open to every role including the `ai` user.

### Added
- **`help.py`**: `Topic` — a help topic's id, title, apps, language, tags, `explains` and body. `parse_topic(text,
  source=...)` reads the Markdown-with-frontmatter shape already drafted for `claudia_typeset` (D99/E13.1), raising
  `HelpContentError` with the source for anything malformed. `HelpLibrary` holds topics loaded from a folder
  (`load_folder`) or added directly (`add`), and answers `get(id)` and `search(query)`. `default_library()` is the
  lazy, server-wide library, loaded once from every installed package's own `help/` folder (`claudia_typeset`,
  `claudia_computes`, `claudia_composes`, `claudia_creates` — a package with no such folder, or that isn't
  installed, is skipped).
- **`core_methods.help_search`** (read, `query:str=""`): topic summaries (id/title/apps/tags) whose title, tags or
  `explains` mention `query`, or every topic if `query` is blank. Inherited by `composes_methods`, `computes_methods`
  and `creates_methods`, so any app gets it for free the moment it has a `help/` folder of its own.
- **`core_methods.help_topic`** (read, `id:str`): one topic in full. `command_error` if `id` is unknown.
- **`computes_methods.functions`** (read, `query:str=""`): the function catalog (library and core forms together,
  via `claudia_computes.search_functions`), as name/signature/tooltip/source summaries.
- **`computes_methods.function_help`** (read, `name:str`): one function's signature, tooltip and full help text, by
  name, case-insensitively. `command_error` if `name` is unknown.

claudia-computes (unversioned) gained the generating side of the function catalog: `FunctionHelp`, `function_catalog
()`, `search_functions(query)` and `get_function(name)`, unifying the library functions' existing `Bound.get_tooltip`
/`get_help` with the core forms' own docstrings — no new content was written for this; both halves already carried
everything needed.


Colour roles over the protocol, and the style methods shared by every app (D200–D203).

### Added
- `claudia_server.styles.add_style_methods(table, guard=None)`: registers `styles`, `palette`, `set_role`,
  `replace_palette`, `set_object_style`, `change_style`, `rename_style` and `check_css` into an app's table. All
  three apps call it, so a presentation and a workbook can now change their styles and not only read them.
- `palette` returns `{roles, readings}`: a role is `{id, name, purpose, colour}`, a reading is
  `{foreground, background, ratio, floor, ok, words}`. A reading carries **no verdict text** — each client says
  what a failure means in its own words, and never shows the ratio to a reader.
- `set_role` gives one role another colour; everything in the document that meant that role follows. Nothing is
  refused for contrast: `palette` reports what a colour costs, it does not prevent it.
- `replace_palette` puts a whole palette in place of the one the document has, which is what "replace palette" and,
  later, a template will use. Refused while a style names a role the new palette has not.
- `set_object_style` puts an object under another style of its own (`fill`, `stroke`, `stroke-width`), beside the
  `set_paragraph_style` that already pointed its words elsewhere.

### Changed
- **Breaking:** every style in `styles` (and in composes' `blocks`) now carries a third form of its CSS,
  `resolved`, with the palette's roles replaced by literal colours. **A client must draw from `resolved`**;
  `computed` still names the roles, which is what a style menu shows. The role grammar deliberately stays on the
  server, so what reaches a browser is always a literal colour.
- `composes_methods` keeps only `set_style` and `deviate_style` of its style methods — the two that name
  paragraphs. The rest are the shared ones, and composes passes `_people_only` as their guard, so in a text the
  assistant still suggests and does not write (D63, SEC-10).

## [0.17.0] - 2026-11-07

The grid, and snapping to it (E10.15), on top of `claudia_creates`'s new `SetSnap` command.

### Added
- **`creates.set_snap`**: a write method taking an object's id and a `snap` boolean. Holds the object to the grid
  or releases it; the grid itself is a view-only helper and has no method of its own here. `creates.slide`'s
  objects each carry the new `snap` field.

## [0.16.0] - 2026-11-07

Who may configure the server, as a question separate from any document's own users (D20/D35): server-side identity,
sessions and a REST API for the settings pages. The pages themselves (Nuxt) are a later patch; this one is the
backend they will call.

### Added
- **`admin.py`**: `AdminAccount`, `AdminDirectory` — a server's administrators, scrypt-hashed the same way a
  document's own users are (`auth.ScryptDirectory`), but kept once for the server, never inside a document.
  `needs_administrator(exposed, admin_count)` is the "exposure gate": a server that only answers to this computer
  never needs one; the moment it is told to listen beyond that, it needs exactly one before its settings do
  anything but offer to make one, and never asks again once it has one.
- **`admin_sessions.py`**: `AdminSession`, `AdminSessions` — short-lived bearer tokens for signed-in administrators,
  in memory only (a restart signs everyone out, same as it drops every open document connection).
- **`admin_api.py`**: `AdminContext`, `AiRuntime`, `admin_router` — the `/api/admin/*` routes: `status`, `setup`,
  `login`, `logout`, `me`, `admins` (list/add/remove/change password) and `settings` (`max-documents`,
  `access-secret` with reveal and rotate, `ai`, `typeset`). Mounted by `create_app`'s new `admin` parameter
  (`None` by default: every existing caller is unaffected). Changing the AI model restarts just the model, in
  process (`AiRuntime.apply`); a changed `max_documents` or access secret takes effect on the next request.
- **`server_settings.py`**: `ServerSettings`, `AiSettings`, `TypesetSettings`, `Changed` and
  `load_settings`/`save_settings`/`load_admins`/`save_admins` — what an administrator has configured, who last
  changed each part of it, and how it is written under `<state dir>/admin/` (next to the TLS certificate).
- `Gateway.set_secret`: changes the access secret while the server runs.
- `create_app`'s new keyword-only `admin: AdminContext | None = None` parameter.
- `python3 -m claudia_server`: `--max-documents` now defaults to whatever was last saved through the settings
  pages (or the built-in default if nothing was ever saved) rather than always to a fixed number; given on the
  command line, it pins the cap for that run only and leaves what is saved untouched. `--access-secret-file` and
  `CLAUDIA_ACCESS_SECRET` follow the same operator-override rule against a secret saved through the settings
  pages. `--ai`/`--ai-device` likewise override an AI model saved through the settings pages; without `--ai`, a
  saved model is loaded instead of (and survives a restart unlike) the stand-in. The start-up banner reports the
  server's administrators, or that it needs one.

### Changed
- `claudia-typeset` is now a dependency (`resolve_program`/`EngineUnavailable`, for the typeset settings' "is this
  program where I said it is" check — no typesetting itself is wired into the server by this release).

## [0.15.0] - 2026-11-07

The groundwork for E5.7 (D31/D148): no interface string has moved into a catalog yet, by design — the plumbing is
proven first, with an (almost) empty catalog, so moving real strings later is mechanical.

### Added
- `hello`'s optional `"locale"` parameter and the matching field on `welcome` and on every live connection
  (`Connection.locale`, normalized by `protocol.normalize_locale`, never trusted raw). Nothing reads it yet — no
  interface string has moved into `_()`/`t()` — but every app gets it for free through the shared handshake.
  `Connection.__init__` and `HostedDocument.connect` take an additional optional `locale` parameter (additive,
  default `DEFAULT_LOCALE`: no behaviour change for a caller that does not pass one).
- `PROTOCOL_VERSION` bumped to **2** for the new field; documented in `docs/server.md`.
- `RequestError.detail` (optional): the finer-grained `claudia_core` error `code` (D148's kernel-side addition)
  behind a wire-level `code` (`"locked"`, `"stale"`, `"conflict"`...), included in `to_dict()`/the wire response
  only when given. `message` stays the English sentence for anyone not yet rendering from `code`/`detail`.
  `MethodTable.dispatch` passes it for `StaleEdit`, `RegionHeld`/`UndoRefused`, `UndoConflict` and any other
  `KernelError`.

## [0.14.0] - 2026-11-07

Importing a picture from disk and putting it on a slide (E10.8), built on `claudia_core`'s new image decoding and
`claudia_creates`'s new image object. Clipboard and drag-and-drop import are deliberately not built yet.

### Added
- **`creates.add_image`**: a write method taking a slide id, a frame (`x y w h`), the file's bytes as base64
  (`data`), a required short `alt` description, the file name the client has (`source_name`), and its full path if
  the client could supply one (`source_path`, nullable — a plain web browser cannot, for its own security). Decodes
  the bytes with `claudia_core.decode_image`, shares the asset across objects that import the same picture exactly
  (byte-for-byte), and adds the image object in the same step of the history. An image keeps its own proportions,
  like a circle.
- **`creates.images`**: the decoded image assets this document has taken in, each as `{id, format, width, height,
  animated, data, first_frame}`.
- **The `"image"` parameter kind** (`images.py`, new module): base64 text decoded to raw bytes, capped at
  `claudia_core.MAX_IMAGE_BYTES`. App-agnostic on purpose — composes and computes register the same kind on their
  own extended table (`table.kind("image")(image_bytes)`), rather than each app writing its own base64/size check.
- **Per-connection event masking**: `hub.py`'s `HostedDocument._on_event` now calls an event's own
  `to_data_for(viewer)` when it has one, instead of the one shared `to_data()` every event used before. This is how
  `creates.slide`/the `objects` event hide an imported image's `source_path` from everyone but the person who
  imported it (the path is unmasked in `imported_by`/`source`/`source_name`, matching the decision that an import
  is attributed, only its local disk path is private). The hook is app-agnostic — `hub.py` imports nothing from
  `claudia_creates` — so any future app's event can opt in the same way.
- `creates.add_object` now refuses `kind="image"` with a pointer to `add_image`, instead of failing deeper inside
  the kernel model with a less specific error.
- `creates.slide`'s object shape documents the new `image`/`imported` fields and the `source_path` masking rule.

### Notes for implementers
- Redaction (`AddObject.redacted()`) does not yet touch an image's `alt`/`source_name`/`source_path`; see
  `claudia_creates`'s 0.2.0 changelog entry. Carried over here unchanged — not addressed by this release.
- A plain web browser's file input/drag-and-drop APIs cannot supply a full filesystem path (only the file's name),
  so a web client should send `source_path: null`. A desktop client that reads the real path can send it, and it
  will be masked correctly for every other viewer.

## [0.13.0] - 2026-11-06

Go back to a checkpoint, with everybody's consent (E3.7), and a read-only preview of any line before anybody is
asked (E3.8). Restoring or switching the line is no longer a bare request: an owner or editor suggests it, and it
happens once everybody connected now as an owner or editor has agreed — unless the one suggesting it is the only
one, in which case it happens at once, same as it always has.

### Added
- `peek_line(line:str)`: a read-only look at any line (active or hidden), without switching to it. On `core_methods`,
  so every app gets it the way it already gets `lines`, `log` and `chat`.
- `restore_policy` / `set_restore_policy(policy:str)`: an owner's choice of `consensus` (silence at the deadline is
  a decline) or `veto` (silence is agreement), for the whole document. Session state, not stored in the document.
- `propose_restore(checkpoint:int)` and `propose_switch(line:str)`: suggest it (E3.7). `command_error` for an
  unknown checkpoint or line, or if a suggestion is already open — at most one at a time.
- `answer_restore(agree:bool)`: agree or decline the open suggestion; resolves it the moment everybody has agreed,
  or the moment anybody declines. `withdraw_restore()`: take it back (the proposer, or an owner).
- `discard_side_history()`: owners only, the wire method `Document.discard_side_history` was missing — forgets
  every hidden line for good. `command_error` while a suggestion is open.
- Events `restore_proposed` (opened, or its answers changed) and `restore_resolved` (`{outcome: agreed|declined|
  withdrawn}`); `agreed` is followed by the usual `branch` and `rebuilt`. A client's welcome now also carries
  `lines`, the open `proposal` if any, and a one-time `returned` notice for whoever was away when one resolved.
- `HostedDocument.editors()`: who is connected now and may write (owners and editors, not viewers or the
  assistant) — who must be asked before a restore or a switch happens.
- `RestoreCoordinator`, `Proposal`, `Resolution`, `RestoreError` (`restore.py`): the consent itself, kept apart
  from the kernel and from the wire protocol on purpose — session state, not a document's stored state.
- The assistant may never propose, answer or withdraw (`forbidden`, SEC-10): going back is a decision of people.

## [0.12.0] - 2026-11-06

Row heights and column widths (E6.13/E6.16, D135): sheet layout, not a cell style.

### Added
- `sizes(sheet)`: the rows and columns of a sheet that were given a size away from the default.
- `resize_lines(sheet, axis, sizes, base:revision?)`, write: sets or clears (`size: null`) the size of up to
  `MAX_RESIZED_LINES` (1,000) rows or columns in one call, each checked against the allowed range. On the AI's
  method allow-list alongside `set_cells`/`add_sheet`/`structure`.

## [0.11.0] - 2026-11-06

Leaving a document, handing over its ownership, deleting it, and exporting its content (E2.3, E2.9; "Manage" in
every app's File menu).

### Added
- `roster`, `leave`, `propose_owner`, `accept_owner`, `delete_document`, `export_content`: the new wire methods
  behind the File ▸ Manage submenu (assign new owner, leave, export, delete). Handing over ownership is a
  propose/accept pair, because a role lives inside its own password-sealed slot (D102): the current owner proposes
  with their own password, and the new owner (who must already be an editor) accepts with theirs, each confirming
  their own identity. `export_content` returns the document's current content as Claudia's own JSON format only
  — not Word, Excel or PowerPoint, and not yet the history or the chat (both stay open, E2.9).
- `RosterDirectory`, `LeavableDirectory`, `TransferableDirectory`, `DeletableDirectory` (`claudia_server.auth`):
  optional directory capabilities for the above, checked with `isinstance` and implemented by `SealedDocuments`
  only — like `RecoverableDirectory`, a server using the lightweight in-memory or file-backed directory does not
  offer them yet, and says so (`unavailable`) rather than failing oddly.
- `SealedDocuments.list_people`, `.leave`, `.propose_owner_transfer`, `.accept_owner_transfer`, `.delete_document`.
- Three new `ephemeral` event kinds: `person_left`, `owner_changed`, `document_deleted` — so everybody still
  connected finds out without having to poll.

## [0.10.0] - 2026-11-06

The worker pool D37 specified and left unbuilt: `Connection.handle` runs synchronously on the event loop, so slow
work in one request used to stall every document the server holds (QA review 2026-11-06, PERF-02; D134).

### Added
- **`WorkerPool`** (`workers.py`): runs a function in a separate OS process and awaits its result —
  `await pool.submit(fn, *args, **kwargs)`. Generic on purpose: knows nothing about cells, formulas or typesetting.
  `fn` and its arguments must be importable at module level and picklable. A worker process dying outright (killed, a
  segfault in a C extension) breaks only the task that caused it: the pool replaces itself transparently on the next
  `submit`, so neither the server nor another document's pending work is affected. `pool.stop()` lets the worker
  processes go; safe before anything was submitted and safe to call more than once. `DEFAULT_WORKERS` (4).
- **`Hub.workers`**: one `WorkerPool` per `Hub` (one process per `--model`, D134 — not a pool shared across process
  boundaries), sized by the new `Hub(..., max_workers=...)` constructor argument. `Hub.stop()` now also calls
  `workers.stop()`.

## [0.9.0] - 2026-11-06

Security release: the second QA review's first recommendation (SEC-10).

### Added
- **The AI's allow-list is enforced at dispatch, not only in the model's output parser (SEC-10, E7.6, E9.9).**
  `Account.allowed_methods` (set by `Account.assistant(allowed_methods=...)`): the write methods this account may
  call, checked by `MethodTable.dispatch` before the method runs — the one place every path goes through
  (`Assistant._call`, the wire, and any future remote AI connection). `Assistant(allowed_methods=...)` passes it on
  when the account is made; `apps.stand_in_assistant_for` and `apps.model_assistant_for` both set it from
  `apps.MODEL_METHODS` of the document's app, so the scripted stand-in is held to the same guarantee as a real
  model, not only the engine `claudia_ai.Agent._take_calls` happens to filter for. `apps.MODEL_METHODS` gained a
  `"composes"` entry: `("suggest",)`, so a composes assistant is refused by name, not only by an empty allowed set.
- `protocol._apply` refuses `account.system` unconditionally: the assistant cannot use the generic `apply` as a
  tunnel around an app's own wrapper checks (`composes._people_only` and the like), whatever its allow-list says.

### Changed
- `Account.__init__` and `Account.assistant()` take an additional optional `allowed_methods` parameter (additive,
  default `None`: no behaviour change for an account nobody restricts). `Assistant.__init__` takes an additional
  optional `allowed_methods` parameter (additive, default `()`: an assistant made without passing it writes
  nothing, which is the safe default rather than a convenience).

## [0.8.0] - 2026-11-03

Sealed documents are packed into blocks with a snapshot, and the recovery key is shown (E2.1, E2.5, E2.2).

### Added
- **Packing.** `SealedDocuments` folds the journal of a document into the blocks of its file and leaves a snapshot when
  the document is let go, when one is opened with unpacked work left over from a crash, and every `pack_every` (500)
  changes while it is open. Opening uses the snapshot and replays only what follows it. A failed packing is logged and
  loses nothing: the journal still has it. A removed, changed or reordered block is refused when the document is
  opened.
- **Recovery key.** The wire method `new_recovery_key` (owners only; `{recovery_key}` as 13 groups of 4 letters and
  digits, shown once, never stored by the server, a key made before stops working). `hello` accepts `recovery_key`
  together with `user` and a *new* `password`: if the key is the document's, the person gets that password, keeps their
  role (somebody new becomes an owner) and is in. A wrong key, a missing document and a server without recovery keys
  look alike. `auth.RecoverableDirectory`; `SealedDocuments.new_recovery_key` and `.recover`.
- `hello` answers `created` (true if this very `hello` made the document), so that a client can show the recovery key
  at once.
- Error code `sealed` (close code 4423): the document is stored but nobody who holds all its keys has opened it since
  the server started. A viewer is told to try again later; before, this was `bad_request`. `DocumentSealed`.
- `Hub.housekeeping()`: idle documents are let go in a thread, under the lock that opening takes, so packing neither
  stops the server nor races with opening the same document again. `Hub.stop()` lets go of every open document, so a
  server that is shut down gracefully leaves packed files.

### Changed
- **Breaking:** a viewer who reaches a sealed document gets the error code `sealed` and close code 4423 instead of
  `bad_request` and 4400.
- Opening a document from a snapshot does not restore undo steps made before the snapshot (they start again).

### Fixed
- Two people logging in at the same moment could hang the server for ever (see claudia-container 0.3.0).

## [0.7.0] - 2026-11-03

### Added
- Styles in texts (E9.7, E1.10): `composes_methods` offers `styles`, `change_style`, `deviate_style`, `rename_style` and
  `check_css`. A style is CSS (the allow-list of `claudia-core`, `CSS_VERSION` 1). `change_style` changes a style for
  every paragraph that has it, by properties (`set`, `unset`) or by the complete CSS `text`; `deviate_style` makes a new
  style from a parent for given paragraphs in one history step, with a provisional name (`Heading 1 (changed)`) and
  `to_name` set until `rename_style` names it; `check_css` reads CSS text and reports every problem with its line,
  without changing anything.
- The `styles` event (the whole style book, with each style's `computed` CSS) comes just before the command event of a
  change of a style.

### Changed
- **Breaking:** `blocks` answers `styles` as `{id, name, purpose, based_on, css, computed, to_name}`; the `next` field
  is gone (what follows a style is decided by the server from the style a deviation is based on).
- A text document's state has `state_schema` 3 (it holds its styles); older states get the built-in styles.

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
- `scripts/start.py --app creates` starts the presentation server (documents in `docs-creates`).

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
