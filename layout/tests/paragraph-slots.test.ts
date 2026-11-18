import { beforeAll, describe, expect, it } from 'vitest'
import { canonicalJson } from '../src/canonical'
import { FontSet } from '../src/fonts/fontset'
import { layoutParagraph, type Slot, type SlotSource } from '../src/text/paragraph'
import { paragraphStyle } from '../src/text/style'
import { fixture } from './fonts'
import { harfbuzz, sha256 } from './helpers'

let fonts: FontSet
const carlito = { sha256: '', variations: {} }
const TEXT =
  'Eine Seite ist in Claudia keine Vermutung des Browsers mehr, sondern das Ergebnis einer Rechnung, die auf jedem Rechner dieselben Zahlen liefert.'
const WIDTH = 300_000

beforeAll(async () => {
  fonts = new FontSet(await harfbuzz())
  carlito.sha256 = sha256(fixture('Carlito-Regular'))
  fonts.add(carlito.sha256, fixture('Carlito-Regular'))
})

const style = (extra = {}) => paragraphStyle(carlito, 12000, { lineHeight: 15000, ...extra })

/** a source from a list of slots, the last one repeating */
const fixed = (slots: readonly Slot[]): ((widest: number) => SlotSource) => () => ({ at: (i) => slots[Math.min(i, slots.length - 1)]! })
const full = (row: number): Slot => ({ x: 0, w: WIDTH, row, lead: 0 })

describe('layoutParagraph beside an object', () => {
  it('breaks exactly as it does without slots when every slot is the whole measure', () => {
    const plain = layoutParagraph(fonts, style(), TEXT, WIDTH)
    const rows = Array.from({ length: 40 }, (_, i) => full(i))
    const slotted = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    expect(slotted.lines.map((l) => [l.start, l.end, l.x, l.natural])).toEqual(plain.lines.map((l) => [l.start, l.end, l.x, l.natural]))
    expect(slotted.height).toBe(plain.height)
  })

  it('puts the words of a line into its slot: the left edge where the slot starts, none wider than the slot', () => {
    const narrow: Slot = { x: 120_000, w: 180_000, row: 0, lead: 0 }
    const rows = [narrow, { ...narrow, row: 1 }, full(2), full(3), full(4), full(5), full(6), full(7), full(8)]
    const p = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    for (const l of p.lines.slice(0, 2)) {
      expect(l.x).toBeGreaterThanOrEqual(120_000)
      expect(l.x + l.natural).toBeLessThanOrEqual(300_000)
    }
    expect(p.lines.map((l) => l.text).join(' ')).toBe(TEXT)
  })

  it('applies the paragraph indent only where the slot touches the column edge, and the first line once', () => {
    const rows = [{ x: 100_000, w: 200_000, row: 0, lead: 0 }, ...Array.from({ length: 30 }, (_, i) => full(i + 1))]
    const p = layoutParagraph(fonts, style({ indentLeft: 20_000, firstLine: 10_000 }), TEXT, WIDTH, { slots: fixed(rows) })
    expect(p.lines[0]!.x).toBe(110_000) // slot x, the first line's indent, no left indent: not at the edge
    expect(p.lines[1]!.x).toBe(20_000) // a full slot touches the edge
  })

  it('lets two slots of one row be two lines on one row: the first has no advance of its own', () => {
    const left: Slot = { x: 0, w: 100_000, row: 0, lead: 0 }
    const right: Slot = { x: 200_000, w: 100_000, row: 0, lead: 0 }
    const rows = [left, right, ...Array.from({ length: 30 }, (_, i) => full(i + 1))]
    const p = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    expect(p.lines[0]!.advance).toBe(0)
    expect(p.lines[1]!.advance).toBe(15_000)
    expect(p.lines[2]!.advance).toBe(15_000)
    expect(p.lines[1]!.x).toBeGreaterThanOrEqual(200_000)
    expect(p.height).toBe(p.lines.reduce((s, l) => s + (l.lead ?? 0) + (l.advance ?? 0), 0))
  })

  it('carries the space a row was pushed down by as the lead of its first line, once per row', () => {
    const rows = [{ ...full(0), lead: 40_000 }, ...Array.from({ length: 30 }, (_, i) => full(i + 1))]
    const p = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    expect(p.lines[0]!.lead).toBe(40_000)
    expect(p.lines[1]!.lead).toBe(0)
  })

  it('does not hold a word back that is wider than a slot it is not given: the source is told the widest word', () => {
    let told = 0
    layoutParagraph(fonts, style(), 'Donaudampfschifffahrtsgesellschaft und so weiter', WIDTH, {
      slots: (widest) => {
        told = widest
        return { at: (i) => full(i) }
      },
    })
    expect(told).toBeGreaterThan(100_000)
  })

  it('is the same every time', () => {
    const rows = [{ x: 120_000, w: 180_000, row: 0, lead: 0 }, ...Array.from({ length: 30 }, (_, i) => full(i + 1))]
    const a = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    const b = layoutParagraph(fonts, style(), TEXT, WIDTH, { slots: fixed(rows) })
    expect(canonicalJson(a)).toBe(canonicalJson(b))
  })
})
