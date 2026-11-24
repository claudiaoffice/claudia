---
id: D1476
title: "The chart slice of E1.18: the object kind, the definition, the asset kind, the stored key, the wire and the web say chart; the id of a chart's definition is `chart` on the wire, as a container's is `container`"
status: current
applies-to: all
date: 2026-11-24
round: "E6.31 Slides in computes, step 4 (branch e6-31-slides-in-computes)"
supersedes: []
superseded-by: []
---

# D1476 · The chart names of E1.18

The chart slice waited (D1433) until the chart tabs were gone (E6.31 step 3, D1475), so that `charts` was free. The
owner agreed the list below on 2026-11-24, by the rule of D1433. Names only, no change of behaviour; stored names change
outright, without an upgrade of older documents (D1430, E1.16).

| Where | Before | After |
|---|---|---|
| Core | object kind `diagram`, `DiagramDefinition`, asset kind `DIAGRAM` | `chart`, `ChartDefinition`, `CHART` |
| Core | `ObjectModel.diagrams`, stored key `diagrams`, event `diagram` | `charts`, `charts`, `chart` |
| Core | `ObjectBody.diagram`, `diagram_from_data`, `blank_diagram`, `_check_diagram_visual` | `.chart`, `chart_from_data`, `blank_chart`, `_check_chart_visual` |
| Core | the style slot key `diagram`, the history label "Add diagram" | `chart`, "Add chart" |
| Core | `testing.diagram_object` | `chart_object` |
| computes | `WorkbookModel.diagram_from_data`, `blank_diagram`; state schema 18 | `chart_from_data`, `blank_chart`; schema 19 |
| Server | `diagrams`, `define_diagram`, `update_diagram`, `forget_diagram` | `charts`, `define_chart`, `update_chart`, `forget_chart` |
| Server | `chart_figure(diagram)`; the answer key `diagram` of `define_…` and `insert_chart` | `chart_figure(chart)`; `chart` |
| Server | "this document does not know the diagram {id}"; `free_name("diagram")`; the kind in `thing_names`, `slide_lens`, `shape_methods` | "… the chart {id}"; `free_name("chart")`; `chart` |
| Web | `state.diagrams`, `updateDiagram`, `forgetDiagram`, `diagramId` | `state.charts`, `updateChart`, `forgetChart`, `chartId` |
| Web | the object kind `'diagram'`, the class `.obj.diagram` | `'chart'`, `.obj.chart` |
| Layout | `ObjectKind` `'diagram'`, `diagramNote` | `'chart'`, `chartNote` |
| Files | creates-io's loss `diagram` (odp) | `chart` |

**The id of a chart's definition on the wire is `chart`** (Q2): `insert_chart` answers `{object, slide, chart}`, where
`object` is the chart object and `chart` the id of its definition, as `add_container` answers `{object, container}`.

**Kept:** computes' `ChartSpec` (D1430: it is computes' `ChartDefinition`) and `NewChart.spec_id`; "Diagramm", the
German word for a chart; "diagram" for a Mermaid diagram (a container), for a drawing in Word, and for what a diagram's
style sheet gives in `rasterise`, `raster`, `pptx` and `claudia-typeset`; `diagram` among the legacy pointer fields of
an object body (`_LEGACY_POINTERS`, `testing.body_before_ref`), the name old bodies were written with, as `rendered`; the help on the tools behind containers; and
the history (changelogs, decisions, notes, stories).
