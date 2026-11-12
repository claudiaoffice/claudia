---
id: D901
title: "Pages are laid out in the client, by one deterministic TypeScript library, and look the same wherever they are made"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D901 · Pages are laid out in the client, by one deterministic TypeScript library, and look the same wherever they are made

**Where every glyph of a page goes is decided in the client, by one layout library written once in TypeScript, and the result is the same on every machine, browser and operating system.** The library takes the document, the font files (by SHA-256) and the shaping engine (by SHA-256) and computes in whole thousandths of a point (*mpt*); its result, a display list, is what the screen shows and what the PDF is written from. For now it runs only in the client (the browser, or the web view of a desktop shell); it is written so that a server could run it too, without a change, if that is ever needed (a headless PDF export, say). Matching the pages of Word or LibreOffice is not a goal: they disagree with each other, depending on printer, version and compatibility mode. Matching ourselves is.

**Notes.** Settles E9.4 ("a decision on the layout approach"). The owner's own sequence of reasoning (2026-11-12): a deterministic layout module at the core rather than leaving paragraphs to the browser; in the client rather than the server (scrolling large documents); written exactly once, in TypeScript only, no second language; then paging and printing in the browser only for now. The layout spike checked the premise before any of this was built: the same layout fingerprint and byte-identical PDFs on Linux, Windows 11 and macOS (Apple Silicon), Node 22 and 26, and in Chrome (V8), Firefox 159 (SpiderMonkey) and Safari 27 (JavaScriptCore), for one German/English sample with two font families. LaTeX (D88, D221) stays the engine for formulas and a publication-quality export; it is not the page view's engine.
