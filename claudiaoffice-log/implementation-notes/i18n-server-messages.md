# Implementation notes: the server's messages in German and English (branch `i18n`, patch 3)

Decision: D293. Backlog: E5.7, E5.17. Web UI: `i18n-web-ui.md`.

## How to add a message

1. In the server write `RequestError("bad_request", msg("set_cells: at most {limit} cells at a time", limit=MAX))`,
   with `from .i18n import msg`. The first argument is one plain string literal (the extractor finds `msg(` like it
   finds `_(`); the values go in as keyword arguments, named for what they are (`limit`, `sheet`, `reason`), never an
   expression's own name. An f-string is not found.
2. Braces: a template without parameters is used as it stands, so a literal `{…}` needs no doubling; with parameters a
   literal brace is written `{{`.
3. `uv run python scripts/extract_i18n.py`, `scripts/update_po.py`, translate in `po/de.po` (formal "Sie", as in the
   rest of the catalog), then regenerate: `scripts/compile_mo.py po/de.po de --locale-dir
   packages/claudia-server/src/claudia_server/locale` as well as the Linux one and the web JSON.
4. A test says it in German over the wire (`packages/claudia-server/tests/test_server_app.py`).

## Things to know

- **`msg` is a `str`.** `json.dumps`, `str()`, `==` and logging all see the English text; only `localized()` looks at
  the template. Code that builds a message by `+` or an f-string from a `Message` gets a plain `str` and loses the
  template: pass the inner message as a parameter instead (`msg("chat: {reason}", reason=exc)`).
- **The core packages are not translated.** `str(exc)` of a `KeyError`/`ValueError` from `claudia-core` and the
  document packages reaches the client in English (E5.17).
- **A language without a catalog falls back to English**, and so does a translation with the wrong placeholders.
