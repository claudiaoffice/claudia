/**
 * A table of a composes text (E9.32): column widths from the words, each box's paragraph laid out at its column's
 * width, rows as tall as their tallest box, and the rules and shading of the table's look.
 *
 * Pure integer arithmetic (mpt), so the same table has the same widths and the same display items on every machine.
 * {@link paginate} pours the rows into pages (`paginate.ts`): this module only says how a table looks when it is all
 * on one page and what may and may not be split.
 *
 * What it reads is the wire form of the table (`tables` of a composes server): rows and columns by id, the boxes that
 * have words or a style, the merges, the look. A box's style `""` follows the table's look: the look's style for the
 * row's role (`table-<look>-<role>`, the names `claudia_composes.model.TABLE_LOOKS` gives them).
 *
 * @module
 */
import { decorationItems, insets, lineItems } from '../display/text'
import type { DisplayItem, Rect } from '../display/list'
import type { FontSet } from '../fonts/fontset'
import { type BoxDecoration } from '../text/css'
import { layoutParagraph, type ParagraphLayout, type ParagraphOptions } from '../text/paragraph'
import type { ParagraphStyle } from '../text/style'

/** A column as the server sends it: `width` is its share of the table in hundredths of a percent, or `null`. */
export interface TableColumnData {
  id: string
  kind: string
  total: string | null
  width: number | null
}
/** A box's paragraph as the server sends it (runs are authorship only and do not change how it looks). */
export interface TableEntryData {
  id?: string
  style: string
  text: string
}
/** A table as `tables` gives it, with `totals`: the words of its total row by column id. */
export interface TableData {
  id: string
  columns: readonly TableColumnData[]
  rows: readonly string[]
  entries: readonly (readonly [string, string, TableEntryData])[]
  merges: readonly { row: string; col: string; rows: number; cols: number }[]
  header_rows: number
  banded: boolean
  look: string
  /** a share of the line in hundredths of a percent, or `null`: the whole line */
  width: number | null
  /** `floating` is printed in the flow too, for now (the caller says so) */
  placement?: string
  totals: Readonly<Record<string, string>>
  /** the word the total row starts with when its first column has no total of its own ("Total", in the reader's language) */
  total_label?: string
}

/** The paragraph style and box a style id gives (what {@link Styles.paragraph} answers). */
export interface TableStyles {
  paragraph(id: string): { style: ParagraphStyle; decoration: BoxDecoration }
}

export type RowRole = 'header' | 'body' | 'total'

/** A box of the table: where it starts, how many columns and rows it joins and what is drawn in it. */
export interface TableCell {
  /** index of the first column, and how many it joins */
  col: number
  cols: number
  /** how many rows it joins (the row it is in is the first) */
  rows: number
  /** left edge and width in the table, mpt */
  x: number
  w: number
  style: string
  paragraph: ParagraphLayout
  /** the box as it is drawn with a rule shared with a neighbour left to the neighbour, and as the style says it */
  decoration: BoxDecoration
  full: BoxDecoration
  /** the room between the border box and the words (padding and border, as the style says) */
  inset: { top: number; right: number; bottom: number; left: number }
}

export interface TableRow {
  role: RowRole
  /** the height of the row on a page, mpt */
  height: number
  cells: TableCell[]
  /** true when this row and the next one must be on a page together (a merge joins them, or the next row is the total) */
  tied: boolean
}

export interface TableLayout {
  id: string
  /** the width of the table and of each column, mpt */
  width: number
  columns: number[]
  rows: TableRow[]
  /** how many of the first rows are the header */
  header: number
}

const HUGE = 100_000_000
const clone = (d: BoxDecoration): BoxDecoration => ({ padding: { ...d.padding }, border: { ...d.border }, background: d.background })

/** The id of the style a look gives a role: `table-<look>-<role>`. */
export const roleStyle = (look: string, role: 'header' | 'body' | 'band' | 'total'): string => `table-${look}-${role}`

/** The ids of the styles the table's boxes are in (its look's four, and the ones the person chose), for loading fonts. */
export function tableStyleIds(data: TableData): string[] {
  const ids = new Set<string>((['header', 'body', 'band', 'total'] as const).map((role) => roleStyle(data.look, role)))
  for (const [, , entry] of data.entries) if (entry.style) ids.add(entry.style)
  return [...ids]
}

/** Column widths: those the person set (a share of the table), the rest by what their words need. Whole mpt that
 *  always add up to `total`. */
function columnWidths(total: number, set: readonly (number | null)[], want: readonly number[], least: readonly number[]): number[] {
  const n = set.length
  const widths = set.map((s) => (s === null ? 0 : Math.floor((total * s) / 10_000)))
  const free = set.flatMap((s, i) => (s === null ? [i] : []))
  const room = free.reduce((sum, i) => sum + least[i]!, 0)
  let fixed = widths.reduce((a, b) => a + b, 0)
  if (fixed > total - room && fixed > 0) {
    // the person asked for more than there is: every width set shrinks alike, the others keep their least
    const scale = Math.max(0, total - room)
    for (let i = 0; i < n; i++) widths[i] = Math.floor((widths[i]! * scale) / fixed)
    fixed = widths.reduce((a, b) => a + b, 0)
  }
  const remaining = total - fixed
  if (free.length) {
    const wanted = free.reduce((sum, i) => sum + want[i]!, 0)
    const share = free.map((i) => {
      if (wanted === 0) return Math.floor(remaining / free.length)
      return remaining >= wanted ? want[i]! + Math.floor(((remaining - wanted) * want[i]!) / wanted) : Math.max(least[i]!, Math.floor((remaining * want[i]!) / wanted))
    })
    let over = share.reduce((a, b) => a + b, 0) - remaining
    while (over > 0) {
      // take from the column with the most to spare, the first of equals
      let at = -1
      free.forEach((i, k) => {
        if (share[k]! > least[i]! && (at < 0 || share[k]! - least[i]! > share[at]! - least[free[at]!]!)) at = k
      })
      if (at < 0) break
      const take = Math.min(over, share[at]! - least[free[at]!]!)
      share[at]! -= take
      over -= take
    }
    free.forEach((i, k) => (widths[i] = share[k]!))
  }
  widths[n - 1]! += total - widths.reduce((a, b) => a + b, 0)
  return widths
}

/**
 * Lay out `data` for a line `width` mpt wide: the table is its own `width` share of it. Every box is a paragraph at
 * the width of its column; a row is as tall as its tallest box, a merged box adds what its rows lack to its last row.
 */
export function layoutTable(fonts: FontSet, styles: TableStyles, data: TableData, width: number, options: ParagraphOptions = {}): TableLayout {
  const total = data.width === null ? width : Math.max(1, Math.floor((width * data.width) / 10_000))
  const columnIndex = new Map(data.columns.map((c, i) => [c.id, i]))
  const rowIndex = new Map(data.rows.map((r, i) => [r, i]))
  const entries = new Map<string, TableEntryData>()
  for (const [row, col, entry] of data.entries) entries.set(`${row}\n${col}`, entry)
  const hasTotal = data.columns.some((c) => c.total !== null)
  const rowCount = data.rows.length + (hasTotal ? 1 : 0)
  const colCount = data.columns.length

  // ---- which box is joined with which: the origin of each slot, and the span of each origin
  const spans = new Map<string, { rows: number; cols: number }>()
  const covered = new Set<string>()
  for (const m of data.merges) {
    const r = rowIndex.get(m.row)
    const c = columnIndex.get(m.col)
    if (r === undefined || c === undefined) continue
    const rows = Math.min(m.rows, data.rows.length - r)
    const cols = Math.min(m.cols, colCount - c)
    if (rows < 1 || cols < 1 || (rows === 1 && cols === 1)) continue
    spans.set(`${r}\n${c}`, { rows, cols })
    for (let i = r; i < r + rows; i++) {
      for (let k: number = c; k < c + cols; k++) if (i !== r || k !== c) covered.add(`${i}\n${k}`)
    }
  }

  const roleOf = (r: number): RowRole => (r >= data.rows.length ? 'total' : r < data.header_rows ? 'header' : 'body')
  const styleOf = (r: number, c: number): string => {
    const own = r < data.rows.length ? entries.get(`${data.rows[r]}\n${data.columns[c]!.id}`)?.style : ''
    if (own) return own
    const role = roleOf(r)
    if (role === 'header') return roleStyle(data.look, 'header')
    if (role === 'total') return roleStyle(data.look, 'total')
    return roleStyle(data.look, data.banded && (r - data.header_rows) % 2 === 1 ? 'band' : 'body')
  }
  const textOf = (r: number, c: number): string => {
    const column = data.columns[c]!
    if (r >= data.rows.length) return data.totals[column.id] || (c === 0 && column.total === null ? (data.total_label ?? '') : '')
    return entries.get(`${data.rows[r]}\n${column.id}`)?.text ?? ''
  }
  const styleFor = (r: number, c: number): { id: string; style: ParagraphStyle; decoration: BoxDecoration } => {
    const id = styleOf(r, c)
    const got = styles.paragraph(id)
    // a column of numbers lines up on its right edge
    const style = data.columns[c]!.kind === 'number' ? { ...got.style, align: 'right' as const } : got.style
    return { id, style, decoration: got.decoration }
  }

  // ---- column widths: from the words of the boxes that sit in one column
  const want: number[] = Array.from({ length: colCount }, () => 0)
  const least: number[] = Array.from({ length: colCount }, () => 0)
  for (let r = 0; r < rowCount; r++) {
    for (let c = 0; c < colCount; c++) {
      if (covered.has(`${r}\n${c}`) || (spans.get(`${r}\n${c}`)?.cols ?? 1) > 1) continue
      const { style, decoration } = styleFor(r, c)
      const inset = insets(decoration)
      const room = inset.left + inset.right + style.indentLeft + style.indentRight
      const text = textOf(r, c)
      const natural = text ? (layoutParagraph(fonts, { ...style, whiteSpace: 'nowrap', hyphens: 'manual' }, text, HUGE, options).lines[0]?.natural ?? 0) : 0
      want[c] = Math.max(want[c]!, natural + room)
      least[c] = Math.max(least[c]!, room + style.size)
    }
  }
  const columns = columnWidths(total, data.columns.map((c) => c.width), want, least)
  const left = [0]
  for (const w of columns) left.push(left.at(-1)! + w)

  // ---- the boxes, and the rows' heights
  const rows: TableRow[] = Array.from({ length: rowCount }, (_, r) => ({ role: roleOf(r), height: 0, cells: [], tied: false }))
  const origin = new Map<string, TableCell>()
  const pending: { row: number; cell: TableCell; need: number }[] = []
  for (let r = 0; r < rowCount; r++) {
    for (let c = 0; c < colCount; c++) {
      if (covered.has(`${r}\n${c}`)) continue
      const span = r < data.rows.length ? (spans.get(`${r}\n${c}`) ?? { rows: 1, cols: 1 }) : { rows: 1, cols: 1 }
      const { id, style, decoration } = styleFor(r, c)
      const inset = insets(decoration)
      const w = left[c + span.cols]! - left[c]!
      const paragraph = layoutParagraph(fonts, style, textOf(r, c), Math.max(1, w - inset.left - inset.right), options)
      const cell: TableCell = { col: c, cols: span.cols, rows: span.rows, x: left[c]!, w, style: id, paragraph, decoration: clone(decoration), full: decoration, inset }
      rows[r]!.cells.push(cell)
      for (let i = r; i < r + span.rows; i++) {
        for (let k: number = c; k < c + span.cols; k++) origin.set(`${i}\n${k}`, cell)
      }
      const need = paragraph.height + inset.top + inset.bottom
      if (span.rows === 1) rows[r]!.height = Math.max(rows[r]!.height, need)
      else pending.push({ row: r, cell, need })
    }
  }
  for (const { row, cell, need } of pending) {
    const last = row + cell.rows - 1
    let have = 0
    for (let i = row; i <= last; i++) have += rows[i]!.height
    if (need > have) rows[last]!.height += need - have
    for (let i = row; i < last; i++) rows[i]!.tied = true
  }
  // the header is one unit, and the total row stays with the row above it
  for (let i = 0; i < Math.min(data.header_rows, data.rows.length) - 1; i++) rows[i]!.tied = true
  if (hasTotal && rowCount >= 2) rows[rowCount - 2]!.tied = true

  // ---- a rule two boxes share is drawn once: the box above keeps its lower rule, the one on the left its right one
  for (let r = 0; r < rowCount; r++) {
    for (const cell of rows[r]!.cells) {
      const above = r > 0 ? origin.get(`${r - 1}\n${cell.col}`) : undefined
      const beside = cell.col > 0 ? origin.get(`${r}\n${cell.col - 1}`) : undefined
      if (above?.full.border.bottom && cell.decoration.border.top) cell.decoration.border = { ...cell.decoration.border, top: null }
      if (beside?.full.border.right && cell.decoration.border.left) cell.decoration.border = { ...cell.decoration.border, left: null }
    }
  }
  return { id: data.id, width: total, columns, rows, header: Math.min(data.header_rows, data.rows.length) }
}

/** The part of a row that is on a page when a row is split by lines: for each of its boxes, the lines from `first` to `end`. */
export type RowPart = [number, number][]

/** One row of a table on a page: its place (page mpt) and height; a repeated header row is `repeat`. */
export interface PlacedRow {
  row: number
  y: number
  h: number
  repeat: boolean
  part?: RowPart
  /** the part is the start / the end of the row (a row that is not split is both) */
  starts?: boolean
  ends?: boolean
}

/**
 * The display items of a table piece: first the shading and rules of every box, then their words. `x` is the left of
 * the table; `rows` are the placed rows in order, those of one piece of the table on one page.
 */
export function tableItems(fonts: FontSet, table: TableLayout, x: number, rows: readonly PlacedRow[]): DisplayItem[] {
  const shapes: DisplayItem[] = []
  const words: DisplayItem[] = []
  rows.forEach((placed, k) => {
    const source = table.rows[placed.row]!
    for (const [index, cell] of source.cells.entries()) {
      // the boxes joined over several rows are as high as the rows of this piece that they join
      let h = placed.h
      for (let j = k + 1; j < rows.length && cell.rows > 1 && rows[j]!.row < placed.row + cell.rows; j++) h += rows[j]!.h
      const rect: Rect = { x: x + cell.x, y: placed.y, w: cell.w, h }
      const open = { top: placed.starts === false, bottom: placed.ends === false }
      shapes.push(...decorationItems(rect, k === 0 ? cell.full : cell.decoration, open))
      const lines = cell.paragraph.lines
      const [from, end] = placed.part?.[index] ?? [0, lines.length]
      let top = placed.y + cell.inset.top
      for (let l = from; l < end; l++) {
        const line = lines[l]!
        words.push(...lineItems(fonts, cell.paragraph, line, x + cell.x + cell.inset.left, top))
        top += line.height
      }
    }
  })
  return [...shapes, ...words]
}
