import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import type { DisplayPage, GlyphRun } from '../src/display/list'
import { walk } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { flowItems, paginate } from '../src/flow/paginate'
import { contentBox, pageGeometry, paperById } from '../src/flow/paper'
import { boxItems, layoutBox } from '../src/text/box'
import { boxDecorationFromCss, paragraphStyleFromCss } from '../src/text/css'
import { writePdf } from '../src/pdf/writer'
import { umToMpt } from '../src/units'
import { here, sha256 } from './helpers'
import { readPdf } from './pdf'
import { blocks, sampleParagraphs } from './sample'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))
const image = (name: string) => new Uint8Array(readFileSync(join(here, 'images', name)))
const noImages = () => undefined
const cm = (n: number) => umToMpt(n * 10_000)
const margins = { top: cm(2.5), right: cm(2), bottom: cm(2.5), left: cm(2) }

function document(paper = 'a4', n = 20): DisplayPage[] {
  const p = paperById(paper)!
  const g = pageGeometry(p.width, p.height, 'portrait', margins)
  const bs = blocks(fonts, resolver, sampleParagraphs(n), contentBox(g).w)
  return flowItems(fonts, paginate(bs, g), bs, g)
}

describe('PDF writer', () => {
  it('writes every glyph run where the display list puts it, as pdf.js reads it back', async () => {
    const pages = document('a4', 20)
    const pdf = await readPdf(writePdf(pages, fonts, noImages, { title: 'Probe', lang: 'de' }))
    expect(pdf.pages).toHaveLength(pages.length)
    let runs = 0
    pages.forEach((page, p) => {
      const got = pdf.pages[p]!
      expect(got.width).toBeCloseTo(page.width / 1000, 3)
      expect(got.height).toBeCloseTo(page.height / 1000, 3)
      const want = [...walk(page.items)].filter((i): i is GlyphRun => i.kind === 'glyphs')
      // pdf.js may join runs of one line; compare by position: every run starts at a text item's place on its line
      for (const run of want) {
        const x = run.x / 1000
        const y = (page.height - run.y) / 1000
        const item = got.items.find((i) => Math.abs(i.y - y) < 0.002 && i.x <= x + 0.002 && x <= i.x + i.w + 0.002)
        expect(item, `run "${run.text}"`).toBeDefined()
        expect(item!.size).toBeCloseTo(run.size / 1000, 3)
        runs++
      }
      // and the text of the page is the text of the runs, in order
      const text = (s: string) => s.replace(/\s+/g, '')
      expect(text(got.items.map((i) => i.str).join(''))).toBe(text(want.map((r) => r.text).join('')))
    })
    expect(runs).toBeGreaterThan(500)
  })

  it('makes the same bytes every time', () => {
    const a = writePdf(document('letter', 12), fonts, noImages, { title: 'Probe', created: '2026-11-12T09:30:00Z' })
    const b = writePdf(document('letter', 12), fonts, noImages, { title: 'Probe', created: '2026-11-12T09:30:00Z' })
    expect(sha256(a)).toBe(sha256(b))
    expect(new TextDecoder('latin1').decode(a.slice(0, 8))).toBe('%PDF-1.7')
  })

  it('embeds subset fonts at the weight the text was shaped with, with the text behind every glyph', async () => {
    const r = paragraphStyleFromCss({ 'font-family': 'Fraunces', 'font-size': '20pt', 'font-weight': '500' }, resolver, fonts)!
    const box = layoutBox(fonts, 'Office für Seiten', r.style, cm(12), cm(3))
    const page: DisplayPage = { width: cm(15), height: cm(5), items: [boxItems(fonts, box, cm(1), cm(1))] }
    const bytes = writePdf([page], fonts, noImages, { title: 't' }, { compress: false })
    const raw = new TextDecoder('latin1').decode(bytes)
    expect(raw).toMatch(/\/BaseFont \/[A-P]{6}\+Fraunces[^ ]*-opsz20wght500/)
    expect(raw).toContain('/FontFile2')
    expect(raw).toMatch(/<[0-9A-F]{4}> <006600660069>/) // the ffi ligature maps back to its three letters
    const text = (await readPdf(bytes)).pages[0]!.items.map((i) => i.str).join('')
    expect(text.replace(/\s+/g, ' ')).toBe('Office für Seiten')
  })

  it('draws boxes clipped and rotated, paths with alpha, and PNG and JPEG images', async () => {
    const deco = boxDecorationFromCss({ 'background-color': 'rgba(214, 71, 122, 0.5)', 'border-top': '2pt dashed #1f1a33', 'padding-top': '4pt' }, 12000)
    const r = paragraphStyleFromCss({ 'font-family': 'Inter', 'font-size': '11pt' }, resolver, fonts)!
    const box = layoutBox(fonts, 'Ein Kasten mit zu viel Text für seine Größe, der deshalb abgeschnitten wird.', r.style, cm(5), cm(1.2), deco)
    const page: DisplayPage = {
      width: cm(15),
      height: cm(10),
      items: [
        boxItems(fonts, box, cm(1), cm(1), 15),
        { kind: 'image', image: 'rgba.png', x: cm(1), y: cm(4), w: cm(3), h: cm(2) },
        { kind: 'image', image: 'photo.jpg', x: cm(5), y: cm(4), w: cm(3), h: cm(2) },
        { kind: 'image', image: 'cmyk.jpg', x: cm(9), y: cm(4), w: cm(3), h: cm(2) },
        { kind: 'image', image: 'palette.png', x: cm(1), y: cm(7), w: cm(2), h: cm(2) },
      ],
    }
    const bytes = writePdf([page], fonts, (id) => image(id), { title: 'Bilder' }, { compress: false })
    const raw = new TextDecoder('latin1').decode(bytes)
    expect(raw).toMatch(/0\.965926 -0\.258819 0\.258819 0\.965926 [-\d.]+ [-\d.]+ cm/) // 15 degrees, from the table
    expect(raw).toMatch(/re W n/)
    expect(raw).toContain('/DCTDecode')
    expect(raw).toContain('/Decode [1 0 1 0 1 0 1 0]')
    expect(raw).toContain('/SMask')
    expect(raw).toMatch(/\/ExtGState << \/GS0/)
    expect(raw).toMatch(/\[[\d.]+ [\d.]+\] 0 d/)
    const pdf = await readPdf(bytes)
    expect(pdf.pages).toHaveLength(1)
  })

  it('embeds the first frame of a GIF and a BMP as decoded pixels', async () => {
    const page: DisplayPage = {
      width: cm(10),
      height: cm(5),
      items: ['transparent.gif', 'interlaced.gif', 'rgb24.bmp'].map((id, i) => ({ kind: 'image' as const, image: id, x: cm(1 + 3 * i), y: cm(1), w: cm(2), h: cm(2) })),
    }
    const bytes = writePdf([page], fonts, (id) => image(id), { title: 'GIF und BMP' }, { compress: false })
    const raw = new TextDecoder('latin1').decode(bytes)
    expect((raw.match(/\/Subtype \/Image/g) ?? []).length).toBe(4) // three images and the GIF's transparency mask
    expect(raw).toContain('/Width 19 /Height 23')
    expect((await readPdf(bytes)).pages).toHaveLength(1)
  })

  it('refuses an image it does not have', () => {
    const page: DisplayPage = { width: cm(5), height: cm(5), items: [{ kind: 'image', image: 'missing', x: 0, y: 0, w: cm(1), h: cm(1) }] }
    expect(() => writePdf([page], fonts, noImages, { title: 't' })).toThrow(/not available/)
  })
})
