---
id: D909
title: "How text is poured into pages"
status: current
applies-to: all
date: 2026-11-12
round: "Pages, print preview and PDF (branch layouting)"
supersedes: []
superseded-by: []
---

# D909 · How text is poured into pages

**A page holds whole lines only. A paragraph leaves at least two lines at the foot of a page and carries at least two to the next (orphans and widows), or moves whole; a paragraph taller than a page is split where it must be. A title or heading (a style that is, or is based on, `title`, `heading-1`, `heading-2`) moves to the next page when the first lines of the next paragraph would not fit beside it. The space between two paragraphs is the larger of the one's space below and the next's space above (as CSS collapses margins), and at the top of a page it is dropped.** A paragraph's background and borders are cut at a page break, without a border along the cut. Justified lines stretch their spaces in whole mpt, at most three times their width; a looser line stays ragged. A word wider than a line is broken between its letters. There is no hyphenation yet.

**Notes.** These are the flow rules of `layout/src/flow/paginate.ts` and `text/paragraph.ts`, written down so that a change to them is a decision (and a new `LAYOUT_VERSION`, which every display list carries). Lines are broken at the opportunities of the Unicode line breaking algorithm (UAX #14), so no break is allowed before a slash or a closing bracket. Spaces are kept as typed (as the editor shows them, `white-space: pre-wrap`).
