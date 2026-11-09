# Implementation notes: help system first iteration (help-system branch)

These are drafted for `claudiaoffice-log/backlog.md` and `claudiaoffice-log/decision-log.md`.
I could not write them into that repo directly this session (GitHub access dropped partway
through — `add_repo`/`list_repos` now report "no GitHub account linked"), so they're here to
paste in once that's reconnected, or for the next session to pick up.

## Backlog updates

**E13.1 (help topic format) — DECIDED.** Markdown + a small `key: value` frontmatter block
(`---` ... `---`), the shape already drafted in `claudia_typeset/help/configure-latex.md`.
Required fields `id`, `title`; optional comma-lists `apps`, `tags`, `explains`; optional
`language` (default `en`). That draft file did not need converting — it already matches what
got built. Parser: `claudia_server.help.parse_topic`.

**E13.2 (tooltip/help contract for library functions) — was already DONE**, contrary to a
stale status line. `claudia_computes.functions.base.Bound.get_tooltip()`/`.get_help()` already
existed in the repo before this iteration started. Nothing to build here; the catalog in E13.6
just calls it.

**E13.3 (help service) — PARTIALLY DONE.**
- Built: `claudia_server.help.HelpLibrary`/`default_library()` — load every installed package's
  `help/` folder, search by substring over title/tags/`explains`, fetch by id.
  Wire: `help_search`/`help_topic` on `core_methods` (read-only, every role, so the `ai` user
  gets it too), inherited automatically by composes/computes/creates.
- Not built: lookup-by-context (what's on screen right now), SQLite FTS5 (the proposal in
  E13.3's own notes), per-language caching. A plain substring search is enough for the handful
  of topics and ~95 functions that exist today; revisit if/when that stops being true.

**E13.5 (help in context) — PARTIALLY DONE.** Formula-bar-only, as scoped: while typing a
formula, the enclosing function's signature + example shows above the formula bar
(`web/app/lib/formula-help.ts`'s `currentFunctionAt`, naive string-literal handling, documented
as a v1 limitation). F1 / right-click "Help on this" is NOT built — it depends on the action
manifest (E5.1), which doesn't exist yet.

**E13.6 (searchable function catalog) — DONE.** Corrects a stale status line that said "69
functions... tooltips and help topics: not done" — that was already false before this
iteration: `Bound.get_tooltip/get_help` existed. What this iteration added is the *unification*:
`claudia_computes.functions.help.function_catalog()` combines the ~69 library `UserFunction`s
and the ~26 core forms (IF, XLOOKUP, INDEX, ...) into one sorted, searchable list of 95 entries
— `search_functions(query)` ranks exact name > prefix > substring-in-name > description match;
`get_function(name)` is a case-insensitive lookup. Server: `functions`/`function_help` on
`computes_methods`. Client: `HelpPanel.vue`'s search box (computes only — it feature-detects
`session.listFunctions` and hides the section for composes/creates, which have no catalog).
No content was authored for this: every tooltip/signature/description comes straight from
existing code (`description`/`Example` on `UserFunction`, or the docstring on a `form`).

**D125 (how-to/docs menu stubs) — activated in the web client, all three apps.**
`help.how-to`/`help.docs` in `Workspace.vue` (computes), `TextWorkspace.vue` (composes) and
`SlideWorkspace.vue`/`DocumentFrame.vue` (creates) now open the real `HelpPanel` instead of
doing nothing. **Not changed:** `clients/linux/src/claudia_shell_gtk/manifest.py`'s
`_help_menu()` still says "Not available yet" for both — left alone on purpose, since neither
computes nor creates has a real GTK window yet, so there's nothing for that menu item to open
there regardless of tooltip text.

**Explicitly out of scope for this iteration** (so they don't read as forgotten):
- Full Markdown/LaTeX rendering of a topic's body (D30/D88) — bodies render as plain
  preformatted text.
- SQLite FTS5 full-text search (E13.3's own later proposal).
- Translating the ~5 new UI strings into `po/de.po` (the .po files were already behind the
  .pot before this change; that's apparently not CI-enforced here).

## Decision log

Nothing new to decide this round — D99's draft format for help topics (previously the only
undecided piece, E13.1) is now the shipped format, as above. No new D-number needed unless the
team wants one to record "D99's draft is final" explicitly.

## Three help topics written (content, not just plumbing)

Drafted from the real, tested behaviour of the functions involved (per the earlier "I'll draft
help content from the code" decision), not from memory:
- `computes.writing-a-formula` — `=`, operators, basic structure.
- `computes.looking-up-a-value` — XLOOKUP, with its MATCH/INDEX relatives name-checked.
- `computes.summing-with-a-condition` — SUMIF/SUMIFS.

## Versioning

`claudia-server` bumped 0.17.0 → 0.18.0 (new public names: `HelpContentError`, `HelpLibrary`,
`Topic`, `default_library`, `parse_topic`; new wire methods `help_search`, `help_topic`,
`functions`, `function_help`). CHANGELOG entry added, API snapshot regenerated.
`claudia-computes` has no versioning ceremony yet (no `_version.py`/snapshot), so its new
`FunctionHelp`/`function_catalog`/`search_functions`/`get_function` needed none.
