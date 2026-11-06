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
2. Dark-mode tokens (UX-05) are agreed (D129) but checked only against each other, not against real content yet —
   worth a second look once the app is actually running in dark mode.
3. White text on the base `--app` colour (e.g. Teal) as a filled background measures 3.9:1 — under 4.5:1 for normal
   text, clears 3:1 for UI components/large text. Not one of UX-04's five measured pairs; noticed while building
   the dark-mode screen. Worth a look independently of dark mode.
4. computes' Edit ▸ Row ▸ / Column ▸ submenu grouping (D130) — Claude's recommendation, given in answer to the
   owner's question; not yet confirmed.

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
