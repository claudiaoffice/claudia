import { describe, expect, it } from 'vitest'
import { DEFAULT_PAGE, MARGINS, describe as describePage, marginPreset, mm, paperLabel, withCustomSize, withPaper } from '~/lib/print/setup'
import { fromBase64, textDocument } from '~/lib/print/document'
import { pageSvg } from '~/lib/print/paint'

describe('the print bar (D904, D906)', () => {
  it('starts from A4 portrait with 2.5 cm margins, like a new text on the server', () => {
    expect(paperLabel(DEFAULT_PAGE)).toBe('A4 · 210 × 297 mm')
    expect(marginPreset(DEFAULT_PAGE)).toBe('normal')
    expect(describePage(DEFAULT_PAGE, 3)).toBe('3 pages · A4 portrait')
  })
  it('switches between preset papers and makes a custom one short side first', () => {
    expect(withPaper(DEFAULT_PAGE, 'letter')).toMatchObject({ paper: 'letter', width: 612000, height: 792000 })
    const custom = withCustomSize(DEFAULT_PAGE, 150, 100)
    expect(custom).toMatchObject({ paper: 'custom', width: 283465, height: 425197 })
    expect([mm(custom.width), mm(custom.height)]).toEqual([100, 150])
    expect(paperLabel(custom)).toBe('100 × 150 mm')
  })
  it('knows the margin presets and says when the margins are the document’s own', () => {
    expect(MARGINS.map((m) => m.label)).toEqual(['1.27 cm', '2.5 cm', '3.5 cm'])
    expect(marginPreset({ ...DEFAULT_PAGE, margins: [1, 2, 3, 4] })).toBeNull()
  })
})

describe('from a session to the layout library', () => {
  it('passes paragraphs, resolved styles and objects through', () => {
    const doc = textDocument(
      [{ id: 'b1', style: 'body', text: 'Hallo', runs: [] }],
      [{ id: 'body', name: 'Body', purpose: '', based_on: null, css: {}, computed: {}, resolved: { 'font-size': '12pt' }, to_name: false, kind: 'paragraph' }],
      DEFAULT_PAGE,
      { objects: [], shapes: [], images: [{ id: 'i1', format: 'png', data: 'AA==' }] },
      'de',
    )
    expect(doc).toMatchObject({ paragraphs: [{ id: 'b1', style: 'body', text: 'Hallo' }], styles: [{ id: 'body', resolved: { 'font-size': '12pt' } }], images: [{ id: 'i1', format: 'png' }], language: 'de' })
    expect([...fromBase64('aGk=')]).toEqual([104, 105])
  })
  it('passes the tables the text shows with their totals, for the layout to set in the flow (E9.32)', () => {
    const table = {
      format: 1, id: 't1', columns: [{ id: 'c1', kind: 'number' as const, total: 'sum', width: null }], rows: ['r1', 'r2'],
      entries: [['r1', 'c1', { style: '', text: 'kg' }], ['r2', 'c1', { style: '', text: '4' }]] as [string, string, { style: string; text: string }][],
      merges: [], header_rows: 1, banded: false, look: 'rules', placement: 'flow' as const, width: null, next_row: 2, next_col: 1, used_by: ['o1'], totals: { c1: '4' },
    }
    const object = { id: 'o1', kind: 'table' as const, w: 480, h: 48, style: 'plain-box', paragraph: null, shape: null, image: null, rotation: 0, ref: 't1', anchor: { kind: 'paragraph' as const, holder: 'b1', offset: 0 } }
    const doc = textDocument([{ id: 'b1', style: 'body', text: 'Hallo', runs: [] }], [], DEFAULT_PAGE, { objects: [object], shapes: [], images: [], tables: [table] }, 'de')
    expect(doc.tables).toEqual([{ ...table, total_label: 'Total' }]) // the word the view shows in the total row
    expect(doc.objects).toEqual([object])
    expect(textDocument([], [], DEFAULT_PAGE, null).tables).toEqual([])
  })
  it('passes the list items with the markers the server counted, and the lists and schemes they are drawn by (E9.21)', () => {
    const doc = textDocument(
      [
        { id: 'b1', style: 'body', text: 'eins', runs: [], item: { list: 'l1', level: 0 }, label: { marker: '1.', path: [1] } },
        { id: 'b2', style: 'body', text: 'kein Punkt', runs: [] },
      ],
      [],
      DEFAULT_PAGE,
      null,
      'de',
      { lists: [{ id: 'l1', scheme: 'numbers', start: 1, name: null }], schemes: [{ id: 'numbers', name: 'Numbers', kind: 'number', indent: 2, gap: 0.5 }] },
    )
    expect(doc.paragraphs).toEqual([
      { id: 'b1', style: 'body', text: 'eins', item: { list: 'l1', level: 0 }, label: { marker: '1.' } },
      { id: 'b2', style: 'body', text: 'kein Punkt', item: null, label: null },
    ])
    expect(doc.lists).toEqual([{ id: 'l1', scheme: 'numbers' }])
    expect(doc.schemes).toEqual([{ id: 'numbers', indent: 2, gap: 0.5 }])
  })
  it('passes a table of contents with its entries and options, for the layout to find their pages (E9.31)', () => {
    const toc = { kind: 'toc' as const, first: 1, last: 2, numbers: true, places: true, leader: 'dots' as const }
    const entry = (target: string, number: string | null, text: string, level: number) => ({ target, level, number, text, style: `contents-${level}`, place: null })
    const doc = textDocument(
      [
        { id: 'toc', style: 'body', text: '', runs: [], generated: toc, entries: [entry('h1', '1', 'Why', 1), entry('h2', '1.1', 'Schools', 2)] },
        { id: 'empty', style: 'body', text: '', runs: [], generated: { ...toc, places: false, leader: 'none' as const } },
      ],
      [],
      DEFAULT_PAGE,
      null,
    )
    expect(doc.paragraphs).toEqual([
      { id: 'toc', style: 'body', text: '', contents: { entries: [{ target: 'h1', words: '1 Why', style: 'contents-1' }, { target: 'h2', words: '1.1 Schools', style: 'contents-2' }], places: true, leader: 'dots' } },
      { id: 'empty', style: 'body', text: '', contents: { entries: [], places: false, leader: 'none' } },
    ])
  })
  it('prints a reference as what it reads as, and leaves a page reference for the layout to fill in (steps H, I)', () => {
    const F = '\ufffc'
    const doc = textDocument(
      [
        {
          id: 'b1',
          style: 'body',
          text: `see ${F} on page ${F}.`,
          runs: [],
          fields: [{ kind: 'ref', target: 'h', show: 'number' }, { kind: 'ref', target: 'h', show: 'page' }],
          shown: [{ text: '2.1', state: 'ok' }, { text: '', state: 'page' }],
        },
      ],
      [],
      DEFAULT_PAGE,
      null,
    )
    expect(doc.paragraphs[0]).toMatchObject({ text: 'see 2.1 on page .', pageRefs: [{ at: 16, target: 'h' }] })
  })
  it('passes the heading level the server gave each style, so the layout keeps headings with their text (E9.22)', () => {
    const style = (id: string, heading?: number | null) => ({ id, name: id, purpose: '', based_on: null, css: {}, computed: {}, resolved: {}, to_name: false, kind: 'paragraph', heading })
    const doc = textDocument([], [style('chapter', 1), style('body', null), style('old')], DEFAULT_PAGE, null)
    expect(doc.styles.map((s) => s.heading)).toEqual([1, null, null])
  })
})

describe('painting a page', () => {
  it('draws words, paths, images and clipped, rotated groups, escaping every text', () => {
    const svg = pageSvg(
      {
        width: 1000,
        height: 2000,
        items: [
          { kind: 'glyphs', face: { sha256: 'ab'.repeat(32), variations: { wght: 600 } }, size: 12000, color: { r: 1, g: 2, b: 3, a: 255 }, x: 10, y: 20, glyphs: [], text: '<a & "b">' },
          { kind: 'path', ops: [['M', 0, 0], ['L', 5, 5], ['Z']], fill: null, stroke: { r: 0, g: 0, b: 0, a: 128 }, lineWidth: 500, dash: [1, 2] },
          { kind: 'group', clip: { x: 1, y: 2, w: 3, h: 4 }, rotation: 15, origin: { x: 5, y: 6 }, items: [{ kind: 'image', image: 'i1', x: 1, y: 2, w: 3, h: 4 }] },
        ],
      },
      (id) => (id === 'i1' ? 'blob:x' : undefined),
      'p0',
    )
    expect(svg).toContain('viewBox="0 0 1 2"') // points, from mpt
    expect(svg).toContain('font-size:12px')
    expect(svg).toContain('&lt;a &amp; &quot;b&quot;&gt;')
    expect(svg).toContain("font-variation-settings:'wght' 600")
    expect(svg).toContain('stroke-dasharray="0.001 0.002"')
    expect(svg).toContain('<clipPath id="p0-1">')
    expect(svg).toContain('transform="rotate(15 0.005 0.006)"')
    expect(svg).toContain('href="blob:x"')
  })

  it('draws gradients, transforms, clip paths, fill rules, stroke details and transparent layers', () => {
    const svg = pageSvg(
      {
        width: 1000,
        height: 1000,
        items: [
          {
            kind: 'group',
            clip: null,
            rotation: 0,
            origin: { x: 0, y: 0 },
            matrix: [500000, 0, 0, 2000000, 1000, 2000],
            clipPath: { ops: [['M', 0, 0], ['L', 10, 0], ['L', 0, 10], ['Z']], evenOdd: true },
            opacity: 128,
            items: [
              {
                kind: 'path',
                ops: [['M', 0, 0], ['L', 5, 5]],
                fill: { kind: 'linear', coords: [0, 0, 1000, 0], stops: [{ offset: 0, color: { r: 255, g: 0, b: 0, a: 255 } }, { offset: 1000000, color: { r: 0, g: 0, b: 255, a: 0 } }], matrix: [1000000, 0, 0, 1000000, 0, 0] },
                stroke: { kind: 'radial', coords: [1, 2, 3, 1, 2, 0], stops: [], matrix: [1000000, 0, 0, 1000000, 0, 0] },
                lineWidth: 1000,
                fillRule: 'evenodd',
                lineCap: 'round',
                lineJoin: 'bevel',
                miterLimit: 4000,
                dash: [1000, 1000],
                dashOffset: 500,
              },
            ],
          },
        ],
      },
      () => undefined,
      'q',
    )
    expect(svg).toContain('<linearGradient id="q-2" gradientUnits="userSpaceOnUse" gradientTransform="matrix(1 0 0 1 0 0)" x1="0" y1="0" x2="1" y2="0">')
    expect(svg).toContain('stop-opacity="0"')
    expect(svg).toContain('<radialGradient id="q-3"')
    expect(svg).toContain('transform="matrix(0.5 0 0 2 1 2)"')
    expect(svg).toContain('clip-rule="evenodd"')
    expect(svg).toContain('opacity="0.502"')
    expect(svg).toContain('fill-rule="evenodd"')
    expect(svg).toContain('stroke-linecap="round" stroke-linejoin="bevel" stroke-miterlimit="4"')
    expect(svg).toContain('stroke-dashoffset="0.5"')
  })
})
