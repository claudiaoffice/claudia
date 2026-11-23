import { beforeAll, describe, expect, it } from 'vitest'
import {
  type PrintedSlide,
  type PrintedSheet,
  type SheetCell,
  type SheetDocument,
  type SheetPrint,
  columnLetters,
  DEFAULT_SHEET_PRINT,
  layoutSheet,
  type SheetPages,
  sheetFontsNeeded,
} from '../src/apps/computes'
import type { PageSetupData, TextStyle } from '../src/apps/objects'
import { canonicalJson } from '../src/canonical'
import { type DisplayItem, type DisplayPage, type GlyphRun, type GroupItem, type PathItem, walk } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { writePdf } from '../src/pdf/writer'
import { sha256 } from './helpers'
import { readPdf } from './pdf'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

const STYLES: TextStyle[] = [
  { id: 'cell-text', based_on: null, resolved: { 'font-family': 'Inter, sans-serif', 'font-size': '14px', 'line-height': '1.2', color: '#1F1A33' } },
  { id: 'cell-head', based_on: 'cell-text', resolved: { 'font-family': 'Inter, sans-serif', 'font-size': '14px', 'line-height': '1.2', color: '#1F1A33', 'font-weight': '700', 'background-color': '#E7E1F4' } },
]
const A4: PageSetupData = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait', margins: [36000, 36000, 36000, 36000], page_numbers: false }
const COL = 72000 // 96 px
const ROW = 19500 // 26 px
const CONTENT_W = 595276 - 72000
const CONTENT_H = 841890 - 72000

const cell = (row: number, col: number, text: string, extra: Partial<SheetCell> = {}): SheetCell => ({ row, col, text, ...extra })
const sheet = (cells: SheetCell[], print: Partial<SheetPrint> = {}, extra: Partial<PrintedSheet> = {}): PrintedSheet => ({
  kind: 'sheet',
  id: 's1',
  name: 'Costs',
  area: null,
  cells,
  colWidths: [],
  rowHeights: [],
  objects: [],
  print: { ...DEFAULT_SHEET_PRINT, ...print },
  ...extra,
})
const book = (sheets: (PrintedSheet | PrintedSlide)[], page: Partial<PageSetupData> = {}, extra: Partial<SheetDocument> = {}): SheetDocument => ({
  sheets,
  styles: STYLES,
  page: { ...A4, ...page },
  language: 'en',
  ...extra,
})
/** a table of `rows` × `cols` cells that say where they are */
const table = (rows: number, cols: number): SheetCell[] =>
  Array.from({ length: rows * cols }, (_, i) => cell(Math.floor(i / cols), i % cols, `r${Math.floor(i / cols) + 1}c${(i % cols) + 1}`))

const runs = (items: readonly DisplayItem[]): GlyphRun[] => [...walk(items)].filter((i): i is GlyphRun => i.kind === 'glyphs')
const words = (page: DisplayPage) => runs(page.items).map((r) => r.text)
/** a page's text in reading order as one string: "n / N" is two words to the layout */
const said = (page: DisplayPage) => words(page).join(' ')
/** the page map of a print of sheets: every page says its rows and columns */
const m = (out: SheetPages) => out.pageMap as { sheet: string; kind: string; rows: [number, number]; cols: [number, number]; scale: number }[]
const paths = (items: readonly DisplayItem[]): PathItem[] => [...walk(items)].filter((i): i is PathItem => i.kind === 'path')
/** the scale of a page's content group, in millionths */
const scaleOf = (page: DisplayPage): number => (page.items.find((i): i is GroupItem => i.kind === 'group' && i.matrix !== undefined)!.matrix![0])

describe('a sheet on pages', () => {
  it('names the fonts its cells need', () => {
    const need = sheetFontsNeeded(book([sheet(table(2, 2))]), resolver)
    expect(need.length).toBeGreaterThanOrEqual(1)
    for (const h of need) expect(fonts.has(h)).toBe(true)
  })

  it('counts columns as letters', () => {
    expect([0, 1, 25, 26, 27, 51, 52, 701, 702, 16383].map(columnLetters)).toEqual(['A', 'B', 'Z', 'AA', 'AB', 'AZ', 'BA', 'ZZ', 'AAA', 'XFD'])
  })

  it('prints a small sheet on one page at 100 %, cells where their columns and rows are', () => {
    const out = layoutSheet(book([sheet([cell(0, 0, 'Name'), cell(0, 1, 'Cost', { align: 'right' }), cell(1, 0, 'Rent'), cell(1, 1, '1,200', { align: 'right' })])]), fonts, resolver)
    expect(out.list.pages).toHaveLength(1)
    const page = out.list.pages[0]!
    expect([page.width, page.height]).toEqual([595276, 841890])
    expect(scaleOf(page)).toBe(1_000_000)
    const byText = new Map(runs(page.items).map((r) => [r.text, r]))
    const name = byText.get('Name')!
    const rent = byText.get('Rent')!
    // the group places the sheet's origin at the margin; the run's x is in the sheet's own space: its cell's left edge plus an inset
    const content = page.items.find((i): i is GroupItem => i.kind === 'group' && i.matrix !== undefined)!
    expect(content.matrix!.slice(4)).toEqual([36000, 36000])
    expect(name.x).toBe(3000)
    expect(rent.x).toBe(3000)
    expect(rent.y).toBeGreaterThan(name.y)
    expect(rent.y - name.y).toBe(ROW)
    // a right-aligned text ends an inset short of its column's right edge
    const cost = byText.get('1,200')!
    const end = cost.x + cost.glyphs.at(-1)!.dx
    expect(end).toBeLessThanOrEqual(2 * COL - 3000)
    expect(end).toBeGreaterThan(2 * COL - 3000 - 12000)
    expect(m(out)).toEqual([{ sheet: 's1', kind: 'sheet', rows: [0, 1], cols: [0, 1], scale: 1_000_000 }])
  })

  it('takes column widths and row heights from the sheet', () => {
    const doc = book([sheet([cell(0, 2, 'C'), cell(3, 0, 'D')], {}, { colWidths: [[0, 200], [1, 50]], rowHeights: [[0, 40], [1, 40], [2, 80]] })])
    const page = layoutSheet(doc, fonts, resolver).list.pages[0]!
    const byText = new Map(runs(page.items).map((r) => [r.text, r]))
    // column C starts after 200 px and 50 px: 250 px = 187500 mpt
    expect(byText.get('C')!.x).toBe(187500 + 3000)
    // row 4 starts after 40 + 40 + 80 px = 160 px = 120000 mpt, text centred in its 26 px row
    expect(byText.get('D')!.y).toBeGreaterThan(120000)
    expect(byText.get('D')!.y).toBeLessThan(120000 + ROW)
  })

  describe('scale', () => {
    it('fits to width by default: all columns on a page, rows run on, never enlarged', () => {
      const cells = table(80, 11) // 11 × 96 px = 792 pt wide
      const out = layoutSheet(book([sheet(cells)]), fonts, resolver)
      const expected = Math.floor((CONTENT_W * 1_000_000) / (11 * COL))
      expect(m(out).every((p) => p.scale === expected)).toBe(true)
      expect(m(out).every((p) => p.cols[0] === 0 && p.cols[1] === 10)).toBe(true)
      expect(m(out).length).toBeGreaterThan(1)
      // consecutive rows, none lost, none twice
      expect(m(out)[0]!.rows[0]).toBe(0)
      for (let i = 1; i < m(out).length; i++) expect(m(out)[i]!.rows[0]).toBe(m(out)[i - 1]!.rows[1] + 1)
      expect(m(out).at(-1)!.rows[1]).toBe(79)
      // a narrow sheet is not blown up
      expect(layoutSheet(book([sheet(table(3, 2))]), fonts, resolver).pageMap[0]!.scale).toBe(1_000_000)
    })

    it('fits to one page when asked', () => {
      const out = layoutSheet(book([sheet(table(80, 11), { scale: { kind: 'fit-page' } })]), fonts, resolver)
      expect(m(out)).toHaveLength(1)
      const total = Math.floor((CONTENT_H * 1_000_000) / (80 * ROW))
      expect(m(out)[0]!.scale).toBe(Math.min(total, Math.floor((CONTENT_W * 1_000_000) / (11 * COL))))
    })

    it('takes a percentage and cuts columns too', () => {
      const out = layoutSheet(book([sheet(table(10, 11), { scale: { kind: 'percent', percent: 100 } })]), fonts, resolver)
      // 523276 mpt hold 7 columns of 72000
      expect(m(out).map((p) => p.cols)).toEqual([[0, 6], [7, 10]])
      expect(m(out).every((p) => p.scale === 1_000_000)).toBe(true)
      const half = layoutSheet(book([sheet(table(10, 11), { scale: { kind: 'percent', percent: 50 } })]), fonts, resolver)
      expect(m(half).map((p) => p.cols)).toEqual([[0, 10]])
      expect(m(half)[0]!.scale).toBe(500_000)
    })

    it('does not shrink below 10 %, and says so', () => {
      const wide = Array.from({ length: 200 }, (_, c) => cell(0, c, `c${c}`))
      const out = layoutSheet(book([sheet(wide)]), fonts, resolver)
      expect(m(out).every((p) => p.scale === 100_000)).toBe(true)
      expect(m(out).length).toBeGreaterThan(1)
      expect(out.notes.some((n) => n.kind === 'sheet' && /10 %/.test(n.reason ?? ''))).toBe(true)
    })
  })

  describe('where the cuts fall', () => {
    const cells = table(70, 11)
    const at100 = { scale: { kind: 'percent', percent: 100 } } as const

    it('goes down first, then across, by default', () => {
      const out = layoutSheet(book([sheet(cells, at100)]), fonts, resolver)
      const rowsPerPage = Math.floor(CONTENT_H / ROW)
      expect(m(out).map((p) => p.cols[0])).toEqual([...Array(Math.ceil(70 / rowsPerPage)).fill(0), ...Array(Math.ceil(70 / rowsPerPage)).fill(7)])
      expect(m(out)[0]!.rows).toEqual([0, rowsPerPage - 1])
    })

    it('can go across first', () => {
      const out = layoutSheet(book([sheet(cells, { ...at100, order: 'across-then-down' })]), fonts, resolver)
      expect(m(out).slice(0, 4).map((p) => [p.rows[0], p.cols[0]])).toEqual([[0, 0], [0, 7], [m(out)[2]!.rows[0], 0], [m(out)[2]!.rows[0], 7]])
    })

    it('gives a row taller than a page a page to itself, cut at its border', () => {
      const out = layoutSheet(book([sheet([cell(0, 0, 'a'), cell(1, 0, 'tall'), cell(2, 0, 'b')], at100, { rowHeights: [[1, 2000]] })]), fonts, resolver)
      expect(m(out).map((p) => p.rows)).toEqual([[0, 0], [1, 1], [2, 2]])
    })

    it('stays inside the margins', () => {
      const out = layoutSheet(book([sheet(cells, at100)]), fonts, resolver)
      for (const page of out.list.pages) {
        const g = page.items.find((i): i is GroupItem => i.kind === 'group' && i.matrix !== undefined)!
        const clip = g.clipPath!.ops
        const xs = clip.flatMap((o) => (o[0] === 'Z' ? [] : [o[1]]))
        const ys = clip.flatMap((o) => (o[0] === 'Z' ? [] : [o[2]]))
        expect(Math.max(...xs) + g.matrix![4]).toBeLessThanOrEqual(595276 - 36000)
        expect(Math.max(...ys) + g.matrix![5]).toBeLessThanOrEqual(841890 - 36000)
      }
    })
  })

  describe('rows and columns on every page', () => {
    const at100 = { scale: { kind: 'percent', percent: 100 } } as const
    it('draws repeated rows at the top of every page that starts after them, and not twice on the first', () => {
      const out = layoutSheet(book([sheet(table(100, 3), { ...at100, repeatRows: [0, 0] })]), fonts, resolver)
      expect(m(out).length).toBeGreaterThan(1)
      for (const [i, page] of out.list.pages.entries()) {
        const w = words(page)
        expect(w.filter((x) => x === 'r1c1')).toHaveLength(1)
        // the first page holds row 1 by itself; later pages hold it again as the top row, then their own rows
        if (i > 0) expect(w).toContain(`r${m(out)[i]!.rows[0] + 1}c1`)
      }
      // a later page has one row fewer of its own
      const first = m(out)[0]!.rows
      const second = m(out)[1]!.rows
      expect(second[1] - second[0]).toBe(first[1] - first[0] - 1)
    })
    it('draws repeated columns at the left of every page that starts after them', () => {
      const out = layoutSheet(book([sheet(table(3, 12), { ...at100, repeatCols: [0, 0] })]), fonts, resolver)
      expect(m(out).length).toBe(2)
      expect(words(out.list.pages[1]!)).toContain('r1c1')
      expect(words(out.list.pages[1]!)).toContain(`r1c${m(out)[1]!.cols[0] + 1}`)
      expect(words(out.list.pages[0]!).filter((x) => x === 'r1c1')).toHaveLength(1)
    })
  })

  describe('what is drawn besides text', () => {
    it('draws gridlines when asked, as one path a page', () => {
      const on = layoutSheet(book([sheet(table(3, 3), { gridlines: true })]), fonts, resolver).list.pages[0]!
      const off = layoutSheet(book([sheet(table(3, 3), { gridlines: false })]), fonts, resolver).list.pages[0]!
      expect(paths(on.items).filter((p) => p.stroke && !p.fill)).toHaveLength(1)
      expect(paths(off.items).filter((p) => p.stroke && !p.fill)).toHaveLength(0)
    })
    it('draws row numbers and column letters when asked, and they are not part of the page map', () => {
      const out = layoutSheet(book([sheet(table(2, 2), { headings: true })]), fonts, resolver)
      const w = words(out.list.pages[0]!)
      for (const h of ['A', 'B', '1', '2']) expect(w).toContain(h)
      expect(m(out)[0]!.rows).toEqual([0, 1])
      expect(words(layoutSheet(book([sheet(table(2, 2))]), fonts, resolver).list.pages[0]!)).not.toContain('A')
    })
    it('paints a cell’s style: its background behind its words', () => {
      const out = layoutSheet(book([sheet([cell(0, 0, 'Total', { style: 'cell-head' })])]), fonts, resolver)
      const bg = paths(out.list.pages[0]!.items).find((p) => p.fill && !('kind' in p.fill) && p.fill.r === 0xe7)
      expect(bg).toBeDefined()
      expect(runs(out.list.pages[0]!.items)[0]!.face).not.toEqual(runs(layoutSheet(book([sheet([cell(0, 0, 'Total')])]), fonts, resolver).list.pages[0]!.items)[0]!.face)
    })
    it('tints cells by what they are for only when asked, and a fill of its own wins', () => {
      const cells = [cell(0, 0, 'rent', { purpose: 'input' }), cell(0, 1, 'sum', { purpose: 'calc' }), cell(0, 2, 'total', { purpose: 'result', style: 'cell-head' })]
      const tints = (purposes: boolean) =>
        paths(layoutSheet(book([sheet(cells, { purposes })]), fonts, resolver).list.pages[0]!.items)
          .filter((p) => p.fill && !('kind' in p.fill))
          .map((p) => (p.fill as { r: number; g: number; b: number }).r.toString(16))
      expect(tints(false)).toEqual(['e7'])
      expect(tints(true).sort()).toEqual(['e7', 'ed', 'fc'])
    })
  })

  describe('text that does not fit its cell', () => {
    const long = 'A long label that cannot stay in one column'
    it('runs on over empty cells to its right', () => {
      const out = layoutSheet(book([sheet([cell(0, 0, long)])]), fonts, resolver)
      const groups = [...walk(out.list.pages[0]!.items)].filter((i): i is GroupItem => i.kind === 'group' && i.clip !== null)
      // no cell cuts it: the words go on past the first column, and the page takes in the columns they cover
      expect(groups.filter((x) => runs(x.items).length > 0 && x.clip!.w <= COL)).toEqual([])
      expect(runs(out.list.pages[0]!.items).find((r) => r.text === 'column')!.x).toBeGreaterThan(COL)
      expect(said(out.list.pages[0]!)).toBe(`${long} Costs`)
      expect(m(out)[0]!.cols[1]).toBeGreaterThan(0)
    })
    it('is cut at the cell’s border when the next cell has something', () => {
      const out = layoutSheet(book([sheet([cell(0, 0, long), cell(0, 1, 'x')])]), fonts, resolver)
      const g = [...walk(out.list.pages[0]!.items)].filter((i): i is GroupItem => i.kind === 'group' && i.clip !== null).find((x) => runs(x.items).some((r) => r.text.includes('long')))
      expect(g).toBeDefined()
      expect(g!.clip!.x + g!.clip!.w).toBeLessThanOrEqual(COL)
    })
    it('does not run a right-aligned number on', () => {
      const out = layoutSheet(book([sheet([cell(0, 1, '123,456,789,012,345,678', { align: 'right' })])]), fonts, resolver)
      const g = [...walk(out.list.pages[0]!.items)].filter((i): i is GroupItem => i.kind === 'group' && i.clip !== null).find((x) => runs(x.items).length)
      expect(g!.clip!.x).toBeGreaterThanOrEqual(COL)
      expect(g!.clip!.x + g!.clip!.w).toBeLessThanOrEqual(2 * COL)
    })
  })

  describe('several sheets, footers and paper', () => {
    const two = () => book([sheet(table(2, 2), {}, { id: 's1', name: 'Costs' }), sheet(table(2, 2), { orientation: 'landscape' }, { id: 's2', name: 'Plan' })], { page_numbers: true })

    it('numbers pages through the whole print and names each page’s sheet at the left', () => {
      const out = layoutSheet(two(), fonts, resolver)
      expect(out.list.pages).toHaveLength(2)
      const footers = out.list.pages.map((p) => runs(p.items).filter((r) => r.y > p.height - 36000))
      expect(footers[0]!.map((r) => r.text)).toEqual(['Costs', '1 /', '2'])
      expect(footers[1]!.map((r) => r.text)).toEqual(['Plan', '2 /', '2'])
      expect(footers[0]![0]!.x).toBe(36000)
      const [name] = footers[0]!
      const number = footers[0]!.at(-1)!
      expect(number!.x + number!.glyphs.at(-1)!.dx).toBeGreaterThan(595276 - 36000 - 12000)
      expect(number!.x + number!.glyphs.at(-1)!.dx).toBeLessThanOrEqual(595276 - 36000)
      expect(name!.size).toBe(9000)
    })
    it('lets each sheet lie as it likes', () => {
      const out = layoutSheet(two(), fonts, resolver)
      expect([out.list.pages[0]!.width, out.list.pages[0]!.height]).toEqual([595276, 841890])
      expect([out.list.pages[1]!.width, out.list.pages[1]!.height]).toEqual([841890, 595276])
    })
    it('leaves the name out when the option is off, and the number when the workbook has none', () => {
      const off = layoutSheet(book([sheet(table(1, 1), { footerName: false })], { page_numbers: true }), fonts, resolver)
      expect(said(off.list.pages[0]!)).toBe('r1c1 1 / 1')
      const none = layoutSheet(book([sheet(table(1, 1))]), fonts, resolver)
      expect(said(none.list.pages[0]!)).toBe('r1c1 Costs')
      const bare = layoutSheet(book([sheet(table(1, 1), { footerName: false })]), fonts, resolver)
      expect(words(bare.list.pages[0]!)).toEqual(['r1c1'])
    })
    it('keeps room for a footer when the bottom margin has none', () => {
      const out = layoutSheet(book([sheet(table(120, 1), { scale: { kind: 'percent', percent: 100 } })], { page_numbers: true, margins: [36000, 36000, 0, 36000] }), fonts, resolver)
      const g = out.list.pages[0]!.items.find((i): i is GroupItem => i.kind === 'group' && i.matrix !== undefined)!
      const bottom = Math.max(...g.clipPath!.ops.flatMap((o) => (o[0] === 'Z' ? [] : [o[2]]))) + g.matrix![5]
      expect(bottom).toBeLessThanOrEqual(841890 - 22677)
    })
  })

  describe('empty pages', () => {
    const far = [cell(0, 0, 'first'), cell(0, 30, 'last')]
    const at100 = { scale: { kind: 'percent', percent: 100 } } as const
    it('leaves out pages with nothing on them by default', () => {
      const out = layoutSheet(book([sheet(far, at100)]), fonts, resolver)
      expect(m(out).map((p) => p.cols[0])).toEqual([0, 28])
      expect(out.list.pages).toHaveLength(2)
    })
    it('keeps them when asked', () => {
      const out = layoutSheet(book([sheet(far, { ...at100, skipEmpty: false })]), fonts, resolver)
      expect(m(out)).toHaveLength(5)
    })
    it('gives one blank page and says so when there is nothing at all', () => {
      const out = layoutSheet(book([sheet([])]), fonts, resolver)
      expect(out.list.pages).toHaveLength(1)
      expect(out.notes.map((n) => n.kind)).toEqual(['sheet'])
    })
  })

  describe('odd input', () => {
    const at100 = { scale: { kind: 'percent', percent: 100 } } as const
    it('does not repeat rows that leave no room for the page’s own', () => {
      const out = layoutSheet(book([sheet(table(6, 1), { ...at100, repeatRows: [0, 0] }, { rowHeights: [[0, 2000]] })]), fonts, resolver)
      expect(m(out).map((p) => p.rows)).toEqual([[0, 0], [1, 5]])
      expect(words(out.list.pages[1]!).filter((w) => w === 'r1c1')).toEqual([])
    })
    it('reads an area given the wrong way round, and ignores cells that cannot exist', () => {
      const area = { row0: 4, col0: 5, row1: 2, col1: 3 }
      const out = layoutSheet(book([sheet([...table(10, 10), cell(-1, 0, 'neg'), cell(0, 99999, 'far'), cell(0.5, 0, 'half')], {}, { area })]), fonts, resolver)
      expect(m(out)[0]).toMatchObject({ rows: [2, 4], cols: [3, 5] })
      expect(words(out.list.pages[0]!)).not.toContain('neg')
    })
    it('stops cutting a sheet at 5 000 pages and says so', () => {
      const out = layoutSheet(book([sheet([cell(0, 0, 'x')], at100, { area: { row0: 0, col0: 0, row1: 1_000_000, col1: 0 } })]), fonts, resolver)
      expect(out.list.pages).toHaveLength(1)
      expect(out.notes.some((n) => n.kind === 'sheet' && /5000/.test(n.reason ?? ''))).toBe(true)
    })
  })

  describe('the area printed', () => {
    it('prints only the area it is given, from its first row and column', () => {
      const out = layoutSheet(book([sheet(table(10, 10), {}, { area: { row0: 2, col0: 3, row1: 4, col1: 5 } })]), fonts, resolver)
      expect(m(out)[0]).toMatchObject({ rows: [2, 4], cols: [3, 5] })
      const w = words(out.list.pages[0]!)
      expect(w).toContain('r3c4')
      expect(w).toContain('r5c6')
      expect(w).not.toContain('r2c4')
      expect(w).not.toContain('r6c6')
      expect(runs(out.list.pages[0]!.items).find((r) => r.text === 'r3c4')!.x).toBe(3000)
    })
    it('covers pictures and charts when it takes the used range', () => {
      const picture = { id: 'p1', kind: 'image' as const, w: 96 * 5, h: 52, style: 'cell-text', paragraph: null, shape: null, image: 'i1', rotation: 0, anchor: { kind: 'cell' as const, row: 4, col: 3 } }
      const out = layoutSheet(book([sheet([cell(0, 0, 'x')], {}, { objects: [picture] })], {}, { images: [{ id: 'i1', format: 'svg', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="#3d5a80"/></svg>' }] }), fonts, resolver)
      // 5 columns wide from D, 2 rows tall from row 5
      expect(m(out)[0]).toMatchObject({ rows: [0, 5], cols: [0, 7] })
    })
  })

  describe('pictures and charts on a sheet', () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="#3d5a80"/></svg>'
    const picture = (row: number, col: number, w = 192, h = 130) => ({ id: 'p1', kind: 'image' as const, w, h, style: 'cell-text', paragraph: null, shape: null, image: 'i1', rotation: 0, anchor: { kind: 'cell' as const, row, col } })
    const circles = (page: DisplayPage) => paths(page.items).filter((p) => p.fill && !('kind' in p.fill) && p.fill.b === 0x80)
    const at100 = { scale: { kind: 'percent', percent: 100 } } as const

    it('draws a picture where it sits, over the cells', () => {
      const out = layoutSheet(book([sheet(table(3, 3), {}, { objects: [picture(1, 1)] })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(circles(out.list.pages[0]!)).toHaveLength(1)
    })
    it('cuts a picture at the page’s edge: it is on both pages, clipped to each', () => {
      // 36 rows of 26 px are 702 pt; at 100 % the content is 606 pt high: a picture from row 20 on is cut
      const out = layoutSheet(book([sheet(table(40, 2), at100, { objects: [picture(37, 0, 192, 200)] })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(m(out).length).toBeGreaterThanOrEqual(2)
      const holding = out.list.pages.filter((p) => circles(p).length > 0)
      expect(holding).toHaveLength(2)
    })
    it('leaves objects out when the option is off', () => {
      const out = layoutSheet(book([sheet(table(3, 3), { objects: false }, { objects: [picture(1, 1)] })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(circles(out.list.pages[0]!)).toHaveLength(0)
    })
    it('draws a chart from the picture the client made of it, and says when it has none', () => {
      const chart = { ...picture(1, 1), kind: 'diagram' as const }
      const drawn = layoutSheet(book([sheet(table(3, 3), {}, { objects: [chart] })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(circles(drawn.list.pages[0]!)).toHaveLength(1)
      const missing = layoutSheet(book([sheet(table(3, 3), {}, { objects: [{ ...chart, image: null }] })]), fonts, resolver)
      expect(missing.notes).toEqual([{ kind: 'object', object: 'p1', reason: 'the chart has no picture to print' }])
    })
  })

  describe('a slide among the sheets (E6.31, D1473)', () => {
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><rect width="400" height="200" fill="#3d5a80"/></svg>'
    const onSlide = (x: number, y: number, w: number, h: number) => ({ id: 'p1', kind: 'image' as const, w, h, style: '', paragraph: null, shape: null, image: 'i1', rotation: 0, anchor: { kind: 'slide' as const, holder: 'd1', x, y } })
    const slide = (extra: Partial<PrintedSlide> = {}): PrintedSlide => ({ kind: 'slide', id: 'd1', name: 'Sales chart', objects: [onSlide(0, 0, 800, 450)], ...extra })
    it('prints as one landscape page between the sheets, its 16:9 frame as large as the page takes', () => {
      const out = layoutSheet(book([sheet(table(3, 3)), slide(), sheet(table(3, 3), {}, { id: 's2', name: 'Costs' })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(m(out).map((p) => [p.sheet, p.kind])).toEqual([['s1', 'sheet'], ['d1', 'slide'], ['s2', 'sheet']])
      const page = out.list.pages[1]!
      expect(page.width).toBeGreaterThan(page.height)
      const group = page.items.find((i): i is GroupItem => i.kind === 'group')!
      // a slide of 1200 pt is scaled to the 769890 mpt wide content box of a landscape A4 (16:9 fits it by its width)
      expect(group.matrix![0]).toBe(Math.floor((769890 * 1_000_000) / 1_200_000))
      // the picture fills the top left quarter of the slide
      const rect = paths(group.items).find((p) => p.fill && !('kind' in p.fill) && p.fill.b === 0x80)!
      expect(Math.max(...rect.ops.flatMap((o) => (o[0] === 'Z' ? [] : [o[1]])))).toBeLessThanOrEqual(600_000)
    })
    it('carries its name and number in the footer like any sheet', () => {
      const out = layoutSheet(book([sheet(table(3, 3)), slide()], { page_numbers: true }, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(said(out.list.pages[1]!)).toBe('Sales chart 2 / 2')
    })
    it('draws a chart on it as its picture, and says so when it has none (E6.31 step 3)', () => {
      const chart = { ...onSlide(0, 0, 1600, 900), kind: 'diagram' as const }
      const drawn = layoutSheet(book([slide({ objects: [chart] })], {}, { images: [{ id: 'i1', format: 'svg', svg }] }), fonts, resolver)
      expect(drawn.notes).toEqual([])
      const group = drawn.list.pages[0]!.items.find((i): i is GroupItem => i.kind === 'group')!
      expect(paths(group.items).some((p) => p.fill && !('kind' in p.fill) && p.fill.b === 0x80)).toBe(true)
      const missing = layoutSheet(book([slide({ objects: [{ ...chart, image: null }] })]), fonts, resolver)
      expect(missing.notes).toEqual([{ kind: 'object', object: 'p1', reason: 'the chart has no picture to print' }])
    })
    it('is a page, even with nothing on it', () => {
      const out = layoutSheet(book([slide({ objects: [] })]), fonts, resolver)
      expect(out.list.pages).toHaveLength(1)
      expect(out.notes).toEqual([])
    })
  })

  describe('as a PDF', () => {
    it('writes the very pages, the same bytes every time, with every cell’s words readable', async () => {
      const doc = () => book([sheet(table(30, 11), { headings: true, gridlines: true, repeatRows: [0, 0] }), sheet(table(3, 3), { orientation: 'landscape' }, { id: 's2', name: 'Plan' })], { page_numbers: true })
      const out = layoutSheet(doc(), fonts, resolver)
      const pdf = writePdf(out.list.pages, fonts, () => undefined, { title: 'Costs' })
      const read = await readPdf(pdf)
      expect(read.pages).toHaveLength(out.list.pages.length)
      const all = read.pages.map((p) => p.items.map((i) => i.str).join(' ')).join(' ')
      expect(all).toContain('r1c1')
      expect(all).toContain('r30c11')
      expect(all.replace(/\s+/g, '')).toContain('1/')
      const again = layoutSheet(doc(), fonts, resolver)
      expect(canonicalJson(again.list)).toBe(canonicalJson(out.list))
      expect(sha256(writePdf(again.list.pages, fonts, () => undefined, { title: 'Costs' }))).toBe(sha256(pdf))
    })
  })

  describe('speed', () => {
    it('lays out 6 000 cells on a few pages in a couple of seconds', () => {
      const t0 = performance.now()
      const out = layoutSheet(book([sheet(table(600, 10), { scale: { kind: 'percent', percent: 100 } })]), fonts, resolver)
      const ms = performance.now() - t0
      expect(m(out).length).toBeGreaterThan(10)
      expect(ms).toBeLessThan(4000)
    })
  })
})
