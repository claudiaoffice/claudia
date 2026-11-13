---
id: D203
title: "An object's own style can be changed after it is made, and the style methods a document needs are the same in every app"
status: current
applies-to: all
date: 2026-11-08
round: "Colour roles: the document's palette (thirty-third round)"
supersedes: []
superseded-by: []
---

# D203 · An object's own style can be changed after it is made, and the style methods a document needs are the same in every app

**An object's own style can be changed after it is made, and the style methods a document needs are the same in every app.** New `core.SetObjectStyle`, with its exact inverse; `replace_object` already checks that the style exists, so it needed nothing new. `claudia_server.styles.add_style_methods` registers `styles`, `palette`, `set_role`, `replace_palette`, `set_object_style`, `change_style`, `rename_style` and `check_css` into an app's table, with a `guard` hook; composes passes `_people_only` (D63, SEC-10) and keeps only `set_style` and `deviate_style`, the two that name paragraphs.

**Notes.** Found while checking the mocked style menu against the code: an object's `style` was settled by `AddObject` and could never be changed again, which left the menu's most ordinary act — picking a style for the shape you have selected — impossible. And `change_style`, `rename_style` and `check_css` existed in `composes_methods` alone, so creates and computes could read their styles and not change them; the same deduplication the object commands had just been through.
