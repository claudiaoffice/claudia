---
id: D320
title: "Every text of the web interface goes through the catalog: one shared language, whole sentences, German complete"
status: current
applies-to: all
date: 2026-11-13
round: "Complete internationalization (branch i18n)"
supersedes: []
superseded-by: []
---

# D320 · Every text of the web interface goes through the catalog: one shared language, whole sentences, German complete

**Every visible text of the web app — labels, titles, tooltips, `aria-label`s, placeholders, notices, error messages, the help panel's chrome, the shortcut tables, the print preview, the admin pages — is a `t('…')` call, and `po/de.po` translates all of them (936 msgids, none left empty).** Until now only the manifest menus and a hand-picked pair of headers were (D148, D160). The owner asked for "all menus, help system, labels etc." in German and English, no further languages; the rest of the work is split into sequential patches, each passing the gate on its own: the web interface (this one), the Linux shell's own strings, the server's messages (they are translated by the connection's locale, `Context.locale`), then help topics and the function catalog.

**One language for the whole page.** `useI18n()` used to give every caller its own language and catalog, so only the workspace that called `choose` switched live. The language and the catalog are now module state in `web/app/lib/i18n.ts`; every `useI18n()` caller and every plain module (`import { translate as t } from './i18n'`, which `scripts/extract_i18n.py` still finds because the call is a bare `t(`) reads the same refs, so a switch re-renders the side panel, the dialogs and the session notices together.

**Whole sentences, never parts of one.** A translator must see and move a complete sentence:
- A sentence with markup inside it is one msgid with named placeholders, filled by `TransText.vue` (`<TransText :text="t('Hand {doc} over …')"><template #doc><b>…</b></template></TransText>`); the splitting is `web/app/lib/trans-parts.ts`, tested without a DOM.
- A noun is never slotted into a sentence ("This {noun} only" has no German that fits "Absatz", "Zelle" and "Objekt" alike). `web/app/lib/noun-phrases.ts` holds one sentence per styled thing; an unknown noun falls back to the object sentence.
- There is no plural machinery: a count with a singular uses two msgids (`1 cell`, `{count} cells`). German and English both have two forms; a language with more would need gettext plurals, which the catalog format and `createTranslator` do not have yet.
- A table of texts at module level (shortcut lists, palette names, export formats, paper sizes) is built from getters (`get label() { return t('…') }`) or a `computed`, so it follows a language switch instead of freezing the language of the first render.

**The catalog stays in step by tooling, not by hand.** `scripts/update_po.py` is `msgmerge` without GNU gettext: it keeps each translation, drops the strings the code lost, adds the new ones untranslated, refreshes the `#:` places and keeps the template's order; `--check` is a new gate check ("i18n merge"). `tests/test_catalogs.py` fails when a msgid has no German, when a translation changes the set of `{placeholder}`s, or when `web/public/i18n/de.json` or `po/xx.po` is not what its source makes.

**Left in English on purpose:** the product and app names (`Claudia`, `Claudia Composes`, …), file formats and key names a person must find on the keyboard are translated where the German keyboard says so (`Ctrl` → `Strg`, `Shift` → `Umschalt`, `Enter` → `Eingabe`), sample SQL and formulas, CSS, the names of fonts and programs, and the text the server sends in `RequestError` messages and print notes (`reason` in the print preview) — those are the server round's.

**Notes.** German uses the formal "Sie" throughout, matching the groundwork. Style is "Format" (`All Styles…` → `Alle Formate…`), checkpoint is "Prüfpunkt", slide "Folie", sheet "Blatt", the AI "KI" and the assistant "Assistent". `Not hyphenated: {reason}` and the other print notes still carry the server's English `reason`; the server round translates them at the source.
