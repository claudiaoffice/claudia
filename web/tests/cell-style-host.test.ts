import { describe, expect, it, vi } from 'vitest'
import { cellSlot, cellStyleHost, type CellStyling } from '~/lib/cell-style-host'
import type { CellRange } from '~/lib/cell-styles'
import { StyleEditor } from '~/lib/style-host'
import type { StyleView } from '~/lib/style-css'
import { STYLE_MODEL } from './style-model.fixture'

const view = (id: string, name: string, kind = 'paragraph'): StyleView => ({
  id,
  name,
  purpose: '',
  based_on: id === 'body-text' ? null : 'body-text',
  css: {},
  computed: {},
  resolved: {},
  to_name: false,
  kind,
})
const R = (slot: 'box' | 'words', area: [number, number, number, number], style: string, layer: CellRange['layer'] = 'range'): CellRange => ({ slot, layer, area, style })

function styling(over: Partial<CellStyling> = {}) {
  const calls: Record<string, unknown[]> = {}
  const spy = (name: string) =>
    vi.fn(async (...args: unknown[]) => {
      calls[name] = args
      return true
    })
  const session: CellStyling = {
    readOnly: false,
    styles: [view('body-text', 'Body text'), view('input', 'Input'), view('note', 'Note'), view('plain-box', 'Plain box', 'box'), view('plain-shape', 'Plain shape', 'outline')],
    roles: [],
    readings: [],
    model: STYLE_MODEL,
    sheet: 's1',
    area: [1, 1, 2, 3],
    anchor: { row: 1, col: 1 },
    ranges: () => [R('box', [0, 3, 1_048_575, 3], 'note', 'column'), R('words', [0, 3, 1_048_575, 3], 'note', 'column'), R('box', [1, 1, 2, 3], 'input'), R('words', [1, 1, 2, 3], 'input')],
    uses: () => ({ input: 2, note: 2 }),
    applyStyle: spy('applyStyle'),
    changeStyle: spy('changeStyle'),
    deviateStyle: spy('deviateStyle'),
    renameStyle: spy('renameStyle'),
    clearCellStyle: spy('clearCellStyle'),
    checkCss: vi.fn(async () => null),
    setRole: spy('setRole'),
    ...over,
  }
  return { host: cellStyleHost(session), session, calls }
}

describe('a cell as one slot to the menu (D311)', () => {
  it('reads every facet both of its slots read, and takes only what fits both', () => {
    expect(cellSlot(STYLE_MODEL)).toEqual({ name: 'cell', label: 'Cell', reads: ['box', 'text', 'paragraph'], kind: 'paragraph', takes: ['paragraph'] })
    expect(cellSlot(null)).toBeUndefined()
  })

  it('has no slot switcher: one style fills both slots', () => {
    const { host } = styling()
    expect(host.slots.map((s) => s.name)).toEqual(['cell'])
    expect(host.slot?.name).toBe('cell')
  })
})

describe('the cells as a style host', () => {
  it('reports the active cell’s style and names the cells', () => {
    const { host } = styling()
    expect(host.current?.id).toBe('input')
    expect(host.noun).toBe('cell')
    expect(host.title).toBe('Cells B2:D3')
    expect(host.these).toBe('These 6 cells only')
    expect(styling({ area: [1, 1, 1, 1] }).host.these).toBe('This cell only')
    expect(styling({ area: [1, 1, 1, 1] }).host.title).toBe('Cell B2')
  })

  it('says where the look comes from', () => {
    const { host } = styling({ anchor: { row: 1, col: 3 } })
    expect(host.origin).toEqual(['Input — these cells’ own style, box and words', 'Under it: column D is Note; the sheet is Body text'])
  })

  it('offers vertical alignment and wrapping, the two box properties only a cell has', () => {
    expect(styling().host.extras).toEqual(['vertical-align', 'white-space'])
  })

  it('puts a style into both slots of the selected cells', async () => {
    const { host, calls } = styling()
    expect(await host.apply('note')).toBe(true)
    expect(calls.applyStyle).toEqual([[{ sheet: 's1', range: [1, 1, 2, 3] }], 'note'])
  })

  it('deviates the selected cells in both slots, or only in their box', async () => {
    const { host, calls } = styling()
    await host.deviate({ set: { color: '@attention' } })
    expect(calls.deviateStyle).toEqual(['input', [{ sheet: 's1', range: [1, 1, 2, 3] }], undefined, { set: { color: '@attention' } }])
    host.narrow!.set(true)
    expect(host.narrow!.on).toBe(true)
    await host.deviate({ set: { 'background-color': '@attention/14' } })
    expect(calls.deviateStyle).toEqual(['input', [{ sheet: 's1', range: [1, 1, 2, 3] }], 'box', { set: { 'background-color': '@attention/14' } }])
  })

  it('deviates the box from the box’s own style once the slots differ', async () => {
    const ranges = () => [R('box', [1, 1, 2, 3], 'note'), R('words', [1, 1, 2, 3], 'input')]
    const { host, calls } = styling({ ranges })
    expect(host.current?.id).toBe('input') // the words: what the cells read as
    host.narrow!.set(true)
    expect(host.current?.id).toBe('note') // "only their box": the box is what changes
    expect(host.slot?.reads).toEqual(['box']) // and only what a box reads is shown
    await host.deviate({ set: { 'background-color': '#fff' } })
    expect(calls.deviateStyle![0]).toBe('note')
    expect(host.origin).toEqual(['Box Note · Words Input — the two slots now differ'])
  })

  it('clears the selected cells’ own style (D317)', async () => {
    const { host, calls } = styling()
    expect(await host.clear!()).toBe(true)
    expect(calls.clearCellStyle).toEqual(['s1', [1, 1, 2, 3]])
  })

  it('counts uses as the server does', () => {
    expect(styling().host.uses()).toEqual({ input: 2, note: 2 })
  })

  it('has nothing current with no cells selected (an object is), and refuses what needs cells', async () => {
    const { host } = styling({ area: null })
    expect(host.current).toBeUndefined()
    expect(await host.apply('note')).toBe(false)
    expect(await host.deviate({ set: { color: '#000' } })).toBe(false)
    expect(await host.clear!()).toBe(false)
  })
})

describe('the box controls only a cell has', () => {
  it('sets the vertical alignment and wrapping of the style', async () => {
    const { host, calls } = styling()
    const editor = new StyleEditor(host, true)
    editor.pick('input')
    await editor.setVertical('bottom')
    expect(calls.changeStyle).toEqual(['input', { set: { 'vertical-align': 'bottom' } }])
    await editor.setWrap(true)
    expect(calls.changeStyle).toEqual(['input', { set: { 'white-space': 'pre-wrap' } }])
    await editor.setWrap(false)
    expect(calls.changeStyle).toEqual(['input', { set: { 'white-space': 'nowrap' } }])
    expect(editor.vertical).toBe('middle')
    expect(editor.wraps).toBe(false)
  })
})

describe('alignment by content (D318)', () => {
  it('says which alignment a style really gives a cell, Body text’s own not counting', () => {
    const styles = [
      { ...view('body-text', 'Body text'), css: { 'text-align': 'left' } },
      { ...view('input', 'Input'), css: {} },
      { ...view('result', 'Result'), css: { 'text-align': 'right' } },
    ]
    const { host } = styling({ styles })
    expect(host.alignOf!('input')).toBeUndefined()
    expect(host.alignOf!('body-text')).toBeUndefined()
    expect(host.alignOf!('result')).toBe('right')
  })
})

describe('hyphenation (D912)', () => {
  it('sets whether the words of a style are hyphenated at line ends', async () => {
    const { host, calls } = styling()
    const editor = new StyleEditor(host, true)
    editor.pick('input')
    expect(editor.hyphenates).toBe(false)
    await editor.setHyphens(true)
    expect(calls.changeStyle).toEqual(['input', { set: { hyphens: 'auto' } }])
    await editor.setHyphens(false)
    expect(calls.changeStyle).toEqual(['input', { set: { hyphens: 'manual' } }])
  })
})
