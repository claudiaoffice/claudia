---
id: D204
title: "A chart definition (`ChartSpec`, a `diagram` in the shared object layer, D177) is defined once and placed separately — never bundled into one call the way…"
status: current
applies-to: computes
date: 2026-11-09
round: "Computes charts: the diagram/chart RPC surface and the Plotly UI (thirty-fourth round)"
supersedes: []
superseded-by: []
---

# D204 · A chart definition (`ChartSpec`, a `diagram` in the shared object layer, D177) is defined once and placed separately — never bundled into one call the way…

**A chart definition (`ChartSpec`, a `diagram` in the shared object layer, D177) is defined once and placed separately — never bundled into one call the way `add_image` bundles decoding and anchoring.** `define_diagram` takes the draft (range, `series_in`, titles, legend, gridlines) and hands back a server-assigned id; the client rejects supplying its own `id`/`format`. `add_chart` (a tab) and `add_diagram_object` (a floating object) each take that id and place it, and either or both may be called from the very same definition, matching the mock's "both tab and floating object" decision from the start rather than as a later addition. `update_diagram` redefines in place (every placement updates together); `forget_diagram` refuses while any placement still shows it (`"diagram {id!r} is in use by {user!r}"`), so a definition cannot be pulled out from under a tab or object that names it. `claudia_server.computes` gained nine new RPC methods for this (`diagrams`, `charts`, `chart_figure`, `define_diagram`, `update_diagram`, `forget_diagram`, `add_diagram_object`, `add_chart`, `remove_chart`); `move_object`/`resize_object`/`rotate_object`/`remove_object` needed no change at all, being already generic by object id regardless of kind.

**Notes.** Settled while building the next round of E6.6 against the shared object layer PR #18 merged onto `computes-plotting`. Rejected an image-like bundled call because a chart, unlike an image, is explicitly meant to be shown more than one way from the moment it is made — bundling "define" and "place" would have forced a fake first placement just to get an id. Id assignment mirrors `add_sheet` (server-assigned, fresh every time) rather than an image's content-hash id or a shape's fixed library id, because two otherwise-identical chart definitions are still distinct: editing one later must not silently change the other.
