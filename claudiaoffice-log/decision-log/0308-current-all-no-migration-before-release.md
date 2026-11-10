---
id: D308
title: "No migration of old documents before the first release"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D308 · No migration of old documents before the first release

**Until the first release, a change to the style model does not have to read documents written by an earlier version.** The model of this round may therefore change what is stored in a `StyleDef`, an `ObjectBody` and the built-in styles without upcasting. The change is recorded in `CHANGELOG.md` for each package it touches.

**Notes.** Narrows D21 (command schemas are versioned and an old document is upcast, never broken) for this period only; from the first release D21 applies without exception. Said by the owner on 2026-11-10: the product is pre-release, so migration of old documents is not important now. The remaining cost is not a migration but a real change: the built-in `plain-shape` is split into an outline style and a shape-label paragraph style (D310).
