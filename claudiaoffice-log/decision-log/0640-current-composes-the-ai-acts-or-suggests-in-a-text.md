---
id: D640
title: "In a text the AI acts or suggests, as in the other apps"
status: current
applies-to: composes
date: 2026-11-15
round: "Code review follow-up: CODE-27 and the text app's AI"
supersedes: []
superseded-by: []
---

# D640 · In a text the AI acts or suggests, as in the other apps

**composes follows D262 like computes and creates: for a person in *act* mode the AI writes the text, for a person in
*suggest* mode it suggests and she accepts.** What it may write through is its allow-list for the app
(`apps.MODEL_METHODS`, SEC-10), checked at dispatch for every engine: `replace_text`, `set_style` and `suggest` in
*act*, `suggest` alone in *suggest* (D262's narrowing). composes' own guard that refused the AI every write
(`_people_only`, from D63) is removed, and with it the `guard` hooks of the shared style, name, list, object, rendered
and search methods, which only composes used: one rule for the assistant in all three apps. How a document is set up
(page, print setup, language) stays people's in every app (`printing.people_only`).

The scripted stand-in (`standin_text.TextEngine`) makes its replacements itself in *act* mode, each paragraph from its
end so that an edit never moves a place still to come, and says how many places it changed and that undo takes a
change back. A finding without a replacement (a long sentence) stays a remark, a suggestion, in both modes.

**Notes.** The owner's answer of 2026-11-15: "that block is no longer warranted, anyone should act or suggest also in
composes". D63 had been superseded by D262 since 2026-11-11; composes still carried its guard, its docstrings still
cited D63, and the web client's AI switch told a text's reader "the AI suggests either way" (removed). The allow-list
in *act* is kept small on purpose, as computes' and creates' are: the words and the paragraph styles, not the
structure of lists, the styles themselves, the palette, objects or search-and-replace. Widening it is a later
decision, per method, as for the other apps. Each `replace_text` is its own step in the history, as a person's typing
is; one step for a whole review would need a batch method that composes does not have yet.
