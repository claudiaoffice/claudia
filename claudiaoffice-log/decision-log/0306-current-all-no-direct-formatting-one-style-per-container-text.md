---
id: D306
title: "No direct formatting: the text in a container has one style; inline marks are optional, named by purpose and opt-in per slot"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D306 · No direct formatting: the text in a container has one style; inline marks are optional, named by purpose and opt-in per slot

**The text in a container (a paragraph, a text box, a shape's label, a cell) has exactly one style; there is no per-word or per-character formatting.** "This word only" does not exist; deviating applies to the whole container (D75, "styles first, deviate second").

**Inline marks are the one deliberate, later exception.** A *mark* is a purpose-named style (Emphasis, Strong, Code) that sets only weight, italics, decoration, font family and palette-role colours (D200) — never a size or a literal colour. Marks are created on purpose in "All styles", never through "this word only", and are opt-in per slot: composes paragraphs may offer them (later); text boxes, shape labels and cells do not. Importing a document maps bold, italic and monospace runs to marks where the slot has them and lists everything else as unmapped (D75, E9.8).

**Notes.** Written in answer to the owner's observation that direct formatting of single words is what makes documents look bad, and that LaTeX keeps content and look apart by making `\emph` the only easy exception. Supersedes the "character styles" item of E9.7, which is replaced by the purpose-named marks; marks are not part of the first implementation.
