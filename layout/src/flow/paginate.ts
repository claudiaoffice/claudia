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
 * @module
 */
import { decorationItems, insets, lineItems } from '../display/text'
import type { DisplayItem, DisplayPage, Rect } from '../display/list'
import type { FontSet } from '../fonts/fontset'
import { type BoxDecoration, NO_DECORATION } from '../text/css'
import type { ParagraphLayout } from '../text/paragraph'
import { contentBox, type PageGeometry } from './paper'

/** One paragraph of a flow. Its `layout` must have been made for the content width minus the decoration's insets. */
export interface FlowBlock {
  id: string
  layout: ParagraphLayout
  decoration?: BoxDecoration
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
}

/** Pour `blocks` into pages of `geometry`. There is always at least one page. */
export function paginate(blocks: readonly FlowBlock[], geometry: PageGeometry): FlowPage[] {
  const box = contentBox(geometry)
  const pages: FlowPage[] = []
  let page: FlowPage = { index: 0, lines: [], fragments: [] }
  pages.push(page)
  let y = 0 // used height of the current page's content box
  let prevAfter = 0
  const newPage = () => {
    page = { index: pages.length, lines: [], fragments: [] }
    pages.push(page)
    y = 0
    prevAfter = 0
  }
  const empty = () => page.lines.length === 0

  const geom = blocks.map((b) => {
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

  for (let i = 0; i < blocks.length; i++) {
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
        if (first && g.style.keepWithNext && i + 1 < blocks.length && !empty()) {
          const next = geom[i + 1]!
          const after = top + g.heights.reduce((s, h) => s + h, 0) + g.inset.bottom
          const need = Math.max(g.style.spaceAfter, next.style.spaceBefore) + headHeight(i + 1, Math.min(next.style.orphans, next.heights.length))
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
export function locate(pages: readonly FlowPage[], blocks: readonly FlowBlock[], block: number, offset: number): Spot | null {
  const layout = blocks[block]?.layout
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

/** The display items of a flow's pages: block decorations first, then the text. */
export function flowItems(fonts: FontSet, pages: readonly FlowPage[], blocks: readonly FlowBlock[], geometry: PageGeometry): DisplayPage[] {
  return pages.map((p) => {
    const items: DisplayItem[] = []
    for (const f of p.fragments) {
      const deco = blocks[f.block]!.decoration
      if (deco) items.push(...decorationItems(f.rect, deco, { top: f.continuesBefore, bottom: f.continuesAfter }))
    }
    for (const l of p.lines) {
      const b = blocks[l.block]!
      items.push(...lineItems(fonts, b.layout, b.layout.lines[l.line]!, l.x, l.top))
    }
    return { width: geometry.width, height: geometry.height, items }
  })
}
