# Implementation notes: help topics and function descriptions in German (branch `i18n`, patch 4)

Decision: D294. Backlog: E13.8, E5.7. Server messages: `i18n-server-messages.md`.

## Translating a help topic

1. Write `<topic>.de.md` next to `<topic>.md` in the package's `help/` folder. Front matter as in the English file,
   plus `language: de` and `source-hash: <fingerprint>`; `title`, `tags` and the text are translated, `apps`
   and `explains` (function and menu names, which are what a person sees) are copied or translated as the screen shows
   them.
2. The fingerprint is `Topic.fingerprint` of the English file (`parse_topic(text).fingerprint`); the test
   `test_every_shipped_translation_is_as_new_as_its_source` prints the one to write when it is wrong.
3. An English topic that changes makes its translations stale on purpose. Re-read the translation, then set the hash.

## Translating a function

A new cell function brings its `description` (and an example `note`, if any) in English; `scripts/extract_i18n.py`
takes them into `po/claudia.pot` through `translatable_texts()`, and `test_every_function_has_a_german_description`
fails until `po/de.po` has them and the server's catalog is rebuilt (`scripts/compile_mo.py po/de.po de --locale-dir
packages/claudia-server/src/claudia_server/locale`).

## Things to know

- **The web catalog carries the function descriptions too** (they are in the one template); the web app never asks
  for them, they cost about ten kilobytes in `de.json`.
- **A topic is German only for a window that said so.** `help_search` and `help_topic` read `Context.locale`; a
  window that switches language says so with `set_locale` (`BaseSession.tellLanguage` in the web app).
- **Default style names are English document data** (`Body text`, `Heading 1`); the German topics quote them as they
  appear on screen.
