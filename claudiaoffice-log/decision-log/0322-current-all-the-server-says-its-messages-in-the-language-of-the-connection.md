---
id: D322
title: "The server says its own messages in the language of the connection"
status: current
applies-to: all
date: 2026-11-13
round: "Complete internationalization (branch i18n)"
supersedes: []
superseded-by: []
---

# D322 · The server says its own messages in the language of the connection

**A message the server writes for a person is raised in English as `msg("template {name}", name=…)` and said in the language of the connection that gets it: the `locale` of `hello` (D31, D148), kept as `Connection.locale` and `Context.locale`.** The answer to the owner's question in 2026-11-13 was "the server translates by connection locale", with `claudia-core` staying free of catalogs.

**How.** `claudia_server.i18n.msg` returns a `Message`, a `str` that reads as its formatted English text (logs, tests and clients that send no locale see exactly what they saw before) and remembers its template and parameters. The places that know the language turn it into text: `RequestError.to_dict(locale)`, the refusals of `hello`, the answer to an unexpected failure. The catalog is `po/<language>.po`, compiled to `claudia_server/locale/<language>/LC_MESSAGES/claudia.mo` like the Linux shell's (D160); the technical debt check fails when it is stale. A translation whose placeholders do not fit the parameters is never an error: the English text is said.

**Why not at the raise site.** The code that raises does not know the language, and passing a locale through every function would put it into code that has nothing to do with people. **Why not a `RequestError.detail` catalog.** The coded errors of `claudia_core` (E5.7 groundwork) have only ten codes; the other messages are formatted where they are raised.

**What stays English, on purpose and for now.** The messages the document packages raise and the server passes on as `str(exc)` (about 400 raise sites in `claudia-core`, `claudia-computes`, `claudia-composes`, `claudia-creates`), the `ValueError`s of the user directories that the admin pages show, and the texts the assistant says in chat. They need templates of their own in the packages (a `code` and parameters on the error, translated by the server through the `detail` the protocol already carries) and, for the admin pages, a language that does not come from a document connection. That is backlog story E5.17. `code` and `detail` are the same in every language, so no client logic depends on the text.

**Notes.** `PROTOCOL_VERSION` stays 2: `message` is still one string. The server package goes to 0.27.0 because `RequestError.to_dict` takes a `locale`.
