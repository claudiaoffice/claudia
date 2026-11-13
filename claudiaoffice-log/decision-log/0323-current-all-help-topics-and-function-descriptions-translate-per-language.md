---
id: D323
title: "Help topics are translated one file per language, function descriptions through the catalog"
status: current
applies-to: all
date: 2026-11-13
round: "Complete internationalization (branch i18n)"
supersedes: []
superseded-by: []
---

# D323 · Help topics are translated one file per language, function descriptions through the catalog

**A help topic is translated by a second file next to it (`writing-a-formula.de.md`), and the descriptions and example wordings of the cell functions are msgids of the one `.po` catalog (D31, D148); the server picks both by the language of the connection (D322), English where there is no translation.** The owner chose this in 2026-11-13 over putting whole topics into `.po` entries.

**Topics.** A translation has the same `id` as its source (so a link or a `help_topic(id)` keeps working), its own `language` and a `source-hash`: the fingerprint of the English file it was made from (twelve hex digits of the file's text, line endings aside). `HelpLibrary.stale()` lists the translations whose source has changed since, `check()` refuses a translation without an English topic, and a test (`test_every_shipped_translation_is_as_new_as_its_source`) fails on a stale one, naming the new hash: translate the change, set the hash. Search finds a topic by the words of its translation *and* of the English one; `help_topic` says which `language` it answered in.

**Function descriptions.** They are data of the library, not `_()` calls, so `claudia_computes.translatable_texts()` lists them and `scripts/extract_i18n.py` takes them into the template. The package stays free of catalogs: `FunctionHelp.translated(translate)` and `Bound.get_help(translate)` take the translating function, the server passes the one of the connection's language. A formula, its result and the signature are not translated; the wording of an example (`{formula}  gives  {result}`) is.

**The language of a window can change** (the person picks another App Language while connected): `set_locale` tells the server, the web session sends it on a language change and after a reconnect. A client that never sends it keeps the `locale` of `hello`.

**What stays as it is.** The names of the styles every text starts with (`Body text`, `Heading 1`) are document data and English; the German topics say so where they name them. The AI answering in the person's language from the English topics (E13.8's last point) is not done: the stand-in understands English only, and a real model is the owner's to configure (E13.4, E7).
