import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { fontsNeeded, layoutText, type TextDocument, type TextStyle } from '../src/apps/composes'
import { Styles } from '../src/apps/objects'
import { DEFAULT_STYLE } from '../src/styles.generated'
import { fingerprintText, walk, type GlyphRun, type PathItem } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { flowItems, paginate, type FlowBlock, type FlowTable } from '../src/flow/paginate'
import { contentBox, pageGeometry } from '../src/flow/paper'
import { layoutTable, type TableData } from '../src/flow/table'
import { here, sha256 } from './helpers'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

// composes' built-in styles exactly as a server sends them (the table looks are among them)
const STYLES: TextStyle[] = JSON.parse(readFileSync(join(here, 'composes-styles.json'), 'utf8'))
const A4 = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait' as const, margins: [70866, 70866, 70866, 70866] as [number, number, number, number], page_numbers: false }
const geometry = pageGeometry(A4.width, A4.height, 'portrait', { top: 70866, right: 70866, bottom: 70866, left: 70866 })
const box = contentBox(geometry)

/** A table as `tables` gives it: `words` is a list of rows (the first the header), each a list of boxes. */
function table(words: string[][], extra: Partial<TableData> = {}): TableData {
  const columns = (words[0] ?? []).map((_, c) => ({ id: `c${c + 1}`, kind: 'text', total: null, width: null }))
  const rows = words.map((_, r) => `r${r + 1}`)
  const entries = words.flatMap((line, r) => line.map((text, c): TableData['entries'][number] => [`r${r + 1}`, `c${c + 1}`, { id: `t1/r${r + 1}/c${c + 1}`, style: '', text }]))
  return { id: 't1', columns, rows, entries, merges: [], header_rows: 1, banded: false, look: 'rules', width: null, totals: {}, ...extra }
}
const styles = () => new Styles(STYLES, fonts, resolver, 'de', DEFAULT_STYLE.composes, [])
const laid = (data: TableData, width = box.w) => layoutTable(fonts, styles(), data, width)
const GARDEN = [
  ['Bed', 'Crop', 'Yield kg'],
  ['North', 'Tomatoes', '212,5'],
  ['South', 'Beans', '88,0'],
  ['Roof', 'Herbs', '14,25'],
]
const long = (n: number) => Array.from({ length: n }, (_, i) => [`Beet ${i + 1}`, `Sorte ${i + 1}`, String(10 + i)])

describe('the layout of a table', () => {
  it('gives the columns the whole width between them, the wider words more of it', () => {
    const t = laid(table([['A', 'Eine lange Überschrift mit vielen Wörtern', 'C'], ['x', 'y', 'z']]))
    expect(t.columns.reduce((s, w) => s + w, 0)).toBe(box.w)
    expect(t.width).toBe(box.w)
    expect(t.columns[1]).toBeGreaterThan(t.columns[0]!)
    expect(t.columns[1]).toBeGreaterThan(t.columns[2]!)
  })

  it('lets a width the person set win, as a share of the table, and a table narrower than the line', () => {
    const t = laid(table(GARDEN, { width: 5000, columns: [{ id: 'c1', kind: 'text', total: null, width: 5000 }, { id: 'c2', kind: 'text', total: null, width: null }, { id: 'c3', kind: 'text', total: null, width: null }] }))
    expect(t.width).toBe(Math.floor(box.w / 2))
    expect(t.columns[0]).toBe(Math.floor(t.width / 2))
    expect(t.columns.reduce((s, w) => s + w, 0)).toBe(t.width)
  })

  it('breaks the words of a box at the width of its column, and makes the row as tall as its tallest box', () => {
    const t = laid(table([['A', 'B'], ['kurz', 'Ein Satz, der in einer schmalen Spalte mehrere Zeilen braucht, weil er so lang ist.']], { columns: [{ id: 'c1', kind: 'text', total: null, width: 3000 }, { id: 'c2', kind: 'text', total: null, width: 7000 }], width: 6000 }))
    const [, body] = t.rows
    const [short, tall] = body!.cells
    expect(short!.paragraph.lines.length).toBe(1)
    expect(tall!.paragraph.lines.length).toBeGreaterThan(2)
    expect(body!.height).toBe(tall!.paragraph.height + tall!.inset.top + tall!.inset.bottom)
    expect(t.rows[0]!.role).toBe('header')
    expect(body!.role).toBe('body')
    expect(t.header).toBe(1)
  })

  it('reads a style of its own for a box, and the look for one that has none, and right-aligns numbers', () => {
    const data = table(GARDEN)
    data.columns = [data.columns[0]!, data.columns[1]!, { ...data.columns[2]!, kind: 'number' }]
    const entries = [...data.entries]
    entries[3] = ['r2', 'c1', { id: 't1/r2/c1', style: 'quote', text: 'North' }]
    data.entries = entries
    const t = laid(data)
    expect(t.rows[0]!.cells[0]!.style).toBe('table-rules-header')
    expect(t.rows[1]!.cells[0]!.style).toBe('quote')
    expect(t.rows[1]!.cells[1]!.style).toBe('table-rules-body')
    expect(t.rows[1]!.cells[2]!.paragraph.style.align).toBe('right')
    expect(t.rows[1]!.cells[1]!.paragraph.style.align).toBe('left')
  })

  it('shades every second body row when it is banded, and the total row has the total look', () => {
    const data = table(GARDEN, { banded: true })
    data.columns = [data.columns[0]!, data.columns[1]!, { ...data.columns[2]!, kind: 'number', total: 'sum' }]
    data.totals = { c3: '314,75' }
    const t = laid(data)
    expect(t.rows.map((r) => r.cells[0]!.style)).toEqual(['table-rules-header', 'table-rules-body', 'table-rules-band', 'table-rules-body', 'table-rules-total'])
    expect(t.rows.at(-1)!.role).toBe('total')
    expect(t.rows.at(-1)!.cells[2]!.paragraph.lines[0]!.words.map((w) => w.text).join('')).toBe('314,75')
    expect(t.rows.at(-1)!.cells[0]!.paragraph.lines[0]!.words).toHaveLength(0)
  })

  it('starts the total row with the label when the first column has no total, and not when it has one', () => {
    const data = table(GARDEN, { total_label: 'Gesamt' })
    data.columns = [data.columns[0]!, data.columns[1]!, { ...data.columns[2]!, kind: 'number', total: 'sum' }]
    data.totals = { c3: '314,75' }
    const words = (t: ReturnType<typeof laid>, c: number) => t.rows.at(-1)!.cells[c]!.paragraph.lines[0]!.words.map((w) => w.text).join('')
    expect(words(laid(data), 0)).toBe('Gesamt')
    data.columns = [{ ...data.columns[0]!, total: 'count' }, data.columns[1]!, data.columns[2]!]
    data.totals = { c1: '3', c3: '314,75' }
    expect(words(laid(data), 0)).toBe('3')
  })

  it('makes a merged box as wide and as high as the boxes it joins, and draws nothing for the boxes it covers', () => {
    const data = table(GARDEN, { merges: [{ row: 'r2', col: 'c1', rows: 2, cols: 2 }] })
    const t = laid(data)
    const merged = t.rows[1]!.cells[0]!
    expect(merged.cols).toBe(2)
    expect(merged.rows).toBe(2)
    expect(merged.w).toBe(t.columns[0]! + t.columns[1]!)
    expect(t.rows[1]!.cells.map((c) => c.col)).toEqual([0, 2])
    expect(t.rows[2]!.cells.map((c) => c.col)).toEqual([2])
    expect(t.rows[1]!.tied).toBe(true) // the two rows belong together on a page
    expect(t.rows[2]!.tied).toBe(false)
  })

  it('is the same on every run', () => {
    const a = JSON.stringify(laid(table(GARDEN)))
    expect(a).toBe(JSON.stringify(laid(table(GARDEN))))
  })
})

/** A flow item for a table, with the space a body paragraph leaves around it. */
const flowTable = (data: TableData, id = 't1'): FlowTable => ({ id, table: laid(data), spaceBefore: 0, spaceAfter: 10800 })
const filler = (n: number): FlowBlock[] =>
  Array.from({ length: n }, (_, i) => {
    const r = styles().paragraph('body')
    return { id: `p${i}`, layout: layoutTextBlock(r.style, `Absatz ${i}`), decoration: r.decoration }
  })
import { layoutParagraph } from '../src/text/paragraph'
const layoutTextBlock = (style: Parameters<typeof layoutParagraph>[1], text: string) => layoutParagraph(fonts, style, text, box.w)

describe('a table on pages', () => {
  it('stays on one page when it fits, below the paragraph before it', () => {
    const blocks: (FlowBlock | FlowTable)[] = [...filler(1), flowTable(table(GARDEN)), ...filler(1)]
    const pages = paginate(blocks, geometry)
    expect(pages).toHaveLength(1)
    const [placed] = pages[0]!.tables
    expect(placed!.block).toBe(1)
    expect(placed!.rows.map((r) => r.row)).toEqual([0, 1, 2, 3])
    expect(placed!.top).toBeGreaterThan(pages[0]!.lines[0]!.top)
    expect(pages[0]!.lines.map((l) => l.block)).toEqual([0, 2])
  })

  it('breaks between rows, repeats the header on every page and places every row once, in order', () => {
    const data = table([['Beet', 'Sorte', 'kg'], ...long(80)])
    const pages = paginate([...filler(1), flowTable(data)], geometry)
    expect(pages.length).toBeGreaterThan(1)
    const bodyRows = pages.flatMap((p) => p.tables.flatMap((t) => t.rows.filter((r) => !r.repeat).map((r) => r.row)))
    expect(bodyRows).toEqual(Array.from({ length: 81 }, (_, i) => i))
    pages.forEach((p, i) => {
      for (const t of p.tables) {
        expect(t.rows[0]!.row).toBe(0) // the header, first or repeated
        expect(t.rows[0]!.repeat).toBe(i > 0)
        let y = t.top
        for (const r of t.rows) {
          expect(r.y).toBe(y)
          y += r.h
        }
        expect(y).toBeLessThanOrEqual(box.y + box.h)
      }
    })
  })

  it('does not leave a header alone at the foot of a page', () => {
    const t = flowTable(table(GARDEN))
    // paragraphs until fewer than a header and one row are left on the page
    const probe = paginate([...filler(1)], geometry)[0]!
    let n = 1
    for (; n < 60; n++) {
      const pages = paginate([...filler(n), t], geometry)
      const placed = pages.flatMap((p, i) => p.tables.map((x) => ({ page: i, rows: x.rows.length })))
      if (placed[0]!.page > 0) break
    }
    expect(probe.lines).toHaveLength(1)
    const pages = paginate([...filler(n), t], geometry)
    const rows = pages.flatMap((p) => p.tables.map((x) => x.rows.map((r) => r.row)))
    expect(rows[0]![0]).toBe(0)
    expect(rows[0]!.length).toBeGreaterThan(1) // a header is never on a page without a row below it
  })

  it('keeps the total row with the row above it, and rows that a merge joins on one page', () => {
    const data = table([['a', 'b'], ...Array.from({ length: 46 }, (_, i) => [`x${i}`, `${i}`])], { merges: [{ row: 'r45', col: 'c1', rows: 2, cols: 1 }] })
    data.columns = [data.columns[0]!, { ...data.columns[1]!, kind: 'number', total: 'sum' }]
    data.totals = { c2: '1035' }
    for (let n = 0; n < 6; n++) {
      const pages = paginate([...filler(n), flowTable(data)], geometry)
      const placed = pages.flatMap((p) => p.tables.map((x) => x.rows.map((r) => r.row)))
      const last = data.rows.length // the total row
      for (const rows of placed) {
        if (rows.includes(last)) expect(rows).toContain(last - 1)
        if (rows.includes(44)) expect(rows).toContain(45) // r45 and r46 are joined
      }
    }
  })

  it('splits a row that is taller than a page by its lines, so no word is lost', () => {
    const words = Array.from({ length: 900 }, (_, i) => `wort${i}`).join(' ')
    const data = table([['A', 'B'], ['kurz', words]])
    const pages = paginate([flowTable(data)], geometry)
    expect(pages.length).toBeGreaterThan(1)
    const t = layoutTable(fonts, styles(), data, box.w)
    const cell = t.rows[1]!.cells[1]!
    const seen = pages.flatMap((p) => p.tables.flatMap((x) => x.rows.filter((r) => r.row === 1).map((r) => r.part![1]!)))
    expect(seen.reduce((s, [from, end]) => s + (end - from), 0)).toBe(cell.paragraph.lines.length)
    for (const p of pages) for (const x of p.tables) for (const r of x.rows) expect(r.y + r.h).toBeLessThanOrEqual(box.y + box.h)
  })

  it('draws backgrounds and rules, then the words, and the rules of a continued row only where it is whole', () => {
    const data = table(GARDEN, { banded: true })
    const blocks = [flowTable(data)]
    const [page] = flowItems(fonts, paginate(blocks, geometry), blocks, geometry)
    const runs = [...walk(page!.items)].filter((i): i is GlyphRun => i.kind === 'glyphs')
    expect(runs.map((r) => r.text)).toEqual(['Bed', 'Crop', 'Yield', 'kg', 'North', 'Tomatoes', '212,5', 'South', 'Beans', '88,0', 'Roof', 'Herbs', '14,25'])
    const paths = [...walk(page!.items)].filter((i): i is PathItem => i.kind === 'path')
    const isSolid = (p: PathItem) => p.fill !== null && 'a' in p.fill && p.fill.a === 255
    const rules = paths.filter(isSolid)
    expect(rules.length).toBeGreaterThanOrEqual(2) // the heavy rule above the header and below it
    expect(paths.some((p) => p.fill !== null && 'a' in p.fill && p.fill.a < 255)).toBe(true) // the band
  })
})

describe('a table in a composes text', () => {
  const objects = (extra: Record<string, unknown> = {}) => [{ id: 'o1', kind: 'table' as const, w: 480, h: 96, style: 'plain-box', paragraph: null, shape: null, image: null, rotation: 0, ref: 't1', anchor: { kind: 'paragraph' as const, holder: 'b1', offset: 0 }, ...extra }]
  const doc = (n: number, data = table(GARDEN), extra: Partial<TextDocument> = {}): TextDocument => ({
    paragraphs: [{ id: 'b1', style: 'body', text: 'Vor der Tabelle.' }, { id: 'b2', style: 'body', text: 'Nach der Tabelle.' }].slice(0, n),
    styles: STYLES,
    page: A4,
    language: 'de',
    objects: objects(),
    tables: [data],
    ...extra,
  })

  it('puts the table after the paragraph it hangs from and the next paragraph after the table', () => {
    const out = layoutText(doc(2), fonts, resolver)
    const runs = [...walk(out.list.pages[0]!.items)].filter((i): i is GlyphRun => i.kind === 'glyphs')
    const ys = (word: string) => runs.find((r) => r.text === word)!.y
    expect(ys('Vor')).toBeLessThan(ys('Bed'))
    expect(ys('Roof')).toBeLessThan(ys('Nach'))
    expect(out.notes.filter((n) => n.kind !== 'hyphenation')).toEqual([])
  })

  it('names the fonts of the look the table is in', () => {
    const faces = fontsNeeded(doc(1), resolver)
    expect(faces.length).toBeGreaterThanOrEqual(1)
    for (const h of faces) expect(fonts.has(h)).toBe(true)
  })

  it('prints a floating table in the flow and says so', () => {
    const out = layoutText(doc(2, table(GARDEN, { placement: 'float' })), fonts, resolver)
    expect(out.notes.some((n) => n.kind === 'object' && n.object === 'o1')).toBe(true)
    const runs = [...walk(out.list.pages[0]!.items)].filter((i): i is GlyphRun => i.kind === 'glyphs')
    expect(runs.some((r) => r.text === 'Roof')).toBe(true)
  })

  it('says so when the table is missing, and prints the rest', () => {
    const out = layoutText(doc(2, table(GARDEN), { tables: [] }), fonts, resolver)
    expect(out.notes.some((n) => n.kind === 'object' && n.object === 'o1')).toBe(true)
    expect(out.list.pages).toHaveLength(1)
  })

  it('breaks a long table over pages and keeps the pages the same on every run (golden)', () => {
    const data = table([['Beet', 'Sorte', 'kg'], ...long(70)])
    const a = layoutText(doc(2, data), fonts, resolver)
    const b = layoutText(doc(2, data), fonts, resolver)
    expect(a.list.pages.length).toBeGreaterThan(1)
    expect(fingerprintText(a.list)).toBe(fingerprintText(b.list))
    expect(sha256(fingerprintText(a.list))).toBe(GOLDEN)
  })
})

const GOLDEN = '864ff9f352c0427cd21293d86bd8b085f3889b515fdee112fba370f6992633a7'
