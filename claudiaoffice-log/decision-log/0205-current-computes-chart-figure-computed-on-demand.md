---
id: D205
title: "A chart's Plotly figure is computed by the server on demand and never pushed or cached server-side; the client re-asks after a `cells` event whose positions…"
status: current
applies-to: computes
date: 2026-11-09
round: "Computes charts: the diagram/chart RPC surface and the Plotly UI (thirty-fourth round)"
supersedes: []
superseded-by: []
---

# D205 · A chart's Plotly figure is computed by the server on demand and never pushed or cached server-side; the client re-asks after a `cells` event whose positions…

**A chart's Plotly figure is computed by the server on demand and never pushed or cached server-side; the client re-asks after a `cells` event whose positions touch the diagram's own range.** `WorkbookModel.chart_figure(diagram_id)` reads the diagram's sheet live through `Sheet.view` and rebuilds the figure fresh on every `chart_figure` RPC call — nothing about a figure is persisted. The web client caches the answer per diagram (`Session.state.figures`) until something invalidates it: the diagram's own definition changing (`diagram` event, any placement), or a `cells` event whose `positions` fall inside the diagram's range on its sheet (`rangeTouchedBy`, checked against every cached figure regardless of which sheet is on screen, since a chart tab may be showing data from a sheet that is not the active one).

**Notes.** Considered and rejected a server-push design (the server recomputing and broadcasting a figure on every relevant cell edit) as needless work on every keystroke for a figure that may not even be on screen; considered and rejected baking Plotly-figure construction into the event payload itself, which would have coupled `claudia_computes.events` to a charting library's JSON shape. A pull-based cache that self-invalidates on the same fine-grained `cells` event positions the grid already uses keeps the figure one request away without the server tracking who is watching what.
