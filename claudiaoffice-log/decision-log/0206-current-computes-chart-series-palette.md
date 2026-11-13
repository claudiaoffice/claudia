---
id: D206
title: "Chart series use a fixed, validated categorical order — teal, iris, rose, chart-safe-apricot (`#13917F, #5B4BC4, #D6477A, #C97A33`) — and it is never…"
status: current
applies-to: computes
date: 2026-11-09
round: "Computes charts: the diagram/chart RPC surface and the Plotly UI (thirty-fourth round)"
supersedes: []
superseded-by: []
---

# D206 · Chart series use a fixed, validated categorical order — teal, iris, rose, chart-safe-apricot (`#13917F, #5B4BC4, #D6477A, #C97A33`) — and it is never…

**Chart series use a fixed, validated categorical order — teal, iris, rose, chart-safe-apricot (`#13917F, #5B4BC4, #D6477A, #C97A33`) — and it is never reordered or cycled.** `claudia_computes.charts.BAR_COLORS`. Run through the dataviz skill's own `validate_palette.js`: this exact order passes lightness band, chroma floor, adjacent-pair CVD separation (worst pair ΔE 10.2 deutan / 8.3 tritan), the normal-vision floor (ΔE 16.1) and contrast against the light surface `#fcfcfb`; two other orderings of the same four colours (iris first, and iris/apricot/teal/rose) both failed CVD separation on the same adjacent pair. A fifth series folds into "Other" rather than generating a fifth hue (the skill's non-negotiable rule); a single-series chart shows no legend (the chart's own title already names it).

**Notes.** The skill's validator was actually run, not eyeballed — color is "computable, so compute it" is the skill's own rule, and the first two orderings tried genuinely failed before the third passed. Not yet re-validated against a dark surface, since the suite has no dark mode wired up for computes yet (tracked under the Menus/dark-mode open question below); worth a look together once that lands, not blocking here.
