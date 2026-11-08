# App Language, the first real catalog (E5.7, D31, D148, D160)

Save as `claudiaoffice-log/implementation-notes/app-language-switch.md`.

The owner's second i18n round: not more plumbing (D148 already built that, in the slice this round builds on
directly) but the first real, visible use of it — a working `Config ▸ App Language` switch, in both shells, with
a real German translation behind it. See `claudiaoffice-log/decision-log.md`'s new D160 row for the decision
itself; this note is the longer version.

## A correction to how this gets delivered

The D141-era i18n-groundwork patch (this round's predecessor) was delivered as code plus a separate
`decision-log-and-backlog-updates.md` of hand-apply instructions, because at the time `claudiaoffice-log/` looked
like a standalone repo. It no longer is: the project's own instructions say it was folded into this repo on
Nov 3rd, and the checked-out branch confirms it — `claudiaoffice-log/decision-log.md` and `backlog.md` are
ordinary tracked files here, already carrying everything through D159 (including that groundwork round, long
since renumbered to **D148** by a later QA pass — see decision-log.md's own "Decision-number renumbering, second
pass" entry). So this round's decision-log and backlog edits are **inside `app-language-switch.patch` itself**,
not a separate document to apply by hand. Worth flagging because the old pattern was followed once already and
would otherwise look like the right thing to repeat.

One consequence worth knowing about: this also means **D148 was the real, final number** for the first i18n
round, not the D141 the earlier deliverable proposed — the renumbering pass moved it after that patch was
written. This round's own new work is logged at **D160**, confirmed as the actual next-free number by reading
the log directly rather than guessing from where an earlier session's notes left off.

## What was built

**Scope, confirmed with the owner via `AskUserQuestion` before building:**
- *Translation scope* — "menu chrome + a few more": every manifest menu/action label and tooltip, in all three
  apps, on both shells, plus one hand-picked pair outside the manifest: `SidePanel.vue`'s "History"/"Chat" panel
  headers.
- *GTK chrome refresh* — "apply on next restart": the GTK shell's native menu bar and title text only re-translate
  on the next launch (the persisted choice is read at start-up); the web page's own UI — in the browser and inside
  the GTK shell alike — switches live, no restart.

**The language list.** `manifest.LANGUAGES` (`clients/linux/...manifest.py`) and `web/app/lib/i18n.ts`'s
`LANGUAGES` both list `[('en', 'English'), ('de', 'Deutsch')]` — kept in sync by hand, the same way the two
shells' `about_links()`-equivalents already are. Each entry's own name is its *autonym*, never run through
translation — the universal convention every OS and browser language picker already follows.

**The Config ▸ App Language menu.** One checkable action per `LANGUAGES` entry (`config.language.en`,
`config.language.de`), in their own submenu, on both shells. Mutual exclusion is enforced *nowhere in the data* —
each item's `checked` just derives independently from the one `locale` ref/equivalent, the identical pattern
`view.dark` already uses; `window.py`'s `set_action_states` needed no special case to keep native tick marks in
step, and no shell-contract message changed.

**Extraction gained a third technique.** `scripts/extract_i18n.py` already walked Python `_("...")` calls and
web `t("...")` calls; `manifest.py`'s menu/action data is built as Python *objects*, not written as `_("...")`
calls, so a new `extract_manifest()` walks the already-built `Manifest`/`Menu`/`Submenu`/`Action` objects directly
— simpler and more robust than trying to regex/AST the dataclass constructor calls in source, and it reuses the
exact objects the real application builds. `LANGUAGES`' own autonyms are excluded by the same `id` rule
(`action.id.startswith("config.language.")`) `manifest.py`'s own `_item_element` already uses to skip them at
render time.

**A real `.mo`, with no system dependency.** GNU `msgfmt` is not on every contributor's machine and is not
installable in this project's own sandboxes (`apt-get install gettext` has no candidate here), so
`scripts/compile_mo.py` reimplements gettext's binary `.mo` format in pure Python — the one narrow slice of it
Claudia actually needs. It reuses `po_to_json.py`'s already-tested `.po` parser rather than writing a third one.
Verified directly against CPython's own `gettext.GNUTranslations`, the one and only reader
`i18n.install_translation` ever points at, not against GNU `msgfmt`'s output — the header entry always declares
`Content-Type: text/plain; charset=UTF-8`, or German's umlauts crash the reader (it falls back to ASCII without
that declaration). CI gained a matching "mo compilation" gate in `check_debt.py`, mirroring "i18n extraction",
now that `po/de.po` has real content worth protecting from drifting out of sync with the compiled catalog.

**`po/de.po`: 146 real German translations.** Covers every manifest label/tooltip and the two `SidePanel.vue`
strings. Compiled to `clients/linux/src/claudia_shell_gtk/locale/de/LC_MESSAGES/claudia.mo` and derived to
`web/public/i18n/de.json` (`po_to_json.py`, unchanged). `po/xx.po`'s pseudolocale was regenerated to match the
larger `claudia.pot` so it stays a useful "nothing is hard-coded" check.

**The GTK shell resolves its own locale once, at start-up.** A new `_resolve_locale()` in `__main__.py`: the
persisted choice (`settings.py`'s `shell.json`, one key — `load_shell_locale`) wins over the detected system
locale. `ComposesApp` takes an explicit `locale` now instead of always calling `detect_system_locale()` itself,
so the resolved value reaches both the native chrome (`install_translation(locale)`, before any window is built)
and the page (forwarded as `ComposesApp(locale=locale)`, reaching the `welcome` message). `window.py`'s existing
`set_action_states` — already written to apply whatever the page reports — now also calls `save_shell_locale`
whenever a `config.language.<tag>` action is reported `checked`, so picking a language in the page persists it
for next launch with no new shell-contract message.

**The web side's `useI18n()`.** A `locale` ref, a `catalog` ref loaded via the existing `loadCatalog`, and `t`
(exposed under that name only on the returned object — the internal function is named `translate`, because
`scripts/extract_i18n.py`'s extraction regex matches *any* bare `t(...)`, including a `function t(...)`
*declaration*, not just a call; this was caught only by running the real extractor end-to-end, not by unit tests
alone). `choose(tag)` persists the pick, switches `locale`, reloads its catalog, and calls `triggerRef(locale)`
unconditionally — needed because re-picking the *already-active* language is a `ref` assignment Vue sees as
unchanged, which would otherwise send no correcting `action_state` report and leave a native shell's own checkbox
stuck unchecked (a GTK checkable action optimistically unchecks itself on any activation, checked ones included,
before the page's next report corrects it).

All three workspace components (`TextWorkspace.vue`, `Workspace.vue`, `SlideWorkspace.vue`) wrap every static
menu label in `t(...)`, including the `Undo {label}`/`Redo {label}` dynamic-suffix labels via the existing
`createTranslator` placeholder mechanism — and, in every case, add the Config ▸ App Language submenu. Data-driven
labels (style names, the shape library) are deliberately left untranslated, per `manifest.py`'s own stated
principle that nothing data-driven gets a static catalog entry.

## Noticed, not fixed

**GTK Title Case vs. web sentence case.** `manifest.py` consistently uses GNOME HIG Title Case ("Paste As", "Dark
Mode", "Close Document") while the web app consistently uses sentence case ("Paste as", "Dark mode", "Close
document") for the *same* ~28 menu items — systematic, not occasional, and pre-existing (unrelated to D130/D131's
native-chrome work). Left alone deliberately: the scope agreed for this round was switching the client's
language, not normalizing its English, and silently rewriting ~28 visible labels would bundle an unrelated
cosmetic change into an i18n-infrastructure patch nobody asked for. Both forms are translated to the *same* German
phrase in `po/de.po`, so German speakers never see the inconsistency — only a future pass that wants to unify the
English source text would need to revisit this.

## A documentation build gotcha worth remembering

Sphinx's Napoleon extension parses a **bare attribute docstring's first physical line** specially: if that line
contains a colon, everything before the colon is treated as a type annotation (split on commas, each fragment
turned into a `py:class` cross-reference) — regardless of whether the attribute's type hint already says
something else, and whether or not the colon was meant that way. `manifest.py`'s new `LANGUAGES` attribute
docstring tripped this (`"""The language picker's own short, explicit list (Config ▸ App Language): exactly..."""`
turned "Config ▸ App Language" into a broken class reference). Confirmed by isolating it in a throwaway Sphinx
project outside this repo: the trigger is specifically a colon on the *first physical line* of the docstring, not
anywhere else in it, not even for a one-paragraph docstring that happens to wrap the colon onto a later physical
line. Fixed by rewording that line to use a dash instead of a colon. No code is affected, no `nitpick_ignore_regex`
entry was added, and this isn't `nitpicky`-specific — it would silently mis-render the HTML even without
`nitpicky = True` catching it as a warning. Worth knowing before writing the *next* bare attribute docstring
anywhere in `claudia-core`, the app packages, or the Linux client: keep the first physical line colon-free.

## Verification

Full `uv run python scripts/check_debt.py --ci` (ruff, ruff format, mypy, vulture, i18n extraction, mo compilation,
the whole pytest suite, the Sphinx build, perf guards, web tests, web types, the Linux client's own mypy and
tests) passes clean except one check this sandbox cannot run meaningfully (a pre-existing `--ci`-mode self-test
that assumes `web/node_modules` is absent; it fails identically on the unmodified base commit, confirmed with
`git stash`). The patch was also applied, standalone, to a fresh clone at the exact base commit and re-verified
there (`git apply --check --binary`, then the decision-log/hygiene/extraction/compile-mo tests and a real
`gettext.GNUTranslations` round-trip through the compiled `.mo`) before delivery.
