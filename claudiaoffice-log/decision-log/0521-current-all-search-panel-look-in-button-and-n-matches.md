---
id: D521
title: "The search panel: one "Look in" button with a checklist, real buttons for Replace and the pattern builder, "n matches", beside the dock"
status: current
applies-to: all
date: 2026-11-15
round: "The search panel and movable dialogs (branch `search-ui`)"
supersedes: []
superseded-by: []
---

# D521 · The search panel: one "Look in" button with a checklist, real buttons for Replace and the pattern builder, "n matches", beside the dock

**Decision.** The quick path of the panel (D282) is a find field, then one row with a **Look in** button and the scope list ("The whole text", "This sheet", …), then the two checkboxes (Match case, Whole text or cell), then two **buttons**, "Replace with… ›" and "Build a pattern…", with more space above the line of matches. The Look-in button says what is on: "Everything (5)", the names when one or two kinds are on ("Text, Headings (2)"), "3 of 5 kinds", or "Nothing"; it opens a list with one checkbox for each kind and the number of matches it has, 🔒 instead of the number for a kind that cannot be replaced while Replace is open (Values in computes, D285), and All and None at the bottom. The line of matches says **"n matches"**. Only computes adds "in m cells", and only when the matches are in fewer cells than their number: a person thinks of a text document as one text and of a presentation as a slide, not as "x texts". The panel sits beside the History and chat dock (never over it), so what the Help tab shows is not hidden by it; with the dock closed it is at the window's edge.

**Notes.** Amends D282 (placement and the quick path); nothing else of it changes. The five switches took most of the panel's height and made the quick path look like a form; one button keeps what is searched visible in one line and the details one click away. Reported by the owner on the composes panel, 2026-11-15 ("in x texts is confusing"; the links were too small and too close to the count). Rejected: a plain drop-down with a single choice (a search often needs two of five kinds) and removing the counts (they tell why a match is missing). Code: `lookInSummary` and `matchSummary` in `web/app/lib/search.ts` (tested), `SearchPanel.vue`. The German wordings are "Alles (5)", "Alle", "Keine", "{count} von {total} Arten".
