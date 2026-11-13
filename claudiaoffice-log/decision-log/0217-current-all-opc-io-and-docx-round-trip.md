---
id: D217
title: "New package `claudia-opc-io` (dependency-free: `read_parts`/`write_parts` for the zip↔parts boundary, `owns`/`reconcile` to restore whatever a library's…"
status: current
applies-to: all
date: 2026-11-08
round: "Real import, edit and re-export: docx, pptx, xlsx, and the test-document library"
supersedes: []
superseded-by: []
previous-id: D177
---

# D217 · New package `claudia-opc-io` (dependency-free: `read_parts`/`write_parts` for the zip↔parts boundary, `owns`/`reconcile` to restore whatever a library's…

**New package `claudia-opc-io` (dependency-free: `read_parts`/`write_parts` for the zip↔parts boundary, `owns`/`reconcile` to restore whatever a library's `save()` was not asked to touch), and `claudia-composes-io` gets a first real import/edit/export path on top of it: `docx_to_text` (a docx's paragraphs into a `TextModel`, Word's built-in styles mapped back) and `apply_edits_to_docx` (re-export by rewriting only the paragraphs whose text, style or open suggestions changed since the baseline import, then `reconcile`-ing against the original bytes so every other part of the package, and every paragraph this call did not touch, survives byte-for-byte).** A table, image or custom style claudia never modeled is not dropped on an edit-and-save round trip. Not covered by this slice: adding or removing a paragraph (`apply_edits_to_docx` raises `UnsupportedEdit`); `reconcile` itself works at whole-part granularity only, with shared/indexed-table merging deferred (relevant once xlsx/pptx, and later odfdo, are wired to the same package). 8 opc-io tests, 10 new composes-io tests, no regression in the 7 pre-existing ones.

**Notes.** Closes the multi-round design discussion that preceded it: model-state diffing over command replay (which would need a second interpreter of every `Command`'s own semantics, kept consistent with the first across every sequence); a retained original-file blob over reopening a path that may have moved or been deleted; a static part-ownership classification, found to break down for shared/indexed tables, relationship-id instability across saves, and per-document rather than static ownership, resolved instead by paragraph-level patching plus whole-part reconciliation. Scoped narrowly and dependency-free rather than as a full OPC abstraction layer on the comparison table's own advice — `python-opc`, an abandoned 2013 attempt at exactly that, never caught on — which is also why it is docx-agnostic from the start, ready for xlsx/pptx, and, with odfdo's own lxml-tree architecture confirmed compatible by direct source reading, ODF later.

*Renumbered on 2026-11-10 from D177, a number that had been allocated twice by branches written in parallel (see `_rounds.md`, "One file per decision").*
