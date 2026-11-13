// The styles of cells as the grid and the style menu read them (E6.13, D307, D311, D317).
//
// A sheet keeps *style ranges*, not a style per cell: a rectangle, the style it names, the slot (`box` or `words`)
// and the layer, which follows from the rectangle's shape — `sheet`, `column`, `row` or `range`. The server sends them
// least specific layer first (`cell_styles`), and inside a layer they never overlap, so "the last range that covers
// a cell" is the cell's style. A cell no range covers has Body text (D313).
//
// Everything here is a pure function of those ranges and the document's styles: the grid paints with `cellLook`
// for the cells on screen only, and the popover says where a look comes from with `whereFrom`.
import { columnName, MAX_COLS, MAX_ROWS } from './cells'
import { translate as t } from './i18n'
import { withDisplayInk, type Css } from './style-css'

export type CellSlot = 'box' | 'words'
export type Layer = 'sheet' | 'column' | 'row' | 'range'
export type Area = [number, number, number, number]

/** One style range, as the server's `cell_styles` sends it. */
export interface CellRange {
  slot: CellSlot
  layer: Layer
  /** `[r0, c0, r1, c1]`, both ends included. */
  area: Area
  style: string
}

/** The style a cell has in one slot, and the layer it comes from (`default`: no range covers it). */
export interface Origin {
  style: string
  layer: Layer | 'default'
}

export const DEFAULT_CELL_STYLE = 'body-text'
export const CELL_SLOTS: readonly CellSlot[] = ['box', 'words']

const covers = ([r0, c0, r1, c1]: Area, row: number, col: number) => r0 <= row && row <= r1 && c0 <= col && col <= c1

/** The style a cell has in `slot`: the most specific layer that covers it, or Body text. */
export function styleAt(ranges: readonly CellRange[], row: number, col: number, slot: CellSlot): Origin {
  for (let i = ranges.length - 1; i >= 0; i--) {
    const r = ranges[i]!
    if (r.slot === slot && covers(r.area, row, col)) return { style: r.style, layer: r.layer }
  }
  return { style: DEFAULT_CELL_STYLE, layer: 'default' }
}

/** Every layer under a cell in `slot`, most specific first, ending with the default: what shows through when the
 * cell's own style is taken away (D317). */
export function layersAt(ranges: readonly CellRange[], row: number, col: number, slot: CellSlot): Origin[] {
  const found: Origin[] = []
  for (let i = ranges.length - 1; i >= 0; i--) {
    const r = ranges[i]!
    if (r.slot === slot && covers(r.area, row, col)) found.push({ style: r.style, layer: r.layer })
  }
  return [...found, { style: DEFAULT_CELL_STYLE, layer: 'default' }]
}

/** The selection as the cells it means: the grid shows the first `view.rows` rows and `view.cols` columns, so a
 * column header selects down to the last row it shows — but a person who clicked it means the whole column, to the
 * sheet's last row, and so the column layer (D307). Likewise a row, and the whole sheet. */
export function sheetArea(area: Area, view: { rows: number; cols: number }): Area {
  const [r0, c0, r1, c1] = area
  return [r0, c0, r0 === 0 && r1 >= view.rows - 1 ? MAX_ROWS - 1 : r1, c0 === 0 && c1 >= view.cols - 1 ? MAX_COLS - 1 : c1]
}

/** The ranges that meet a window, in their order: what the grid looks a visible cell up in, so a lookup costs the
 * ranges on screen and never the sheet's. */
export function within(ranges: readonly CellRange[], r0: number, c0: number, r1: number, c1: number): CellRange[] {
  return ranges.filter(({ area }) => area[0] <= r1 && area[2] >= r0 && area[1] <= c1 && area[3] >= c0)
}

function place(origin: Origin, row: number, col: number): string {
  switch (origin.layer) {
    case 'range':
      return t('these cells’ own style')
    case 'row':
      return t('row {n}’s style', { n: row + 1 })
    case 'column':
      return t('column {name}’s style', { name: columnName(col) })
    case 'sheet':
      return t('the sheet’s style')
    default:
      return t('no style of their own')
  }
}

function beneath(origin: Origin, row: number, col: number, name: string): string {
  if (origin.layer === 'row') return t('row {n} is {style}', { n: row + 1, style: name })
  if (origin.layer === 'column') return t('column {name} is {style}', { name: columnName(col), style: name })
  return t('the sheet is {style}', { style: name }) // the sheet's own range, or the default every sheet has
}

/** The line at the top of the popover on cells (`computes-cell-style-popover.svg`): which style the cell has and
 * where it comes from — its own range, the row's, the column's or the sheet's — and what lies beneath; once the two
 * slots hold different styles, both. `nameOf` gives a style's name. */
export function whereFrom(ranges: readonly CellRange[], row: number, col: number, nameOf: (id: string) => string): string[] {
  const box = styleAt(ranges, row, col, 'box')
  const words = styleAt(ranges, row, col, 'words')
  if (box.style !== words.style) return [t('Box {box} · Words {words} — the two slots now differ', { box: nameOf(box.style), words: nameOf(words.style) })]
  const style = nameOf(words.style)
  const where = place(words, row, col)
  const lines = [words.layer === 'default' ? t('{style} — {place}', { style, place: where }) : t('{style} — {place}, box and words', { style, place: where })]
  // A sheet's own style covers every cell, so the default beneath it never shows and is not named.
  const under = layersAt(ranges, row, col, 'words')
    .slice(1)
    .filter((o, _, all) => o.layer !== 'default' || !all.some((x) => x.layer === 'sheet'))
  if (words.layer !== 'default' && under.length) lines.push(t('Under it: {list}', { list: under.map((o) => beneath(o, row, col, nameOf(o.style))).join('; ') }))
  return lines
}

/** How a cell is drawn. */
export interface CellLook {
  /** What its box paints: background, borders, padding. */
  box: Css
  /** What its words look like: font, size, weight, slant, decoration, colour, spacing. */
  words: Css
  align: 'left' | 'center' | 'right' | 'justify'
  valign: 'top' | 'middle' | 'bottom'
  wrap: boolean
  /** Nothing to paint for the box: no element is needed for it. */
  plain: boolean
}

interface Styled {
  id: string
  based_on: string | null
  css: Css
  resolved: Css
}

/** The alignment a cell style sets itself, or one of its parents short of Body text (D318): Body text's own
 * alignment is a paragraph's, and a cell without one of its own aligns by what it holds — numbers right, text left,
 * as every spreadsheet does. Undefined: "by content". */
export function alignOf(styles: Record<string, Styled>, id: string): string | undefined {
  const seen = new Set<string>()
  for (let s = styles[id]; s && s.id !== DEFAULT_CELL_STYLE && !seen.has(s.id); s = s.based_on ? styles[s.based_on] : undefined) {
    seen.add(s.id)
    if (s.css['text-align']) return s.css['text-align']
  }
  return undefined
}

const LAYOUT = new Set(['vertical-align', 'white-space'])
const ALIGN = new Set(['left', 'center', 'right', 'justify'])
const VALIGN = new Set(['top', 'middle', 'bottom'])

function byContent(kind: string | undefined): CellLook['align'] {
  if (kind === 'int' || kind === 'float') return 'right'
  return kind === 'bool' || kind === 'error' ? 'center' : 'left'
}

/** How a cell whose box slot holds `box` and whose words slot holds `words` is drawn (D311): the box from the box
 * facet of its style, the words from the text facet of theirs. `kind` is what the cell holds (`int`, `text`, …),
 * for the alignment of a cell whose style sets none. A style that is not there is drawn as Body text. */
export function cellLook(styles: Record<string, Styled>, facets: Record<string, string[]> | undefined, box: string, words: string, kind?: string): CellLook {
  const of = (id: string) => (styles[id] ?? styles[DEFAULT_CELL_STYLE])?.resolved ?? {}
  const boxed = new Set(facets?.box ?? [])
  const texted = new Set(facets?.text ?? [])
  const boxCss = of(box)
  const paint: Css = {}
  for (const [name, value] of Object.entries(boxCss)) if (boxed.has(name) && !LAYOUT.has(name)) paint[name] = value
  const look: Css = {}
  for (const [name, value] of Object.entries(of(words))) if (texted.has(name)) look[name] = value
  const align = alignOf(styles, words) ?? alignOf(styles, box) ?? byContent(kind)
  const valign = boxCss['vertical-align'] ?? 'middle'
  return {
    box: paint,
    words: withDisplayInk(look),
    align: (ALIGN.has(align) ? align : 'left') as CellLook['align'],
    valign: (VALIGN.has(valign) ? valign : 'middle') as CellLook['valign'],
    wrap: boxCss['white-space'] === 'normal' || boxCss['white-space'] === 'pre-wrap',
    plain: Object.keys(paint).length === 0,
  }
}
