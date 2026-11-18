---
id: D780
title: "A style knows where it comes from (document, built-in, template) and can be hidden; only a document style can be deleted"
status: current
applies-to: all
date: 2026-11-17
round: "Deleting and hiding styles (E1.10)"
supersedes: []
superseded-by: []
---

# D780 · A style knows where it comes from (document, built-in, template) and can be hidden; only a document style can be deleted

**`StyleDef` gets `origin` and `hidden`.** `origin` is `"builtin"` (the app made it: every document starts with it), `"template"` (a template put it there; no app has templates yet, the value is taken so that a template can arrive without changing the rule) or `"document"` (a person made it, or a deviation did; the default). `hidden` keeps a style out of the menus a person picks from, and out of nothing else: it still resolves, so nothing that has it looks any different. Neither is written when it has its default, so a style that has neither writes exactly what it wrote before, and there is no upcast (D308).

**Only a `document` style can be deleted.** Root, built-in and template styles can only be hidden (`SetStyleHidden`, one command, undoable, any role that can write). "Root" needs no flag of its own: every root an app has is a built-in (body text, and the box and outline styles).

**Notes.** The apps mark their built-ins where they make them (the `_style` helper of each app's built-in list), not in the document. A client filters hidden styles out of the menus it offers and shows them again in All styles (D302), where the person unhides them.
