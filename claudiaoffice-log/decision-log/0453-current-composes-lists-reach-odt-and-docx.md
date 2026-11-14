---
id: D453
title: "Lists of a composes text are written to odt and docx, read back, and patched into a kept file"
status: current
applies-to: composes
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D453 · Lists of a composes text are written to odt and docx, read back, and patched into a kept file

**An item of a list (`ListItem`) is written as an item of a `text:list` (odt) or a paragraph with `w:numPr` (docx), its list (`ListDef`: scheme, start, name) as a `text:list-style` or a `w:abstractNum` with a `w:num`; both formats read them back into the same items and lists, and an edit-and-reexport keeps the lists the file has. `"lists"` is a written facet of both converters (D450): a changed list is no longer a `not-written` loss.**

**Notes.**

* *One list, one identity.* Items that share a list id are one list in document order, whatever lies between them. In
  docx that is a `w:numId`. In odt it is a top-level `text:list`, with the pieces after a paragraph written as lists
  that continue the first (`text:continue-list` naming its `xml:id`); a file's own list that has no `xml:id` gets one
  only when a later piece must name it.
* *Looks the model does not draw* (another number format, another bullet, a numbering style carried by a docx
  paragraph style) are read as lists with the scheme of their first level and reported as `list-look` on import (they
  replace the old `list` code); levels deeper than nine are `list-depth`. The file keeps its own look until the
  list's definition is changed in the model, which then writes the model's look.
* *Patching* rewrites only what changed. In odt a list whose items changed is written again (a list that holds
  tables or other markup than items and paragraphs is refused with `UnsupportedEdit`, so the file is written new and
  `not-patched` is reported, D441); an untouched list stays byte for byte. In docx a changed definition points the
  existing `w:num` at a new `w:abstractNum`, so no paragraph is touched; the numbering part is only taken from the
  patched package when it changed (and, for a file that had none, with the package entries that name it).
* `XmlPart` (odf-io) turns an inserted element into bytes only when the result is made, so a later edit of that
  element (the `xml:id` a continuing list names) is in the output; `set_attributes` accepts the `xml:` prefix.
* A docx paragraph that is patched keeps its Word style unless the model's style changed (before, any style the
  model does not know was replaced by Normal in every rewritten paragraph).
* Adding or removing paragraphs in a docx is still the fresh-file path; a later slice of this round lifts that.
