---
id: D132
title: "A document's own default ink (stored as black, however written) is swapped for the page's own text colour at display time only, never in the stored style"
status: current
applies-to: all
date: 2026-11-06
round: "Menu redesign and accessibility baseline (nineteenth round)"
supersedes: []
superseded-by: []
---

# D132 · A document's own default ink (stored as black, however written) is swapped for the page's own text colour at display time only, never in the stored style

**A document's own default ink (stored as black, however written) is swapped for the page's own text colour at display time only, never in the stored style.** Applies wherever a style's computed CSS reaches the page — composes' paragraphs and creates' text/shape objects alike.

**Notes.** Owner's framing: "in the document they would count as black obviously" — typed text was unreadable, black-on-near-black, in dark mode because a style's stored `color` always overrides the container's theme-aware default. Chosen (over a document-wide black→ink-token migration, which would have changed stored data) via `AskUserQuestion`. Web client only, per the owner's choice; GTK has no document rendering of its own to fix.
