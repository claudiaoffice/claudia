---
id: D282
title: "The dialog is a non-modal panel over the document, opened by Ctrl+F (find) or Ctrl+H (replace unfolded)"
status: current
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D282 · The dialog is a non-modal panel over the document, opened by Ctrl+F (find) or Ctrl+H (replace unfolded)

**One panel, not a modal dialog.** Edit ▸ Search & replace… opens a floating panel at the right of the document area, over the document and not in the History and chat dock. The document stays visible and editable, and matches show **in place** (a tinted cell, a marked word) while the panel lists them. The quick path is a find field with "1 of 6", next/previous, "Look in" and a few options; "Replace with…" and "Build a pattern…" unfold below it. Ctrl+F opens it for finding, Ctrl+H with Replace unfolded; Esc closes it. It is **one frontend component** used by all three apps in every shell (the desktop shells frame the web app), talking to a `SearchHost` the app gives it — the way the styling dialog talks to a `StyleHost` (E5.13).

**Notes.** Claude's proposal, agreed by the owner with the mock-ups on 2026-11-13. Rejected: a modal dialog (hides the thing being searched and cannot show matches in place) and a docked pane (the right dock belongs to History and chat, E5.6; a left pane would collide with composes' outline view). Shown in `notes/mockups/computes-search-find.svg` and `search-replace-edit-menu.svg`. On macOS Cmd replaces Ctrl through the shared shortcut table (D122).

**As built (2026-11-13).** `web/app/components/SearchPanel.vue` for all three apps, `web/app/lib/sheet-search-host.ts` for computes; fixed at the right of the document, below the formula bar, and a bottom sheet on narrow windows. Ctrl+F and Ctrl+H follow the shared shortcut rule (D122): they do not fire while a text field has the focus, so inside the formula bar the browser's own find opens; Edit ▸ Search & replace… always works. Esc closes the panel and returns the focus to the grid.
