# CODE-78 · A refusal reaches a person in her language (D1510)

Branch `code-78-translated-refusals`, 2026-11-23. Spec: `specs/server/refusals.feature`.

## What was built

- `claudia_core.errors.Refusal(template, **params)` (a `ValueError`) and `N_(template)`, the marker for a template
  kept in a table. Exported from `claudia_core`.
- `claudia_server.i18n.message_of(error)`: a `Message` for a `Refusal`, the English text for anything else.
  `localized` says message parameters in the same language. Every `RequestError`/`HubError` that passed on
  `str(exc)` of a model now passes `message_of(exc)`; `msg("...{reason}", reason=exc)` passes `message_of(exc)`. The
  reasons in the style deletion dialog's targets are said in the connection's language.
- `scripts/extract_i18n.py` collects `Refusal("…", k=v)` and `N_("…")`, searches `claudia-core` too, and reports a
  `Refusal` built from an f-string. A `Refusal(TABLE[kind], …)` (a template looked up) is fine: the table is marked.
- The refusals a person can meet, in the core (names, styles, lists, schemes, palette, tables, objects, chat,
  paragraphs, page setup, pictures) and in computes (names, sheets, charts, pivot tables, number formats, sizes, spilled
  cells, structural edits, print scale), composes (suggestions, tables of contents) and creates (notes, planned times,
  the slide's bounds): about 140 sites. `ImageError`, `PageSetupError`, `PivotError`, `ChartError` and the two
  `PrintSetupError`s are subclasses of `Refusal`; their checks of malformed data stay English (no `N_`).
- `name_problem` (core and computes) returns the `Refusal`, not a string. `ObjectModel.name_taken`, extended by each
  app, has one sentence per kind of thing.
- About 150 German translations (`po/de.po`), the server's `.mo`, the web's JSON catalogs and the pseudo-locale.

## Assumptions

- "A person can meet it" was judged site by site: what the interface can send when a person types, picks or pastes
  (and what a colleague's edit at the same moment can cause). Checks of ids, kinds, JSON shapes and wire fields stay
  English. Where unsure (a limit a dialog already enforces), the refusal was translated.
- The English of a taken name now uses the interface's words: "a text box", "a picture", "a chart", "a named range",
  "a list item" (was "a text", "an image", "a diagram", "a range", "an item"). A row or column size says "a row is … to
  … high" / "a column is … to … wide".
- A sentence that carries a style's kind ("a paragraph style") was rewritten without it ("styles of different
  kinds"), because the kinds are English words that would otherwise sit untranslated in a German sentence.
- A name a person gave is quoted “…” in the English (German „…“), no longer with Python's quotes ('Revenue'): sheet,
  chart, pivot table, field, source and number format names. Ids (of a list, a scheme) and wrong input echoed back
  ("got 'x'") keep `!r`.
- Numbers are filled in plain (1002, not 1,002): a separator in the template would be the English one in German too.
- Placeholders are named for what a translator needs to know: `{limit}`, `{least}`, `{length}`, `{width}`,
  `{height}`, `{name}`, `{field}`; one sentence has one template (a taken sheet name is one msgid, whether the command
  or the name check refuses it).

## Review (two axes) and what changed after it

Done: placeholders renamed; duplicate msgids merged ("a sheet called 'x' exists" is the taken-name sentence); names
quoted “…”; no thousands separator; a style's kind and a cell's slot no longer enter a sentence as an English word (one
template per slot); the chart title limit, the wrap gap, "a chart's range must be inside the sheet" and "a table of
contents takes no typing" are refusals; `chart_from_data` no longer turns a `ChartError` back into a plain
`ValueError`; the style targets' `_run` passes the refusal on with `message_of`; the extractor accepts a looked-up
template only as a name, an attribute, an item or a `.get(...)`, and reports `Refusal(str(e))` and
`Refusal(text.format(...))`; `Refusal` and `N_` in the API docs. German: "Die Kopfzeile bleibt …", the bullet sentence,
"Ein Name enthält keine Steuerzeichen".

Left: the subclasses of `Refusal` (`ImageError`, `ChartError`, …) still build their checks of malformed data with
f-strings; the extractor does not report those, because they are English on purpose (D1510). A pivot table that fails
in its cell says why in the cell's error text, which belongs to the document, not to one person, and stays English.
`Refusal` is a `ValueError`, not a `KernelError`: every `except ValueError` must keep catching it (coding standards §6
asks for one hierarchy; this is the recorded exception, D1510). The versions stay as they are: API changes go under
[Unreleased], as the other changes of this week did.

## Tests

- `packages/claudia-core/tests/test_refusal.py`, `packages/claudia-server/tests/test_server_i18n.py` (German, nested
  messages, other errors), `test_server_thing_names.py` (a computes clash and an empty name in German),
  `tests/test_extract_i18n.py` (the markers and the f-string guard), `tests/test_catalogs.py` (every string has German
  with the same placeholders).
- `tests/e2e/specs/test_refusals.py`: a sheet and a slide renamed to a taken name by a person who chose German.

## Not done

- History labels ("Replace in N cells") and the server's own English `ValueError`s of files and settings are not
  refusals of a model; they are UX-22 and the admin pages.
- Refusals in the I/O packages (an import that fails) are reported by the server's own messages and were not touched.
