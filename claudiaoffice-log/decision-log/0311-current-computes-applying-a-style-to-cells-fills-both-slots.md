---
id: D311
title: "Applying a style to cells fills both of their slots with the one bundle"
status: current
applies-to: computes
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D311 · Applying a style to cells fills both of their slots with the one bundle

**Applying a style to cells points both of their slots — the box (Box) and the words (Paragraph + Text), D304, D307 — at the one named style.** Each slot reads only its own facets, so for the person a cell takes a style exactly as a composes paragraph does. "Change the box only" in the editor deviates the box slot alone (D309), and only then do a cell's two slots name different styles; the editor then says so ("Box: Total (changed) · Words: Total").

**Notes.** The alternative was two pickers, one for a cell's box and one for its words: more flexible, but a person names and picks two things for one purpose, which is what D62 and D309 avoid. `SetCellStyle` and the server's apply method take one style and fill both slots unless a slot is named. Confirmed by the owner on 2026-11-10.
