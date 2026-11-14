---
id: D287
title: "Search & replace: open questions"
status: undecided
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D287 · Search & replace: open questions

**Open, none blocks the first version in computes.** (1) Panel placement: floating over the document (D282) or a bar above it for the quick path only. (2) Python `re` or the `regex` package (D284); whether a typed pattern may use look-behind and back-references. (3) Whether **Values** means the raw value or the formatted text shown (E6.14, number and date formats). (4) Which more things computes searches: sheet names, names and tables (D600–D609), chart titles, floating text objects, cell styles by name. (5) **Accent-insensitive** matching, and the default for Match case (proposed: off, as in Excel). (6) **Saved searches** and a history of recent ones. (7) Searching across documents, which would cross the privacy boundary of D72 and is not proposed. (8) Replace in composes while others type: matches move; proposed to stand on the n-word lock zone (D11) and to skip a match whose text changed. (9) The shortcut for Replace on macOS, which the platform has on Cmd+Option+F.

**Notes.** Written 2026-11-13 with D281–D286. (2) is answered by D288: `regex` runs patterns, `re` reads them, so look-behind is fixed-width and back-references are allowed as in Python. The rest is still open.
