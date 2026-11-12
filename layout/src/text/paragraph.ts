/// <reference path="./linebreak.d.ts" />
/**
 * Paragraph to lines: break a paragraph of one style into lines of a given width.
 *
 * Break opportunities are those of the Unicode line breaking algorithm (UAX #14). Each piece between two
 * opportunities is shaped on its own by HarfBuzz, then lines are filled greedily; a piece wider than a whole line is
 * broken between glyph clusters. Justified lines spread the remaining width over their spaces as whole mpt, the
 * remainder going to the first spaces, so no float ever decides a position. The result does not depend on where the
 * paragraph will be placed, so it can be cached and reused by a page, a box or a table cell.
 *
 * @module
 */
import LineBreaker from 'linebreak'
import type { FontSet } from '../fonts/fontset'
import { mulDivRound } from '../units'
import type { ParagraphStyle } from './style'

/** Justification stretches a space at most this many times its natural width; looser lines stay ragged. */
export const MAX_STRETCH = 3

/** A shaped word placed on a line. Lengths in mpt; `x` is relative to the paragraph's content box. */
export interface PlacedWord {
  x: number
  /** advance width */
  w: number
  text: string
  gids: number[]
  /** where each glyph is drawn, from `x` */
  dx: number[]
  /** the characters each glyph stands for (`''` for the second glyph of a cluster) */
  chars: string[]
  /** UTF-16 offset of the word in the paragraph text */
  offset: number
}

/** One line of a paragraph. */
export interface Line {
  /** UTF-16 offsets of the paragraph text the line holds: `start <= i < end` (trailing spaces included) */
  start: number
  end: number
  /** where the line's content starts, from the left edge of the content box */
  x: number
  /** sum of the word widths and the unstretched spaces between them */
  natural: number
  /** distance from the line's top to its baseline, and the line's height (the style's line height) */
  baseline: number
  height: number
  words: PlacedWord[]
  text: string
}

export interface ParagraphLayout {
  style: ParagraphStyle
  /** the width the lines were broken for */
  width: number
  lines: Line[]
  /** sum of the line heights (not counting space before and after) */
  height: number
  /** true when a line is wider than `width` (`white-space: nowrap`) */
  overflows: boolean
}

interface Piece {
  w: number
  text: string
  offset: number
  gids: number[]
  dx: number[]
  chars: string[]
  /** cumulative advances in mpt, gids.length + 1 long, for breaking inside the piece */
  cum: number[]
}
interface Item {
  word: Piece | null
  spaces: number
  forced: boolean
  offset: number
  end: number
}

const NEWLINES = [0x0a, 0x0d, 0x85, 0x2028, 0x2029]

/** Lay out `text` with `style` into lines of `width` mpt. */
export function layoutParagraph(fonts: FontSet, style: ParagraphStyle, text: string, width: number): ParagraphLayout {
  const metrics = fonts.metrics(style.face)
  const upem = metrics.unitsPerEm
  const toMpt = (units: number) => mulDivRound(units, style.size, upem)
  const shapeOptions = style.language ? { language: style.language } : {}
  const space = fonts.shape(style.face, ' ', shapeOptions)
  const spaceW = toMpt(space.advances[0] ?? Math.round(upem / 4)) + style.letterSpacing + style.wordSpacing

  // line box: CSS half-leading around the font's ascender and descender
  const asc = toMpt(metrics.ascender)
  const desc = toMpt(-metrics.descender)
  const baseline = Math.floor((style.lineHeight - (asc + desc)) / 2) + asc

  const shapePiece = (piece: string, offset: number): Piece => {
    const s = fonts.shape(style.face, piece, shapeOptions)
    const cum = [0]
    const dx: number[] = []
    let x = 0
    for (let i = 0; i < s.gids.length; i++) {
      dx.push(toMpt(x + s.xOffsets[i]!))
      x += s.advances[i]!
      cum.push(toMpt(x))
    }
    // letter spacing: after every cluster (the glyph that starts one carries it, like browsers do per character)
    if (style.letterSpacing) {
      let extra = 0
      for (let i = 0; i < s.gids.length; i++) {
        dx[i]! += extra
        if (s.chars[i] !== '' && (i + 1 >= s.gids.length || s.chars[i + 1] !== '')) extra += style.letterSpacing
        cum[i + 1]! += extra
      }
    }
    return { w: cum[cum.length - 1]!, text: piece, offset, gids: s.gids, dx, chars: s.chars, cum }
  }

  // ---- break opportunities -> items (a word plus the spaces after it)
  const items: Item[] = []
  const breaker = new LineBreaker(text)
  let last = 0
  for (let b = breaker.nextBreak(); b; b = breaker.nextBreak()) {
    let seg = text.slice(last, b.position)
    const segStart = last
    last = b.position
    let forced = false
    if (b.required) {
      let cut = seg.length
      while (cut > 0 && NEWLINES.includes(seg.charCodeAt(cut - 1))) cut--
      forced = cut < seg.length // a newline in the text, not just the end of it
      seg = seg.slice(0, cut)
    }
    let end = seg.length
    while (end > 0 && (seg.charCodeAt(end - 1) === 0x20 || seg.charCodeAt(end - 1) === 0x09)) end--
    const word = end > 0 ? shapePiece(seg.slice(0, end).replace(/\t/g, ' '), segStart) : null
    items.push({ word, spaces: seg.length - end, forced, offset: segStart, end: b.position })
  }
  if (items.length === 0) items.push({ word: null, spaces: 0, forced: false, offset: 0, end: 0 })

  const lines: Line[] = []
  const availFor = (i: number) => width - style.indentLeft - style.indentRight - (i === 0 ? style.firstLine : 0)
  const startFor = (i: number) => style.indentLeft + (i === 0 ? style.firstLine : 0)
  const nowrap = style.whiteSpace === 'nowrap'
  let overflows = false

  const finish = (its: Item[], isLast: boolean) => {
    const idx = lines.length
    const avail = availFor(idx)
    const lastI = its.length - 1
    let natural = 0
    let gaps = 0
    its.forEach((it, i) => {
      natural += it.word?.w ?? 0
      if (i < lastI) {
        natural += it.spaces * spaceW
        gaps += it.spaces
      }
    })
    if (natural > avail) overflows = true
    const forced = its[lastI]!.forced
    const extra = avail - natural
    let base = 0
    let rem = 0
    let offset = 0
    if (style.align === 'justify' && !isLast && !forced && gaps > 0 && extra > 0 && extra <= MAX_STRETCH * spaceW * gaps) {
      base = Math.floor(extra / gaps)
      rem = extra - base * gaps
    } else if (style.align === 'center') offset = Math.max(0, Math.floor(extra / 2))
    else if (style.align === 'right') offset = Math.max(0, extra)
    const x0 = startFor(idx) + offset
    let x = x0
    let spaceIndex = 0
    const words: PlacedWord[] = []
    let lineText = ''
    its.forEach((it, i) => {
      if (it.word) {
        words.push({ x, w: it.word.w, text: it.word.text, gids: it.word.gids, dx: it.word.dx, chars: it.word.chars, offset: it.word.offset })
        x += it.word.w
        lineText += it.word.text
      }
      if (i < lastI) {
        for (let k = 0; k < it.spaces; k++) {
          x += spaceW + base + (spaceIndex < rem ? 1 : 0)
          spaceIndex++
          lineText += ' '
        }
      }
    })
    lines.push({
      start: its[0]!.offset,
      end: its[lastI]!.end,
      x: x0,
      natural,
      baseline,
      height: style.lineHeight,
      words,
      text: lineText,
    })
  }

  const widthWith = (its: Item[], next: Item): number => {
    let w = 0
    its.forEach((it) => {
      w += (it.word?.w ?? 0) + it.spaces * spaceW
    })
    return w + (next.word?.w ?? 0)
  }

  /** A piece wider than an empty line: emit full lines of whole clusters, keep the rest as the current item. */
  const breakOverflow = (it: Item): Item => {
    const avail = availFor(lines.length)
    if (nowrap || !it.word || it.word.w <= avail) return it
    const w = it.word
    let start = 0
    const n = w.gids.length
    let current: Item = it
    while (start < n) {
      let end = start + 1
      // grow by whole clusters while they fit
      while (end < n && (w.chars[end] === '' || w.cum[end + 1]! - w.cum[start]! <= availFor(lines.length))) end++
      while (end < n && w.chars[end] === '') end++
      const chunk = slicePiece(w, start, end)
      if (end >= n) {
        current = { ...it, word: chunk, offset: chunk.offset }
        break
      }
      finish([{ word: chunk, spaces: 0, forced: true, offset: chunk.offset, end: chunk.offset + chunk.text.length }], false)
      start = end
    }
    return current
  }

  let cur: Item[] = []
  for (let it of items) {
    if (!nowrap && cur.length > 0 && widthWith(cur, it) > availFor(lines.length)) {
      finish(cur, false)
      cur = []
    }
    if (cur.length === 0) it = breakOverflow(it)
    cur.push(it)
    if (it.forced) {
      finish(cur, false)
      cur = []
    }
  }
  if (cur.length > 0) finish(cur, true)
  else finish([{ word: null, spaces: 0, forced: false, offset: text.length, end: text.length }], true)
  return { style, width, lines, height: lines.length * style.lineHeight, overflows }
}

function slicePiece(w: Piece, start: number, end: number): Piece {
  const base = w.cum[start]!
  const chars = w.chars.slice(start, end)
  const text = chars.join('')
  // offset of the chunk in the paragraph: the piece's offset plus the characters before `start`
  const before = w.chars.slice(0, start).join('').length
  return {
    w: w.cum[end]! - base,
    text,
    offset: w.offset + before,
    gids: w.gids.slice(start, end),
    dx: w.dx.slice(start, end).map((d) => d - base),
    chars,
    cum: w.cum.slice(start, end + 1).map((c) => c - base),
  }
}
