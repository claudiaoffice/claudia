---
id: D1510
title: "A refusal of a model is typed: it keeps its English template and parameters, and the server says it in the person's language"
status: current
applies-to: all
date: 2026-11-23
round: "CODE-78 (branch code-78-translated-refusals)"
supersedes: []
superseded-by: []
---

# D1510 · A refusal is typed and said in the person's language

- **What.** A model (the core and the three apps) that will not do what a person asked raises a
  `claudia_core.Refusal`: a `ValueError` that reads as the English sentence and keeps the `template` it was made from
  and the `params` that fill it in. The server turns it into a message with `i18n.message_of(error)`, and the message is
  said in the language of the connection, like the server's own `msg(...)`. A message that fills another one
  ("{method}: {reason}") is said in that language too.
- **Which refusals.** Those a person can meet through the interface: a name that another thing has or that is not a
  name, limits (sizes, counts, lengths), what a table, a style, a list, a pivot table, a picture or a page cannot be.
  A check that only a wrong client can fail (a malformed request, an unknown id) stays a plain `ValueError` in English:
  no person meets it, and translating it would cost every translator for nothing. Agreed with the owner on 2026-11-23.
- **One template per kind.** A sentence is never built from words that another language bends: a name that is taken
  has one sentence per kind of thing ("ein Bild", "eine Form", `ObjectModel.name_taken`), a style deleted or re-based has
  one per verb, a row and a column one each. A template kept apart from its call is marked with `N_`.
- **A ValueError, not a KernelError.** A refusal is the `ValueError` the models raised before, so that every
  `except ValueError` in the apps, the I/O packages and the server keeps catching it; this is the one exception to the
  single error hierarchy of the coding standards.
- **The catalog.** Templates are collected from the source like `msg(...)` (`scripts/extract_i18n.py`, now with
  `claudia-core`), into the one catalog the server and the web share. The extractor reports a `Refusal` whose template
  is built at runtime (an f-string), so no refusal can slip past the translators. The core stays free of any catalog: it
  only marks.
- **Why not translate the English text by patterns** (the other option the owner was offered): a catalog of English
  sentences with their blanks guessed back out of them breaks when the English is reworded, and cannot tell two
  sentences apart that differ only in a filled-in word.

**Why.** CODE-78: a person who works in German was told "There is already a sheet called …" in English.
