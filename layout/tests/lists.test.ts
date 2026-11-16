// List items on the page (E9.21, E9.22): the marker is drawn in the gutter before the text, by the same geometry the
// editor uses (`itemGeometry`, which the web app's CSS is made from), so a list looks the same printed and on screen.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { layoutText, type TextDocument, type TextStyle } from '../src/apps/composes'
import { walk, type GlyphRun } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { itemGeometry, MARKER_GAP_EM } from '../src/text/list-geometry'
import { here } from './helpers'
import { hyphenatorFor } from './fonts'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

const STYLES: TextStyle[] = JSON.parse(readFileSync(join(here, 'composes-styles.json'), 'utf8'))
const A4 = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait' as const, margins: [70866, 70866, 70866, 70866] as [number, number, number, number], page_numbers: false }
const LISTS = [{ id: 'l1', scheme: 'numbers' }, { id: 'l2', scheme: 'bullets' }]
const SCHEMES = [{ id: 'numbers', indent: 1.6, gap: 0.25 }, { id: 'bullets', indent: 2, gap: 0.5 }]

describe('where a list item sits', () => {
  const blocks = [{ item: { list: 'l1', level: 0 } }, { item: { list: 'l1', level: 1 } }, { item: null }, { item: { list: 'l2', level: 0 } }]
  it('moves a level in by its scheme’s indent, and puts its scheme’s gap only before the next item of its list', () => {
    expect(itemGeometry(blocks, 0, LISTS, SCHEMES)).toEqual({ left: 0, step: 1.6, pad: 1.6, gap: 0.25 })
    expect(itemGeometry(blocks, 1, LISTS, SCHEMES)).toEqual({ left: 1.6, step: 1.6, pad: 3.2, gap: null })
    expect(itemGeometry(blocks, 2, LISTS, SCHEMES)).toBeNull()
    expect(itemGeometry(blocks, 3, LISTS, SCHEMES)).toEqual({ left: 0, step: 2, pad: 2, gap: null })
  })
  it('falls back to the default indent and gap for a list whose scheme has not arrived', () => {
    expect(itemGeometry([{ item: { list: 'lx', level: 0 } }, { item: { list: 'lx', level: 0 } }], 0, [], [])).toEqual({ left: 0, step: 1.6, pad: 1.6, gap: 0.25 })
  })
})

describe('a list on the page', () => {
  const words = 'Ein Punkt der Liste, lang genug, dass er über das Ende der ersten Zeile hinaus in eine zweite umbricht und weiterläuft.'
  const doc = (extra: Partial<TextDocument> = {}): TextDocument => ({
    blocks: [
      { id: 'b1', style: 'body', text: 'Davor.' },
      { id: 'b2', style: 'body', text: words, item: { list: 'l1', level: 0 }, label: { marker: '1.' } },
      { id: 'b3', style: 'body', text: 'Innen.', item: { list: 'l1', level: 1 }, label: { marker: 'a.' } },
      { id: 'b4', style: 'body', text: 'Zwei.', item: { list: 'l1', level: 0 }, label: { marker: '2.' } },
      { id: 'b5', style: 'body', text: 'Zehn.', item: { list: 'l1', level: 0 }, label: { marker: '10.' } },
    ],
    styles: STYLES,
    page: A4,
    language: 'de',
    lists: LISTS,
    schemes: SCHEMES,
    ...extra,
  })
  const runs = (d: TextDocument) => [...walk(layoutText(d, fonts, resolver, { hyphenator: hyphenatorFor('de') }).list.pages[0]!.items)].filter((r): r is GlyphRun => r.kind === 'glyphs')

  it('draws every marker on the first line of its item, right-aligned in its box, and moves the text in', () => {
    const all = runs(doc())
    const at = (text: string) => all.find((r) => r.text === text)!
    const left = at('Davor.').x
    const size = 12000 // body text, 12pt in mpt
    for (const [marker, first, level] of [['1.', 'Ein', 0], ['a.', 'Innen.', 1], ['2.', 'Zwei.', 0]] as const) {
      const m = at(marker)
      const textStart = left + (level + 1) * 1.6 * size
      expect(m.y).toBe(at(first).y)
      expect(at(first).x).toBeCloseTo(textStart, -1)
      // in its box: after the level's indent, and ending at least MARKER_GAP_EM before the text
      expect(m.x).toBeGreaterThanOrEqual(left + level * 1.6 * size)
      expect(m.x).toBeLessThan(textStart - MARKER_GAP_EM * size)
    }
    // right-aligned: a wider number starts further left and ends where the narrower one does
    expect(at('10.').x).toBeLessThan(at('1.').x)
    // the second line of the long item starts where its first line's text does, not under the marker
    const lines = [...new Set(all.filter((r) => words.includes(r.text)).map((r) => r.y))]
    expect(lines.length).toBeGreaterThan(1)
    expect(Math.min(...all.filter((r) => r.y === lines[1]).map((r) => r.x))).toBeCloseTo(at('Ein').x, -1)
  })

  it('draws the marker upright and in the regular weight, as the editor does, even in a bold italic style', () => {
    const loud = STYLES.map((s) => (s.id === 'body' ? { ...s, resolved: { ...s.resolved, 'font-weight': '700', 'font-style': 'italic' } } : s))
    const all = runs(doc({ styles: loud }))
    const marker = all.find((r) => r.text === '1.')!
    const text = all.find((r) => r.text === 'Ein')!
    expect(marker.face).not.toEqual(text.face)
  })

  it('leaves a paragraph without an item where it was, and an item without a label counted yet without a marker', () => {
    const all = runs(doc({ blocks: [{ id: 'b1', style: 'body', text: 'Davor.' }, { id: 'b2', style: 'body', text: 'Noch nicht gezählt.', item: { list: 'l1', level: 0 } }] }))
    expect(all.map((r) => r.text)).toEqual(['Davor.', 'Noch', 'nicht', 'gezählt.'])
  })
})
