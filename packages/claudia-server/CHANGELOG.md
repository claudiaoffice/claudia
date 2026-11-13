# Changelog of claudia-server

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

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
