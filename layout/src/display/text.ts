/**
 * Display items for laid-out text: glyph runs for the words of a paragraph's lines, underline and strike-through
 * lines, and the background and borders of a box.
 *
 * @module
 */
import type { FontSet } from '../fonts/fontset'
import type { BoxDecoration } from '../text/css'
import type { Line, ParagraphLayout } from '../text/paragraph'
import { mulDivRound } from '../units'
import { type DisplayItem, type GlyphRun, type PathItem, type Rect, rectPath } from './list'

/**
 * The items of one line: a glyph run per word, and decoration lines. `left` is where the paragraph's content box
 * starts and `top` where the line's box starts, on the page.
 */
export function lineItems(fonts: FontSet, layout: ParagraphLayout, line: Line, left: number, top: number): DisplayItem[] {
  const { style } = layout
  const y = top + line.baseline
  const items: DisplayItem[] = []
  for (const w of line.words) {
    const run: GlyphRun = {
      kind: 'glyphs',
      face: style.face,
      size: style.size,
      color: style.color,
      x: left + w.x,
      y,
      glyphs: w.gids.map((gid, i) => ({ gid, dx: w.dx[i]!, chars: w.chars[i]! })),
      text: w.text,
    }
    items.push(run)
  }
  if ((style.underline || style.strike) && line.words.length) {
    const m = fonts.metrics(style.face)
    const thickness = Math.max(1, mulDivRound(Math.round(m.unitsPerEm / 16), style.size, m.unitsPerEm))
    const first = line.words[0]!
    const last = line.words.at(-1)!
    const x0 = left + first.x
    const x1 = left + last.x + last.w
    const bar = (yy: number): PathItem => ({ kind: 'path', ops: rectPath({ x: x0, y: yy, w: x1 - x0, h: thickness }), fill: style.color, stroke: null, lineWidth: 0 })
    if (style.underline) items.push(bar(y + mulDivRound(Math.round(m.unitsPerEm / 10), style.size, m.unitsPerEm)))
    if (style.strike) items.push(bar(y - mulDivRound(Math.round((m.capHeight || m.ascender * 0.7) / 2), style.size, m.unitsPerEm)))
  }
  return items
}

/**
 * Background and borders of a box. `outer` is the border box. With `open` the top or bottom edge belongs to a
 * fragment that continues on another page, so its border is not drawn.
 */
export function decorationItems(outer: Rect, deco: BoxDecoration, open: { top?: boolean; bottom?: boolean } = {}): DisplayItem[] {
  const out: DisplayItem[] = []
  if (deco.background) out.push({ kind: 'path', ops: rectPath(outer), fill: deco.background, stroke: null, lineWidth: 0 })
  const { top, right, bottom, left } = deco.border
  const side = (r: Rect, s: NonNullable<typeof top>): PathItem => {
    const dash = s.style === 'dashed' ? [s.width * 3, s.width * 2] : s.style === 'dotted' ? [s.width, s.width] : undefined
    if (dash) {
      const horizontal = r.w >= r.h
      const mid = horizontal ? r.y + Math.floor(r.h / 2) : r.x + Math.floor(r.w / 2)
      return {
        kind: 'path',
        ops: horizontal ? [['M', r.x, mid], ['L', r.x + r.w, mid]] : [['M', mid, r.y], ['L', mid, r.y + r.h]],
        fill: null,
        stroke: s.color,
        lineWidth: s.width,
        dash,
      }
    }
    return { kind: 'path', ops: rectPath(r), fill: s.color, stroke: null, lineWidth: 0 }
  }
  if (top && !open.top) out.push(side({ x: outer.x, y: outer.y, w: outer.w, h: top.width }, top))
  if (bottom && !open.bottom) out.push(side({ x: outer.x, y: outer.y + outer.h - bottom.width, w: outer.w, h: bottom.width }, bottom))
  if (left) out.push(side({ x: outer.x, y: outer.y, w: left.width, h: outer.h }, left))
  if (right) out.push(side({ x: outer.x + outer.w - right.width, y: outer.y, w: right.width, h: outer.h }, right))
  return out
}

/** The insets of a decoration (padding plus border) on each side. */
export function insets(deco: BoxDecoration): { top: number; right: number; bottom: number; left: number } {
  const b = deco.border
  return {
    top: deco.padding.top + (b.top?.width ?? 0),
    right: deco.padding.right + (b.right?.width ?? 0),
    bottom: deco.padding.bottom + (b.bottom?.width ?? 0),
    left: deco.padding.left + (b.left?.width ?? 0),
  }
}
