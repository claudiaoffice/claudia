/**
 * A computes workbook, as the client holds it, laid out on pages (D1009): every sheet cut into pages by rows and
 * columns, a slide on a page of its own. Pure, like the composes and creates adapters: the caller fetches the
 * fonts {@link sheetFontsNeeded} names first.
 *
 * What is printed is already decided when it gets here. The caller says which sheets, and for each sheet which cells
 * (as they are shown, with their style and what they are for), how wide and high its columns and rows are, which area
 * (the print area, the selection, or none: the used range), and how it prints (D1004). The workbook's page (paper,
 * margins, page numbers) is shared by every sheet; each sheet lies as it likes.
 *
 * **Cuts** (D1005). A sheet is cut automatically only: a row or a column starts a new page where the next one no longer
 * fits at the chosen scale, and a row or column taller or wider than a page gets a page to itself and is cut at the
 * page's edge. Rows and columns marked to repeat are drawn again at the top and left of every page that starts after
 * them. A page with nothing on it is left out unless the sheet says otherwise.
 *
 * **Scale** (D1002). `fit-width` shrinks the sheet until its columns fill the page's width, never enlarges it;
 * `fit-page` shrinks it until one page holds it; `percent` is taken as it is. Nothing is printed smaller than 10 %.
 *
 * **Drawing.** A cell is a box of its column's width and its row's height, drawn through the shared text layout: its
 * style gives font, colour, background and borders; text that does not fit runs on over the empty cells to its right
 * (left-aligned text only) and is cut at the first cell with something in it or at the page's edge. Everything of a
 * page sits in one group that scales it and cuts it at the sheet's edge, so a display list reads the same on screen
 * and in the PDF.
 *
 * @module
 */
import { type DisplayItem, type DisplayList, type DisplayPage, type GroupItem, type PathOp, type Rect, rectPath, walk } from '../display/list'
import { decorationItems, lineItems } from '../display/text'
import { contentBox, type Orientation, type PageGeometry, pageGeometry } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import type { FontResolver } from '../fonts/resolve'
import { type BoxDecoration, NO_DECORATION } from '../text/css'
import { type BoxLayout, layoutBox } from '../text/box'
import { layoutParagraph } from '../text/paragraph'
import { paragraphStyle, type ParagraphStyle, type Rgba } from '../text/style'
import { LAYOUT_VERSION } from '../version'
import { drawSlide, placedSlide, slideFrame, type SlideObject } from './slides'
import {
  cssOf,
  drawObject,
  type ImageInfo,
  muted,
  type Note,
  objectFonts,
  type ObjectContext,
  PAGE_NUMBER_BAND,
  PAGE_NUMBER_SIZE,
  type PageSetupData,
  px,
  type ShapeOutline,
  styleFont,
  Styles,
  type TextStyle,
  type VisualObject,
} from './objects'

export type { ImageInfo, Note, PageSetupData, ShapeOutline, TextStyle } from './objects'

/** A zero-based rectangle of cells, both ends included. */
export interface CellArea {
  row0: number
  col0: number
  row1: number
  col1: number
}

/** What a cell is for (E6.5 purposes): the tint it gets when the sheet asks for tints (D1007). */
export type CellPurpose = 'input' | 'calc' | 'result'

/**
 * A cell as it is shown: its text already formatted by its number format. `style` is the text style (the resolved CSS
 * of `styles`: font, colour, background, borders, padding); `align` is the alignment the cell shows (numbers to the
 * right), or the style's when missing.
 */
export interface SheetCell {
  row: number
  col: number
  text: string
  align?: 'left' | 'right' | 'center'
  style?: string
  purpose?: CellPurpose
}

/** A picture or a chart on a sheet: the shared object body, pinned to a cell. A chart is printed as the SVG picture the
 *  client made of it, named by `image` (D1008). */
export interface SheetPicture extends VisualObject {
  anchor: { kind: 'cell'; row: number; col: number }
}

export type SheetScale = { kind: 'fit-width' } | { kind: 'fit-page' } | { kind: 'percent'; percent: number }

/** How one sheet prints (D1004). Rows and columns are zero-based, both ends included. */
export interface SheetPrint {
  orientation: Orientation
  scale: SheetScale
  order: 'down-then-across' | 'across-then-down'
  repeatRows: readonly [number, number] | null
  repeatCols: readonly [number, number] | null
  gridlines: boolean
  /** row numbers and column letters */
  headings: boolean
  /** tint cells by what they are for (D1007) */
  purposes: boolean
  /** the sheet's name at the left of the footer (D1006) */
  footerName: boolean
  /** pictures and charts */
  objects: boolean
  /** leave out pages with nothing on them */
  skipEmpty: boolean
}

/** A sheet that prints as it is on the server: portrait, fit to width, down then across, gridlines and headings off. */
export const DEFAULT_SHEET_PRINT: SheetPrint = {
  orientation: 'portrait',
  scale: { kind: 'fit-width' },
  order: 'down-then-across',
  repeatRows: null,
  repeatCols: null,
  gridlines: false,
  headings: false,
  purposes: false,
  footerName: true,
  objects: true,
  skipEmpty: true,
}

/** A sheet to print: `area` is what the caller decided (print area, selection), `null` for the used range. Sizes are
 *  the sparse lists `[index, CSS pixels]` of the rows and columns that differ from the defaults (D135). */
export interface PrintedSheet {
  kind: 'sheet'
  id: string
  name: string
  area: CellArea | null
  cells: readonly SheetCell[]
  colWidths: readonly (readonly [number, number])[]
  rowHeights: readonly (readonly [number, number])[]
  /** CSS pixels: 96 for a column, 26 for a row when missing */
  defaultColWidth?: number
  defaultRowHeight?: number
  objects: readonly SheetPicture[]
  print: SheetPrint
}

/** A slide among the sheets (E6.31, D1473): one landscape page, the slide as large as the page takes it, drawn as
 * creates draws its slides. */
export interface PrintedSlide {
  kind: 'slide'
  id: string
  name: string
  objects: readonly SlideObject[]
}

export interface SheetDocument {
  /** what is printed, in order */
  sheets: readonly (PrintedSheet | PrintedSlide)[]
  styles: readonly TextStyle[]
  shapes?: readonly ShapeOutline[]
  images?: readonly ImageInfo[]
  /** the workbook's paper, margins and page numbers; each sheet says how it lies */
  page: PageSetupData
  /** BCP 47 language of the workbook, for shaping */
  language?: string | null
}

/** Where on the sheet a page's cells come from: for the preview's page map. `rows` and `cols` are `null` for a slide. */
export interface SheetPageInfo {
  sheet: string
  kind: 'sheet' | 'slide'
  rows: [number, number] | null
  cols: [number, number] | null
  /** the scale in millionths */
  scale: number
}

export interface SheetPages {
  list: DisplayList
  /** the first page's geometry (other sheets may lie the other way) */
  geometry: PageGeometry
  notes: Note[]
  /** image ids the display list draws */
  images: string[]
  embedded: Map<string, Uint8Array>
  /** one entry for every page of `list`, in the same order */
  pageMap: SheetPageInfo[]
}

// ---- constants ----------------------------------------------------------------------------------------------

/** The style cells without a style of their own take. */
const DEFAULT_STYLE = 'cell-text'
/** Space between a cell's border and its text, where the style gives none: 4 px. */
const CELL_INSET = px(4)
/** Row numbers' column and column letters' row, in the sheet's own measure (before scaling). */
const ROW_HEADING_W = px(40)
const COL_HEADING_H = px(22)
const DEFAULT_COL = 96
const DEFAULT_ROW = 26
const MAX_ROWS = 1_048_576
const MAX_COLS = 16_384
/** Scale limits, millionths: 10 % to 400 %. */
const MIN_SCALE = 100_000
const MAX_SCALE = 4_000_000
const ONE = 1_000_000
/** A sheet of more pages than this is cut off, with a note. */
const MAX_PAGES = 5000
const GRID: Rgba = { r: 208, g: 208, b: 208, a: 255 }
const HEADING_FILL: Rgba = { r: 240, g: 240, b: 240, a: 255 }
/** What cells are for, tinted as the grid shows them (design system). */
const TINTS: Record<CellPurpose, Rgba> = {
  input: { r: 0xfc, g: 0xe8, b: 0xcf, a: 255 },
  calc: { r: 0xed, g: 0xe8, b: 0xf7, a: 255 },
  result: { r: 0xd9, g: 0xee, b: 0xe9, a: 255 },
}

/** Column letters of a zero-based index: 0 → A, 25 → Z, 26 → AA, 16383 → XFD. */
export function columnLetters(index: number): string {
  let n = index + 1
  let s = ''
  while (n > 0) {
    const r = (n - 1) % 26
    s = String.fromCharCode(65 + r) + s
    n = Math.floor((n - 1) / 26)
  }
  return s
}

// ---- rows and columns -----------------------------------------------------------------------------------------

/**
 * The sizes along one axis: every index has the default size but a few. `offset(i)` is where index `i` starts, from
 * index 0, in mpt; both lookups take O(log n) in the number of exceptions.
 */
class Axis {
  private readonly at: number[] = []
  private readonly size_: number[] = []
  /** `delta[k]`: how much the first `k` exceptions add to the default sizes */
  private readonly delta: number[] = [0]

  constructor(
    private readonly fallback: number,
    custom: readonly (readonly [number, number])[],
    private readonly limit: number,
  ) {
    const sorted = new Map<number, number>()
    for (const [i, s] of custom) if (Number.isInteger(i) && i >= 0 && i < limit && Number.isFinite(s)) sorted.set(i, Math.max(0, px(s)))
    for (const i of [...sorted.keys()].sort((a, b) => a - b)) {
      this.at.push(i)
      this.size_.push(sorted.get(i)!)
      this.delta.push(this.delta.at(-1)! + sorted.get(i)! - fallback)
    }
  }

  private below(i: number): number {
    // exceptions with an index below `i`
    let lo = 0
    let hi = this.at.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (this.at[mid]! < i) lo = mid + 1
      else hi = mid
    }
    return lo
  }

  size(i: number): number {
    const k = this.below(i)
    return this.at[k] === i ? this.size_[k]! : this.fallback
  }

  offset(i: number): number {
    return this.fallback * i + this.delta[this.below(i)]!
  }

  /** The length of indices `a` to `b`, both included (0 when `b < a`). */
  span(a: number, b: number): number {
    return b < a ? 0 : this.offset(b + 1) - this.offset(a)
  }

  /** The index that holds position `pos` (mpt from the start), or the last index. */
  indexAt(pos: number): number {
    let lo = 0
    let hi = this.limit - 1
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (this.offset(mid + 1) > pos) hi = mid
      else lo = mid + 1
    }
    return lo
  }
}

/** The first index of `cells` (sorted by row) whose row is at least `row`. */
function firstFrom(cells: readonly SheetCell[], row: number): number {
  let lo = 0
  let hi = cells.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (cells[mid]!.row < row) lo = mid + 1
    else hi = mid
  }
  return lo
}

/** A sheet made ready: sorted cells, axes, the area and where the objects sit. */
interface Prepared {
  sheet: PrintedSheet
  cells: SheetCell[]
  rows: Axis
  cols: Axis
  area: CellArea | null
  /** objects to print, each drawn once in the sheet's own coordinates (mpt from A1) */
  objects: { rect: Rect; item: GroupItem }[]
}

interface Chunk {
  from: number
  to: number
  /** rows or columns drawn again before these: `[from, to]` */
  repeat: [number, number] | null
}

/** Rows or columns `first` to `last` cut into pages of `room` mpt, with the repeated ones drawn again after the first. */
function cut(first: number, last: number, room: number, axis: Axis, repeat: readonly [number, number] | null): Chunk[] {
  const out: Chunk[] = []
  let start = first
  while (start <= last && out.length < MAX_PAGES) {
    let rep: [number, number] | null = repeat && start > repeat[0] ? [repeat[0], Math.min(repeat[1], start - 1)] : null
    let repSize = rep ? axis.span(rep[0], rep[1]) : 0
    if (repSize >= room) {
      // no room left for the rows of the page itself: the repeated ones are not repeated
      rep = null
      repSize = 0
    }
    const free = room - repSize
    let end = start
    let used = axis.size(start)
    while (end < last && used + axis.size(end + 1) <= free) {
      end++
      used += axis.size(end)
    }
    out.push({ from: start, to: end, repeat: rep })
    start = end + 1
  }
  return out
}

/** One page of the plan: where its cells come from. */
interface PlannedPage {
  rows: Chunk
  cols: Chunk
}

/** Everything the drawing of one sheet needs besides the pages themselves. */
interface SheetPlan {
  prepared: Prepared
  geometry: PageGeometry
  box: Rect
  scale: number
  pages: PlannedPage[]
  footer: boolean
}

// ---- fonts ----------------------------------------------------------------------------------------------------

/** What a client's chart or picture is, for the shared object code, on a sheet or a slide: a chart with a picture is
 * drawn as that picture. */
const asDrawn = <O extends VisualObject>(o: O): O => (o.kind === 'chart' && o.image ? { ...o, kind: 'image' } : o)

/** The SHA-256 of every font file laying out `doc` needs, as `resolver` picks them. */
export function sheetFontsNeeded(doc: SheetDocument, resolver: FontResolver): string[] {
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const out = new Set<string>()
  const add = (id: string) => {
    const face = styleFont(cssOf(styles, id, DEFAULT_STYLE), resolver)
    if (face) out.add(face)
  }
  // headings, footers and cells without a style use the default one
  add(DEFAULT_STYLE)
  for (const s of doc.sheets) {
    if (s.kind !== 'sheet') continue
    for (const c of s.cells) if (c.style) add(c.style)
    if (s.print.objects) for (const h of objectFonts(s.objects.map(asDrawn), styles, doc.images ?? [], resolver, DEFAULT_STYLE)) out.add(h)
  }
  for (const s of doc.sheets) if (s.kind === 'slide') for (const h of objectFonts(s.objects, styles, doc.images ?? [], resolver, DEFAULT_STYLE)) out.add(h)
  return [...out].sort()
}

// ---- layout -----------------------------------------------------------------------------------------------------

/** Lay out `doc` as its sheets say. Every font {@link sheetFontsNeeded} names must be in `fonts`. */
export function layoutSheet(doc: SheetDocument, fonts: FontSet, resolver: FontResolver): SheetPages {
  const notes: Note[] = []
  const styles = new Styles(doc.styles, fonts, resolver, doc.language, DEFAULT_STYLE, notes)
  const embedded = new Map<string, Uint8Array>()
  const context: ObjectContext = {
    fonts,
    resolver,
    styles,
    shapes: new Map((doc.shapes ?? []).map((s) => [s.id, s])),
    images: new Map((doc.images ?? []).map((i) => [i.id, i])),
    notes,
    embedded,
    paragraphOptions: {},
    chartNote: 'the chart has no picture to print',
  }
  const base = styles.paragraph(DEFAULT_STYLE)
  const page = doc.page
  const margins = { top: page.margins[0], right: page.margins[1], bottom: page.margins[2], left: page.margins[3] }

  // ---- plan every sheet first: the footer's "n / N" needs the count
  const plans: (SheetPlan | { slide: PrintedSlide; geometry: PageGeometry; box: Rect })[] = []
  const geometries = new Map<Orientation, PageGeometry>()
  const geometryFor = (o: Orientation): PageGeometry => {
    let g = geometries.get(o)
    if (!g) {
      g = pageGeometry(page.width, page.height, o, margins)
      geometries.set(o, g)
    }
    return g
  }
  const boxOf = (g: PageGeometry, footer: boolean): Rect => {
    const box = contentBox(g)
    // room for the footer when the bottom margin has none
    if (footer && g.margin.bottom < PAGE_NUMBER_BAND) box.h -= PAGE_NUMBER_BAND - g.margin.bottom
    return box
  }
  let total = 0
  for (const s of doc.sheets) {
    if (s.kind === 'slide') {
      const geometry = geometryFor('landscape')
      plans.push({ slide: s, geometry, box: boxOf(geometry, true) })
      total++
      continue
    }
    const geometry = geometryFor(s.print.orientation)
    const footer = page.page_numbers || s.print.footerName
    const prepared = prepare(s, fonts, styles, context)
    const box = boxOf(geometry, footer)
    const plan = planSheet(prepared, geometry, box, footer, notes)
    plans.push(plan)
    total += plan.pages.length
  }

  // ---- draw
  const pages: DisplayPage[] = []
  const pageMap: SheetPageInfo[] = []
  const draw = { fonts, styles, context, base: base.style }
  for (const plan of plans) {
    if ('slide' in plan) {
      const placed = placedSlide(drawSlide(plan.slide.objects.map(asDrawn), context), plan.box)
      const p: DisplayPage = { width: plan.geometry.width, height: plan.geometry.height, items: [placed.group, slideFrame(placed.rect)] }
      footerItems(draw, p, plan.geometry, plan.geometry.margin.bottom, plan.slide.name, page.page_numbers, pages.length + 1, total)
      pages.push(p)
      pageMap.push({ sheet: plan.slide.id, kind: 'slide', rows: null, cols: null, scale: ONE })
      continue
    }
    for (const planned of plan.pages) {
      const p = drawSheetPage(plan, planned, draw)
      footerItems(draw, p, plan.geometry, plan.geometry.margin.bottom, plan.prepared.sheet.print.footerName ? plan.prepared.sheet.name : null, page.page_numbers, pages.length + 1, total)
      pages.push(p)
      pageMap.push({ sheet: plan.prepared.sheet.id, kind: 'sheet', rows: [planned.rows.from, planned.rows.to], cols: [planned.cols.from, planned.cols.to], scale: plan.scale })
    }
  }

  // nothing to print at all: one blank page, and a note, so there is something to show and to write
  if (pages.length === 0) {
    const first = doc.sheets[0]
    const g = geometryFor(!first ? page.orientation : first.kind === 'sheet' ? first.print.orientation : 'landscape')
    pages.push({ width: g.width, height: g.height, items: [] })
    pageMap.push({ sheet: doc.sheets[0]?.id ?? '', kind: 'sheet', rows: [0, 0], cols: [0, 0], scale: ONE })
    if (!notes.some((n) => n.kind === 'sheet')) notes.push({ kind: 'sheet', reason: 'there is nothing to print' })
  }

  const used: string[] = []
  for (const p of pages) for (const it of walk(p.items)) if (it.kind === 'image' && !used.includes(it.image)) used.push(it.image)
  return {
    list: { layoutVersion: LAYOUT_VERSION, shaper: fonts.shaperId, pages },
    geometry: { width: pages[0]!.width, height: pages[0]!.height, margin: { ...margins } },
    notes,
    images: used,
    embedded,
    pageMap,
  }
}

// ---- preparing a sheet -------------------------------------------------------------------------------------------

function prepare(sheet: PrintedSheet, fonts: FontSet, styles: Styles, context: ObjectContext): Prepared {
  const rows = new Axis(px(sheet.defaultRowHeight ?? DEFAULT_ROW), sheet.rowHeights, MAX_ROWS)
  const cols = new Axis(px(sheet.defaultColWidth ?? DEFAULT_COL), sheet.colWidths, MAX_COLS)
  const cells = sheet.cells
    .filter((c) => Number.isInteger(c.row) && Number.isInteger(c.col) && c.row >= 0 && c.col >= 0 && c.row < MAX_ROWS && c.col < MAX_COLS)
    .map((c) => ({ ...c, text: c.text.replace(/[\r\n\t]+/g, ' ') }))
    .sort((a, b) => a.row - b.row || a.col - b.col)

  // objects: each drawn once at its own place; a chart without a picture is only noted
  const objects: Prepared['objects'] = []
  if (sheet.print.objects) {
    for (const o of sheet.objects) {
      if (!Number.isInteger(o.anchor.row) || !Number.isInteger(o.anchor.col) || o.anchor.row < 0 || o.anchor.col < 0) continue
      const rect: Rect = { x: cols.offset(Math.min(o.anchor.col, MAX_COLS - 1)), y: rows.offset(Math.min(o.anchor.row, MAX_ROWS - 1)), w: px(o.w), h: px(o.h) }
      if (rect.w <= 0 || rect.h <= 0) continue
      const item = drawObject(asDrawn(o), rect, context)
      if (item) objects.push({ rect, item })
    }
  }

  const prepared: Prepared = { sheet, cells, rows, cols, area: null, objects }
  prepared.area = sheet.area ? normalised(sheet.area) : usedRange(prepared, fonts, styles)
  return prepared
}

function normalised(a: CellArea): CellArea {
  const clamp = (n: number, max: number) => Math.min(max - 1, Math.max(0, Math.trunc(n)))
  return {
    row0: clamp(Math.min(a.row0, a.row1), MAX_ROWS),
    row1: clamp(Math.max(a.row0, a.row1), MAX_ROWS),
    col0: clamp(Math.min(a.col0, a.col1), MAX_COLS),
    col1: clamp(Math.max(a.col0, a.col1), MAX_COLS),
  }
}

const hasContent = (c: SheetCell, purposes: boolean): boolean => c.text !== '' || c.style !== undefined || (purposes && c.purpose !== undefined)

/**
 * From A1 to the last cell with something in it or the last row and column a picture covers, and to the right as far as
 * the text of a row's last cell runs on. `null` when there is nothing.
 */
function usedRange(p: Prepared, fonts: FontSet, styles: Styles): CellArea | null {
  let maxRow = -1
  let maxCol = -1
  for (const c of p.cells) {
    if (!hasContent(c, p.sheet.print.purposes)) continue
    if (c.row > maxRow) maxRow = c.row
    if (c.col > maxCol) maxCol = c.col
  }
  for (const o of p.objects) {
    maxRow = Math.max(maxRow, p.rows.indexAt(o.rect.y + o.rect.h - 1))
    maxCol = Math.max(maxCol, p.cols.indexAt(o.rect.x + o.rect.w - 1))
  }
  if (maxRow < 0 || maxCol < 0) return null
  // text that runs on beyond the last column: only the last cell with text of a row can
  const baseCol = maxCol
  for (let i = 0; i < p.cells.length; i++) {
    const c = p.cells[i]!
    if (c.text === '' || c.col > baseCol) continue
    const next = p.cells[i + 1]
    if (next && next.row === c.row) continue
    const words = styles.paragraph(c.style ?? DEFAULT_STYLE)
    if ((c.align ?? words.style.align) !== 'left') continue
    const room = p.cols.span(c.col, maxCol)
    // a text is never wider than its length in ems
    if (room >= c.text.length * words.style.size + 2 * CELL_INSET) continue
    const wide = layoutParagraph(fonts, { ...words.style, whiteSpace: 'nowrap', align: 'left' }, c.text, 1 << 30)
    const last = wide.lines[0]?.words.at(-1)
    if (!last) continue
    const end = p.cols.offset(c.col) + last.x + last.w + 2 * CELL_INSET
    if (end > p.cols.offset(maxCol + 1)) maxCol = Math.max(maxCol, Math.min(MAX_COLS - 1, p.cols.indexAt(end - 1)))
  }
  return { row0: 0, col0: 0, row1: maxRow, col1: maxCol }
}

// ---- planning a sheet's pages ----------------------------------------------------------------------------------------

function planSheet(p: Prepared, geometry: PageGeometry, box: Rect, footer: boolean, notes: Note[]): SheetPlan {
  const print = p.sheet.print
  const area = p.area
  if (!area) {
    notes.push({ kind: 'sheet', reason: `“${p.sheet.name}” has nothing to print` })
    return { prepared: p, geometry, box, scale: ONE, pages: [], footer }
  }
  const hx = print.headings ? ROW_HEADING_W : 0
  const hy = print.headings ? COL_HEADING_H : 0
  const totalW = hx + p.cols.span(area.col0, area.col1)
  const totalH = hy + p.rows.span(area.row0, area.row1)
  const scale = scaleOf(p.sheet, print.scale, box, totalW, totalH, notes)

  // the room one page has, in the sheet's own measure
  const roomW = Math.max(1, Math.floor((box.w * ONE) / scale) - hx)
  const roomH = Math.max(1, Math.floor((box.h * ONE) / scale) - hy)
  const rowChunks = cut(area.row0, area.row1, roomH, p.rows, print.repeatRows)
  const colChunks = cut(area.col0, area.col1, roomW, p.cols, print.repeatCols)
  const truncated = rowChunks.at(-1)!.to < area.row1 || colChunks.at(-1)!.to < area.col1

  const pairs: PlannedPage[] = []
  const add = (rows: Chunk, cols: Chunk) => {
    if (pairs.length < MAX_PAGES) pairs.push({ rows, cols })
    else truncated_ = true
  }
  let truncated_ = truncated
  if (print.order === 'down-then-across') for (const cols of colChunks) for (const rows of rowChunks) add(rows, cols)
  else for (const rows of rowChunks) for (const cols of colChunks) add(rows, cols)
  if (truncated_) notes.push({ kind: 'sheet', reason: `“${p.sheet.name}” makes more than ${MAX_PAGES} pages; the rest is not printed` })

  const pages = print.skipEmpty ? pairs.filter((q) => hasInk(p, q)) : pairs
  return { prepared: p, geometry, box, scale, pages, footer }
}

function scaleOf(sheet: PrintedSheet, scale: SheetScale, box: Rect, totalW: number, totalH: number, notes: Note[]): number {
  if (scale.kind === 'percent') return Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.round(scale.percent * 10_000)))
  let s = ONE
  if (totalW > 0) s = Math.min(s, Math.floor((box.w * ONE) / totalW))
  if (scale.kind === 'fit-page' && totalH > 0) s = Math.min(s, Math.floor((box.h * ONE) / totalH))
  if (s < MIN_SCALE) {
    notes.push({ kind: 'sheet', reason: `“${sheet.name}” would need less than 10 % to fit the page, so it is printed at 10 % and cut into pages` })
    return MIN_SCALE
  }
  return s
}

/** True when a page has a cell with something in it or a picture on it (not counting rows and columns it repeats). */
function hasInk(p: Prepared, page: PlannedPage): boolean {
  const purposes = p.sheet.print.purposes
  for (let i = firstFrom(p.cells, page.rows.from); i < p.cells.length; i++) {
    const c = p.cells[i]!
    if (c.row > page.rows.to) break
    if (c.col >= page.cols.from && c.col <= page.cols.to && hasContent(c, purposes)) return true
  }
  const x0 = p.cols.offset(page.cols.from)
  const x1 = p.cols.offset(page.cols.to + 1)
  const y0 = p.rows.offset(page.rows.from)
  const y1 = p.rows.offset(page.rows.to + 1)
  return p.objects.some((o) => o.rect.x < x1 && o.rect.x + o.rect.w > x0 && o.rect.y < y1 && o.rect.y + o.rect.h > y0)
}

// ---- drawing -----------------------------------------------------------------------------------------------------

interface Drawing {
  fonts: FontSet
  styles: Styles
  context: ObjectContext
  base: ParagraphStyle
}

/** A band of rows or columns on a page: indices `from` to `to`, starting `at` mpt into the page's own measure. */
interface Band {
  from: number
  to: number
  at: number
}

const bands = (chunk: Chunk, start: number, axis: Axis): { main: Band; bands: Band[] } => {
  const bs: Band[] = []
  let at = start
  if (chunk.repeat) {
    bs.push({ from: chunk.repeat[0], to: chunk.repeat[1], at })
    at += axis.span(chunk.repeat[0], chunk.repeat[1])
  }
  const main: Band = { from: chunk.from, to: chunk.to, at }
  bs.push(main)
  return { main, bands: bs }
}

function drawSheetPage(plan: SheetPlan, page: PlannedPage, draw: Drawing): DisplayPage {
  const p = plan.prepared
  const print = p.sheet.print
  const { fonts } = draw
  const hx = print.headings ? ROW_HEADING_W : 0
  const hy = print.headings ? COL_HEADING_H : 0
  const rowBands = bands(page.rows, hy, p.rows)
  const colBands = bands(page.cols, hx, p.cols)
  const last = <T>(a: T[]): T => a[a.length - 1]!
  const width = last(colBands.bands).at + p.cols.span(last(colBands.bands).from, last(colBands.bands).to)
  const height = last(rowBands.bands).at + p.rows.span(last(rowBands.bands).from, last(rowBands.bands).to)

  const items: DisplayItem[] = []
  const x = (b: Band, col: number) => b.at + p.cols.offset(col) - p.cols.offset(b.from)
  const y = (b: Band, row: number) => b.at + p.rows.offset(row) - p.rows.offset(b.from)

  // gridlines: one path for the whole page
  if (print.gridlines) {
    const ops: PathOp[] = []
    for (const rb of rowBands.bands) {
      for (let r = rb.from; r <= rb.to + 1; r++) {
        const yy = y(rb, r)
        for (const cb of colBands.bands) ops.push(['M', cb.at, yy], ['L', cb.at + p.cols.span(cb.from, cb.to), yy])
      }
    }
    for (const cb of colBands.bands) {
      for (let c = cb.from; c <= cb.to + 1; c++) {
        const xx = x(cb, c)
        for (const rb of rowBands.bands) ops.push(['M', xx, rb.at], ['L', xx, rb.at + p.rows.span(rb.from, rb.to)])
      }
    }
    items.push({ kind: 'path', ops, fill: null, stroke: GRID, lineWidth: 500 })
  }

  // cells: every background and border first, then every text, so a text that runs on lies over its neighbours
  for (const rb of rowBands.bands) {
    for (const cb of colBands.bands) {
      const decorations: DisplayItem[] = []
      const texts: DisplayItem[] = []
      cellsOf(p, rb, cb, x, y, draw, decorations, texts)
      items.push(...decorations, ...texts)
    }
  }

  // pictures and charts: in the main part only, cut at its edge
  const main = { rows: rowBands.main, cols: colBands.main }
  const mainAbs: Rect = { x: p.cols.offset(main.cols.from), y: p.rows.offset(main.rows.from), w: p.cols.span(main.cols.from, main.cols.to), h: p.rows.span(main.rows.from, main.rows.to) }
  for (const o of p.objects) {
    if (o.rect.x >= mainAbs.x + mainAbs.w || o.rect.x + o.rect.w <= mainAbs.x || o.rect.y >= mainAbs.y + mainAbs.h || o.rect.y + o.rect.h <= mainAbs.y) continue
    items.push({
      kind: 'group',
      clip: null,
      rotation: 0,
      origin: { x: 0, y: 0 },
      matrix: [ONE, 0, 0, ONE, main.cols.at - mainAbs.x, main.rows.at - mainAbs.y],
      clipPath: { ops: rectPath(mainAbs) },
      items: [o.item],
    })
  }

  // headings
  if (print.headings) {
    const style = paragraphStyle(draw.base.face, Math.round(draw.base.size * 0.85), { align: 'center', color: muted(draw.base.color), whiteSpace: 'nowrap' })
    const heading = (rect: Rect, label: string) => {
      items.push({ kind: 'path', ops: rectPath(rect), fill: HEADING_FILL, stroke: GRID, lineWidth: 500 })
      const line = layoutParagraph(fonts, style, label, rect.w)
      const first = line.lines[0]
      if (first) items.push(...lineItems(fonts, line, first, rect.x, rect.y + Math.floor((rect.h - style.lineHeight) / 2)))
    }
    items.push({ kind: 'path', ops: rectPath({ x: 0, y: 0, w: hx, h: hy }), fill: HEADING_FILL, stroke: GRID, lineWidth: 500 })
    for (const cb of colBands.bands) for (let c = cb.from; c <= cb.to; c++) if (p.cols.size(c) > 0) heading({ x: x(cb, c), y: 0, w: p.cols.size(c), h: hy }, columnLetters(c))
    for (const rb of rowBands.bands) for (let r = rb.from; r <= rb.to; r++) if (p.rows.size(r) > 0) heading({ x: 0, y: y(rb, r), w: hx, h: p.rows.size(r) }, String(r + 1))
  }

  const content: GroupItem = {
    kind: 'group',
    clip: null,
    rotation: 0,
    origin: { x: 0, y: 0 },
    matrix: [plan.scale, 0, 0, plan.scale, plan.box.x, plan.box.y],
    clipPath: { ops: rectPath({ x: 0, y: 0, w: width, h: height }) },
    items,
  }
  return { width: plan.geometry.width, height: plan.geometry.height, items: [content] }
}

/** The text style a cell prints with: its style's, on one line, aligned as the cell shows it. */
const cellStyles = new WeakMap<Styles, Map<string, { style: ParagraphStyle; decoration: BoxDecoration; vertical: 'top' | 'middle' | 'bottom' }>>()
function cellStyle(styles: Styles, id: string, align: SheetCell['align']) {
  let byKey = cellStyles.get(styles)
  if (!byKey) cellStyles.set(styles, (byKey = new Map()))
  const key = `${id}\u0000${align ?? ''}`
  let got = byKey.get(key)
  if (!got) {
    const words = styles.paragraph(id)
    const own = words.style.align === 'justify' ? 'left' : words.style.align
    const explicit = styles.css(id)['vertical-align']
    const padding = words.decoration.padding
    got = {
      style: { ...words.style, whiteSpace: 'nowrap', align: align ?? own, indentLeft: 0, indentRight: 0, firstLine: 0, spaceBefore: 0, spaceAfter: 0 },
      decoration: { ...words.decoration, padding: { ...padding, left: padding.left || CELL_INSET, right: padding.right || CELL_INSET } },
      vertical: explicit ? words.verticalAlign : 'middle',
    }
    byKey.set(key, got)
  }
  return got
}

/** The lines of a laid-out box, placed with its top left at (x, y). */
function textLines(fonts: FontSet, laid: BoxLayout, x: number, y: number): DisplayItem[] {
  const para = laid.paragraph
  if (!para) return []
  const out: DisplayItem[] = []
  let top = y + laid.textTop
  for (let i = 0; i < laid.visibleLines; i++) {
    const line = para.lines[i]!
    out.push(...lineItems(fonts, para, line, x + laid.content.x, top))
    top += line.height
  }
  return out
}

function cellsOf(
  p: Prepared,
  rb: Band,
  cb: Band,
  x: (b: Band, col: number) => number,
  y: (b: Band, row: number) => number,
  draw: Drawing,
  decorations: DisplayItem[],
  texts: DisplayItem[],
): void {
  const { fonts, styles } = draw
  const purposes = p.sheet.print.purposes
  for (let i = firstFrom(p.cells, rb.from); i < p.cells.length; i++) {
    const c = p.cells[i]!
    if (c.row > rb.to) break
    if (c.col < cb.from || c.col > cb.to) continue
    const w = p.cols.size(c.col)
    const h = p.rows.size(c.row)
    if (w <= 0 || h <= 0 || !hasContent(c, purposes)) continue
    const { style, decoration, vertical } = cellStyle(styles, c.style ?? DEFAULT_STYLE, c.align)
    const rect: Rect = { x: x(cb, c.col), y: y(rb, c.row), w, h }
    const deco: BoxDecoration = purposes && c.purpose && !decoration.background ? { ...decoration, background: TINTS[c.purpose] } : decoration
    decorations.push(...decorationItems(rect, deco))
    if (c.text === '') continue

    let laid = layoutBox(fonts, c.text, style, w, h, deco, vertical)
    let box = rect
    if (laid.paragraph?.overflows && style.align === 'left' && cb.to > c.col) {
      // the text runs on over the empty cells to its right, up to the first one with something in it
      let stop = cb.to
      for (let j = i + 1; j < p.cells.length && p.cells[j]!.row === c.row; j++) {
        const n = p.cells[j]!
        if (n.text !== '') {
          stop = Math.min(stop, n.col - 1)
          break
        }
      }
      if (stop > c.col) {
        box = { ...rect, w: w + p.cols.span(c.col + 1, stop) }
        laid = layoutBox(fonts, c.text, style, box.w, h, { ...NO_DECORATION, padding: deco.padding }, vertical)
      }
    }
    const lines = textLines(fonts, laid, box.x, box.y)
    if (laid.clipped) texts.push({ kind: 'group', clip: box, rotation: 0, origin: { x: box.x + Math.floor(box.w / 2), y: box.y + Math.floor(box.h / 2) }, items: lines })
    else texts.push(...lines)
  }
}

// ---- the footer ----------------------------------------------------------------------------------------------------

/**
 * The sheet's name at the left margin and "n / N" at the right, in the light 9 pt of every app's page numbers (D1006),
 * centred in the bottom margin (which has at least {@link PAGE_NUMBER_BAND} for it).
 */
function footerItems(draw: Drawing, page: DisplayPage, geometry: PageGeometry, bottomMargin: number, name: string | null, numbered: boolean, n: number, total: number): void {
  if (!name && !numbered) return
  const { fonts, base } = draw
  const box = contentBox(geometry)
  const size = PAGE_NUMBER_SIZE
  const style = (align: 'left' | 'right') => paragraphStyle(base.face, size, { lineHeight: Math.round(size * 1.2), align, color: muted(base.color), whiteSpace: 'nowrap' })
  const band = Math.max(bottomMargin, PAGE_NUMBER_BAND)
  const top = (height: number) => geometry.height - Math.floor((band + height) / 2)
  let reserved = 0
  if (numbered) {
    const line = layoutParagraph(fonts, style('right'), `${n} / ${total}`, box.w)
    reserved = line.lines[0] ? line.lines[0].words.reduce((m, w) => Math.max(m, w.x + w.w), 0) - Math.min(...line.lines[0].words.map((w) => w.x)) : 0
    if (name) {
      const left = layoutParagraph(fonts, style('left'), name, Math.max(0, box.w - reserved - 2 * CELL_INSET))
      pushLine(page, fonts, left, box.x, top(left.height), left.overflows ? { x: box.x, y: top(left.height), w: Math.max(0, box.w - reserved - 2 * CELL_INSET), h: left.height } : null)
    }
    pushLine(page, fonts, line, box.x, top(line.height), null)
  } else if (name) {
    const left = layoutParagraph(fonts, style('left'), name, box.w)
    pushLine(page, fonts, left, box.x, top(left.height), left.overflows ? { x: box.x, y: top(left.height), w: box.w, h: left.height } : null)
  }
}

function pushLine(page: DisplayPage, fonts: FontSet, layout: ReturnType<typeof layoutParagraph>, x: number, top: number, clip: Rect | null): void {
  const line = layout.lines[0]
  if (!line) return
  const items = lineItems(fonts, layout, line, x, top)
  if (clip) page.items.push({ kind: 'group', clip, rotation: 0, origin: { x: clip.x, y: clip.y }, items })
  else page.items.push(...items)
}
