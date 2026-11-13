---
id: D917
title: "A presentation prints as slides or handouts, set in the document; page setup and language move to the kernel"
status: current
applies-to: all
date: 2026-11-13
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D917 · A presentation prints as slides or handouts, set in the document; page setup and language move to the kernel

**A creates presentation carries how it prints: a layout — `slides` (one to a page) or handouts of 2, 3 (beside ruled lines for notes), 4, 6 or 9 to a page — and a page setup, changed in one step for everybody (`claudia_creates.SetPrintSetup`; wire `print_setup`, `set_print_setup`; event `print_setup`; `SlideModel` state schema 7).** A new presentation, and every older one, prints one slide to a page of the slide's own size: the new paper preset `slide`, 7.5 × 13.333 in (338.7 × 190.5 mm, PowerPoint's 16:9), landscape, no margins, so the page is the slide edge to edge. A4, Letter and the others stay selectable. The owner chose all four of these points (2026-11-13: settings in the document, slides plus handouts, a slide-sized page, a language shared with composes).

**A presentation has a language too, the same way a text has (D915): one command for both apps, `claudia_core.SetLanguage` (kind `core.SetLanguage`), with the event `language` and the wire methods `language`, `set_language` (`claudia_server.printing.add_language_methods`).** `PageSetup` and `normalize_language` moved from `claudia_composes` to `claudia_core` (`claudia_core.page`, `claudia_core.language`); composes re-exports them, and replays logs that wrote `composes.SetLanguage` with an alias command of that kind. A new presentation starts in its creator's interface language, as a text does. Creates' built-in styles do not hyphenate (`hyphens` stays `manual`): a slide's short lines should not be broken.

**How slides are placed (`layout/src/apps/creates.ts`, `layoutSlides`).** A slide is 1600 × 900 CSS pixels, drawn once at 1200 × 675 pt and put on the page through a group's transform (scale in millionths), fitted into its cell and centred there, cut at the slide's edge. Handouts form a grid inside the margins with 8 mm between cells: on a portrait page 2 → 1 × 2, 3 → 1 × 3 (the slide takes 55 % of the width, the rest is ruled every 8 mm), 4 → 2 × 2, 6 → 2 × 3, 9 → 3 × 3; on a landscape page the grid turns (and with 3 the lines go under the slides, which take half the height). Every slide gets a thin grey frame unless it fills the page edge to edge. Page numbers are the same as composes' (D904). The objects are drawn by the code composes' floating objects use (`layout/src/apps/objects.ts`, D907); charts are not printed yet and the preview says so.

**Notes.** Speaker notes are not part of a presentation yet, so there is no notes-page layout; when they are, it is one more layout value. Printing from the desktop shells is E9.23's.
