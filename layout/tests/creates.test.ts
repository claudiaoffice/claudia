import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { gridOf, layoutSlides, type PrintSetupData, type SlideDocument, type SlideObject, slideFontsNeeded } from '../src/apps/creates'
import type { ShapeOutline, TextStyle } from '../src/apps/objects'
import { canonicalJson } from '../src/canonical'
import { type DisplayItem, type GroupItem, walk } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { writePdf } from '../src/pdf/writer'
import { hyphenatorFor } from './fonts'
import { here, sha256 } from './helpers'
import { readPdf } from './pdf'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

// creates' built-in styles and shapes exactly as a server sends them (`styles`, `shapes`)
const STYLES: TextStyle[] = JSON.parse(readFileSync(join(here, 'creates-styles.json'), 'utf8'))
const SHAPES: ShapeOutline[] = JSON.parse(readFileSync(join(here, 'creates-shapes.json'), 'utf8'))
const margins = (m: number) => [m, m, m, m] as [number, number, number, number]
const SLIDE_PAGE: PrintSetupData = { layout: 'slides', page: { paper: 'slide', width: 540000, height: 960000, orientation: 'landscape', margins: margins(0), page_numbers: false } }
const A4 = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait' as const, margins: margins(36000), page_numbers: false }

const text = (id: string, slide: string, words: string, x = 100, y = 80, w = 1400, h = 200): SlideObject => ({
  id,
  kind: 'text',
  w,
  h,
  style: 'plain-box',
  paragraph: { style: 'body-text', text: words },
  shape: null,
  image: null,
  rotation: 0,
  anchor: { kind: 'slide', container: slide, x, y },
})
const shape = (id: string, slide: string, words: string): SlideObject => ({
  id,
  kind: 'shape',
  w: 600,
  h: 300,
  style: 'plain-shape',
  paragraph: { style: 'shape-label', text: words },
  shape: 'rectangle',
  image: null,
  rotation: 0,
  anchor: { kind: 'slide', container: slide, x: 500, y: 400 },
})
function deck(n: number, print: PrintSetupData = SLIDE_PAGE, extra: Partial<SlideDocument> = {}): SlideDocument {
  return {
    slides: Array.from({ length: n }, (_, i) => ({ id: `s${i + 1}`, objects: [text(`t${i + 1}`, `s${i + 1}`, `Folie ${i + 1}: Seiten, die überall gleich sind`), shape(`r${i + 1}`, `s${i + 1}`, 'Mitte')] })),
    styles: STYLES,
    shapes: SHAPES,
    images: [],
    print,
    language: 'de',
    ...extra,
  }
}
const slidesOf = (items: readonly DisplayItem[]) => items.filter((i): i is GroupItem => i.kind === 'group' && i.matrix !== undefined)
const frames = (items: readonly DisplayItem[]) => items.filter((i) => i.kind === 'path' && i.stroke && !i.fill && i.ops.length === 5)

describe('a presentation on pages', () => {
  it('names the fonts its slides need', () => {
    const need = slideFontsNeeded(deck(2), resolver)
    expect(need.length).toBeGreaterThanOrEqual(1)
    for (const h of need) expect(fonts.has(h)).toBe(true)
  })

  it('prints one slide to a slide-sized page, edge to edge, at 0.8 of its 1200 × 675 pt', () => {
    const out = layoutSlides(deck(3), fonts, resolver)
    expect(out.list.pages).toHaveLength(3)
    const [first] = out.list.pages
    expect([first!.width, first!.height]).toEqual([960000, 540000])
    const [slide] = slidesOf(first!.items)
    expect(slide!.matrix).toEqual([800000, 0, 0, 800000, 0, 0])
    expect(frames(first!.items)).toHaveLength(0)
    const runs = [...walk(slide!.items)].filter((i) => i.kind === 'glyphs')
    expect(runs.map((r) => (r.kind === 'glyphs' ? r.text : '')).join(' ')).toContain('Folie 1:')
    expect(out.notes).toEqual([])
    expect([out.slides, out.perPage]).toEqual([3, 1])
  })

  it('frames a slide that does not fill its page, and keeps a band for page numbers', () => {
    const out = layoutSlides(deck(2, { layout: 'slides', page: { ...SLIDE_PAGE.page, page_numbers: true } }), fonts, resolver)
    const page = out.list.pages[1]!
    const [slide] = slidesOf(page.items)
    expect(slide!.matrix![0]).toBeLessThan(800000)
    expect(frames(page.items)).toHaveLength(1)
    const number = page.items.filter((i) => i.kind === 'glyphs')
    expect(number.map((r) => (r.kind === 'glyphs' ? r.text : '')).join(' ')).toBe('2 / 2')
  })

  it('arranges handouts in a grid, reading order, each slide fitted and framed', () => {
    const out = layoutSlides(deck(7, { layout: 'handouts-6', page: A4 }), fonts, resolver)
    expect(out.list.pages).toHaveLength(2)
    const placed = slidesOf(out.list.pages[0]!.items)
    expect(placed).toHaveLength(6)
    expect(slidesOf(out.list.pages[1]!.items)).toHaveLength(1)
    expect(frames(out.list.pages[0]!.items)).toHaveLength(6)
    const at = placed.map((g) => [g.matrix![4], g.matrix![5]])
    // two columns, three rows: left then right, top to bottom
    expect(at[0]![0]).toBeLessThan(at[1]![0]!)
    expect(at[0]![1]).toBe(at[1]![1])
    expect(at[2]![1]).toBeGreaterThan(at[0]![1]!)
    for (const g of placed) {
      const w = Math.round((1200000 * g.matrix![0]) / 1e6)
      expect(g.matrix![4]).toBeGreaterThanOrEqual(36000)
      expect(g.matrix![4] + w).toBeLessThanOrEqual(595276 - 36000)
    }
    expect(gridOf('handouts-6', true)).toEqual({ columns: 3, rows: 2 })
    expect(gridOf('handouts-2', false)).toEqual({ columns: 1, rows: 2 })
  })

  it('puts lines for notes beside three slides a page', () => {
    const out = layoutSlides(deck(3, { layout: 'handouts-3', page: A4 }), fonts, resolver)
    const page = out.list.pages[0]!
    const rules = page.items.filter((i) => i.kind === 'path' && i.ops.length === 2)
    expect(rules.length).toBeGreaterThan(20)
    const [slide] = slidesOf(page.items)
    const right = slide!.matrix![4] + Math.round((1200000 * slide!.matrix![0]) / 1e6)
    for (const r of rules) if (r.kind === 'path' && r.ops[0]![0] === 'M') expect(r.ops[0]![1]).toBeGreaterThan(right)
  })

  it('centres a shape’s words in it, inside a margin, as the slide on screen does', () => {
    const out = layoutSlides(deck(1), fonts, resolver)
    const [slide] = slidesOf(out.list.pages[0]!.items)
    const label = [...walk(slide!.items)].find((i) => i.kind === 'glyphs' && i.text === 'Mitte')
    expect(label).toBeDefined()
    if (label?.kind !== 'glyphs') return
    // the rectangle is 400..700 px high at 750 mpt a px: its middle is at 550 px
    expect(Math.abs(label.y - 550 * 750)).toBeLessThan(20000)
  })

  it('says what it cannot print and what is not hyphenated', () => {
    const chart: SlideObject = { ...text('d1', 's1', ''), kind: 'diagram', paragraph: null }
    const hyphenating: TextStyle[] = STYLES.map((s) => (s.id === 'body-text' ? { ...s, resolved: { ...s.resolved, hyphens: 'auto' } } : s))
    const doc = deck(1, SLIDE_PAGE, { styles: hyphenating, language: null })
    ;(doc.slides[0]!.objects as SlideObject[]).push(chart)
    const out = layoutSlides(doc, fonts, resolver)
    expect(out.notes).toEqual([
      { kind: 'object', object: 'd1', reason: 'charts cannot be printed from a presentation yet' },
      { kind: 'hyphenation', reason: 'the presentation has no language set, so words are not hyphenated' },
    ])
    const hyphenated = layoutSlides({ ...doc, language: 'de' }, fonts, resolver, { hyphenator: hyphenatorFor('de') })
    expect(hyphenated.notes.filter((n) => n.kind === 'hyphenation')).toEqual([])
    expect(hyphenated.list.hyphenation).toBeDefined()
  })

  it('prints an SVG picture on a slide as what it is made of', () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="#3d5a80"/></svg>'
    const picture: SlideObject = { ...text('p1', 's1', ''), kind: 'image', paragraph: null, image: 'i1', style: 'plain-image', w: 300, h: 300 }
    const doc = deck(1, SLIDE_PAGE, { images: [{ id: 'i1', format: 'svg', svg }] })
    ;(doc.slides[0]!.objects as SlideObject[]).push(picture)
    const out = layoutSlides(doc, fonts, resolver)
    const circle = [...walk(out.list.pages[0]!.items)].find((i) => i.kind === 'path' && i.fill && !('kind' in i.fill) && i.fill.b === 0x80)
    expect(circle).toBeDefined()
  })

  it('writes a PDF of the very pages, the same bytes every time', async () => {
    const out = layoutSlides(deck(4, { layout: 'handouts-4', page: { ...A4, orientation: 'landscape', page_numbers: true } }), fonts, resolver)
    const pdf = writePdf(out.list.pages, fonts, () => undefined, { title: 'Deck' })
    const read = await readPdf(pdf)
    expect(read.pages).toHaveLength(1)
    expect(Math.round(read.pages[0]!.width)).toBe(842)
    const words = read.pages[0]!.items.map((i) => i.str).join(' ')
    for (const n of [1, 2, 3, 4]) expect(words).toContain(`Folie ${n}:`)
    expect(words.replace(/\s+/g, '')).toContain('1/1')
    const again = layoutSlides(deck(4, { layout: 'handouts-4', page: { ...A4, orientation: 'landscape', page_numbers: true } }), fonts, resolver)
    expect(canonicalJson(again.list)).toBe(canonicalJson(out.list))
    expect(sha256(writePdf(again.list.pages, fonts, () => undefined, { title: 'Deck' }))).toBe(sha256(pdf))
  })
})
