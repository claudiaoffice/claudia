# I18n groundwork (E5.7, D31, D148)

The groundwork for translating Claudia's interface, decided and built in one slice before any real string moves
into a catalog: prove the single-source-of-truth pipeline end to end with an (almost) empty catalog, so that
moving strings later is mechanical rather than a design question.

## Decisions this slice rests on

- **gettext `.po` is the single source, not ICU/vue-i18n** (D31, confirmed by D148): `.po` is more common across
  non-web codebases generally and is what the GTK client needs natively; the web client's JSON catalog is *derived*
  from it (`scripts/po_to_json.py`), never maintained by hand, so the two can never drift apart.
- **Locale is always a client-side setting** (D31, D35): there is no server-side account profile to keep it on —
  accounts are scoped per-document. Detected from the OS/browser by default; a `Config` menu override is decided
  but not built (no screen design exists yet, per the project's own "screens before code" rule).
- **Help-text translation is discussed, not decided**: short strings (tooltips, `getHelptext()`) would go through
  the same `.po`; longer "how do I" topics would likely need their own per-language files with staleness tracking
  against the English source, since a stale translation of a short tooltip and a stale translation of a paragraph
  are different problems. Left for E13.8/D76, both still open.

## What was built

**`claudia-core`** (`errors.py`, v0.8.0): every `KernelError` subclass gained a stable `code: ClassVar[str]`
(`unknown_command`, `stale_edit`, `region_held`, `undo_refused`, `undo_conflict`, ...), independent of the baked
English `str(exc)` message. The kernel still imports no gettext and knows no catalog exists — `test_purity.py`
still passes unchanged. `ClassVar` attributes are invisible to `scripts/api_surface.py` (it inspects callable
signatures and `property` instances only), so this did not need a signature-level entry in the API snapshot, only
the version bump + CHANGELOG entry the policy still asks for.

**`claudia-server`** (`protocol.py`, `hub.py`, `app.py`, v0.15.0): `hello` accepts an optional `locale`; `welcome`
always echoes one back. `protocol.normalize_locale` falls back to `DEFAULT_LOCALE` ("en") for anything missing, not
a string, too long, or not BCP-47-ish shaped — never refuses the connection over it. `Context.locale` carries it to
every method (nothing reads it yet). `PROTOCOL_VERSION` is now 2. `RequestError.detail` carries the finer-grained
`claudia_core` error `code` behind the wire-level `code` (`"locked"`, `"stale"`, ...), wired through
`MethodTable.dispatch`'s `except` clauses for `StaleEdit`, `RegionHeld`/`UndoRefused`, `UndoConflict` and any other
`KernelError` — present in `to_dict()`/the wire response only when given, so it costs existing clients nothing.
`Connection`/`HostedDocument.connect` take an additional optional `locale` keyword.

**Linux client** (`clients/linux/src/claudia_shell_gtk/i18n.py`, new): `detect_system_locale`, `negotiate`,
`install_translation` (gettext, domain `claudia`, `fallback=True`, binds `_` process-wide). `app.py` detects the
system locale at startup and passes it down through `window.py`/`bridge.py` to the shell-contract's `hello`, so the
same locale the GTK shell detected is what the embedded web page's connection sends on. The shell contract
(`clients/contract/shell-contract.v1.schema.json`) gained an optional `locale` on `welcome` — additive, no new
schema version. No label in the GTK shell or the web app is wrapped in `_()`/`t()` yet.

**Web client** (`web/app/lib/locale.ts`, `i18n.ts`, new): `currentLocale()` — the person's own override if they
set one (`localStorage`, not yet exposed as a UI control), else the OS/browser locale, else `"en"` — safe to call
outside a browser (guards `navigator`/`localStorage` behind `typeof` checks, since `vitest`'s `environment: 'node'`
has neither as a bare global, and Node 21+'s own minimal built-in `navigator` is not a substitute for a real
browser's). `loadCatalog(locale, base, fetchImpl)` fetches `${base}/${locale}.json` (default base `/i18n`, served
from `web/public/i18n/`, Nuxt's static-asset directory), returning `{}` — not an error — for `'en'`, a missing
file, or anything that fails to parse as a flat string-to-string object. `createTranslator(catalog)` returns a
`t(msgid, vars?)` that falls back to `msgid` itself for anything the catalog does not have, with `{placeholder}`
interpolation. `web/app/lib/people.ts`'s `clock`/`ago` (the two places that formatted a date for display) now
default their `locale` parameter to `currentLocale()` instead of silently following whatever the *browser* happens
to be set to, which could disagree with what the person picked inside Claudia. `OpenDialog.vue` sends
`currentLocale()` in `hello`'s `locale`. No string is routed through `t()` yet.

**Extraction and CI** (`scripts/extract_i18n.py`, new): collects `_("...")` calls (Python, via `ast` — anything
that is not one plain string literal, an f-string included, is *reported*, not silently dropped) and `t("...")`
calls (web, via regex, since no TS/Vue parser is a project dependency — comments and string literals are stripped
first so an example written in a doc comment, such as `i18n.ts`'s own docstring, is never mistaken for a real
call) into one `po/claudia.pot`. `check_debt.py` gained an "i18n extraction" check (`--check` mode) so the template
can never go stale relative to source. Currently empty (0 msgids) — correct, since nothing calls `_()`/`t()` yet;
proves the mechanism, not a catalog.

**Derivation and testing** (`scripts/po_to_json.py`, `scripts/make_pseudolocale.py`, new): `po_to_json.py` converts
any `.po`/`.pot` into the flat JSON `web/public/i18n/` reads, skipping the header entry and any untranslated
(`msgstr ""`) one, so an unfinished translation falls back to English rather than rendering an empty string.
`make_pseudolocale.py` generates `po/xx.po` from the `.pot` — `xx` is not a real BCP-47 tag any browser would send,
so it can only ever be reached deliberately (a future `?locale=xx` or a "Pseudolocale (testing)" Config entry, not
built) — mechanically "translating" every string by accenting vowels, padding ~40% longer, wrapping in brackets,
and leaving `{placeholder}`s untouched; a lapsed hard-coded string, a layout that assumes English-length text, or a
mangled placeholder all become visible at a glance once real strings exist. Currently also empty, for the same
reason as the `.pot`; `web/public/i18n/xx.json` was generated from it to prove `po_to_json.py` reads a pseudo-`.po`
the same way it reads a real one.

## Not built (next slices)

- No interface string actually moved off plain English into `_()`/`t()` anywhere — by design, this slice only
  proves the pipeline.
- The Config-menu locale override (needs a screen design first, per the project's own rule).
- Numbers and dates a person *types* are not yet parsed with their own locale before a command is made (part of
  E5.7's acceptance criteria, not attempted here).
- Help-topic translation (E13.8/D76): discussed, not decided or built.
- A CI gate that actually renders the UI under the `xx` pseudo-locale and asserts nothing reads as plain English —
  there is nothing to assert yet, since no string has moved.

## Verification (re-measured in the 2026-11-07 QA round, full `main` checkout)

- `claudia-core`: `uv run pytest packages/claudia-core/tests` — 369 passed, including `test_errors.py`. `ruff`,
  `ruff format`, `mypy` clean.
- `claudia-server`: `uv run pytest packages/claudia-server/tests` — 642 passed, including coverage of
  `normalize_locale`, `Context.locale`, `RequestError.detail`, and a real-websocket round trip of `hello`'s
  `locale` (`test_server_app.py`). `ruff`, `ruff format`, `mypy` clean. `scripts/api_surface.py --write` shows
  exactly the intended additive signature changes.
- Linux client: `clients/linux`'s own `pytest` — 214 passed, 38 skipped (GTK-dependent cases, cleanly, with no
  display attached) — including `test_i18n.py` and the extended `test_contract.py`; `mypy` clean.
- Web: `npm test` (vitest, 325 passed across 24 files) and `npm run typecheck` (vue-tsc) clean, including
  `locale.test.ts` and `i18n.test.ts`; the Node-environment guard in `locale.ts` was specifically checked against
  `people.test.ts`'s existing `ago()`/`clock()` calls, which now transitively call `currentLocale()`.
- `scripts/extract_i18n.py`, `po_to_json.py`, `make_pseudolocale.py`: each has its own unit tests
  (`tests/test_extract_i18n.py`, `test_po_to_json.py`, `test_make_pseudolocale.py`) and was also run for real
  against the repository, producing the checked-in `po/claudia.pot` (empty), `po/xx.po` (empty), and
  `web/public/i18n/xx.json` (`{}`) — all three confirmed correct for a repo with no translatable strings yet.

Two things noticed while this slice was being verified, and **fixed in the same QA round, not left open**:
`decision-log.md` had `D135` allocated three times (Row height and column width, The Manage menu, and Additive
xlsx/docx/pptx extensions — a third branch beyond the two this note first found) and
`packages/claudia-server/CHANGELOG.md` had `## [0.9.0]` twice with `0.10.0` sandwiched between — the same class of
parallel-merge collision D133 exists to catch for decision numbers, caught instead by hand. Both are renumbered;
a new gate line (`tests/test_changelog_versions.py`) now catches the second class the way `test_decision_log.py`
already catches the first. Also: `uv sync --locked` failed outright because the root `pyproject.toml` never listed
the three `*-io` packages (`claudia-composes-io`, `claudia-computes-io`, `claudia-creates-io`) as dependencies, so
their own `openpyxl`/`python-docx`/`python-pptx` were never installed — fixed, with its own gate line
(`tests/test_workspace_sync.py`).
