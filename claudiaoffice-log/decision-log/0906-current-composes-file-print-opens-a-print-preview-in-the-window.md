---
id: D906
title: "File ▸ Print… (Ctrl+P) turns the main window into a print preview; Print hands the same PDF to the browser"
status: current
applies-to: composes
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D906 · File ▸ Print… (Ctrl+P) turns the main window into a print preview; Print hands the same PDF to the browser

**File ▸ Print… (Ctrl+P) shows the text's pages in the main window, in place of the text: a bar where the style bar was (paper, orientation, margins, page numbers, Download PDF, Print…), the pages below, read-only, two side by side or zoomed.** ← or Esc goes back to the text; the history and chat panel stays. Print… (or Ctrl+P again) writes the PDF of the pages shown and hands it to the browser's print dialog in a frame of its own (a tab where a browser cannot print a PDF in a frame); Download PDF saves the same file. The pages on screen are drawn from the same display list as the PDF, with the same font files: every word stands where the PDF puts it. A viewer sees the pages and prints them but cannot change the page setup. A change by anybody shows in everybody's preview.

**Notes.** The screens were agreed as an SVG mock-up first (`notes/mockups/print-preview.svg`). This **refines D61**, which said composes has "no separate print dialog or overlay": the preview is a mode of the main window, not a dialog, and the print dialog is the browser's own. D61's flow/page switch stays as it is; the page view (E9.6) is still the approximate one, and moving it onto the layout library is its own story (E9.24). The letters inside a word are shaped by the browser when they are drawn on screen (D910). The desktop shells' native menus do not have the item yet (E9.23); Ctrl+P works in their page.

*2026-11-12:* the bar gained a Language choice and wraps when the window is narrow (**D916**).

*2026-11-13:* the preview is one component for composes and creates (**D918**).
