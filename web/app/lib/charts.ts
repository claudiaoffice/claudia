// Charts (E6.6): a diagram definition (`claudia_computes.ChartSpec`) shown by a chart, an object on a sheet or a slide
// (E6.31, D1475) — the client half of the shared object layer's `diagram` kind (`lib/objects.ts`). Plotly itself (the chart library, D33/D42) is only loaded by the
// component that actually draws a figure; this module is just the wire shapes and the range-building helper,
// so it costs nothing to import from code that only lists or edits definitions.

/** One corner of a chart's range: always on a named sheet (unlike a formula, a definition has no "current
 * sheet" to default to — `claudia_computes.charts`'s own module docstring says why). */
export interface ChartCellRef {
  row: number
  col: number
  sheet: string
}
export interface ChartRange {
  first: ChartCellRef
  last: ChartCellRef
}

/** A cell range as `insertChart`/`updateDiagram` want it, from two corners in any order. */
export function chartRange(sheet: string, r0: number, c0: number, r1: number, c1: number): ChartRange {
  const ref = (row: number, col: number): ChartCellRef => ({ row, col, sheet })
  return { first: ref(Math.min(r0, r1), Math.min(c0, c1)), last: ref(Math.max(r0, r1), Math.max(c0, c1)) }
}

/** The fields a person edits in the insert/properties dialog; `insertChart`/`updateDiagram` add `kind` (bar
 * only so far, E6.6) and send this straight on — the id and format are the server's to assign (`computes.py`). */
export interface ChartDraft {
  /** The cells to draw — or, instead, `source` names a table or query result to follow (E6.5): one of the two. */
  range?: ChartRange
  /** The name of a named range, table or `SQL()` result the chart reads live, and `source_scope` the sheet it is
   * scoped to (`null` for a workbook-wide name). */
  source?: string
  source_scope?: string | null
  series_in: 'columns' | 'rows'
  /** Whether the range's first row is a header (the series' names, or the category labels when `series_in` is
   * "rows") rather than a row of data like every other — on by default, matching the usual "select your data
   * including its headers", but turned off reads every row as data (the header-row bug reported after the
   * first round: a 2-column, 3-row range of plain category/value pairs with no header line of its own used to
   * silently lose its first row). Has no column equivalent yet — only the row convention needed one in
   * practice; the first column still goes by the range's own shape, same as it always has. */
  header_row: boolean
  title: string
  x_title: string
  y_title: string
  legend: boolean
  gridlines: boolean
}

/** A chart definition as the server stores and sends it (`diagrams`, the `diagram` event) — a `ChartDraft` plus
 * the id and format it was given. Not itself placed anywhere: a chart object (`ObjectBody.diagram`) shows it. */
export interface ChartSpec extends ChartDraft {
  format: number
  id: string
  kind: 'bar'
}

/** A chart's Plotly figure (`chart_figure`'s answer): `data` is one trace per series, `layout` the titles,
 * legend and gridlines — built once by the server from a `ChartSpec` plus its sheet's live cells, so every
 * client draws the same picture (`e0-3-web-surface-notes.md`). Loosely typed on purpose: this module does not
 * otherwise know Plotly's own types, and a figure is handed to `Plotly.newPlot` exactly as it arrives. */
export interface ChartFigure {
  data: Record<string, unknown>[]
  layout: Record<string, unknown>
}

/** Where a chart view gets its figure (computes' session): the one at hand, and asking for it. */
export interface ChartFigures {
  /** The cached figure of a definition, or `null` while it has not come yet. */
  figureOf(diagramId: string): ChartFigure | null
  /** Ask for a definition's figure, unless it is at hand; with `force`, ask again. */
  ensureFigure(diagramId: string, force?: boolean): Promise<void>
}

/** Whether a sheet's changed positions could change a diagram's own figure: same sheet, and at least one
 * position inside its range. Used to decide whether a `cells` push event invalidates a cached figure (session's
 * own `onAppEvent`), mirroring how `claudia_server.computes`'s `chart_figure` docstring tells a client when to
 * ask again. */
export function rangeTouchedBy(range: ChartRange, sheet: string, positions: [number, number][]): boolean {
  if (range.first.sheet !== sheet) return false
  const { first, last } = range
  return positions.some(([r, c]) => r >= first.row && r <= last.row && c >= first.col && c <= last.col)
}
