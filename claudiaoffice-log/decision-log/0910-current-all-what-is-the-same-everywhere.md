---
id: D910
title: "What is the same everywhere, and what is not"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D910 · What is the same everywhere, and what is not

**The display list and the PDF are the same, byte for byte, wherever the same document is laid out with the same fonts and the same HarfBuzz build: every length is a whole mpt; no `Math.sin`, `Math.cos`, `Math.atan2` or `Math.pow` (whose last digit may differ between engines) is used — rotation uses a table of sines and arcs a series of plus, minus, times and divide; images are decoded by the library's own code; streams are compressed by fflate in JavaScript; and no date is written into the PDF.** Not part of the promise: how the browser draws the letters inside a word on screen (it shapes them itself, from the same font file, to a few hundredths of a point), and the printer.

**Notes.** Measured in the spike (D901). The library's tests compare against BigInt arithmetic, Pillow's pixels and pdf.js's reading of every PDF; the e2e test checks that the PDF printed is the PDF downloaded. A creation date can be added later by the caller (`PdfInfo.created`) where byte identity across machines does not matter.
