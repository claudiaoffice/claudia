// A workbook as the layout library's `layoutSheet` reads it (E6.19, D1001–D1009): the cells as they are shown (through
// their number formats and styles), the sizes of rows and columns, the floating pictures and charts, and how each
// sheet prints. Everything comes from the session; what is not loaded yet is loaded first (`loadForPrint`).
import { utf8Decode, type CellArea, type CellPurpose, type ImageInfo, type PrintedChart, type PrintedSheet, type SheetCell, type SheetDocument, type SheetPicture, type TextStyle } from '@claudia/layout'
import { showFormatted } from '../cells'
import { cellLook, styleAt, within, type CellLook, type CellRange } from '../cell-styles'
import { formatCodeOf, inkOf, symbolsFor } from '../number-format'
import { tableAt } from '../names'
import { currentLocale } from '../locale'
import type { Session } from '../session'
import { fromBase64 } from './document'
import { DEFAULT_PAGE } from './setup'
import { DEFAULT_SHEET_PRINT_DATA, layoutPrint, type Contents, type SheetPrintData } from './sheet'

/** The most cells of a sheet looked at for what they show (a sheet printed whole has its used range, never more). */
const MAX_PRINTED_CELLS = 400_000
/** A chart tab's picture: only its shape counts, it is scaled to the page (D1008). */
const CHART_W = 640
const CHART_H = 400

/** What the person asked the preview to print. */
export interface SheetRequest {
  contents: Contents
  /** the sheet or chart tab that is shown in the window */
  shown: { kind: 'sheet' | 'chart'; id: string }
  /** the selected cells of the shown sheet: first row, first column, last row, last column */
  selection: [number, number, number, number] | null
}

/** A chart as an SVG picture, by the id of its definition; `null` where one cannot be made (a server without the
 * figure, a browser without the chart library). */
export type ChartPictures = (spec: string, w: number, h: number) => Promise<string | null>

/** The id a chart's picture has among the document's images. */
export const chartImage = (spec: string): string => `chart:${spec}`

/** The sheets and chart tabs the request prints, in tab order: sheets first, then charts. */
export function printedIds(session: Session, request: SheetRequest): { kind: 'sheet' | 'chart'; id: string }[] {
  const { sheets, charts } = session.state
  if (request.contents === 'workbook') return [...sheets.map((s) => ({ kind: 'sheet' as const, id: s.id })), ...charts.map((c) => ({ kind: 'chart' as const, id: c.id }))]
  const known = request.shown.kind === 'sheet' ? sheets.some((s) => s.id === request.shown.id) : charts.some((c) => c.id === request.shown.id)
  return known ? [request.shown] : []
}

/** The charts a request prints, by the id of their definition, with the size (in CSS pixels) each is drawn at: a floating
 * chart at its own, a chart tab at the size of a page's worth (D1008). */
export function chartSizes(session: Session, request: SheetRequest): Map<string, [number, number]> {
  const sizes = new Map<string, [number, number]>()
  for (const { kind, id } of printedIds(session, request)) {
    if (kind === 'chart') {
      const spec = session.state.charts.find((c) => c.id === id)?.spec_id
      if (spec && !sizes.has(spec)) sizes.set(spec, [CHART_W, CHART_H])
    } else {
      for (const o of session.objectsOn(id)) if (o.kind === 'diagram' && o.diagram && !sizes.has(o.diagram)) sizes.set(o.diagram, [o.w, o.h])
    }
  }
  return sizes
}

/** Load what printing needs of the sheets it prints: their sizes, their style ranges and all their cells. */
export async function loadForPrint(session: Session, request: SheetRequest): Promise<void> {
  const ids = printedIds(session, request).filter((p) => p.kind === 'sheet')
  await Promise.all(
    ids.map(async ({ id }) => {
      const info = session.state.sheets.find((s) => s.id === id)
      await Promise.all([session.ensureSizes(id), session.ensureCellStyles(id), info && info.rows > 0 && info.cols > 0 ? session.ensure(id, 0, info.rows - 1, 0, info.cols - 1) : Promise.resolve()])
    }),
  )
}

/** The setup of a sheet or chart tab, the server's or the default. */
export const setupOf = (session: Session, id: string): SheetPrintData => session.state.sheetPrint[id] ?? DEFAULT_SHEET_PRINT_DATA

/** Where on a sheet a selection lies, as the layout library says it. */
const areaOf = ([r0, c0, r1, c1]: [number, number, number, number]): CellArea => ({ row0: Math.min(r0, r1), col0: Math.min(c0, c1), row1: Math.max(r0, r1), col1: Math.max(c0, c1) })

/** The text styles of the document, and one more for every box/words pair that cells use: a cell has two (D311), the
 * layout library one, so the pair is merged the way the grid paints it. */
class CellStyles {
  readonly merged = new Map<string, TextStyle>()
  private looks = new Map<string, CellLook>()

  constructor(private readonly session: Session) {}

  /** The look of a cell, and the id of the merged text style that prints it (none for Body text, which cells without a
   * style of their own take anyway). `ink` is the colour its number format asks for (`[Red]`, D378). */
  look(box: string, words: string, kind: string | undefined, ink: string | null): { id: string | undefined; look: CellLook } {
    const key = `${box}|${words}|${kind ?? ''}`
    let look = this.looks.get(key)
    if (!look) this.looks.set(key, (look = cellLook(this.session.state.styles, this.session.state.styleModel?.facets, box, words, kind)))
    if (box === 'body-text' && words === 'body-text' && ink === null) return { id: undefined, look }
    const id = `cell:${box}|${words}${ink ? `|${ink}` : ''}`
    if (!this.merged.has(id)) {
      const resolved = { ...look.words, ...look.box, 'vertical-align': look.valign, ...(look.wrap ? { 'white-space': 'normal' } : {}), ...(ink ? { color: ink } : {}) }
      this.merged.set(id, { id, based_on: null, resolved })
    }
    return { id, look }
  }
}

function cellsOf(session: Session, id: string, area: CellArea | null, purposes: boolean, styles: CellStyles): SheetCell[] {
  const state = session.state
  const info = state.sheets.find((s) => s.id === id)
  const ranges: readonly CellRange[] = session.cellStyles(id)
  const r1 = Math.max((info?.rows ?? 0) - 1, area?.row1 ?? -1)
  const c1 = Math.max((info?.cols ?? 0) - 1, area?.col1 ?? -1)
  const row0 = area?.row0 ?? 0
  const col0 = area?.col0 ?? 0
  const rowEnd = area ? area.row1 : r1
  const colEnd = area ? area.col1 : c1
  const named = purposes ? state.names.filter((n) => n.region?.sheet === id) : []
  const symbols = symbolsFor(currentLocale())
  const codes = new Map<string, string | null>()
  const out: SheetCell[] = []
  let looked = 0
  for (let row = row0; row <= rowEnd; row++) {
    const near = ranges.length ? within(ranges, row, col0, row, colEnd) : []
    for (let col = col0; col <= colEnd; col++) {
      const content = session.cell(id, row, col)
      if (content === null && near.length === 0 && !named.length) continue // nothing there to show (the common case, fast)
      if (++looked > MAX_PRINTED_CELLS) return out
      const box = near.length ? styleAt(near, row, col, 'box').style : 'body-text'
      const words = near.length ? styleAt(near, row, col, 'words').style : 'body-text'
      if (!codes.has(words)) codes.set(words, formatCodeOf(state.styles, state.numberFormats, words))
      const shown = showFormatted(content, codes.get(words) ?? null, symbols)
      const { id: style, look } = styles.look(box, words, content?.t, inkOf(shown.colour))
      const purpose = named.length ? purposeOf(state.names, id, row, col) : undefined
      if (content === null && look.plain && purpose === undefined) continue
      out.push({ row, col, text: shown.text, align: look.align === 'justify' ? 'left' : look.align, ...(style ? { style } : {}), ...(purpose ? { purpose } : {}) })
    }
  }
  return out
}

/** What a cell is for, from the name whose cells hold it (E6.5): the layout tints inputs, calculations and results. */
function purposeOf(names: Session['state']['names'], sheet: string, row: number, col: number): CellPurpose | undefined {
  const found = tableAt(names, sheet, row, col)?.purpose
  return found === 'input' || found === 'calc' || found === 'result' ? found : undefined
}

function picturesOf(session: Session, sheet: string, pictures: ReadonlyMap<string, string>): SheetPicture[] {
  return session.objectsOn(sheet).flatMap((o): SheetPicture[] => {
    const anchor = { kind: 'cell' as const, row: o.anchor.row, col: o.anchor.col }
    const base = { id: o.id, kind: o.kind, w: o.w, h: o.h, style: o.style, paragraph: o.paragraph ? { style: o.paragraph.style, text: o.paragraph.text } : null, shape: o.shape, image: o.image, rotation: o.rotation, anchor }
    if (o.kind === 'diagram') return [{ ...base, kind: 'diagram', image: o.diagram && pictures.has(o.diagram) ? chartImage(o.diagram) : null }]
    // a rendered text container (D390) prints as the picture it shows; one nothing has drawn a picture for yet is left out
    if (o.kind === 'rendered') return o.image ? [{ ...base, kind: 'image' }] : []
    return [base as SheetPicture]
  })
}

/** The workbook as the layout library reads it. `charts` holds the SVG pictures made of the charts that are printed,
 * by the id of their definition (`chartsPrinted`). */
export function sheetDocument(session: Session, request: SheetRequest, charts: ReadonlyMap<string, string> = new Map()): SheetDocument {
  const state = session.state
  const styles = new CellStyles(session)
  const printed: (PrintedSheet | PrintedChart)[] = []
  for (const { kind, id } of printedIds(session, request)) {
    const setup = setupOf(session, id)
    if (kind === 'chart') {
      const chart = state.charts.find((c) => c.id === id)!
      printed.push({ kind: 'chart', id, name: chart.name, image: charts.has(chart.spec_id) ? chartImage(chart.spec_id) : null, w: CHART_W, h: CHART_H, orientation: setup.orientation })
      continue
    }
    const info = state.sheets.find((s) => s.id === id)!
    const area = request.contents === 'selection' && request.selection && request.shown.id === id ? areaOf(request.selection) : null
    printed.push({
      kind: 'sheet',
      id,
      name: info.name,
      area,
      cells: cellsOf(session, id, area, setup.purposes, styles),
      colWidths: [...(state.colWidths[id] ?? [])].sort((a, b) => a[0] - b[0]),
      rowHeights: [...(state.rowHeights[id] ?? [])].sort((a, b) => a[0] - b[0]),
      objects: picturesOf(session, id, charts),
      print: layoutPrint(setup),
    })
  }
  const images: ImageInfo[] = [
    // an SVG picture is drawn from its text (D914); the others from their bytes
    ...Object.values(state.images).map((i) => ({ id: i.id, format: i.format, ...(i.format === 'svg' ? { svg: utf8Decode(fromBase64(i.data)) } : {}) })),
    ...[...charts].map(([spec, svg]) => ({ id: chartImage(spec), format: 'svg', svg })),
  ]
  return {
    sheets: printed,
    styles: [...Object.values(state.styles).map((s) => ({ id: s.id, based_on: s.based_on, resolved: s.resolved })), ...styles.merged.values()],
    images,
    page: state.printPage ?? DEFAULT_PAGE,
    language: state.language ?? null,
  }
}
