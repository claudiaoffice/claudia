/**
 * Flow pagination: paragraphs, already broken into lines, poured into pages of any size.
 *
 * Rules, in the order they win:
 * 1. A line is never split; a page holds whole lines only.
 * 2. A paragraph taller than a page is split wherever it must be.
 * 3. Otherwise a paragraph leaves at least `orphans` lines at the foot of a page and carries at least `widows` lines
 *    to the next one, or moves whole.
 * 4. A paragraph with `keepWithNext` (a heading) moves to the next page when the first lines of the next paragraph
 *    would not fit beside it.
 * 5. Space between paragraphs is the larger of the one's `spaceAfter` and the next's `spaceBefore` (CSS margin
 *    collapsing); at the top of a page it is dropped.
 *
 * A table (E9.32) is poured by the same rules with its rows as the lines: a row is never split, unless it is taller
 * than a page (then by its lines); rows that a merge joins and the last row beside the total row stay together; the
 * header rows come back on top of every page the table continues on, and are never left alone at the foot of one.
 *
 * @module
 */
import { decorationItems, insets, lineItems } from '../display/text'
import type { DisplayItem, DisplayPage, Rect } from '../display/list'
import type { FontSet } from '../fonts/fontset'
import { type BoxDecoration, NO_DECORATION } from '../text/css'
import type { ParagraphLayout } from '../text/paragraph'
import { contentBox, type PageGeometry } from './paper'
import { type PlacedRow, type RowPart, type TableLayout, tableItems } from './table'

/** One paragraph of a flow. Its `layout` must have been made for the content width minus the decoration's insets. */
export interface FlowBlock {
  id: string
  layout: ParagraphLayout
  decoration?: BoxDecoration
  /** a list item's marker (E9.21): a one-line paragraph drawn on the baseline of the block's first line, its box
   *  starting `x` from the left of the block's content box */
  marker?: { layout: ParagraphLayout; x: number }
}

/** A table in a flow: where it goes is the item's place among the blocks; `spaceBefore` and `spaceAfter` are the room
 *  around it (collapsing with a paragraph's, as paragraphs' do). */
export interface FlowTable {
  id: string
  table: TableLayout
  spaceBefore: number
  spaceAfter: number
}
/** What a flow is poured from: paragraphs and tables, in the order of the text. */
export type FlowItem = FlowBlock | FlowTable

/** The part of a table on one page: its rows (the repeated header rows first) from `top` down, left edge `x`. */
export interface PlacedTable {
  /** the item of the flow it is a part of */
  block: number
  x: number
  top: number
  rows: PlacedRow[]
}

/** A line of a block on a page: where its box starts (left of the paragraph's content box, top of the line box). */
export interface PlacedLine {
  block: number
  line: number
  x: number
  top: number
}

/** The part of a block on one page, for drawing its decoration. `rect` is the border box of that part. */
export interface Fragment {
  block: number
  first: number
  /** one past the last line */
  end: number
  rect: Rect
  continuesBefore: boolean
  continuesAfter: boolean
}

export interface FlowPage {
  index: number
  lines: PlacedLine[]
  fragments: Fragment[]
  tables: PlacedTable[]
}

/** The rows of a table that stay together (a merge joins them) are one unit; a table is poured unit by unit. */
function tableUnits(t: TableLayout): [number, number][] {
  const units: [number, number][] = []
  for (let r = 0; r < t.rows.length; ) {
    let e = r
    while (e < t.rows.length - 1 && t.rows[e]!.tied) e++
    units.push([r, e + 1])
    r = e + 1
  }
  return units
}
const rowsHeight = (t: TableLayout, from: number, end: number): number => {
  let h = 0
  for (let r = from; r < end; r++) h += t.rows[r]!.height
  return h
}
/** How many header rows come back on top of each page a table continues on: none if the header is joined to the body
 *  by a merge, or takes more than half a page. */
function repeatedRows(t: TableLayout, boxHeight: number): number {
  if (t.header === 0 || t.header >= t.rows.length || t.rows[t.header - 1]!.tied) return 0
  return rowsHeight(t, 0, t.header) * 2 <= boxHeight ? t.header : 0
}
/** What a table needs at the foot of a page to begin there: its header and the first rows after it that belong together. */
function tableHead(t: TableLayout): number {
  const units = tableUnits(t)
  const first = units.find(([s]) => s >= t.header) ?? units[0]
  return rowsHeight(t, 0, t.header) + (first && first[0] >= t.header ? rowsHeight(t, first[0], first[1]) : 0)
}

/** Pour `items` into pages of `geometry`. There is always at least one page. */
export function paginate(items: readonly FlowItem[], geometry: PageGeometry): FlowPage[] {
  const box = contentBox(geometry)
  const pages: FlowPage[] = []
  let page: FlowPage = { index: 0, lines: [], fragments: [], tables: [] }
  pages.push(page)
  let y = 0 // used height of the current page's content box
  let prevAfter = 0
  const newPage = () => {
    page = { index: pages.length, lines: [], fragments: [], tables: [] }
    pages.push(page)
    y = 0
    prevAfter = 0
  }
  const empty = () => page.lines.length === 0 && page.tables.length === 0

  const geom = items.map((b) => {
    if ('table' in b) return null
    const inset = insets(b.decoration ?? NO_DECORATION)
    return { inset, heights: b.layout.lines.map((l) => l.height), style: b.layout.style }
  })
  /** Lines of block `i`, starting at line `from`, that fit below `top` (with the bottom inset if they are the last). */
  const fitting = (i: number, from: number, top: number): number => {
    const g = geom[i]!
    let used = top
    let k = 0
    for (let l = from; l < g.heights.length; l++) {
      used += g.heights[l]!
      const bottom = l === g.heights.length - 1 ? g.inset.bottom : 0
      if (used + bottom > box.h) break
      k++
    }
    return k
  }
  /** Height block `i` needs on a fresh stretch of page to show `lines` lines from its start. */
  const headHeight = (i: number, lines: number): number => {
    const g = geom[i]!
    let h = g.inset.top
    for (let l = 0; l < Math.min(lines, g.heights.length); l++) h += g.heights[l]!
    return h + (lines >= g.heights.length ? g.inset.bottom : 0)
  }

  /** Pour the table `item` (number `index`): unit by unit, a new piece on each page, the header on top of the later ones. */
  const placeTable = (index: number, item: FlowTable) => {
    const t = item.table
    const units = tableUnits(t)
    const repeat = repeatedRows(t, box.h)
    const headerHeight = rowsHeight(t, 0, repeat)
    let piece: PlacedTable | null = null
    let started = false // some of the table is on a page already
    y += empty() ? 0 : Math.max(prevAfter, item.spaceBefore)
    const put = (row: number, repeated: boolean, part?: RowPart, h = t.rows[row]!.height, starts = true, ends = true) => {
      piece!.rows.push({ row, y: box.y + y, h, repeat: repeated, ...(part ? { part, starts, ends } : {}) })
      y += h
    }
    const open = (repeated: boolean) => {
      piece = { block: index, x: box.x, top: box.y + y, rows: [] }
      page.tables.push(piece)
      started = true
      if (repeated) for (let r = 0; r < repeat; r++) put(r, true)
    }
    const next = () => {
      newPage()
      piece = null
    }
    /** A row taller than the room it has is split by its lines, the rest going on the next page. */
    const split = (row: number) => {
      const cells = t.rows[row]!.cells
      let from = cells.map(() => 0)
      for (;;) {
        const room = box.h - y
        let h = 0
        const part: RowPart = cells.map((cell, k) => {
          const lines = cell.paragraph.lines
          const cap = room - cell.inset.top - cell.inset.bottom
          let n = from[k]!
          let used = 0
          while (n < lines.length && (n === from[k] || used + lines[n]!.height <= cap)) used += lines[n++]!.height
          if (n > from[k]!) h = Math.max(h, cell.inset.top + used + cell.inset.bottom)
          return [from[k]!, n]
        })
        const ends = part.every(([, n], k) => n === cells[k]!.paragraph.lines.length)
        put(row, false, part, h, from.every((n) => n === 0), ends)
        if (ends) return
        from = part.map(([, n]) => n)
        next()
        open(repeat > 0)
      }
    }
    for (let u = 0; u < units.length; ) {
      const [s, e] = units[u]!
      const unit = rowsHeight(t, s, e)
      // the header is not left alone: it goes where the first rows after it go
      const after = repeat > 0 && s === 0 && e === repeat ? units[u + 1] : undefined
      const need = unit + (after ? rowsHeight(t, after[0], after[1]) : 0)
      const again = !piece && started && repeat > 0 // a new piece begins with the header's rows again
      if (y + (again ? headerHeight : 0) + need <= box.h) {
        if (!piece) open(again)
        for (let r = s; r < e; r++) put(r, false)
        u++
      } else if (!empty()) {
        next()
      } else if (!piece && y + unit <= box.h) {
        // the page is empty and the rows fit it, but not with the header above them
        open(false)
        for (let r = s; r < e; r++) put(r, false)
        u++
      } else if (s + 1 === e) {
        // one row taller than a page
        if (!piece) open(again)
        split(s)
        u++
      } else {
        if (!piece) open(again)
        for (let r = s; r < e; r++) put(r, false) // joined rows taller than a page: they are drawn, past the foot
        u++
      }
    }
    prevAfter = item.spaceAfter
  }

  for (let i = 0; i < items.length; i++) {
    const item = items[i]!
    if ('table' in item) {
      placeTable(i, item)
      continue
    }
    const g = geom[i]!
    const n = g.heights.length
    let from = 0
    let first = true
    while (from < n) {
      const gap = empty() ? 0 : first ? Math.max(prevAfter, g.style.spaceBefore) : 0
      const top = y + gap + (first ? g.inset.top : 0)
      const fit = fitting(i, from, top)
      const rest = n - from
      let k: number
      if (fit >= rest) {
        k = rest
        // keep with next: the next paragraph's first lines must fit beside this one
        if (first && g.style.keepWithNext && i + 1 < items.length && !empty()) {
          const following = items[i + 1]!
          const next = geom[i + 1]
          const after = top + g.heights.reduce((s, h) => s + h, 0) + g.inset.bottom
          const need =
            'table' in following
              ? Math.max(g.style.spaceAfter, following.spaceBefore) + tableHead(following.table)
              : Math.max(g.style.spaceAfter, next!.style.spaceBefore) + headHeight(i + 1, Math.min(next!.style.orphans, next!.heights.length))
          if (after + need > box.h) {
            newPage()
            continue
          }
        }
      } else {
        k = fit
        if (rest - k < g.style.widows) k = rest - g.style.widows
        if (k < g.style.orphans || (first && k < Math.min(g.style.orphans, rest))) k = 0
        if (k <= 0) {
          if (!empty()) {
            newPage()
            continue
          }
          k = Math.max(1, fit) // a paragraph taller than a page: split where it must be
        }
      }
      const x = box.x + g.inset.left
      let lineTop = box.y + top
      const fragTop = lineTop - (first ? g.inset.top : 0)
      for (let l = from; l < from + k; l++) {
        page.lines.push({ block: i, line: l, x, top: lineTop })
        lineTop += g.heights[l]!
      }
      const last = from + k === n
      const fragBottom = lineTop + (last ? g.inset.bottom : 0)
      page.fragments.push({
        block: i,
        first: from,
        end: from + k,
        rect: { x: box.x, y: fragTop, w: box.w, h: fragBottom - fragTop },
        continuesBefore: !first,
        continuesAfter: !last,
      })
      y = fragBottom - box.y
      from += k
      first = false
      if (!last) newPage()
    }
    prevAfter = g.style.spaceAfter
  }
  return pages
}

/** Where a character of a block ended up: page, the x of the character and the top of its line (page mpt). */
export interface Spot {
  page: number
  x: number
  top: number
  lineHeight: number
}

/** The spot of UTF-16 offset `offset` of block `block` (an index), or `null` if the block is not in `pages`. */
export function locate(pages: readonly FlowPage[], blocks: readonly FlowItem[], block: number, offset: number): Spot | null {
  const item = blocks[block]
  const layout = item && !('table' in item) ? item.layout : undefined
  if (!layout) return null
  let lineIndex = layout.lines.findIndex((l) => offset >= l.start && offset < l.end)
  if (lineIndex < 0) lineIndex = offset <= 0 ? 0 : layout.lines.length - 1
  const line = layout.lines[lineIndex]!
  for (const p of pages) {
    const placed = p.lines.find((l) => l.block === block && l.line === lineIndex)
    if (!placed) continue
    let x = line.x
    for (const w of line.words) {
      if (offset < w.offset) break
      x = w.x + w.w
      if (offset < w.offset + w.length) {
        let pos = w.offset
        x = w.x
        for (let g = 0; g < w.chars.length; g++) {
          if (pos >= offset) {
            x = w.x + w.dx[g]!
            break
          }
          pos += w.chars[g]!.length
        }
        break
      }
    }
    return { page: p.index, x: placed.x + x, top: placed.top, lineHeight: line.height }
  }
  return null
}

/** The display items of a flow's pages: block decorations first, then the text, then the tables. */
export function flowItems(fonts: FontSet, pages: readonly FlowPage[], blocks: readonly FlowItem[], geometry: PageGeometry): DisplayPage[] {
  return pages.map((p) => {
    const items: DisplayItem[] = []
    for (const f of p.fragments) {
      const deco = (blocks[f.block] as FlowBlock).decoration
      if (deco) items.push(...decorationItems(f.rect, deco, { top: f.continuesBefore, bottom: f.continuesAfter }))
    }
    for (const l of p.lines) {
      const b = blocks[l.block] as FlowBlock
      const line = b.layout.lines[l.line]!
      items.push(...lineItems(fonts, b.layout, line, l.x, l.top))
      const marker = l.line === 0 ? b.marker : undefined
      const mark = marker?.layout.lines[0]
      if (marker && mark) items.push(...lineItems(fonts, marker.layout, mark, l.x + marker.x, l.top + line.baseline - mark.baseline))
    }
    for (const t of p.tables) items.push(...tableItems(fonts, (blocks[t.block] as FlowTable).table, t.x, t.rows))
    return { width: geometry.width, height: geometry.height, items }
  })
}
