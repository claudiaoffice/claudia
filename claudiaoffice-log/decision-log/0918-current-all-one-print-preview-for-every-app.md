---
id: D918
title: "One print preview for every app that prints; creates' bar adds Layout — designed without a review"
status: current
applies-to: all
date: 2026-11-13
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D918 · One print preview for every app that prints; creates' bar adds Layout — designed without a review

**File ▸ Print… (Ctrl+P) is the same in composes and creates: one component (`web/app/components/PrintPreview.vue`) shows the pages in place of the document, and Ctrl+P in it prints, Esc goes back. What it prints and what it offers comes from a print source (`web/app/lib/print/source.ts`: `textSource`, `slideSource`), so the bar reads the same in both: ← Print preview · Layout (creates only) · Paper · Portrait/Landscape · Margins · Language · Page numbers · Download PDF · Print….** The status line says what is printed: "3 pages · A4 portrait" for a text, "7 slides on 2 pages · A4 portrait" for a presentation. The window's own bars (composes' style bar, creates' insert bar and slide tabs) are hidden while the pages are shown.

**What only a presentation offers:** the Layout choice (Slides, then under Handouts: 2 per page, 3 per page with lines, 4, 6, 9 per page), the `Slide size` paper first in the Paper list, and None among the margins. A text offers neither the slide paper nor None. Choices that would make no sense together are made together: a handout layout chosen while the paper is the slide's own moves to A4 portrait with narrow margins; Slides turns the page landscape; the slide paper brings landscape and no margins. Each is one step in the history.

**Drawn the same in both apps.** A shape's label is inset 8 px from the outline's text area and centred vertically unless its style says otherwise, as creates shows it on screen; composes' floating shapes (D907) now print so too. Page numbers are 9 pt in both, in the body text's colour made lighter. `LAYOUT_VERSION` is `claudia-layout-3`.

The owner asked for a consistent UI and left the design to Claude, as for D916; it is recorded as screenshots of the built screens (`notes/mockups/print-preview-creates-slides.png`, `print-preview-creates-handouts-6.png`, `print-preview-creates-handouts-3.png`) to be looked at later.

**Notes.** Refines D906 (composes' preview) and D916 (its bar). computes (E6.19) gets its own source when it prints.
