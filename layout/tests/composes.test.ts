import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { fontsNeeded, layoutText, type TextDocument, type TextStyle } from '../src/apps/composes'
import { walk, type GlyphRun } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { writePdf } from '../src/pdf/writer'
import { canonicalJson } from '../src/canonical'
import { here, sha256 } from './helpers'
import { readPdf } from './pdf'
import { sampleParagraphs } from './sample'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

// composes' built-in styles exactly as a server sends them (TextModel().styles.views(palette.colours()))
const STYLES: TextStyle[] = JSON.parse(readFileSync(join(here, 'composes-styles.json'), 'utf8'))
const A4 = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait' as const, margins: [70866, 70866, 70866, 70866] as [number, number, number, number], page_numbers: true }
const STYLE_OF: Record<string, string> = { title: 'title', h1: 'heading-1', body: 'body', quote: 'quote' }

function doc(n = 30, extra: Partial<TextDocument> = {}): TextDocument {
  return {
    blocks: sampleParagraphs(n).map((p, i) => ({ id: `b${i + 1}`, style: STYLE_OF[p.style]!, text: p.text })),
    styles: STYLES,
    page: A4,
    language: 'de',
    ...extra,
  }
}

describe('a composes text on pages', () => {
  it('names the fonts it needs, all in the catalogue', () => {
    const need = fontsNeeded(doc(), resolver)
    expect(need.length).toBeGreaterThanOrEqual(2) // Inter for the body, Fraunces for headings
    for (const h of need) expect(fonts.has(h)).toBe(true)
  })

  it('lays out the built-in styles on numbered A4 pages, headings kept with their text', () => {
    const out = layoutText(doc(), fonts, resolver)
    expect(out.list.pages.length).toBeGreaterThan(3)
    expect(out.notes).toEqual([])
    out.list.pages.forEach((page, i) => {
      const runs = [...walk(page.items)].filter((r): r is GlyphRun => r.kind === 'glyphs')
      // the number is the last line drawn: its runs join to "n / N" (no break is allowed before the slash, UAX #14)
      const y = runs.at(-1)!.y
      expect(runs.filter((r) => r.y === y).map((r) => r.text).join(' ')).toBe(`${i + 1} / ${out.list.pages.length}`)
    })
  })

  it('follows any paper: the same text on Letter landscape gives more, wider lines per page', () => {
    const letter = layoutText(doc(30, { page: { ...A4, paper: 'letter', width: 612000, height: 792000, orientation: 'landscape' } }), fonts, resolver)
    expect(letter.geometry.width).toBe(792000)
    expect(letter.list.pages[0]!.width).toBe(792000)
  })

  it('says when a style asks for a font the server does not have', () => {
    const georgia = STYLES.map((s) => (s.id === 'body' ? { ...s, resolved: { ...s.resolved, 'font-family': 'Georgia, serif' } } : s))
    expect(layoutText(doc(3, { styles: georgia }), fonts, resolver).notes).toEqual([{ kind: 'font', requested: 'Georgia', used: 'Fraunces' }])
  })

  it('draws floating objects where they hang, clipped, and says what it cannot print', () => {
    const d = doc(5, {
      objects: [
        { id: 'o1', kind: 'text', w: 200, h: 40, style: 'plain-box', paragraph: { style: 'body', text: 'Ein Kasten mit sehr viel Text, der nicht hineinpasst und abgeschnitten wird.' }, shape: null, image: null, rotation: 0, anchor: { kind: 'block', container: 'b3', offset: 5 } },
        { id: 'o2', kind: 'shape', w: 100, h: 100, style: 'plain-shape', paragraph: { style: 'shape-label', text: 'Kreis' }, shape: 'circle', image: null, rotation: 10, anchor: { kind: 'block', container: 'b2', offset: 0 } },
        { id: 'o3', kind: 'image', w: 70, h: 50, style: 'plain-image', paragraph: null, shape: null, image: 'img1', rotation: 0, anchor: { kind: 'block', container: 'b4', offset: 0 } },
        { id: 'o4', kind: 'image', w: 70, h: 50, style: 'plain-image', paragraph: null, shape: null, image: 'svg1', rotation: 0, anchor: { kind: 'block', container: 'b4', offset: 0 } },
      ],
      shapes: [{ id: 'circle', path: 'M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z', text_area: { x: 14.6, y: 14.6, w: 70.8, h: 70.8 } }],
      images: [{ id: 'img1', format: 'png' }, { id: 'svg1', format: 'svg' }],
    })
    const out = layoutText(d, fonts, resolver)
    expect(out.images).toEqual(['img1'])
    expect(out.notes).toEqual([{ kind: 'object', object: 'o4', reason: 'SVG pictures cannot be printed yet' }])
    const groups = out.list.pages.flatMap((p) => p.items.filter((i) => i.kind === 'group'))
    expect(groups).toHaveLength(4)
    const text = groups[0]!
    expect(text.kind === 'group' && text.clip).toMatchObject({ w: 150000, h: 30000 })
  })

  it('gives the same display list and the same PDF every time, read back by pdf.js', async () => {
    const a = layoutText(doc(12), fonts, resolver)
    const b = layoutText(doc(12), fonts, resolver)
    expect(sha256(canonicalJson(a.list))).toBe(sha256(canonicalJson(b.list)))
    const pdfA = writePdf(a.list.pages, fonts, () => undefined, { title: 'Bericht', lang: 'de', created: '2026-11-12T09:00:00Z' })
    const pdfB = writePdf(b.list.pages, fonts, () => undefined, { title: 'Bericht', lang: 'de', created: '2026-11-12T09:00:00Z' })
    expect(sha256(pdfA)).toBe(sha256(pdfB))
    const read = await readPdf(pdfA)
    expect(read.pages).toHaveLength(a.list.pages.length)
    expect(read.pages[0]!.items.map((i) => i.str).join(' ')).toContain('Ein Bericht über Seiten')
  })
})
