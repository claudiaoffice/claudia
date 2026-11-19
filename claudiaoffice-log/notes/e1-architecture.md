# E1 architecture: the what-if, names and descriptions, the way back, the font banner

*Draft for the owner's review, 2026-11-19, branch `e1-core`. Nothing here is built. The mocks are agreed
(`names-01` … `names-05`, `requirements-01`); the what-if design is agreed (D1308); the decisions behind this note are
D1308, D1310–D1313, D1317 and D1318. The function folder and the macro/UserFunction topic stay parked (D1309, D1313):
**nothing below touches them.***

Three diagrams, in `notes/mockups/` (SVG with a PNG next to each; solid outline = exists today, dashed = new in E1,
a bold coloured line in a solid box = a new member of an existing class):

| Diagram | Shows |
|---|---|
| `e1-architecture-01-what-if` | `Document.what_if`, `WhatIf`, `Proposal`, `ProposalOutdated`, `Entry.via` in `claudia_core`; `WhatIfDesk` and the wire methods in `claudia_server` |
| `e1-architecture-02-names-and-descriptions` | the description hooks next to the name hooks, the commands, the one server method for the one dialog, the export option |
| `e1-architecture-03-way-back-and-fonts` | the way back in the web session, the chip, the menu entry, the shells, the font banner with the administrators-only "Get" |

## 1. The one rule that decides where things go

**The kernel owns state and commands; the apps answer questions about their own things; the server and the web app ask
those questions in one shared way and never learn which app they talk to.** That is already how `named_things()` works
(E1.13), so descriptions follow the names rather than getting a path of their own. Your note of today, "every object
has a name and a description for now", is the same rule: a description is a plain string beside the name.

## 2. What I checked in the code

| Where | What is there | What it means for E1 |
|---|---|---|
| `claudia_core/objects.py`, `ObjectModel` (about lines 599–680) | `named_things()`, `thing_name()`, `set_thing_name()` as hooks the apps override | the description hooks go right beside them |
| same file, `ObjectBody.description` / `.decorative`, `DescribeObject` (about line 2332), `RenameThing` (about line 2258) | a drawn object's description and Decorative tick; the rename command | `DescribeObject` stays for drawn things (it carries Decorative); a new `DescribeThing` serves everything else |
| `claudia_composes/model.py`, `TextModel.block_names` (line 457; state key `"names"`, read back with a default, line 524) | paragraphs' names as `dict[id, str]` | `block_descriptions` is the same shape, the same default on read: "absent = no description", no migration (pre-release, D308) |
| `claudia_server/object_methods.py`, `describe_object` (about line 146); `claudia_server/thing_names.py` | the server side of the describe dialog and of the `#` list | one new method for the combined dialog beside them |
| `web/app/lib/base-session.ts`: `goToThing`, `goBack`, `Pointed {id, container, from}`, `POINT_MS = 3000` | the jump and a way back that is cleared after three seconds together with the highlight | the cause of N2; the fix is to separate the two lifetimes |
| `web/app/components/SidePanel.vue` | the Back chip is drawn inside the chat form | the cause of N3; the chip moves into its own component over the view |
| `web/app/components/ObjectDescriptionDialog.vue` | title "Describe object", description + Decorative, **no name field** | the bug N1; one dialog replaces it |
| `claudia_composes_io/_docx_references.py`, `_odt_references.py` | write bookmarks (`_Ref…`, `ref-…`) for paragraphs a reference points at; read them back | the model for "bookmark only for a person-given name" (D1311) |
| docx / odt writers | **no comment is written anywhere**; comments are only *recognised* on import (`w:commentReference`), to report that a removed block had one | the export option of D1318 needs new writing code on both sides |
| `clients/contract/shell-contract.v1.schema.json` | `native-menu`: the shell shows File, Edit, Tools and Help itself; `actions`: it sends `action` messages | the new menu entry is in *View*, which the page draws, so it needs no change in the shells |
| `web/app/components/AdminFonts.vue`, `AddFontsDialog.vue` | the administrator's font page | "Get" opens it, filled in; no new dialog |

## 3. The what-if (diagram 1)

As proposed in `e1-what-if-api.md` and approved as D1308; the diagram only fixes the places:

* **`claudia_core`** (no I/O): `WhatIf` and `Proposal` in a new module `what_if.py`; `Document.what_if` and
  `Document.apply_proposal` in `document.py`; `ProposalOutdated` with the errors; `Entry.via` in the log entry.
  Reason: it is a function of the document's own state and commands, and it must run in the tests without a server.
* **`claudia_server`**: `WhatIfDesk` in a new `what_if.py` beside `replay.py` and `planned.py`; the five wire methods in
  the next API version number's additive surface (documented in the API snapshot). Reason: *who may keep and see it*
  is a server question, as it is for the two caches it sits beside.
* `as_of` and `as_planned` do not change; they share the read allow-list with `as_what_if`.
* Nothing else is built on it in E1 except the tests and the desk; the AI's suggest mode (E7.8) is its first consumer
  and stays its own story.

## 4. Names and descriptions (diagram 2)

### Core

* `ObjectModel` gets **`thing_description(id)`** and **`set_thing_description(id, text)`** next to `thing_name` and
  `set_thing_name`. The base class answers for drawn objects from `ObjectBody.description`; each app overrides it for
  what is not drawn.
* **Commands.** `RenameThing` exists. New: **`DescribeThing(id, description)`** for everything that is not drawn.
  `DescribeObject` stays as it is, because Decorative is a property of drawn things only (D1317).
  **One dialog, one history step:** the server issues a `Batch` of the two existing commands (`RenameThing`,
  `DescribeThing`/`DescribeObject`), so Undo takes both back. No new compound command class.
* **Generic names at creation** (D1310): `name_unnamed` runs where a thing is created or imported, so a name is there
  from the first moment ("Paragraph 12", "Slide 3"): the first free number in the one namespace (cleaned, casefolded,
  1–60 characters, D554). Splitting keeps the name on the first part (as in `names.feature`).
* **Headings are called by their title** (D1311): the name is *derived* from the text when asked, never stored, with
  "(2)" on a duplicate, so it cannot go stale and costs no command. A person cannot rename a heading (locked in the
  dialog, `names-02`).

### Per app

| App | Description is kept in | Names are kept in |
|---|---|---|
| composes | `TextModel.block_descriptions: dict[id, str]` (new; state schema +1, absent = none) for paragraphs, lists, tables | `TextModel.block_names` (exists) |
| computes | beside the existing sheet / chart-tab / range names in the workbook model | exists |
| creates | beside the slide names; drawn things keep `ObjectBody.description` | exists |

### Server and web

* **`name_and_describe(id, name, description[, decorative])`** in `object_methods.py`/`thing_names.py`: validates both,
  applies the `Batch`, returns the new pair. A refused name answers in words (a name that is taken, `names.feature`).
  Additive to the wire API; the old `describe_object` keeps working until the web and the shells are moved, then is
  listed as deprecated in the API changelog.
* **Web:** `ObjectDescriptionDialog.vue` becomes `NameAndDescribeDialog.vue` with the name field (empty and required for
  an unnamed range or table, as in `names-02`), the description, and Decorative only where `thing.kind` is drawn.
  Edit ▸ Name & describe… and the right-click entry open it (already one entry in the menus workbook).
* The `#` list asks `named_things()` plus the in-view paragraphs (D551 already limits it); nothing new on the wire
  beyond the description preview.

### Import and export (D1311, D1318)

* **Import:** names that the file gives (docx/odt bookmarks around one paragraph) become names; everything else gets a
  generic name on import (D1310). Comments are **not** read back as descriptions.
* **Export, bookmarks:** only for names a person gave. A generic "Paragraph 12" never leaves the document.
* **Export, descriptions (D1318):** an *export option*, off by default, shown only when at least one paragraph has a
  description. docx: a `comments.xml` part and `commentRangeStart/End/Reference` around the paragraph; odt:
  an `office:annotation` on the paragraph. Because neither writer has any comment code, the writer for each is a small
  new module (`_docx_comments.py`, `_odt_comments.py`) beside the existing `_docx_references.py`/`_odt_references.py`,
  called from `docx.py`/`odt.py` only when the option is on. The option reaches the writer as one field of the
  export request (additive to the API), not as a global.

## 5. The way back (diagram 3)

* **State stays in the session** (`base-session.ts`), once: `pointed` keeps `{id, container, from}` and `from` becomes a
  `WayBack = {container, topVisiblePlace}` taken *before* every jump. All jumps (the `#` list, search hits, reference
  clicks, "show me" in the History panel) already go through `goToThing`, so that is the one place that sets it.
* **Two lifetimes:** the highlight keeps `POINT_MS`; the way back lives until it is **used**, **typing**, a **click in
  the text** or **another jump** (D1312). `clearBack()` is called from those four places.
* **Where "top visible place" comes from:** each app's session already knows what is on screen; a small
  `viewAnchor()` per app (composes: first visible paragraph id; computes: sheet and top-left cell; creates: slide id)
  gives it, and `goBack()` restores the container and then scrolls to the anchor.
* **The chip** moves out of `SidePanel.vue` into `BackChip.vue`, floating over the view as in the approved mock, so it
  works with History & Chat folded away (N3). It is a status region, focusable, Esc dismisses it (BITV, below).
* **The menu entry** *View ▸ Back where I was* (`view.back`, Ctrl+Shift+B / Cmd+Shift+B) goes into the shared menu
  manifest and into `claudia-menus.xlsx`, enabled only while a way back exists. View is drawn by the page, so the GTK
  and Neutralino shells need no native code (check against the contract's `native-menu` rule in the build).

## 6. The font banner (E1.9, font half only)

`FontReportBanner.vue` shows the missing fonts; **Get** is drawn only for an administrator and opens the existing
administrator font page with the missing families filled in. Everyone else sees the same banner with "ask an
administrator" and no button. **The server decides**: a Get request from a non-administrator is refused whatever the
page sent (the rule of D251–D253). Scenarios are in `specs/container/requirements.feature`.

## 7. Deleted paragraphs (D551 extension)

A tag to a deleted paragraph already replays the document at the last moment the thing existed. With paragraphs named,
the same applies to them: `last_seen(id)` (exists) gives the revision, `peek_revision` shows it, and the chip's way
back returns to where the reader was. No new mechanism; the work is the tests.

## 8. Order of work, if you agree (TDD, nothing before your go)

1. First patch of the branch: the scenarios from `names.feature`/`requirements.feature` as failing E2E, the unit tests
   for the commands and the model fields. (This patch blocks D1300–D1329 in `ranges.md` for everyone else: apply it
   first.)
2. Core: `block_descriptions`, `DescribeThing`, `thing_description` hooks, generic names at creation, headings derived.
3. Server: `name_and_describe`, the what-if kernel and desk (D1308), the font "Get" check.
4. Web: `NameAndDescribeDialog`, `BackChip`, `goBack` with two lifetimes, the menu entry, the banner.
5. Import/export: the bookmark rule, the comment writers and the export option.
6. Desktop clients: run both against the new server; i18n (`extract_i18n`, `update_po`); `claudia-menus.xlsx`; changelogs;
   Sphinx and API snapshots.

## 9. Definition-of-done notes (what each item needs here)

* **i18n:** new labels: "Name & describe…" (exists), "Name", "Description", "Back where I was", "Write paragraph
  descriptions as comments", the banner sentences, the refusal sentences.
* **Key shortcuts:** `view.back` Ctrl+Shift+B / Cmd+Shift+B is new; nothing else in E1 adds a menu entry.
* **BITV, where we diverge:** none planned for the dialog (labelled fields, errors in words). To check: the chip is a
  *status* region that appears without the focus moving, which a screen-reader user may miss; the Back menu entry is
  the keyboard route (that is why it exists), and Esc dismisses the chip. The divergence to state if it stays so: the
  chip is not announced twice.
* **Import/export:** the bookmark rule and the comment option above; round-trip test for a paragraph with a given name.
* **Desktop clients in sync:** no native code for E1; verify both against the new server and the new View entry.

## 10. Questions, with my defaults

Answer "ok" or replace; anything unanswered is built as the default.

| #   | Question                                                                                                    | Default                                                                                                                                                                      | Answer                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Keep `DescribeObject` for drawn things and add `DescribeThing` for the rest, or one command for both?       | Both: Decorative only exists for drawn things, and one command with an optional field would make illegal states easy                                                         | Agreed                                                                                                                                |
| A2  | One dialog = one history step by issuing a `Batch` of the two existing commands, or a new compound command? | A `Batch`; no new command class                                                                                                                                              | Agreed                                                                                                                                |
| A3  | A heading's name is derived from its title, never stored?                                                   | Yes; so the "(2)" for duplicates is also derived and cannot go stale                                                                                                         | Agreed                                                                                                                                |
| A4  | The export option: a tick in the export dialog, off by default, shown only when a description exists?       | Yes                                                                                                                                                                          | Agreed                                                                                                                                |
| A5  | Which things become comments?                                                                               | Paragraphs, headings, lists and tables (for a table or list, the comment sits on its first paragraph). Sheet, slide and range descriptions are left to those apps' exporters | If any of these things have user-assigned descriptions, yes, those should become review-comments in the export if the user so chooses |
| A6  | The comment's author and date?                                                                              | The exporting person and the day of the export; not the description's author, because the string has none                                                                    | Agreed                                                                                                                                |
| A7  | Does import read a Word/OpenDocument comment back as a description?                                         | No: a comment is a conversation, not a note on a thing; import stays as D1311 says                                                                                           | Agreed                                                                                                                                |
| A8  | If Ctrl+Shift+B turns out to be taken in one of the browsers or web views, fall back to what?               | Ctrl+Alt+B (Cmd+Opt+B); I will check Chrome, Firefox, WebKitGTK and WebView2 before the manifest change and tell you                                                         | Agreed                                                                                                                                |

## 11. What I could not check

No browser was started and no shell client run for this note: the table in section 2 is from reading the code, not
from using it. The statement that View is drawn by the page and not by the shell comes from the contract's description
of `native-menu`; it is the one assumption I would run first.
