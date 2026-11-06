# E5.1 / E5.10 — menu redesign and accessibility baseline

Proposed, 2026-11-05; a patch implementing it exists the same day, delivered as a file (no push access — the owner
commits it on a feature branch, per the project's working model). **Per PROC-03, nothing here counts as built until
a commit carries it** — this section describes what the delivered patch contains, not a status to copy into
`backlog.md`; that still waits for the commit. Decisions confirmed by the owner, plus the ones Claude proposed and
flagged as unconfirmed, are in `decision-log.md` (D120–D130); this file is the working detail behind them.

## What the patch contains (delivered 2026-11-05, awaiting commit)

Everything below is implemented and its own tests pass; the breakdown is by how it was checked, not by confidence.

**Verified in the sandbox** (no GTK/WebKit there, so this is everything that doesn't need them):

- The web app (`web/app/`): all three workspaces (`TextWorkspace.vue`, `Workspace.vue`, `SlideWorkspace.vue`) rebuilt
  to the seven-menu schema (D120, D123–D130), with `MenuBar.vue`'s new submenu capability (Edit ▸ Paste as ▸ Plain
  text everywhere, Edit ▸ Row ▸ / Column ▸ in computes per D130). Shortcuts moved to one shared map (`lib/shortcuts.ts`,
  D122). `Modal.vue` replaced by a native `<dialog>` (D128's Esc-always-closes). `tokens.css` carries the UX-04/UX-05
  fix and dark tokens (D129). New `lib/shell-bridge.ts`: the web app now speaks the shell contract directly — D121's
  other half, see below — gated behind `shell.nativeMenu` so a plain browser tab is unaffected. New `lib/clipboard.ts`
  for Copy/Cut/Paste outside the editable-document case. `261/261` vitest, `vue-tsc --noEmit` clean.
- The Linux client's data layer (`clients/linux/src/claudia_shell_gtk/`): `manifest.py` rebuilt to the seven-menu
  schema with a new `Submenu` type, extended to `computes()` and `creates()` (new, D121 — identities only, see below
  for what's still missing); `identity.py` gained their `AppIdentity` entries; `window.ui` gained the three new
  `GtkMenuButton`s. `app.py`/`webpage.py`: the shim/`webroutes.json` mechanism is retired (D121) — the message
  handler now lives in the WebKit view's main world instead of an isolated one, matching the web app now posting to
  it directly instead of being scraped by an injected adapter; `data/shim.js` and `data/webroutes.json` are deleted.
  `193 passed, 36 skipped` (the skips are the `pytest.mark.gtk` tests — see below), `ruff`/`mypy`/`vulture` clean.
  `test_manifest.py`'s drift guard now compares ids directly against each app's `.vue` source (the stronger
  guarantee the first draft of this note called for), not against the retired route table.

**Not verified here — needs the owner's own GTK/WebKit environment** (`import gi` fails in this sandbox: no
PyGObject, so nothing below ever ran): the `pytest.mark.gtk` tests, 36 of them, including the rewritten
`test_webpage.py` (its stub page now speaks the contract itself instead of being shim-driven) and
`test_window_ui.py`'s two changed assertions. The reasoning for each GTK-side change is written down above and in
the diff's own comments, but only `xvfb-run -a pytest -m gtk` (or a real display) can actually confirm WebKit
accepts a main-world message handler the way the change assumes.

**Deliberately out of scope, left for a later pass:** computes and creates have no GTK window, application class,
icon, desktop entry or `__main__` entry point yet — only the identity and manifest data exist. `claudia-composes` is
still the only real Linux app; the new menus/manifests for the other two are exercised solely by their own tests
until that window-class work happens.

**Still open, not resolved by this patch:** D130 (computes' Row/Column submenu grouping) is Claude's own
recommendation, not yet confirmed by the owner, and could change the shape of `edit.row`/`edit.column` on both
sides if revisited. The four items already listed as open below stand unchanged.

Addresses the QA report's recommendation 3 (`qa-recommendations.md`): UX-01, UX-03, UX-04, UX-05, done together
because they share one test harness; and separately resolves UX-06/UX-09, which were blocking E5.1 outright.

## What this round found, before any screens were drawn

- The menu divergence QA measured is real: composes has 6 web menus (File/Edit/Format/View/Tools/Help), creates has
  5, computes has 4. `manifest.py` (the Linux GTK menu, composes only) deliberately collapses to D4's old four by
  folding Format/View into Tools — a second, different structure again.
- UX-01 is a web (`MenuBar.vue`) defect specifically. The GTK side already builds a real `GMenu` from
  `manifest.py` via GtkBuilder XML, which gets keyboard navigation for free from GTK itself.
- The GTK menu doesn't call into the page directly: `shim.js` (D117) finds items **by their visible label text** in
  the hidden web menu and clicks them, polling every 750 ms for enabled/checked state. Relabelling anything in the
  new schema means `webroutes.json` has to move with it, or the GTK client's actions silently stop firing — this is
  why D121 retires the shim instead of patching it again.
- Found in passing, unrelated to any of this: `webroutes.json`'s `file.open` entry is mapped to the label
  `"Close document"` — a copy/paste bug. Will be fixed alongside.
- Today's shortcuts are hints only (`hint: 'Ctrl+S'` etc. in the menu data), hardcoded and duplicated almost
  verbatim across `TextWorkspace.vue`, `DocumentFrame.vue` and `Workspace.vue`'s `onWindowKey`. Redo is bound to
  both `Ctrl+Y` and `Ctrl+Shift+Z` — Ctrl+Y is the Windows/Office convention, not GNOME HIG's.
- `StyleMenu.vue`'s `style.look` / `style.all` actions already match "Edit this style…" / "All styles…" almost
  exactly; this round only renames them into the Format menu.

## The schema (D120)

```
File            Edit                  Format           View                Tools         Config      Help
 New             Undo                  <style names>     Show who did what   <app only>    Shortcuts   Ask ai
 Open             Redo                  ---               History and chat                              How do I…?
 Save             ---                   Edit this style…  Dark / light mode                              Documentation
 Save new ckpt    Copy                  All styles…       ---                                            About claudia
 Download         Cut                                     <app specific>
 Share            Paste
 Close document    Paste as
                    > Plain text
                   ---
                   <app specific>
```

Per-app Edit app-specific section (D123 — insert-like items and "New…" actions moved here, not File/Tools):

- **composes:** nothing yet (today's Edit has only Undo/Redo).
- **computes:** New sheet…, —, Row ▸ (Insert above, Insert below, Delete), Column ▸ (Insert left, Insert right,
  Delete), —, Clear cells. Row/Column grouping is D130, proposed in answer to the owner's own question —
  not yet confirmed.
- **creates:** New slide…, —, Text box, —, the shape library, —, Delete.

Per-app Tools (unchanged from today, just relocated under the new empty top-level Tools; D120 reads Tools as fully
app-specific — open item below on whether that stays true):

- **composes:** Ask the assistant…, Review this text, Review this paragraph, —, Insert sample text.
- **computes:** Ask the assistant…, Ask for an example budget.
- **creates:** Ask the assistant… only.

File ships flat, no separators, matching the owner's sketch literally — flagged as open item 1 below since today's
File groups Save-actions / Share / Close with dividers.

## Screens

- `mockups/menu-bar-states.svg` — closed bar (all three apps), File open, Edit open for computes (shared block +
  app-specific block + the Paste-as submenu), the keyboard-focus/ARIA state UX-01 actually changes, and the one new
  capability `MenuBar.vue` needs: a real submenu. Three items now use it — Edit ▸ Paste as ▸ Plain text, and (D130,
  proposed) Edit ▸ Row ▸ and Edit ▸ Column ▸ in computes — all the same mechanism, so it's still one capability, not
  three. Format's style list stays flat (grouped by separator, not nested).
- `mockups/dialog-focus-trap.svg` — UX-03: an unlocked dialog (Share…) and a locked one (Save new checkpoint),
  both as native `<dialog>` + `showModal()` would give it: focus trapped inside, background inert, focus returned
  to the opening menu item on close. `Modal.vue`'s existing `locked` prop (Esc/outside-click disabled) has to carry
  over to the native version.
- `mockups/contrast-and-dark-mode.svg` — UX-04's fix applied to the exact pairs QA measured (before/after, with
  ratios), and the UX-05 dark-token proposal (not yet agreed — see `decision-log.md`).

## Open items (not decided — flagged on the screens themselves, repeated here)

Resolved since the first round, kept here only as a pointer to the deciding entry: File's separators (D124), the
empty-but-visible treatment for Format/"How do I…?"/"Documentation" (D125), Help ▸ "Ask ai" (D126), style grouping
(D127), Esc-always-closes (D128), and the UX-04/UX-05 token sheet (D129).

Still open:

1. Tools reads as 100% app-specific per the sketch — owner said "don't know yet, not too much for it at the moment",
   so left open rather than assumed either way.
2. ~~Dark-mode tokens (UX-05) are agreed (D129) but checked only against each other, not against real content
   yet — worth a second look once the app is actually running in dark mode.~~ That second look happened: see
   "Dark-mode contrast bugs, found running the patch" below — exactly the risk this item flagged, and it was real.
3. ~~White text on the base `--app` colour (e.g. Teal) as a filled background measures 3.9:1 — under 4.5:1 for normal
   text, clears 3:1 for UI components/large text.~~ That filled-background pairing was never touched — it stays
   3.9:1 either way. What the next round actually found and fixed is a different, related pairing: `--app`/`--app-dark`
   used as *text itself* (no fill), which measures worse still in dark mode. See "`--app-text`" below.
4. computes' Edit ▸ Row ▸ / Column ▸ submenu grouping (D130) — Claude's recommendation, given in answer to the
   owner's question; not yet confirmed.

## Dark-mode contrast bugs, found running the patch (2026-11-06, awaiting commit)

The owner applied the patch to a branch (`darkmode-menues-ux-quality`) and ran it in dark mode — the first time any
of this was checked against real content rather than token-against-token (item 2 above). Two reports, one root cause:

- **The wordmark disappeared.** `Wordmark.vue` set `color: var(--ink)`, a constant that never flips with the theme;
  in dark mode it sat on `--page-dark`/`--surface-dark`, both dark, for near-zero contrast. Fixed with a new token,
  `--wordmark` (`tokens.css`): resolves to `--ink` in light mode as before, and to a new `--rose-light: #ef87ac` in
  dark mode — Rose lightened rather than darkened, chosen for 7.7:1 against `--page-dark` and 6.6:1 against
  `--surface-dark`, both comfortably past AA even for normal text.
- **Selected/hovered items were unreadable in dark mode** (menu items, the History & chat toggle, the recovery-key
  box, style pickers, tab bars) — every one of them paired `background: var(--mist)` with no explicit text colour.
  `--mist` is deliberately light-fixed, never redefined for dark mode (same as `--app`/`--app-soft`); `--text` and
  `--muted`, what an unstyled element inherits, *do* flip to light values in dark mode — so anything relying on
  inherited text colour over a `--mist` background breaks specifically in dark mode. The owner's own report named
  the correct reference pattern already in the codebase: computes' active-cell row/column marks
  (`SheetGrid.vue`'s `.colhead.on`/`.rowhead.on`), which already pair `background: var(--mist)` with an explicit
  `color: var(--ink)`. Every other `background: var(--mist)` (or `color-mix(..., white)`, equally light-fixed) in
  `web/app/components/` got the same explicit `color: var(--ink)` added: `MenuBar.vue` (top-level and dropdown
  items), `TopBar.vue` (History & chat toggle), `RecoveryKeyDialog.vue`, `FooterBar.vue` and `SlideWorkspace.vue`
  (tab bars), `StyleFontPicker.vue`, `StyleMenu.vue`, `StyleSizeField.vue`, `StyleBar.vue` (two rules), and
  `StyleCssEditor.vue`'s textarea. Left alone, deliberately: rules that mix `--mist` with `transparent` rather than
  a light-fixed colour (e.g. `StylesDialog.vue`'s list hover) already composite against the theme-aware surface
  behind them and darken correctly on their own.

Also addressed in the same round, reported alongside the above:

- **GTK dialog buttons read as oversized next to the web app's own.** The cause was `Adw.AboutDialog`'s own
  Website/Troubleshooting/Legal row, which libadwaita renders as full-width, generously-padded pill buttons by
  default — the only real dialog in the Linux shell, so this one widget fully explained the report. Replaced with
  a hand-built `Adw.Dialog` (`window.py`'s `_show_about`) styled by a new `.about-link` rule
  (`data/style.css`, loaded once at startup in `app.py`) sized to match `web/app/assets/app.css`'s `.btn` (6px/16px
  padding, fully rounded) instead of inheriting libadwaita's own `.pill` sizing, which is exactly the "big and
  round" being reported. D28's "Notes" column is updated to match (`decision-log.md`).
- **The web and Linux About dialogs had drifted apart** (D28 asked for one shared dialog; by this point they
  showed different content). Both now show the app's own logo, its title, and the same three links in the same
  order — Website, Report an Issue, Legal — read from one place on each side (`manifest.py`'s new `about_links()`
  on the GTK side, `AboutDialog.vue`'s `LINKS` on the web side; the two shells have no manifest in common to read
  this from, so a change to one needs the same change made to the other by hand). `about_links()` lives in
  `manifest.py`, not `window.py`, specifically so it can be tested without GTK: `test_manifest.py` checks the three
  links, their order and their targets; `test_window.py` checks the dialog actually shows them (GTK-marked, so
  unverified in this sandbox, same caveat as everywhere else in this file).
- **A `start-client.sh` launcher**, at the repository root, for starting the Linux client directly — distinct from
  `start.sh`, which starts a server and opens a browser. It does what `README.md`'s "Running it from a checkout"
  otherwise has a person type by hand (`uv sync` for the server's `.venv`, `npm run build` for the web frontend if
  it isn't built yet), then hands off to `/usr/bin/python3` for the actual GTK process — never to `uv run`, per the
  "Two interpreters" split that section describes (a uv-managed interpreter cannot import the system's `gi`/GTK
  bindings).

**Verified in the sandbox:** all of the above except the two `test_window.py` GTK-marked tests — the full
`194 passed, 37 skipped` for the Linux client (`ruff`/`mypy`/`vulture` clean), `261/261` vitest, `vue-tsc --noEmit`
clean. `start-client.sh` was checked for shell syntax only (`sh -n`); nothing here could start a real GTK window to
confirm the dialog or the launcher by eye.

## A further, larger round of dark-mode bugs (2026-11-06, awaiting commit)

The owner tested the patch above and reported that it was "better, but the devil is in the details about dark
mode" — a new list of problems, all in dark mode, this time in dialogs and typed text rather than the chrome fixed
above. Per the owner's own instruction ("before we go any further with code, please make design suggestions"), each
was measured and a design was agreed (two points via `AskUserQuestion`, D131 and D132) before anything was changed.

- **Dialog and input boundaries were invisible in dark mode (Prio 1a).** Two separate causes, not one:
  - `Modal.vue`'s `.modal` rule had `border: 0`, relying only on `--shadow` — a near-black shadow at low opacity,
    calibrated for a light backdrop, that all but disappears against a dark one. Given an explicit
    `border: 1px solid var(--line-field)` in both themes, not only dark mode.
  - A systemic mix-up between `--line` (14% ink — tokens.css's own comment: "decorative only, not a contrast pair")
    and `--line-field` (48% ink, the token actually rated for a 3:1 UI-component boundary, introduced by D129/UX-04):
    seventeen component-level sites were using `--line` for a genuine control, panel or dialog edge —
    `StyleBar.vue`, `MenuBar.vue`'s dropdown panel, `Popover.vue`, `StyleFontPicker.vue` (three sites),
    `StyleSpec.vue` (two), `FormulaBar.vue`, `StyleSizeField.vue`, `StyleColorPicker.vue` (four),
    `StyleCssEditor.vue`, `OpenDialog.vue`, `StylesDialog.vue` — plus, found only by tracing why `ShareDialog.vue`
    itself needed no edit, **two foundational sites in `app.css`** that every plain `.btn` and every `.field input`/
    `.field select` in the app inherits from: this is why the owner's report named Share's own inputs specifically.
    All nineteen now use `--line-field`. Left alone, deliberately, where a border really is a divider between
    adjacent elements rather than an edge of its own: `StyleSpec.vue`'s `.marks button + button` and
    `FormulaBar.vue`'s hover-only `.text:hover`.
  - The Share dialog's role dropdown stayed white in dark mode specifically because **no `color-scheme` CSS
    property existed anywhere in the app** — native form-control chrome (a `<select>`'s own popup, checkboxes,
    scrollbars) is drawn by the browser engine itself and ignores `data-theme` entirely unless told which variant
    to draw. Added `color-scheme: light` / `color-scheme: dark` to `tokens.css`, tied to the same `data-theme`
    attribute as everything else, so it always follows the resolved theme rather than deferring to the OS.
- **Typed text in composes and creates was unreadable in dark mode — black letters on a black page/slide
  (Prio 1b, D132).** The named-style pipeline (`style-css.ts`'s `paragraphCss`, consumed by `TextEditor.vue`; the
  equivalent path through `slide-style.ts`'s `scaleCss`, consumed by `SlideCanvas.vue`) renders a style's stored
  `color` as an inline style that always wins over the container's own theme-aware default — exactly the owner's own
  framing, "in the document they would count as black obviously": the document genuinely is black-on-white, this
  is a display problem, not a data problem. Added `isDefaultInk()`/`withDisplayInk()` (`style-css.ts`): when a
  style's resolved `color` is the document's own default ink (confirmed against the project's own existing test
  fixture, which already used `#1F1A33` for the "body" style), the page substitutes `var(--text)` **for display
  only** — the stored value is never touched, and a colour someone actually chose is left exactly as authored in
  both themes. Wired into `paragraphCss()` (composes) and `SlideCanvas.vue`'s `cssOf()` (creates); `SlideCanvas.vue`
  builds both its text and its outline rendering from that one function, so the fix reaches text without touching
  shape fills/strokes.
- **"Rename" (and other accent-coloured text) was barely visible in dark mode.** `--app-dark`/`--app` used as
  literal *text* colour (a link, "Rename", an active mark) — as opposed to a filled background with white text,
  the pairing the design system's own comment already vouches for — measures under the WCAG floor against
  `--surface-dark` for every app colour: Rose 2.86:1 (fails even the 3:1 UI floor), Teal 3.13:1, Apricot 3.71:1
  (both under 4.5:1 normal-text), base Teal 4.04:1, base Rose 3.78:1 (also under 4.5:1); only base Apricot clears it
  at 7.46:1. A new semantic token, `--app-text` (`tokens.css`): equals `--app-dark` in light mode (unchanged there),
  and in dark mode resolves to a freshly lightened per-app variant — `--rose-light` (already existed, from the
  wordmark fix), plus two new ones, `--teal-light: #3dbfaa` (6.9:1) and `--apricot-light: #e8954a` (6.6:1), both
  measured against `--surface-dark`. Swapped in wherever `--app-dark`/`--app` was literal text:
  `StyleBar.vue`, `MenuBar.vue`, `StylesDialog.vue`'s "Rename" link (the one the owner named directly),
  `StyleFontPicker.vue`, `ShortcutsDialog.vue`, `StyleColorPicker.vue`, `StyleCssEditor.vue`, `StyleMenu.vue`,
  `OpenDialog.vue`, `FormulaBar.vue`. **Deliberately left alone** in two places found during the same audit, and in
  one more found by analogy before it could repeat a third time: `StyleSpec.vue`'s `.marks button[aria-pressed='true']`
  and `SlideWorkspace.vue`'s `.tabs button.on` both pair `--app-dark` text with a background that mixes with literal
  `white` (`--app-soft`, or an inline `color-mix(..., white)`) and so stays light regardless of theme — `--app-dark`
  as their text is already theme-stable for the same reason, and swapping it would have put light-mode-only-safe
  text on a background that never darkens. `FooterBar.vue`'s identical pattern was checked and left untouched for
  the same reason, without repeating the mistake on it.
- **The About dialog's website link was wrong.** `manifest.py`, `AboutDialog.vue` and their tests now point at
  `https://www.claudia-office.de` (the `www.` was missing).
- **The About dialog stayed whatever theme GTK's own `Adw.StyleManager` happened to be in, regardless of the
  document's own Dark Mode toggle (D131).** `window.py`'s `set_action_states` already receives `view.dark`'s
  resolved `checked` state from the page on every change (a click, or the system preference changing while "system"
  is selected) — no new shell-contract message was needed, only a shell-side consumer: `_sync_native_theme` now
  calls `Adw.StyleManager.get_default().set_color_scheme(FORCE_DARK | FORCE_LIGHT)` to match. `FORCE_*`, not
  `PREFER_*`, because the whole point of the in-app toggle is that it overrides the desktop setting, so the shell's
  own chrome has to be just as overridable.

**Verified in the sandbox:** `264/264` vitest (up from 261), `vue-tsc --noEmit` clean, `194 passed, 38 skipped` for
the Linux client (one more GTK-marked test than before, for the native dark-mode sync — still unverified here, same
caveat as every GTK-marked test in this file), `ruff`/`mypy`/`vulture` clean. Nothing here could open a real browser
or GTK window to confirm a dialog's border or the About dialog's theme by eye.

## Three more bugs, found testing that patch (2026-11-06, awaiting commit)

The owner applied the patch above and reported three further problems — two readable as the inversion/boundary fixes
not reaching every place they needed to, one a question about why a dialog looked unfixed on Linux specifically.

- **A style's own name was invisible in the style pickers, in dark mode** — "All styles…" (`StylesDialog.vue`) and
  "Edit this style…" (`StyleMenu.vue`) both preview a style by rendering its name in its own look
  (`previewCss(s.computed)`), and `previewCss` (`style-css.ts`) never got the `withDisplayInk` swap that
  `paragraphCss` got in the previous round — same root cause (D132), just a second call site the fix had not yet
  reached. `previewCss` now runs its result through `withDisplayInk` too, so a style whose colour is still the
  document's own default ink previews in the page's text colour, exactly as it already does in the document body.
- **computes' Edit ▸ Row / Edit ▸ Column flyouts were gone**, reported as a functional bug, not a dark-mode one —
  and on inspection, not new: the submenu mechanism `MenuBar.vue` built for "Paste as ▸ Plain text" (and reused for
  Row/Column, D130) only ever opened a flyout from the keyboard (Arrow-Right after Arrow-Down onto the parent item).
  Hovering a flyout parent with the mouse set `activeTop` to it but explicitly nulled `activeSub`, and clicking it
  was a deliberate no-op (`choose()` returned early whenever an item carried `items`) — so a mouse-only person could
  select "Row" and watch nothing happen, indistinguishable from the item not being there. This was true for every
  flyout, including "Paste as", from whichever round first built the mechanism; Row/Column just made it easy to
  notice, there being nothing to fall back on if the flyout itself never shows. Fixed: hovering a flyout parent now
  opens its flyout at once (a new `enterItem()`, replacing the old inline mouseenter handler that zeroed `activeSub`),
  and clicking one now toggles it open/closed instead of doing nothing, so a click, not only a hover, discovers it.
  **No test added**: the project's test suite is pure logic tests on composables (`node` environment, no DOM, no
  `@vue/test-utils` dependency) — nothing here mounts a Vue component and simulates a pointer event anywhere in the
  codebase, so a one-off test harness for this one component would be a new testing pattern, not a consistent one.
  Flagged instead as something to check by hand (or to build real component-interaction testing for, as its own
  piece of work) before relying on this being covered automatically again.
- **The Linux client's Shortcuts dialog still looked like an old build** (a large, pill-shaped Close button) even
  though the identical dialog in the browser looked right. Not a second dialog and not a dark-mode bug: Shortcuts
  (like "All styles…", Share, and everything except the About dialog, D28) is a `Kind.PAGE` action — plain web
  content, the very same `ShortcutsDialog.vue` and `app.css` in both places. The difference is staleness, not code:
  the Linux client never opens a dev server, it only ever loads the **bundled** frontend from `web/.output` (D43),
  and `start-client.sh`'s own build step (added last round) only ran "if missing" — so once built, it kept serving
  whatever `.btn` looked like on the very first run, unaffected by every CSS fix since, including this round's and
  last round's `--line-field` and `--app-text` work. `start-client.sh` now rebuilds on every run (matching the
  README's own manual steps exactly), skippable with `CLAUDIA_SKIP_WEB_BUILD=1` for a person who knows their build
  is current and wants a faster start. A rebuild (or deleting `web/.output`) is also the immediate fix for the
  owner's own checkout right now.

**Verified in the sandbox:** `265/265` vitest (up from 264), `vue-tsc --noEmit` clean; `start-client.sh` checked for
shell syntax only (`sh -n`), same limitation as before — nothing here can run a real build or open a GTK window to
confirm the Close button or the flyouts by eye. The Linux client's own test suite is untouched this round (no `.py`
files changed), so it was not re-run.

## Implementation shape, once the screens are agreed

- `MenuBar.vue` gets the ARIA menu-button/menubar pattern (focus-on-open, arrow/Home/End/typeahead, Esc + focus
  restore, Alt/F10 to reach the bar) plus the one new submenu capability — same roving-focus logic, one extra
  nesting depth, not a second component.
- `manifest.py` is rebuilt to the seven-menu schema and extended with `computes()` and `creates()` manifests
  alongside the existing `composes()`; `webroutes.json` and `shim.js` are deleted once the web app speaks the shell
  contract (the version-negotiated JSON bridge from D114) directly instead of being driven through the DOM.
  The `test_manifest.py` drift-guard test's job moves from "web label matches shim's route table" to "web menu
  data matches the shared manifest", which is a stronger guarantee than today's, not a weaker one.
- Shortcuts move into one shared composable / structured map (`useShortcuts` or similar) consumed by all three
  workspace components, replacing the duplicated `onWindowKey` handlers, with accelerators also driving `manifest.py`
  for GTK (today's `accelerators: tuple[str, ...]` on `Action` already exists for exactly this).
- `Modal.vue` is replaced by a native `<dialog>` wrapper; the `locked` prop's semantics (no Esc, no outside click)
  carry over.
- `tokens.css`: `--muted` → 65% ink, `--line` split into `--line` (dividers) and new `--line-field` (~50% ink, input
  borders); dark tokens added behind `prefers-color-scheme`/`data-theme`, once agreed.
