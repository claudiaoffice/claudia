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
    expect(doc).toMatchObject({ blocks: [{ id: 'b1', style: 'body', text: 'Hallo' }], styles: [{ id: 'body', resolved: { 'font-size': '12pt' } }], images: [{ id: 'i1', format: 'png' }], language: 'de' })
    expect([...fromBase64('aGk=')]).toEqual([104, 105])
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
    expect(svg).toContain('<clipPath id="p0-clip1">')
    expect(svg).toContain('transform="rotate(15 0.005 0.006)"')
    expect(svg).toContain('href="blob:x"')
  })
})
