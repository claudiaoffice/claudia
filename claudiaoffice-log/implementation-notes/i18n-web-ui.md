# Implementation notes: the web interface in German and English (branch `i18n`, patch 1)

Decisions: D320, D321. Backlog: E5.7. The groundwork is in `i18n-groundwork.md` and
`implementation-notes-app-language-switch.md`; this note is what was added to it for the web app.

## How to add a text

1. Write `t('Open Document…')` in a template or script (`const { t } = useI18n()`), or in a plain module
   `import { translate as t } from './i18n'`. The extractor finds an unqualified `t('…')` with one plain string
   literal; a ternary or a template literal inside `t(` is not found — write two `t()` calls.
2. A value in `{braces}` is a placeholder: `t('Row {n}', { n })`. The translation must keep the same set of names
   (`tests/test_catalogs.py` checks it).
3. A sentence with markup inside: `TransText`, never a text cut into pieces around a `<b>`.
4. Run `uv run python scripts/extract_i18n.py`, then `uv run python scripts/update_po.py`, translate the empty
   `msgstr`s in `po/de.po`, then regenerate the derived files:
   `uv run python scripts/make_pseudolocale.py`, `uv run python scripts/po_to_json.py po/de.po de`,
   `uv run python scripts/po_to_json.py po/xx.po xx`, `uv run python scripts/compile_mo.py po/de.po de`.
   `scripts/check_debt.py` fails on each of them that is stale.

## Things that went wrong on the way, so the next person does not repeat them

- **A constant that calls `t()` at module level is translated once**, in the language of the moment the module
  loaded. Shortcut lists, palettes, export formats and paper sizes are getters or `computed`s now.
- **`t` is the translator in every component.** A `v-for="t in …"` shadows it (eslint `vue/no-template-shadow`);
  the loop variables are `tb`, `row`, …
- **The component is `TransText`, not `Trans`** (eslint `vue/multi-word-component-names`).
- **A language switch must re-render everything**, which is why the language is module state; a test
  (`web/tests/i18n.test.ts`, "one language for the whole page") pins it.
- **Default props are not translated.** `withDefaults(…, { caption: 'Style' })` stays English; the component
  computes the text from the prop instead (`StylePicker.vue`).
- **A string that is the same word in two places can still need two msgids** — "Orientation" of a page and
  "Alignment" of text are both "Ausrichtung" in German, so the page one is "Seitenausrichtung".
- **Fixed phrases in code, such as a CSS value or a key name read from `event.key`, are not texts.**

## What is not done here

- The Linux shell's own strings (patch 2), the server's messages (patch 3), help topics and the function catalog
  (patch 4).
- Numbers and dates are formatted with the browser's locale where they were before; parsing what a person types
  by their locale is still the open part of E5.7.
- No plural forms: two msgids where a count has a singular.
