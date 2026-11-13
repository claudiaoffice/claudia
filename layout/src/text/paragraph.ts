/// <reference path="./linebreak.d.ts" />
/**
 * Paragraph to lines: break a paragraph of one style into lines of a given width.
 *
 * Break opportunities are those of the Unicode line breaking algorithm (UAX #14), plus the places a word may be
 * hyphenated: a soft hyphen (U+00AD) typed into it, and, with `hyphens: auto`, the points the language's patterns
 * give ({@link Hyphenator}). Each piece between two opportunities is shaped once by HarfBuzz.
 *
 * Lines are chosen for the whole paragraph at once, by Knuth and Plass's algorithm (the one TeX uses, D912): every
 * way of breaking is weighed by how much its lines stretch or shrink, and the paragraph with the least *demerits*
 * wins. It runs up to three times: without automatic hyphens and strictly; then with them; then accepting anything
 * that fits, and breaking a word too long for a line between letters. Ragged text (left, centre, right) is weighed
 * against a fixed slack per line, so its lines come out even too. Every quantity is a whole mpt and every
 * computation is on integers, so the same paragraph breaks the same way in every engine.
 *
 * Justified lines spread the remaining width over their spaces as whole mpt, the remainder going to the first
 * spaces. The result does not depend on where the paragraph will be placed, so it can be cached and reused by a
 * page, a box or a table cell.
 *
 * @module
 */
import LineBreaker from 'linebreak'
import type { FontSet } from '../fonts/fontset'
import { mulDivRound } from '../units'
import { HYPHENATION, type Hyphenator } from './hyphenate'
import type { ParagraphStyle } from './style'

/** Justification stretches a space at most this many times its natural width; looser lines stay ragged. */
export const MAX_STRETCH = 3

/** A shaped word (or the part of one on a line) placed on a line. Lengths in mpt; `x` is relative to the paragraph. */
export interface PlacedWord {
  x: number
  /** advance width */
  w: number
  /** the text drawn: soft hyphens left out, a hyphen added where the word is broken */
  text: string
  gids: number[]
  /** where each glyph is drawn, from `x` */
  dx: number[]
  /** the characters each glyph stands for (`''` for the second glyph of a cluster) */
  chars: string[]
  /** UTF-16 offset of the word in the paragraph text, and how many characters of it the word stands for */
  offset: number
  length: number
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
  /** the line ends in a hyphen the layout added (a word broken at a soft hyphen or a hyphenation point) */
  hyphenated: boolean
}

export interface ParagraphLayout {
  style: ParagraphStyle
  /** the width the lines were broken for */
  width: number
  lines: Line[]
  /** sum of the line heights (not counting space before and after) */
  height: number
  /** true when a line is wider than `width` (`white-space: nowrap`, or a letter wider than a line) */
  overflows: boolean
}

/** What a paragraph needs besides its style: the hyphenation patterns of its language, if any. */
export interface ParagraphOptions {
  hyphenator?: Hyphenator | null
}

interface Piece {
  w: number
  /** the shaped text: the source with soft hyphens taken out */
  text: string
  /** source offset of each character of `text`, and of its end (`text.length + 1` entries) */
  src: number[]
  gids: number[]
  dx: number[]
  chars: string[]
  /** cumulative advances in mpt, gids.length + 1 long */
  cum: number[]
}
interface Item {
  word: Piece | null
  spaces: number
  forced: boolean
  offset: number
  end: number
  /** glyph indices a word may be broken before: soft hyphens, then (with `hyphens: auto`) pattern points */
  manual: number[]
  auto: number[]
  /** the word ends in a hyphen of its own (`E-`), so breaking after it shows that hyphen */
  explicit: boolean
  /** the word ends in a soft hyphen (UAX #14 breaks after one): breaking after it draws a hyphen */
  soft: boolean
  /** no break after the word (it ends in a soft hyphen and `hyphens` is `none`) */
  glued: boolean
}

// ---- the elements of Knuth and Plass: boxes, glue and penalties
interface Box {
  t: 'box'
  w: number
  item: number
  g0: number
  g1: number
}
interface Glue {
  t: 'glue'
  w: number
  stretch: number
  shrink: number
  /** infinite stretch (the end of a paragraph or of a line ended by a newline) */
  fil: number
  item: number
}
interface Penalty {
  t: 'pen'
  /** width added when the line breaks here (a hyphen) */
  w: number
  p: number
  flagged: boolean
  item: number
  /** the glyph the word is broken before, or -1 for a break after the whole item */
  g: number
  /** a hyphen is drawn when the line breaks here */
  hyphen: boolean
}
type El = Box | Glue | Penalty

const INFINITY = 10000
const FORCED = -INFINITY
const LINE_PENALTY = 10
const HYPHEN_PENALTY = 50
const EXPLICIT_PENALTY = 50
/** a break between the letters of a word too long for a line: only when nothing else fits */
const EMERGENCY_PENALTY = 5000
const DOUBLE_HYPHEN_DEMERITS = 10000
const ADJACENT_DEMERITS = 10000
/** a paragraph's last line made of the end of a hyphenated word (D912: as good as never) */
const LAST_LINE_HYPHEN_DEMERITS = 1_000_000
/**
 * The passes, as TeX makes them: strict and without pattern hyphens; with them; with extra stretch for every line
 * (TeX's emergency stretch, for a measure too narrow for the words); and finally anything at all, a line that cannot
 * be made to fit included.
 */
const PASSES = [
  { tolerance: 100, auto: false, stretch: false, emergency: false },
  { tolerance: 200, auto: true, stretch: false, emergency: false },
  { tolerance: 200, auto: true, stretch: true, emergency: false },
  { tolerance: INFINITY, auto: true, stretch: true, emergency: true },
] as const
/** the emergency stretch, in em: what a ragged line may fall short at little cost, too */
const EMERGENCY_EM = 1.5
const RAGGED_EM = 3

const NEWLINES = [0x0a, 0x0d, 0x85, 0x2028, 0x2029]
const SOFT_HYPHEN = '­'
const HYPHEN_CHARS = new Set(['-', '‐', '‒', '–'])
const LETTERS = /\p{L}[\p{L}\p{M}]*/gu

/** TeX's badness: about 100·(t/s)³, in integers; {@link INFINITY} when there is no room to stretch at all. */
export function badness(t: number, s: number): number {
  if (t === 0) return 0
  if (s <= 0) return INFINITY
  const r = Math.floor((t * 297) / s)
  if (r > 1290) return INFINITY
  return Math.floor((r * r * r + 0x20000) / 0x40000)
}

/** Lay out `text` with `style` into lines of `width` mpt. */
export function layoutParagraph(fonts: FontSet, style: ParagraphStyle, text: string, width: number, options: ParagraphOptions = {}): ParagraphLayout {
  const metrics = fonts.metrics(style.face)
  const upem = metrics.unitsPerEm
  const toMpt = (units: number) => mulDivRound(units, style.size, upem)
  const shapeOptions = style.language ? { language: style.language } : {}
  const space = fonts.shape(style.face, ' ', shapeOptions)
  const spaceW = toMpt(space.advances[0] ?? Math.round(upem / 4)) + style.letterSpacing + style.wordSpacing
  const justify = style.align === 'justify'
  const hyphens = style.hyphens ?? 'manual'
  const hyphenator = hyphens === 'auto' ? (options.hyphenator ?? null) : null

  // line box: CSS half-leading around the font's ascender and descender
  const asc = toMpt(metrics.ascender)
  const desc = toMpt(-metrics.descender)
  const baseline = Math.floor((style.lineHeight - (asc + desc)) / 2) + asc

  const shapePiece = (source: string, offset: number): Piece => {
    let shaped = ''
    const src: number[] = []
    for (let i = 0; i < source.length; i++) {
      if (source[i] === SOFT_HYPHEN) continue
      shaped += source[i] === '\t' ? ' ' : source[i]
      src.push(offset + i)
    }
    src.push(offset + source.length)
    const s = fonts.shape(style.face, shaped, shapeOptions)
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
    return { w: cum[cum.length - 1]!, text: shaped, src, gids: s.gids, dx, chars: s.chars, cum }
  }

  // the hyphen drawn where a word is broken
  const hyphenShape = fonts.shape(style.face, '-', shapeOptions)
  const hyphenGlyphs = hyphenShape.gids.map((gid, i) => ({ gid, dx: toMpt(hyphenShape.xOffsets[i]!) }))
  const hyphenW = toMpt(hyphenShape.advances.reduce((a, b) => a + b, 0)) + style.letterSpacing

  /** glyph index that starts the cluster beginning at text index t of the piece, or -1 */
  const clusterStarts = (w: Piece): Map<number, number> => {
    const out = new Map<number, number>()
    let pos = 0
    let monotonic = true
    for (let g = 0; g < w.chars.length; g++) {
      const c = w.chars[g]!
      if (c === '') continue
      out.set(pos, g)
      pos += c.length
    }
    if (pos !== w.text.length) monotonic = false // a right-to-left run: no breaks inside it
    return monotonic ? out : new Map()
  }

  // ---- break opportunities -> items (a word plus the spaces after it)
  const items: Item[] = []
  const breaker = new LineBreaker(text)
  let last = 0
  let afterSoft = false
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
    const source = seg.slice(0, end)
    const word = end > 0 && source.replaceAll(SOFT_HYPHEN, '') !== '' ? shapePiece(source, segStart) : null
    const manual: number[] = []
    const auto: number[] = []
    let explicit = false
    // a soft hyphen ends a piece (UAX #14 breaks after it); `none` does not break there at all
    const endsSoft = source.endsWith(SOFT_HYPHEN) && end === seg.length && !forced
    const soft = hyphens !== 'none' && endsSoft
    const partOfSoft = afterSoft || soft
    afterSoft = soft
    if (word) {
      explicit = HYPHEN_CHARS.has(word.text.at(-1)!)
      const starts = clusterStarts(word)
      if (hyphens !== 'none' && source.includes(SOFT_HYPHEN)) {
        // a soft hyphen typed into the word: break there (and only there, as TeX does)
        let shapedIndex = 0
        for (let i = 0; i < source.length; i++) {
          if (source[i] === SOFT_HYPHEN) {
            const g = starts.get(shapedIndex)
            if (g !== undefined && g > 0 && !manual.includes(g)) manual.push(g)
          } else shapedIndex++
        }
      } else if (hyphenator && !partOfSoft) {
        for (const m of word.text.matchAll(LETTERS)) {
          const letters = m[0]
          if ([...letters].length < HYPHENATION.minWord) continue
          for (const p of hyphenator.points(letters)) {
            const before = [...letters.slice(0, p)].length
            const after = [...letters.slice(p)].length
            if (before < HYPHENATION.left || after < HYPHENATION.right) continue
            const g = starts.get(m.index + p)
            if (g !== undefined && g > 0) auto.push(g)
          }
        }
      }
    }
    items.push({ word, spaces: seg.length - end, forced, offset: segStart, end: b.position, manual, auto, explicit, soft, glued: endsSoft && !soft })
  }
  if (items.length === 0) items.push({ word: null, spaces: 0, forced: false, offset: 0, end: 0, manual: [], auto: [], explicit: false, soft: false, glued: false })

  const availFor = (i: number) => width - style.indentLeft - style.indentRight - (i === 0 ? style.firstLine : 0)
  const startFor = (i: number) => style.indentLeft + (i === 0 ? style.firstLine : 0)
  const narrowest = Math.min(availFor(0), availFor(1))

  // ---- choose the breaks
  let breaks: El[] | null = null
  let els: El[] = []
  if (style.whiteSpace === 'nowrap') {
    els = elements(items, spaceW, justify, hyphenW, narrowest, true, true)
    breaks = [els.at(-1)!]
  } else {
    for (const pass of PASSES) {
      els = elements(items, spaceW, justify, hyphenW, narrowest, pass.auto, false)
      // ragged lines may fall 3 em short at little cost; justified ones only get the emergency stretch
      const slack = justify ? (pass.stretch ? Math.round(style.size * EMERGENCY_EM) : 0) : style.size * RAGGED_EM
      breaks = choose(els, availFor, slack, pass.tolerance, pass.emergency)
      if (breaks) break
    }
  }

  // ---- lines from the breaks
  const lines: Line[] = []
  let overflows = false
  let from = 0
  let carry: { item: number; g: number } | null = null // a word broken by a hyphen: where its rest starts
  for (const brk of breaks!) {
    const to = els.indexOf(brk)
    const idx = lines.length
    // the line's pieces: [item, g0, g1] glyph ranges, merged per item, and the spaces after each
    const parts: { item: number; g0: number; g1: number; spaces: number }[] = []
    for (let k = from; k < to; k++) {
      const el = els[k]!
      if (el.t === 'box') {
        const prev = parts.at(-1)
        if (prev && prev.item === el.item && prev.g1 === el.g0 && prev.spaces === 0) prev.g1 = el.g1
        else parts.push({ item: el.item, g0: el.g0, g1: el.g1, spaces: 0 })
      } else if (el.t === 'glue' && el.fil === 0) {
        const prev = parts.at(-1)
        if (prev && prev.item === el.item) prev.spaces += items[el.item]!.spaces
        else parts.push({ item: el.item, g0: 0, g1: 0, spaces: items[el.item]!.spaces })
      }
    }
    const brkG = brk.t === 'pen' ? brk.g : -1
    const hyphen = brk.t === 'pen' && brk.hyphen && brkG >= 0
    const isLast = brk === els.at(-1)
    const endsParagraphLine = isLast || (brk.t === 'pen' && brk.p === FORCED)
    // spaces after the last word of a line are not part of it
    const lastPart = parts.at(-1)
    if (lastPart) lastPart.spaces = 0

    const words: PlacedWord[] = []
    let natural = 0
    let gaps = 0
    parts.forEach((part, i) => {
      const word = items[part.item]!.word
      if (word && part.g1 > part.g0) natural += word.cum[part.g1]! - word.cum[part.g0]!
      if (i < parts.length - 1) {
        natural += part.spaces * spaceW
        gaps += part.spaces
      }
    })
    if (hyphen) natural += hyphenW
    const avail = availFor(idx)
    const extra = avail - natural
    let base = 0
    let rem = 0
    let offset = 0
    const shrinkable = gaps * Math.floor(spaceW / 3)
    // justified lines stretch or shrink their spaces to the measure; any line too long shrinks them (as TeX does,
    // even the last line of a paragraph)
    if (gaps > 0 && ((justify && !endsParagraphLine && extra >= 0 && extra <= MAX_STRETCH * spaceW * gaps) || (extra < 0 && extra >= -shrinkable))) {
      base = Math.floor(extra / gaps)
      rem = extra - base * gaps
    } else if (style.align === 'center') offset = Math.max(0, Math.floor(extra / 2))
    else if (style.align === 'right') offset = Math.max(0, extra)
    const x0 = startFor(idx) + offset
    let x = x0
    let spaceIndex = 0
    let lineText = ''
    parts.forEach((part, i) => {
      const word = items[part.item]!.word
      if (word && part.g1 > part.g0) {
        const placed = placeWord(word, part.g0, part.g1, x)
        if (hyphen && i === parts.length - 1) addHyphen(placed)
        const prev = words.at(-1)
        if (prev && prev.x + prev.w === x && prev.offset + prev.length === placed.offset) {
          // pieces of one word (split at a soft hyphen): one word on the line
          for (let g = 0; g < placed.gids.length; g++) {
            prev.gids.push(placed.gids[g]!)
            prev.dx.push(placed.dx[g]! + prev.w)
            prev.chars.push(placed.chars[g]!)
          }
          prev.w += placed.w
          prev.text += placed.text
          prev.length += placed.length
        } else words.push(placed)
        x += placed.w
        lineText += placed.text
      }
      for (let k = 0; k < part.spaces; k++) {
        x += spaceW + base + (spaceIndex < rem ? 1 : 0)
        spaceIndex++
        lineText += ' '
      }
    })
    const right = words.length ? words.at(-1)!.x + words.at(-1)!.w : x0
    if (right > startFor(idx) + avail) overflows = true
    const first = parts[0]
    const firstItem = first ? items[first.item]! : items[brk.item]!
    const start = carry && first && carry.item === first.item ? firstItem.word!.src[charsBefore(firstItem.word!, carry.g)]! : firstItem.offset
    let end: number
    if (hyphen) {
      const w = items[brk.item]!.word!
      end = w.src[charsBefore(w, brkG)]!
      carry = { item: brk.item, g: brkG }
    } else {
      end = isLast ? text.length : items[brk.item]!.end
      carry = null
    }
    lines.push({ start, end, x: x0, natural, baseline, height: style.lineHeight, words, text: lineText, hyphenated: hyphen })
    // the next line starts after the break and whatever is discarded there (glue, penalties)
    from = nextStart(els, to)
  }
  if (lines.length === 0) lines.push({ start: text.length, end: text.length, x: startFor(0), natural: 0, baseline, height: style.lineHeight, words: [], text: '', hyphenated: false })
  return { style, width, lines, height: lines.length * style.lineHeight, overflows }

  function placeWord(w: Piece, g0: number, g1: number, x: number): PlacedWord {
    const base = w.cum[g0]!
    const chars = w.chars.slice(g0, g1)
    const a = charsBefore(w, g0)
    const b = charsBefore(w, g1)
    return {
      x,
      w: w.cum[g1]! - base,
      text: chars.join(''),
      gids: w.gids.slice(g0, g1),
      dx: w.dx.slice(g0, g1).map((d) => d - base),
      chars,
      offset: w.src[a]!,
      length: w.src[b]! - w.src[a]!,
    }
  }
  function addHyphen(placed: PlacedWord) {
    if (!hyphenGlyphs.length) return
    hyphenGlyphs.forEach((h, i) => {
      placed.gids.push(h.gid)
      placed.dx.push(placed.w + h.dx)
      placed.chars.push(i === 0 ? '-' : '')
    })
    placed.w += hyphenW
    placed.text += '-'
  }
}

/** Where the line after a break at `at` starts: past the glue and penalties discarded at the break. */
function nextStart(els: readonly El[], at: number): number {
  let s = at + 1
  while (s < els.length) {
    const el = els[s]!
    if (el.t === 'box' || (el.t === 'pen' && el.p === FORCED) || (el.t === 'glue' && el.fil > 0)) break
    s++
  }
  return s
}

/** Characters of the shaped text before glyph `g` (whole clusters). */
function charsBefore(w: Piece, g: number): number {
  let n = 0
  for (let i = 0; i < g && i < w.chars.length; i++) n += w.chars[i]!.length
  return n
}

/** The paragraph as boxes, glue and penalties. */
function elements(items: readonly Item[], spaceW: number, justify: boolean, hyphenW: number, narrowest: number, withAuto: boolean, nowrap: boolean): El[] {
  const els: El[] = []
  items.forEach((it, i) => {
    const w = it.word
    if (w) {
      const cuts = new Set<number>(it.manual)
      if (withAuto) for (const g of it.auto) cuts.add(g)
      // a word too long for any line may be broken between its clusters, as a last resort
      const emergency = new Set<number>()
      if (!nowrap && w.w > narrowest) {
        for (let g = 1; g < w.gids.length; g++) if (w.chars[g] !== '' && !cuts.has(g)) emergency.add(g)
      }
      const all = [...cuts, ...emergency].sort((a, b) => a - b)
      let g0 = 0
      for (const g of all) {
        els.push({ t: 'box', w: w.cum[g]! - w.cum[g0]!, item: i, g0, g1: g })
        if (!nowrap) {
          const hyphen = cuts.has(g)
          els.push({ t: 'pen', w: hyphen ? hyphenW : 0, p: hyphen ? HYPHEN_PENALTY : EMERGENCY_PENALTY, flagged: hyphen, item: i, g, hyphen })
        }
        g0 = g
      }
      els.push({ t: 'box', w: w.w - w.cum[g0]!, item: i, g0, g1: w.gids.length })
    }
    const lastItem = i === items.length - 1
    if (it.forced || lastItem) {
      els.push({ t: 'glue', w: 0, stretch: 0, shrink: 0, fil: 1, item: i })
      els.push({ t: 'pen', w: 0, p: FORCED, flagged: false, item: i, g: -1, hyphen: false })
    } else if (it.spaces > 0) {
      els.push({
        t: 'glue',
        w: it.spaces * spaceW,
        stretch: justify ? it.spaces * Math.floor(spaceW / 2) : 0,
        shrink: justify ? it.spaces * Math.floor(spaceW / 3) : 0,
        fil: 0,
        item: i,
      })
    } else if (!nowrap && w && it.soft) {
      // a soft hyphen at the end of the piece: a hyphen is drawn if the line breaks here
      els.push({ t: 'pen', w: hyphenW, p: HYPHEN_PENALTY, flagged: true, item: i, g: w.gids.length, hyphen: true })
    } else if (!nowrap && w && !it.glued) {
      // a break after the item without a space (after a hyphen, a slash, between ideographs)
      els.push({ t: 'pen', w: 0, p: it.explicit ? EXPLICIT_PENALTY : 0, flagged: it.explicit, item: i, g: -1, hyphen: false })
    }
  })
  return els
}

interface Node {
  /** the element the line before broke at (-1: the start of the paragraph), and where the next line starts */
  at: number
  start: number
  line: number
  fitness: number
  /** lines in a row ending in a hyphen, up to and including the one ending here */
  hyphens: number
  /** the line ending here ends in a hyphen the layout drew (not one of the text's own) */
  hyphenated: boolean
  flagged: boolean
  demerits: number
  prev: Node | null
}

/**
 * The best breaks for `els`, or `null` if none keeps every line within `tolerance`. `availFor(line)` is a line's
 * width; `ragged` is the slack a ragged line may have at no cost (0 for justified text). With `emergency`, a line
 * that cannot be made to fit is taken anyway rather than giving up.
 */
function choose(els: readonly El[], availFor: (line: number) => number, ragged: number, tolerance: number, emergency: boolean): El[] | null {
  // running sums before each element
  const n = els.length
  const W = new Array<number>(n + 1).fill(0)
  const Y = new Array<number>(n + 1).fill(0)
  const Z = new Array<number>(n + 1).fill(0)
  const F = new Array<number>(n + 1).fill(0)
  for (let i = 0; i < n; i++) {
    const el = els[i]!
    W[i + 1] = W[i]! + (el.t === 'pen' ? 0 : el.w)
    Y[i + 1] = Y[i]! + (el.t === 'glue' ? el.stretch : 0)
    Z[i + 1] = Z[i]! + (el.t === 'glue' ? el.shrink : 0)
    F[i + 1] = F[i]! + (el.t === 'glue' ? el.fil : 0)
  }

  let active: Node[] = [{ at: -1, start: 0, line: 0, fitness: 2, hyphens: 0, hyphenated: false, flagged: false, demerits: 0, prev: null }]
  for (let i = 0; i < n; i++) {
    const el = els[i]!
    const breakable = el.t === 'pen' ? el.p < INFINITY : el.t === 'glue' && i > 0 && els[i - 1]!.t === 'box'
    if (!breakable) continue
    const p = el.t === 'pen' ? el.p : 0
    const flagged = el.t === 'pen' && el.flagged
    const drawsHyphen = el.t === 'pen' && el.hyphen && el.g >= 0
    const best = new Map<string, Node>()
    const keep: Node[] = []
    const dropped: { node: Node; fitness: number }[] = []
    for (const a of active) {
      const natural = W[i]! - W[a.start]! + (el.t === 'pen' ? el.w : 0)
      const avail = availFor(a.line)
      const diff = avail - natural
      let bad: number
      let fitness: number
      if (diff >= 0) {
        bad = F[i]! - F[a.start]! > 0 ? 0 : badness(diff, Y[i]! - Y[a.start]! + ragged)
        fitness = bad > 99 ? 0 : bad > 12 ? 1 : 2
      } else {
        const shrink = Z[i]! - Z[a.start]!
        bad = -diff > shrink ? INFINITY + 1 : badness(-diff, shrink)
        fitness = bad > 12 ? 3 : 2
      }
      const overfull = bad > INFINITY
      // a node stays active while lines from it may still fit (not overfull) and no forced break has come
      const stays = !overfull && p !== FORCED
      if (stays) keep.push(a)
      const feasible = !overfull && bad <= tolerance
      if (!feasible) {
        if (!stays) dropped.push({ node: a, fitness })
        continue
      }
      if (flagged && a.hyphens >= HYPHENATION.maxConsecutive) continue
      let d = (LINE_PENALTY + Math.min(bad, INFINITY)) ** 2
      if (p > 0) d += p * p
      else if (p > FORCED) d -= p * p
      if (flagged && a.flagged) d += DOUBLE_HYPHEN_DEMERITS
      if (p === FORCED && a.hyphenated) d += LAST_LINE_HYPHEN_DEMERITS
      if (Math.abs(fitness - a.fitness) > 1) d += ADJACENT_DEMERITS
      const total = a.demerits + d
      const hyphens = flagged ? a.hyphens + 1 : 0
      // every line after the first has the same width, so nodes differing only in their line number are alike
      const key = `${fitness}:${hyphens}:${drawsHyphen ? 1 : 0}`
      const known = best.get(key)
      if (!known || total < known.demerits) {
        best.set(key, { at: i, start: nextStart(els, i), line: a.line + 1, fitness, hyphens, hyphenated: drawsHyphen, flagged, demerits: total, prev: a })
      }
    }
    if (emergency && keep.length === 0 && best.size === 0 && dropped.length) {
      // nothing fits any more: break here anyway, after the best line so far (a line wider than the measure)
      let rescue = dropped[0]!
      for (const d of dropped) if (d.node.demerits < rescue.node.demerits) rescue = d
      const a = rescue.node
      const hyphens = flagged ? a.hyphens + 1 : 0
      best.set('rescue', { at: i, start: nextStart(els, i), line: a.line + 1, fitness: rescue.fitness, hyphens, hyphenated: drawsHyphen, flagged, demerits: a.demerits + (LINE_PENALTY + INFINITY) ** 2, prev: a })
    }
    active = [...keep, ...[...best.entries()].sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0)).map(([, v]) => v)]
    if (active.length === 0) return null
  }
  // every paragraph ends in a forced break, so only nodes breaking there are left
  let bestNode: Node | null = null
  for (const a of active) if (a.at === n - 1 && (!bestNode || a.demerits < bestNode.demerits)) bestNode = a
  if (!bestNode) return null
  const out: El[] = []
  for (let a: Node | null = bestNode; a && a.at >= 0; a = a.prev) out.push(els[a.at]!)
  return out.reverse()
}
