---
id: D393
title: "Third-party plugins are data only: manifests with argv templates, never code"
status: current
applies-to: all
date: 2026-11-13
round: "Rendered text containers (branch containers)"
supersedes: []
superseded-by: []
---

# D393 · Third-party plugins are data only: manifests with argv templates, never code

**A folder may bring only manifests (`api: 1`): the tools needed, typed settings, an argv template, support files, a diagnostics reader, limits, editor hints and `forbid` patterns. Code is a built-in adapter only (LaTeX, over the typesetter of E3.4).** The service enforces every rule in one place: argv only, never a shell; settings that are free text may not become arguments; structured config files instead of string-built ones; `forbid` patterns checked on the source (Typst `@pkg/` imports); a job folder as `HOME` and `TMPDIR`; the sandbox of D98 with the limits capped by the administrator's `RenderPolicy`; bounded concurrency; a result cache.

**Notes.** Three real tools showed what the contract must hold: Typst needs a page prefix and a root, Mermaid needs a browser and config files, LaTeX needs an adapter. Diagnostics are read into lines of the person's text (the prefix is subtracted).
