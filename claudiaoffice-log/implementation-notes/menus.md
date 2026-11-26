# Implementation notes: the menus (E5.23, E5.24), branch `menus`

Design: `notes/menus-architecture.md` (D1643–D1649). Scenarios: `specs/menus/menus-that-fit.feature`. One section per
slice of the build (§5 of the design).

## Slice 1 · The definition moves to `clients/contract` (D1643), 2026-11-25

No change of behaviour.
- `clients/linux/src/claudia_shell_gtk/manifest.py` became `clients/contract/src/claudia_menus/manifest.py`, with git's
  rename kept, plus a `pyproject.toml` (project `claudia-menus`, Python ≥ 3.12, no dependencies).
- The GtkBuilder part (`menu_xml`, `menu_elements`, `menu_button_id`) stays GTK's: it is now
  `claudia_shell_gtk/menu_xml.py`.
- `UnknownApp`, which the manifest took from the Linux client's `identity.py`, is now the definition's own `KeyError`.
  Nothing caught the old one from `for_app`.

What followed the move:
- **The Linux client:** `app.py`, `bridge.py`, `window.py` and eight test files import `claudia_menus`. `pyproject.toml`
  puts `../contract/src` on pytest's and mypy's paths and counts `claudia_menus` as first-party.
- **Start and package:** `start-linux-client.sh` puts `clients/contract/src` on `PYTHONPATH`.
  `packaging/debian/build-deb.sh` copies `claudia_menus` beside `claudia_shell_gtk` into `/opt/claudia/shell`, which the
  launchers already put on `PYTHONPATH`. `deb.yml` also runs on changes to `clients/contract/**`.
- **The generators and scripts:** `scripts/generate_keys.py`, `scripts/menu_audit.py`, `scripts/extract_i18n.py` and
  `clients/neutralino/tools/generate_menu.py` (and its mypy path) read the definition from its new place.
- **Generated files:** `web/app/lib/keys.generated.ts` and `notes/keyboard-shortcuts.md` were regenerated; only the
  path in their header changed. `po/claudia.pot`, `po/de.po` and `po/xx.po` were regenerated; only the `#:` places of
  the menu strings changed. The Neutralino menus (`--check`) are unchanged.
- **Vulture** looks at `clients/contract/src`.
- **The contract's README** describes the package.
- **One new test,** `test_the_definition_needs_nothing_but_its_own_folder`: a fresh interpreter with only
  `clients/contract/src` on its path builds all three apps' menus and loads neither GTK nor the Linux client.

Left as they were: notes, decisions, changelogs and bug entries that name the old path as history.

**Assumptions:** none about behaviour. The package's tests stay in the Linux client (see the design §3.1).

**Run:**
- the Linux client's tests on the system Python 3.12: 656 passed, 64 skipped (below);
- the root tests of keys, strings, catalogues, the audit and the specs;
- the Neutralino tool tests and `check-menu`;
- ruff, ruff format, vulture, and mypy for the Linux client and the Neutralino tools;
- the Debian build (`packaging/debian/build-deb.sh`): the package holds `claudia_menus` beside the client, and the
  computes menus build from the unpacked package.

**Not run:** the 64 tests that need GTK 4 and libadwaita, among them the window, the web page and the end-to-end test
of the Linux client. PyGObject cannot be imported in this workspace (a broken `gi` of the distribution), so no window
was opened and `window.py`'s new imports were not executed. The same tests run in CI under Xvfb.

## Slice 2 · The definition is the workbook's (D1605, D1646), 2026-11-25

**Test first.** `tests/test_menu_workbook.py` compares the definition with `notes/claudia-menus.xlsx`, app by app. It
checks the menus and the context menus: their order, groups, words (D1609, D1618), keys on the web, Linux, Windows
and macOS, and the "Fits when" rule word for word. It failed on the first missing field, then on every difference.

**What the definition gained:**
- `Keys(default, macos)`, which replaces `accelerators`;
- `Action.fits`;
- `ContextMenu` and `Manifest.context_menus`;
- `Manifest.keys_only`, for the workbook's sheet "Keys without entry": Del (computes) and Ctrl+_ (composes).

**How a place is modelled.** An action may stand in several places, Edit ▸ Copy and an object's Copy, say. It keeps its
id, kind and key; the label and rule belong to the place (`_here`). `Manifest.actions` lists each action once, so the
GTK client registers it once and the bridge knows the ids of the context menus.

**The menus, rebuilt to the workbook.**
- Inserting went to Insert, and Search and Replace… to Tools.
- Name & Describe… went to Edit.
- Rotate, Wrap Text, Reference in Chat and Go to Target went to the context menus (D1602, D1607).
- The pivot table's own entries went to its context menu (D1612), and Present ▸ to Tools.
- File lost Save, Assign New Owner…, Accept Ownership… and Leave Document…; Delete From Server… went to the front page
  (D1608).
- Labels follow the workbook's words, keys follow D1617 (Edit Style is Ctrl+Shift+Alt+H, Insert ▸ Table…
  Ctrl+Shift+Alt+T), and macOS gets its own keys for Name & Describe… and History & Chat (D1616).

**Not built yet.** Entries whose feature does not exist yet are listed in the test and stay out of the definition.
Both lists only shrink:
- `NOT_BUILT_YET`: My Role…, Select Next/Previous Object, the shapes and the text box in computes, New Page, Citation…,
  Quiet Mode, Corkboard, Scrapbook, Bibliography…, Names… in composes and creates;
- `CONTEXT_NOT_BUILT_YET`: Edit Text in computes and composes.

**Follow-ups to keep the branch working until slice 4:**
- **The web** still builds its menus by hand until slice 4 (D1644). The cross-check of ids
  (`clients/linux/tests/test_manifest.py`) lists in `WEB_CATCHES_UP`, per app, the ids the web has and the workbook
  dropped, and the shapes it lacks.
- **Web keys:** the web's own key for File ▸ Save went, so Ctrl+S is Save Checkpoint…'s (it asks for a name now); the
  soft hyphen went with its entry (the owner removed it, "To decide"); Edit Style's hint follows the key table.
- **Tests that repeated what the workbook says** (places, words and keys in `test_manifest.py`) were removed; the
  structural ones stay.
- **Labels, keys and paths in other tests:** `web/e2e/demo.cjs`, `print.cjs`, `macos-shell.cjs` and `windows-shell.cjs`,
  `clients/neutralino/tests/shell-page.test.ts`, `clients/linux/tests/test_bridge.py`.
- **`specs/composes/tables.feature`:** the approved scenarios pressed Ctrl+Shift+F for Insert ▸ Table…. They press
  Ctrl+Shift+Alt+T now, as D1617 decided; the step code follows.
- **Translations:** every new label and tooltip is translated into German, with "Formatvorlage" for a style (D1618);
  the catalogues, the `.mo` and the web's JSON were regenerated.
- **Six notes** named the moved file `claudia_shell_gtk/manifest.py` as built, so `test_notes_claim_built_files.py`
  failed after slice 1 (not run then). They name the new path now.

**Assumptions**, confirmed by the owner afterwards (D1651):
- **Ask ai…** in Tools and in Help is one action, `tools.ask`, because the workbook gives both Ctrl+F1; Help's entry
  keeps its own rule. The web's `help.ask` goes in slice 4.
- **About** is "About", as the workbook's words say, not "About Claudia Composes".
- **The context menus' names** for Preferences ▸ Shortcuts: Object, Cell, Paragraph, List, Table, Heading, Sheet Tab or
  Slide Tab, Slide, Row Header, Column Header, Chart on a Sheet, Pivot Table, Reference.

**Run:**
- the workbook test;
- the Linux client's tests (590 passed, 64 skipped for GTK) and its mypy;
- the root tests without the browser (1408 passed);
- the Neutralino tests (552) and its tool tests;
- the web's unit tests (2143), type check and eslint;
- ruff and vulture;
- in Chromium:
  - the tables spec: its Insert ▸ Table… scenarios pass on the new key;
  - all 34 regression scripts, including the macOS and Windows shell scripts on their stand-in windows: 34 passed.
    `objects.cjs` no longer presses the quarter turns' keys, which left with their entries;
  - the `@core` specs: 142 passed, 23 expected failures (`@pending`), 80 skipped (steps not written yet).

**Not run:**
- the 64 tests that need GTK 4 (no window opens in this workspace);
- Firefox (not installed here);
- the Neutralino clients on a real Mac or Windows.

## After slice 2 · The owner's answers (D1651, D1652), 2026-11-25

- **Present on macOS.** Present ▸ From Slide and From Beginning have the letter keys of D344 on macOS
  (Ctrl+Shift+Option+H, Ctrl+Option+P): in the workbook's macOS column, then in the definition (`Keys.macos`, with
  `<Control>` for Ctrl). The workbook test failed on the edited workbook, then passed.
- **Must not break.** The test that covers a feature's key risk carries `@pytest.mark.must_not_break`. The marker is
  registered in the root and the Linux client's `pyproject.toml`, and the convention, with its TypeScript form, is in
  `coding-standards.md` §2. The menu workbook test is the first.

## Slice 3 · Judging what fits (`web/app/lib/fits/`), 2026-11-25

**Test first.** `web/tests/fits.test.ts` tests at the seam agreed for this slice: rules in, verdicts out, plain data.
- A rule is read from the workbook's words; an unknown phrase throws rather than hiding an entry; every rule of the
  definition reads, in all three apps.
- What fits is offered.
- What does not is hidden by default with its sentence, or greyed when the trial says so; an entry's own setting beats
  its reason's.
- The first failing reason in the order of D1642 is named; an entry's own sentence replaces its reason's (D1650).
- Every selected thing must fit.
- A caret in text is text but not "something selected".
- The server's tools, the client and the ai are asked.
- The trial's setting is read from the address.

**The modules** (pure TypeScript, no Vue):
- `facts.ts`: the facts and the reasons in their order.
- `conditions.ts`: the registry, one entry per phrase the definition uses, with its sentence.
- `rule.ts`: `parseRule`, cached.
- `policy.ts`: `policyFromAddress`: `?fits=role:grey&fits-entry=edit.undo:show`; every reason starts at hide.
- `judge.ts`: `judge` → `Verdict`.

**Changes outside `fits/`:**
- **The look-only sentence.** "You can only look at this document." is the rule "role: editor or owner"'s sentence
  (D1650), so it is written in `conditions.ts` and the session says it through `lookOnlyWords`.
  `tests/look-only.test.ts` (CODE-98) now names that file as its one writer.
- **German.** 19 new sentences are translated.

**Assumptions:**
- ~~An entry set to "show" and one set to "grey" behave alike~~: the owner dropped "show" (D1653); an entry's own
  setting is `grey` or `hide`.
- The sentences of the conditions are mine; the owner reviews them with the notices (slice 5).
- The test reads the rules from the macOS and Windows menus' JSON (`clients/neutralino/src/generated/`), the
  definition as plain data, until slice 4 generates the definition for the web.

**Run:** the web's unit tests (2157), type check and eslint; the root tests without the browser (1408); the catalogue
tests.

## Slice 4 · The web from the definition, 2026-11-25

**Test first.** `web/tests/assemble.test.ts` tests at the seam agreed for this slice (Q3): the definition, handlers and
facts in, menus out.
- Every title stays; what does not fit is left out, or greyed when its reason or the entry says so (D1606, D1653).
- A line between groups only where both kept something; a submenu with nothing left goes; a submenu of greyed entries
  is greyed.
- A menu with nothing left is one greyed line saying why, the first reason of D1642 first (D1603).
- An entry is judged again when it runs, by a click, a shell or a key, and says why instead of running (D1603, D1604).
- A switch is turned to what a shell asks, and only when it is not that already.
- Every action's state goes to a shell, also of an entry left out.
- A context menu runs what the place that opens it does, keeping the workspace's sentence (Copy's).
- `handlerGaps` names a handler missing and one left over.
- `web/tests/window-handlers.test.ts` tests what the shared entries do (About, Undo's words, Copy's and Share…'s
  sentences, the languages).

**The modules:**
- `scripts/generate_menus.py` (was `generate_keys.py`) writes `web/app/lib/menus.generated.ts`: the key table as
  before, and each app's menus, context menus and keys without entry.
- `web/app/lib/menus/assemble.ts`: `assembleMenus` → `{ bar, context(id, own), states, actions, run }`.
- `web/app/lib/menus/use-menus.ts`: the live version for a workspace, and `windowFacts`, what every window knows
  (role, the server's tools, a real ai, undo and redo, a place to go back to). A workspace without a handler for one of
  its actions says so on the console, where the browser tests look.
- `web/app/lib/menus/window-handlers.ts`: what File, Undo, Redo, the clipboard, Search and Replace…, View's shared
  entries, Ask ai…, Preferences and Help do; `FrameDialog` moved here.
- Removed: `document-menus.ts`, `format-menu.ts`, `rotate-menu.ts`, `object-menu.ts`, `menu-dispatch.ts`,
  `HeaderMenu.vue` and their tests; `table-menu.ts` keeps what can be done to a table and its keys in a box.

**The workspaces.** Each has a map of handlers and says what is selected:
- `DocumentFrame.vue` takes the assembled menus: it draws the bar, reports the states, runs what a shell asks, and
  listens for every action's key from the definition (`actionShortcuts`). The workspaces keep only the keys with rules
  of their own: the table's keys in a box, Ctrl+H, the steps between objects, Present's Mac keys.
- The context menus come from the definition: the object's (all three apps), the cell's and the pivot table's
  (computes, the pivot's first, D1612), the row and column headers' (computes), the chart's Move to Slide (computes),
  the table's (composes), the paragraph's, a heading's or a list's on a right press in a text (composes, D1603), a
  reference's (composes), the slide's away from any object (creates, D1619) and a sheet's or slide's tab (computes,
  creates).
- `MenuBar.vue` keeps an open menu as it opened (D1603); `ContextMenu.vue` shows an entry's key from the table.

**What changed for a person** (all from the workbook, the decisions or D1654):
- What does not fit is left out by default: a viewer's Insert says "Nothing to insert: you can only look at this
  document."; Edit shows Copy, Cut and Name & Describe… once something is selected; Undo once there is something.
- A key of an entry that does not fit says why: a viewer's Ctrl+Shift+Alt+S, "Only an owner can share this
  document."; Ctrl+Z with nothing to undo, "There is nothing to undo.".
- The entries stand where the workbook puts them (Insert has what adds, Present is in Tools, Style ▸ Apply… opens the
  style popover in place of the list of styles that was a flyout, D300's groups went with it).
- A right press on a paragraph opens its menu; Style… there opens the style popover (the workbook, 25.11.26). A heading
  and a list item have no Style… in their menus.
- The quarter turns are the Rotate By… popover's 90° (the workbook, decision #6).
- The duplicated keys (Edit Style, Name & Describe…, Wrap Text, the lists, the hyphen, the random numbers, Print) went
  from the workspaces; the definition's keys do the same, judged.

**What the workbook's rules did not say** (D1654; each greys the entry with its sentence, the owner may make any a
condition):
- every app: Replay… with no history yet or not connected; Who Wrote What in computes and creates (not built);
  an object's Cut and Copy for what is not a picture;
- computes: Rename Sheet… with no sheet shown; Style ▸ Apply… and Edit… with neither cells nor an object; List ▸ (cells
  hold no lists); Go to Target (no references on a sheet);
- composes: Go to Target with no reference at the caret, or one whose target is gone; the non-breaking hyphen,
  Table of Contents, Cross Reference…, Table…, Image… and Text Box with no caret, Table… in a table; a shape the server
  does not offer; Continue Previous List with no list before; Number Headings with no heading style; a table's
  entries where they have nothing to do or no box has the caret; Row Height… and Column Width… of a table (not built);
- creates: Rename Slide…, Agenda and Plan Time for Slide… with no slide shown; Go to Target; a shape the server does not
  offer; Continue Previous List; Number All Slide Titles; Present with no slides.

**The definition** (and the workbook, one row each):
- Edit Text is in the object's menu of computes and composes too (for a container, the object that holds words there);
  `CONTEXT_NOT_BUILT_YET` is empty.
- Style ▸ Apply… and Style ▸ Edit… fit "selection: something, or the cursor in a text": a style is for the paragraph
  the cursor is in too, which "something" left out (a caret is not something, D1601). The condition is new (D1654).
  Edit ▸ Name & Describe… keeps "something", as the approved spec says; a paragraph is named from its own menu. The words of a selected text box count as text, and as a list's item where
  they are one.

**Assumptions:**
- "document: has something to refer to" is taken as true in composes and creates: the picker asks the server what
  there is, and the page does not know before.
- "document: has random numbers" is true when a loaded cell holds or depends on random numbers or alternatives.
- The client fact is "desktop" when the shell is there (`DocumentFrame.inDesktopApp`).
- Copy's and Share…'s own sentences (D1650) are in the page's handlers: only the page says a notice.
- The menu line with nothing left goes on after the colon in small letters in English and keeps the capital otherwise
  (German starts a sentence after a colon with one).

**Bugs found** (logged, the owner's rule): UX-95 (size 2: Assign New Owner…, Accept Ownership…, Leave Document… and
Delete From Server… have no place until My Role… and the front page's Delete are built), UX-96 (size 3: entries the
web has and the workbook's context menus do not list), UX-97 (size 3: words just typed cannot be selected with
Shift+Home). UX-94 is fixed: the web's menus are the definition's.

**Tests changed with it:**
- The spec `menus-that-fit.feature` is bound (`tests/e2e/specs/test_menus_that_fit.py`): 15 scenarios lost
  `@pending:e5.24`; those of the copy guard, Paste As, the Shortcuts dialog, German and the open menu wait for their
  slices. `NOT_BOUND_YET` is empty.
- Steps and scripts follow the new places (Insert ▸ Image…, Text Box, Shape ▸, Chart…, New Slide; Format ▸ Style ▸;
  Palette…; Tools ▸ Present ▸; the paragraph's menu); a viewer's left-out entry counts as not chosen.
- `computes/slides.feature` says Insert ▸ Chart…; `composes/tables.feature`'s merge scenarios say the table's menu;
  `desktop/about.feature`'s unit test is `window-handlers.test.ts`.
- The drift guard of ids in `clients/linux/tests/test_manifest.py` went: the web cannot drift from the definition now.
- Six notes named removed files as built; they name them as gone.

## Slice 5 · Keys and Preferences ▸ Shortcuts, 2026-11-25

Delivered in the same commit as slice 4: the keys of every entry came with slice 4 already (judged when pressed,
D1604), and the two share the files they change.

**Test first** (the seams of slice 5):
- `web/tests/fits.test.ts`: a rule in plain words, who first, then when ("editors and owners, when something is
  selected"); every condition of the three apps has words.
- `web/tests/assemble.test.ts`: the listing of Preferences ▸ Shortcuts: every action once, by menu, with its place, its
  key and when it fits; tagged "not for you" (role), "not now" (document, selection, a workspace's own "not now") or
  "not here" (server, client, ai); what only a context menu has under that menu; the keys without an entry.
- `web/tests/shortcuts.test.ts`: macOS's own keys on a Mac (D1648): the chord, how it is written (Cmd, Ctrl, Shift,
  Option, as the workbook writes them), and that the Control key itself is matched only where a chord asks for it.
- `tests/test_menus_generated.py`: `<Control>` becomes the chord's `control`; an action with a key of its own on macOS
  has it in the table.
- `web/tests/present-keys.test.ts`: F5 and Shift+F5 are the entries' keys; the letter keys beside them have ids of
  their own, so that F5 is listened for too; on a Mac the letter keys are the definition's own.

**What changed:**
- `scripts/generate_menus.py` writes `mac` beside an action's chord where macOS has its own key: Name & Describe…,
  History & Chat, Present ▸ From Slide and From Beginning.
- `shortcuts.ts`: `onMac` moved here; `chordOf`, `hintOf` and `chordLabel` take macOS's keys and words on a Mac.
- `present-keys.ts` keeps only the letter keys beside F5 outside a Mac; `presentHint` and `presentChord` went, the
  hints are the definition's (`hintOf`).
- `fits/conditions.ts`: every condition has its plain words (`plain`); `fits/rule.ts`: `describeRule`.
- `menus/assemble.ts`: `listing()`.
- `ShortcutsDialog.vue`: the switch What Fits Now / Everything (What Fits Now first), a search field, the groups, and
  "Other keys" (F6, Ctrl+H, the steps between objects, the letter keys of Present) with what is no key at all.
- The spec's Shortcuts scenario is bound and lost `@pending:e5.24`.

**The "why" sentences and the plain words, for the owner's review** (Q2 of slice 3): listed in the reply that delivers
this slice; they are in `fits/conditions.ts` (one per condition), `menus/window-handlers.ts` (Copy, Share…) and the
workspaces' "not now" (slice 4's list above). German follows the Sie form.

**Assumptions:**
- The why line of an empty menu and the muted rows of the dialog use `--muted`, which greyed entries already use
  (about 5:1): there is no paler grey in the menus to keep apart from it (D1642).
- On a Mac, a chord without macOS's own key still answers to Cmd or Ctrl, as before; only macOS's own chords ask for
  the Control key itself.

## After slices 4 and 5 · UX-95, UX-96, UX-97 (D1655, D1656), 2026-11-26

**UX-97, words just typed and Shift+Home.** Failing first: the menus spec's step "I select a word" now presses
Shift+Home right after typing, as a person does (it waited for the word to be sent before), and
`web/tests/text-session.test.ts` selects across the words not sent yet. Two causes:
- The page's selection was only taken where it was collapsed in the words not sent yet (Home, D1350). Now
  `TextEditor.vue` works out each end of the page's selection as a place in the paragraph once those words are in it
  (`placeOnceSent`), and the session selects that once they are sent (`selectOnceSent`, which replaces
  `caretInUnsent`).
- The caret was drawn as a selection over those words: its anchor before them, its focus behind. It is collapsed
  behind them now, so the new check does not take a caret for a selection.

**UX-96, the reference's own entries** (D1655, undecided). Failing first: the workbook test, with two new rows of the
Context menus sheet (Show as ▸, Remove reference; Go to target moved to the second group); then
`web/tests/reference-handlers.test.ts` and the spec scenario "A reference has a context menu of its own".
- The definition's reference menu: Show As ▸ the five ways (`format.show-as-*`, checkable), Go to Target, Remove
  Reference (`edit.remove-reference`). No keys (D1614); Remove Reference lost the "Delete" hint the web drew beside
  it, because the definition has no key for it.
- `lib/menus/reference-handlers.ts`: one map for the reference the menu is on, or for none (the workspaces' own maps,
  which the Shortcuts list reads: "There is no reference here.").
- Wrap Text… stays one entry with its choices (D1654); the purpose chooser of a column is a popover of a control and
  gets no row.

**UX-95, My Role… and Delete in the list** (D1656). Failing first: `specs/document-file/my-role-and-delete.feature`
(four scenarios) and `web/tests/window-handlers.test.ts`, `web/tests/details.test.ts`.
- The definition: File ▸ Manage ▸ My Role… (`file.manage.my-role`, Ctrl+Shift+Alt+L, everybody); it left
  `NOT_BUILT_YET`.
- `MyRoleDialog.vue` says your role and leads to `AssignOwnerDialog`, `AcceptOwnershipDialog` and
  `LeaveDocumentDialog`, unchanged.
- The front page's list on this server has a Delete button per document; `DeleteFromListDialog.vue` asks for the name
  and password, and `deleteFromServer` in `lib/open.ts` connects, asks and closes, as `saveDetails` does (both now
  `askOnce`). The deleted document leaves Mine and its collections too.
- `DeleteDocumentDialog.vue` and `BaseSession.deleteDocument` went: nothing opened them since slice 4.

**Assumptions:**
- Accept Ownership… is offered to everybody but an owner, and Leave the Document… to everybody: the server says no
  where it does not apply, as before.
- Delete is offered in the list on this server only, not in Mine, which lists documents of other servers too.
