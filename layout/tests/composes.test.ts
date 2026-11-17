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
import { hyphenatorFor } from './fonts'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))
// body text asks for hyphenation (`hyphens: auto`), as a server's styles do; a server gives the patterns with them
const GERMAN = { hyphenator: hyphenatorFor('de') }

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
    const out = layoutText(doc(), fonts, resolver, GERMAN)
    expect(out.list.pages.length).toBeGreaterThan(3)
    expect(out.notes).toEqual([])
    out.list.pages.forEach((page, i) => {
      const runs = [...walk(page.items)].filter((r): r is GlyphRun => r.kind === 'glyphs')
      // the number is the last line drawn: its runs join to "n / N" (no break is allowed before the slash, UAX #14)
      const y = runs.at(-1)!.y
      expect(runs.filter((r) => r.y === y).map((r) => r.text).join(' ')).toBe(`${i + 1} / ${out.list.pages.length}`)
    })
  })

  it('keeps a heading with the paragraph after it by the level its style gives, whatever the style is called (E9.22)', () => {
    // "chapter" is a style of the writer's own; the server says whether it gives a heading level
    const chapter = (heading: number | null) => STYLES.concat([{ ...STYLES.find((s) => s.id === 'heading-2')!, id: 'chapter', heading }])
    const body = 'Ein Satz, der eine Zeile füllt, und noch einer, der sie umbricht und dann noch etwas weitergeht.'
    const text = (n: number) => [
      ...Array.from({ length: n }, (_, i) => ({ id: `b${i + 1}`, style: 'body', text: body })),
      { id: 'h', style: 'chapter', text: 'KAPITEL' },
      { id: 'after', style: 'body', text: body },
    ]
    const lastLineOfPageOne = (n: number, heading: number | null) => {
      const out = layoutText({ blocks: text(n), styles: chapter(heading), page: A4, language: 'de' }, fonts, resolver, GERMAN)
      const runs = [...walk(out.list.pages[0]!.items)].filter((r): r is GlyphRun => r.kind === 'glyphs')
      const numberLine = runs.at(-1)!.y
      return runs.filter((r) => r.y !== numberLine).at(-1)!.text // the line above the page number
    }
    // somewhere the heading falls on the last line of page one when it is no heading...
    const n = Array.from({ length: 40 }, (_, i) => i + 5).find((k) => lastLineOfPageOne(k, null) === 'KAPITEL')
    expect(n).toBeDefined()
    // ...and the level alone moves it over to the next page with its paragraph
    expect(lastLineOfPageOne(n!, 1)).not.toBe('KAPITEL')
  })

  it('follows any paper: the same text on Letter landscape gives more, wider lines per page', () => {
    const letter = layoutText(doc(30, { page: { ...A4, paper: 'letter', width: 612000, height: 792000, orientation: 'landscape' } }), fonts, resolver, GERMAN)
    expect(letter.geometry.width).toBe(792000)
    expect(letter.list.pages[0]!.width).toBe(792000)
  })

  it('says when a style asks for a font the server does not have', () => {
    const georgia = STYLES.map((s) => (s.id === 'body' ? { ...s, resolved: { ...s.resolved, 'font-family': 'Georgia, serif' } } : s))
    expect(layoutText(doc(3, { styles: georgia }), fonts, resolver, GERMAN).notes).toEqual([{ kind: 'font', requested: 'Georgia', used: 'Fraunces' }])
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
      images: [
        { id: 'img1', format: 'png' },
        { id: 'svg1', format: 'svg', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 70 50"><rect width="70" height="50" fill="#D6477A"/><filter id="f"/></svg>' },
      ],
    })
    const out = layoutText(d, fonts, resolver, GERMAN)
    expect(out.images).toEqual(['img1'])
    expect(out.notes).toEqual([])
    const svgGroup = out.list.pages.flatMap((p) => p.items).find((i) => i.kind === 'group' && i.items[0]?.kind === 'group' && i.items[0].items[0]?.kind === 'path')
    expect(svgGroup).toBeDefined()
    const groups = out.list.pages.flatMap((p) => p.items.filter((i) => i.kind === 'group'))
    expect(groups).toHaveLength(4)
    const text = groups[0]!
    expect(text.kind === 'group' && text.clip).toMatchObject({ w: 150000, h: 30000 })
  })

  it('gives the same display list and the same PDF every time, read back by pdf.js', async () => {
    const a = layoutText(doc(12), fonts, resolver, GERMAN)
    const b = layoutText(doc(12), fonts, resolver, GERMAN)
    expect(sha256(canonicalJson(a.list))).toBe(sha256(canonicalJson(b.list)))
    const pdfA = writePdf(a.list.pages, fonts, () => undefined, { title: 'Bericht', lang: 'de', created: '2026-11-12T09:00:00Z' })
    const pdfB = writePdf(b.list.pages, fonts, () => undefined, { title: 'Bericht', lang: 'de', created: '2026-11-12T09:00:00Z' })
    expect(sha256(pdfA)).toBe(sha256(pdfB))
    const read = await readPdf(pdfA)
    expect(read.pages).toHaveLength(a.list.pages.length)
    expect(read.pages[0]!.items.map((i) => i.str).join(' ')).toContain('Ein Bericht über Seiten')
  })
})

describe('a table of contents on pages (E9.31, step F)', () => {
  const withContents = (leader: 'dots' | 'none' = 'dots', places = true): TextDocument => {
    const base = doc(30)
    const headings = base.blocks.filter((b) => b.style === 'heading-1')
    const contents = { entries: headings.map((h) => ({ target: h.id, words: h.text, style: 'contents-1' })), places, leader }
    return { ...base, blocks: [{ id: 'toc', style: 'body', text: '', contents }, ...base.blocks] }
  }
  const runsOf = (items: Parameters<typeof walk>[0]) => [...walk(items)].filter((r): r is GlyphRun => r.kind === 'glyphs')

  it('prints each heading’s page right-aligned on its entry’s line, as the page the heading starts on', () => {
    const d = withContents()
    const out = layoutText(d, fonts, resolver, GERMAN)
    const headings = d.blocks.filter((b) => b.style === 'heading-1')
    expect(headings.length).toBeGreaterThan(1)
    const lastHeading = headings.at(-1)!
    expect(out.pageOf.get(lastHeading.id)).toBeGreaterThan(1)
    const runs = runsOf(out.list.pages[0]!.items)
    const entryWord = lastHeading.text.split(' ').at(-1)!
    const entry = runs.filter((r) => r.text === entryWord)[headings.length - 1]! // the headings read alike: the last entry
    const number = runs.find((r) => r.y === entry.y && r.text === String(out.pageOf.get(lastHeading.id)))
    expect(number).toBeDefined()
    expect(number!.x).toBeGreaterThan(entry.x)
  })

  it('draws the dot leader only when asked, and no pages when the places are off', () => {
    const dots = (d: TextDocument) => layoutText(d, fonts, resolver, GERMAN).list.pages[0]!.items.filter((i) => i.kind === 'path' && i.fill).length
    expect(dots(withContents('dots'))).toBeGreaterThan(dots(withContents('none')))
    const off = layoutText(withContents('dots', false), fonts, resolver, GERMAN)
    const on = layoutText(withContents('dots'), fonts, resolver, GERMAN)
    expect(runsOf(off.list.pages[0]!.items).length).toBeLessThan(runsOf(on.list.pages[0]!.items).length)
  })

  it('makes each entry a link to its heading, and the headings the PDF’s bookmarks', async () => {
    const out = layoutText(withContents(), fonts, resolver, GERMAN)
    const links = out.list.pages[0]!.links ?? []
    const headings = withContents().blocks.filter((b) => b.style === 'heading-1')
    expect(links).toHaveLength(headings.length)
    expect(links.at(-1)!.page).toBe(out.pageOf.get(headings.at(-1)!.id)! - 1)
    expect(out.outline.map((o) => o.title)).toEqual(withContents().blocks.filter((b) => b.style === 'title' || b.style === 'heading-1').map((b) => b.text))
    const pdf = new TextDecoder('latin1').decode(writePdf(out.list.pages, fonts, () => undefined, { title: 'Contents' }, { compress: false, outline: out.outline }))
    expect(pdf.match(/\/Subtype \/Link/g)).toHaveLength(headings.length)
    expect(pdf).toContain('/Type /Outlines')
    expect(pdf).toContain('/PageMode /UseOutlines')
    expect((await readPdf(writePdf(out.list.pages, fonts, () => undefined, { title: 'Contents' }, { outline: out.outline }))).pages).toHaveLength(out.list.pages.length)
  })

  it('leaves a text without a table as it was: no links, and the same pages', () => {
    const plain = layoutText(doc(30), fonts, resolver, GERMAN)
    expect(plain.list.pages.every((p) => p.links === undefined)).toBe(true)
    expect(plain.pageOf.get('b1')).toBe(1)
  })
})

describe('page references in a text (step I)', () => {
  const referring = (at: 'start' | 'end'): TextDocument => {
    const base = doc(30)
    const last = base.blocks.filter((b) => b.style === 'heading-1').at(-1)!
    const words = 'Mehr dazu auf Seite '
    const ref: TextDocument['blocks'][number] = { id: 'ref', style: 'body', text: `${words}.`, pageRefs: [{ at: words.length, target: last.id }] }
    return { ...base, blocks: at === 'start' ? [ref, ...base.blocks] : [...base.blocks, ref] }
  }
  const runsOf = (pages: ReturnType<typeof layoutText>['list']['pages']) => pages.flatMap((p) => [...walk(p.items)].filter((r): r is GlyphRun => r.kind === 'glyphs'))

  it('fills in the page the target starts on, found by laying the text out', () => {
    const d = referring('start')
    const out = layoutText(d, fonts, resolver, GERMAN)
    const last = d.blocks.filter((b) => b.style === 'heading-1').at(-1)!
    const page = out.pageOf.get(last.id)!
    expect(page).toBeGreaterThan(1)
    expect(runsOf(out.list.pages).some((r) => r.text === `${page}.`)).toBe(true)
    expect(out.notes.filter((n) => n.kind === 'pages')).toEqual([])
  })

  it('needs nothing more for a reference to a page before it, and a text without any takes one pass as before', () => {
    const out = layoutText(referring('end'), fonts, resolver, GERMAN)
    expect(runsOf(out.list.pages).some((r) => /^\d+\.$/.test(r.text) && r.text !== '000.')).toBe(true)
    expect(canonicalJson(layoutText(doc(30), fonts, resolver, GERMAN).list)).toBe(canonicalJson(layoutText(doc(30), fonts, resolver, GERMAN).list))
  })
})
