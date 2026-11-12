import { beforeAll, describe, expect, it } from 'vitest'
import { canonicalJson } from '../src/canonical'
import { FontSet } from '../src/fonts/fontset'
import { layoutParagraph, MAX_STRETCH } from '../src/text/paragraph'
import { paragraphStyle } from '../src/text/style'
import { fixture } from './fonts'
import { harfbuzz, sha256 } from './helpers'

let fonts: FontSet
const carlito = { sha256: '', variations: {} }
const inter = { sha256: '', variations: { opsz: 14, wght: 400 } }
const TEXT =
  'Eine Seite ist in Claudia keine Vermutung des Browsers mehr, sondern das Ergebnis einer Rechnung, die auf jedem Rechner dieselben Zahlen liefert.'

beforeAll(async () => {
  fonts = new FontSet(await harfbuzz())
  for (const [ref, name] of [[carlito, 'Carlito-Regular'], [inter, 'InterVariable']] as const) {
    ref.sha256 = sha256(fixture(name))
    fonts.add(ref.sha256, fixture(name))
  }
})

describe('layoutParagraph', () => {
  it('breaks into lines no wider than the measure, and keeps every character', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000), TEXT, 200000)
    expect(p.lines.length).toBeGreaterThan(2)
    for (const l of p.lines) expect(l.x + l.natural).toBeLessThanOrEqual(200000)
    expect(p.lines.map((l) => l.text).join(' ')).toBe(TEXT)
    expect(p.lines[0]!.start).toBe(0)
    expect(p.lines.at(-1)!.end).toBe(TEXT.length)
    for (let i = 1; i < p.lines.length; i++) expect(p.lines[i]!.start).toBe(p.lines[i - 1]!.end)
    expect(p.overflows).toBe(false)
  })

  it('justifies every line but the last to exactly the measure, in whole mpt', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { align: 'justify' }), TEXT, 200000)
    const m = fonts.metrics(carlito)
    const spaceW = Math.round((fonts.shape(carlito, ' ').advances[0]! * 12000) / m.unitsPerEm)
    let justified = 0
    for (const l of p.lines.slice(0, -1)) {
      const last = l.words.at(-1)!
      const gaps = l.text.split(' ').length - 1
      if (last.x + last.w === 200000) justified++
      // a line that would need its spaces stretched more than MAX_STRETCH times stays ragged
      else expect(200000 - l.natural).toBeGreaterThan(MAX_STRETCH * spaceW * gaps)
    }
    expect(justified).toBeGreaterThan(0)
    const last = p.lines.at(-1)!
    expect(last.words.at(-1)!.x + last.words.at(-1)!.w).toBe(last.natural)
  })

  it('centres and right-aligns', () => {
    const c = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { align: 'center' }), 'Mitte', 100000).lines[0]!
    expect(c.x).toBe(Math.floor((100000 - c.natural) / 2))
    const r = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { align: 'right' }), 'Rechts', 100000).lines[0]!
    expect(r.x + r.natural).toBe(100000)
  })

  it('indents the first line and the sides', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { firstLine: 20000, indentLeft: 5000, indentRight: 7000 }), TEXT, 200000)
    expect(p.lines[0]!.x).toBe(25000)
    expect(p.lines[1]!.x).toBe(5000)
    for (const l of p.lines) expect(l.x + l.natural).toBeLessThanOrEqual(200000 - 7000)
  })

  it('breaks a word wider than the line between clusters', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000), 'W'.repeat(80), 100000)
    expect(p.lines.length).toBeGreaterThan(1)
    for (const l of p.lines) expect(l.natural).toBeLessThanOrEqual(100000)
    expect(p.lines.map((l) => l.text).join('')).toBe('W'.repeat(80))
  })

  it('keeps a line together with white-space: nowrap and says that it overflows', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { whiteSpace: 'nowrap' }), TEXT, 100000)
    expect(p.lines).toHaveLength(1)
    expect(p.overflows).toBe(true)
  })

  it('starts a new line at a newline in the text', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000), 'eins\nzwei', 300000)
    expect(p.lines.map((l) => l.text)).toEqual(['eins', 'zwei'])
  })

  it('gives an empty paragraph one empty line', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { lineHeight: 18000 }), '', 300000)
    expect(p.lines).toHaveLength(1)
    expect(p.height).toBe(18000)
  })

  it('maps a ligature glyph back to all its letters', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 12000), 'office', 300000)
    const w = p.lines[0]!.words[0]!
    expect(w.chars.join('')).toBe('office')
    expect(w.gids.length).toBeLessThan(6) // the ffi ligature
  })

  it('places the baseline by half-leading, as CSS does', () => {
    const p = layoutParagraph(fonts, paragraphStyle(carlito, 10000, { lineHeight: 20000 }), 'x', 300000)
    const m = fonts.metrics(carlito)
    const asc = Math.round((m.ascender * 10000) / m.unitsPerEm)
    const desc = Math.round((-m.descender * 10000) / m.unitsPerEm)
    expect(p.lines[0]!.baseline).toBe(Math.floor((20000 - asc - desc) / 2) + asc)
  })

  it('spaces letters out with letter-spacing', () => {
    const plain = layoutParagraph(fonts, paragraphStyle(carlito, 12000), 'abc', 300000).lines[0]!.natural
    const spaced = layoutParagraph(fonts, paragraphStyle(carlito, 12000, { letterSpacing: 1000 }), 'abc', 300000).lines[0]!.natural
    expect(spaced).toBe(plain + 3000)
  })

  it('gives the same result for the same input (a fingerprint)', () => {
    const a = canonicalJson(layoutParagraph(fonts, paragraphStyle(inter, 10500, { align: 'justify' }), TEXT, 150000))
    const b = canonicalJson(layoutParagraph(fonts, paragraphStyle(inter, 10500, { align: 'justify' }), TEXT, 150000))
    expect(a).toBe(b)
  })
})
