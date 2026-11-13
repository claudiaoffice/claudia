---
id: D405
title: "What could not be kept is reported as codes (`Loss(kind, detail, count)`), and the screen that shows them is designed before it is built"
status: current
applies-to: all
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D405 · What could not be kept is reported as codes (`Loss(kind, detail, count)`), and the screen that shows them is designed before it is built

**The conversion layers never write a sentence for a person: a loss is a code (`table`, `frame`, `footnote`, `formatting`, `style`, `authorship`...), an optional detail (the name of a style), and a count, and the interface puts it into words in the person's language.** Both directions have one: `odt_import_losses` (what the model does not show of a file; none of it is lost from the file, D403) and `odt_export_losses` (what the file cannot hold of a model). The codes so far: `table`, `list`, `index`, `frame`, `formatting`, `link`, `tracked-change`, `footnote`, `endnote`, `field`, `comment`, `ruby`, `style`, `heading-level`, `authorship`, `remark`, `suggestion`, `suggestion-anchor`, and `removed-<kind>` from an edit. `export_office` for odt answers with the export list as `losses` (D410).

**Notes.** The loss-list screen is an SVG design first, agreed before any UI code (project rule); it is not part of this slice, and the import UI is being thought through with another agent. Until it exists nothing in the web app shows `losses`. Every export of a typed text reports `authorship`: it is true (an odt has nowhere for who wrote which run) and the screen may decide to show it quietly.
