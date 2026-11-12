import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { cellLook, layersAt, sheetArea, styleAt, whereFrom, within, type CellRange } from '~/lib/cell-styles'
import type { StyleView } from '~/lib/style-css'

const R = (slot: 'box' | 'words', layer: CellRange['layer'], area: [number, number, number, number], style: string): CellRange => ({ slot, layer, area, style })

// Least specific layer first, as the server's `cell_styles` sends them: column D is Note, B2:D3 is Input.
const RANGES: CellRange[] = [
  R('box', 'column', [0, 3, 1_048_575, 3], 'note'),
  R('words', 'column', [0, 3, 1_048_575, 3], 'note'),
  R('box', 'range', [1, 1, 2, 3], 'input'),
  R('words', 'range', [1, 1, 2, 3], 'input'),
]

const view = (id: string, name: string, css: Record<string, string>, based_on: string | null = 'body-text'): StyleView => ({
  id,
  name,
  purpose: '',
  based_on,
  css,
  computed: css,
  resolved: css,
  to_name: false,
  kind: 'paragraph',
})
const BODY = view('body-text', 'Body text', { 'font-family': 'Inter', 'font-size': '13px', 'text-align': 'left', color: '#1F1A33' }, null)
const STYLES: Record<string, StyleView> = {
  'body-text': BODY,
  input: view('input', 'Input', { ...BODY.css, color: '#5B4BC4', 'background-color': 'rgba(240, 180, 40, 0.14)' }),
  note: view('note', 'Note', { ...BODY.css, 'font-style': 'italic' }),
  result: view('result', 'Result', { ...BODY.css, 'font-weight': '600', 'border-top': '1px solid #8a8499', 'text-align': 'right', 'vertical-align': 'bottom', 'white-space': 'pre-wrap' }),
}
STYLES.input!.css = { color: '#5B4BC4', 'background-color': 'rgba(240, 180, 40, 0.14)' }
STYLES.note!.css = { 'font-style': 'italic' }
STYLES.result!.css = { 'font-weight': '600', 'border-top': '1px solid #8a8499', 'text-align': 'right', 'vertical-align': 'bottom', 'white-space': 'pre-wrap' }

describe('where a cell’s style comes from (D307)', () => {
  it('takes the most specific layer that covers the cell', () => {
    expect(styleAt(RANGES, 1, 1, 'words')).toEqual({ style: 'input', layer: 'range' })
    expect(styleAt(RANGES, 1, 3, 'box')).toEqual({ style: 'input', layer: 'range' })
    expect(styleAt(RANGES, 9, 3, 'box')).toEqual({ style: 'note', layer: 'column' })
  })

  it('has Body text where no range covers the cell', () => {
    expect(styleAt(RANGES, 9, 0, 'words')).toEqual({ style: 'body-text', layer: 'default' })
    expect(styleAt([], 0, 0, 'box')).toEqual({ style: 'body-text', layer: 'default' })
  })

  it('lists every layer under a cell, most specific first', () => {
    expect(layersAt(RANGES, 1, 3, 'words')).toEqual([
      { style: 'input', layer: 'range' },
      { style: 'note', layer: 'column' },
      { style: 'body-text', layer: 'default' },
    ])
  })

  it('keeps only the ranges that meet a window', () => {
    expect(within(RANGES, 5, 0, 9, 2)).toEqual([])
    expect(within(RANGES, 0, 3, 0, 3).map((r) => r.style)).toEqual(['note', 'note'])
  })
})

describe('the line at the top of the popover (computes-cell-style-popover.svg)', () => {
  const names = (id: string) => STYLES[id]?.name ?? id

  it('says the cells’ own style, and what lies beneath it', () => {
    expect(whereFrom(RANGES, 1, 3, names)).toEqual(['Input — these cells’ own style, box and words', 'Under it: column D is Note; the sheet is Body text'])
  })

  it('names a whole column, a row and the sheet as where a look comes from', () => {
    expect(whereFrom(RANGES, 9, 3, names)).toEqual(['Note — column D’s style, box and words', 'Under it: the sheet is Body text'])
    const rows = [R('box', 'sheet', [0, 0, 1_048_575, 16_383], 'note'), R('words', 'sheet', [0, 0, 1_048_575, 16_383], 'note'), R('box', 'row', [4, 0, 4, 16_383], 'result'), R('words', 'row', [4, 0, 4, 16_383], 'result')]
    expect(whereFrom(rows, 4, 2, names)).toEqual(['Result — row 5’s style, box and words', 'Under it: the sheet is Note'])
    expect(whereFrom([], 0, 0, names)).toEqual(['Body text — no style of their own'])
  })

  it('says both styles once the two slots differ', () => {
    const split = [...RANGES, R('box', 'range', [1, 1, 1, 1], 'input-changed')]
    expect(whereFrom(split, 1, 1, (id) => (id === 'input-changed' ? 'Input (changed)' : names(id)))).toEqual(['Box Input (changed) · Words Input — the two slots now differ'])
  })
})

describe('how a cell is drawn', () => {
  it('draws its box from the box slot and its words from the words slot', () => {
    const look = cellLook(STYLES, STYLE_MODEL.facets, 'input', 'note', 'int')
    expect(look.box).toEqual({ 'background-color': 'rgba(240, 180, 40, 0.14)' })
    expect(look.words['font-style']).toBe('italic')
    expect(look.words['background-color']).toBeUndefined()
  })

  it('aligns by what the cell holds unless a cell style sets an alignment: Body text’s own does not count', () => {
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'input', 'input', 'int').align).toBe('right')
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'input', 'input', 'text').align).toBe('left')
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'result', 'result', 'text').align).toBe('right')
  })

  it('reads vertical alignment and wrapping from the box', () => {
    const look = cellLook(STYLES, STYLE_MODEL.facets, 'result', 'body-text', 'text')
    expect(look.valign).toBe('bottom')
    expect(look.wrap).toBe(true)
    expect(look.box['border-top']).toBe('1px solid #8a8499')
    expect(look.box['vertical-align']).toBeUndefined() // a layout property, not paint
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'body-text', 'body-text', 'text')).toMatchObject({ valign: 'middle', wrap: false })
  })

  it('knows when there is nothing to paint for the box', () => {
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'body-text', 'body-text', 'text').plain).toBe(true)
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'input', 'body-text', 'text').plain).toBe(false)
  })

  it('keeps the size of its words and their colour, readable in either theme', () => {
    const look = cellLook(STYLES, STYLE_MODEL.facets, 'body-text', 'body-text', 'text')
    expect(look.words['font-size']).toBe('13px')
    expect(look.words.color).toBe('var(--text)') // the default ink follows the theme
    expect(look.words['text-align']).toBeUndefined() // `align` says it
  })

  it('draws an unknown style as Body text', () => {
    expect(cellLook(STYLES, STYLE_MODEL.facets, 'gone', 'gone', 'text').words['font-family']).toBe('Inter')
  })
})

describe('a header selects the whole line, not just the rows the grid shows', () => {
  const VIEW = { rows: 10_000, cols: 702 }
  it('stretches a selection that spans the view to the sheet’s own end, so it goes into the column, row or sheet layer', () => {
    expect(sheetArea([0, 2, 9_999, 2], VIEW)).toEqual([0, 2, 1_048_575, 2])
    expect(sheetArea([4, 0, 4, 701], VIEW)).toEqual([4, 0, 4, 16_383])
    expect(sheetArea([0, 0, 9_999, 701], VIEW)).toEqual([0, 0, 1_048_575, 16_383])
  })

  it('leaves any other selection as it is', () => {
    expect(sheetArea([1, 1, 2, 3], VIEW)).toEqual([1, 1, 2, 3])
    expect(sheetArea([1, 2, 9_999, 2], VIEW)).toEqual([1, 2, 9_999, 2]) // not from the first row: not the column
  })
})
