// Printing a workbook (E6.19, D1001–D1009): the session's print setup and language, the bar's choices, the workbook as
// the layout library reads it, and the print source that lets the one preview print a sheet like a text or a deck.
import { describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { Session } from '~/lib/session'
import { STYLE_MODEL } from './style-model.fixture'
import { DEFAULT_PAGE } from '~/lib/print/setup'
import {
  CONTENTS,
  DEFAULT_SHEET_PRINT_DATA,
  SCALES,
  describeSheets,
  layoutPrint,
  scaleId,
  scaleOf,
  withScale,
  type SheetPrintData,
} from '~/lib/print/sheet'
import { chartSizes, loadForPrint, printedIds, sheetDocument, type SheetRequest } from '~/lib/print/sheet-document'
import { svgOfDataUrl } from '~/lib/print/chart-picture'
import { sheetSource, type PrintPages } from '~/lib/print/source'
import type { PrintAssets } from '~/lib/print/assets'

const layoutCalls = vi.hoisted(() => ({ sheets: [] as unknown[] }))
vi.mock('@claudia/layout', async (original) => {
  const real = await original<typeof import('@claudia/layout')>()
  return {
    ...real,
    layoutSheet: (doc: unknown, ...rest: unknown[]) => (
      layoutCalls.sheets.push([doc, ...rest]),
      { list: { version: 'x', pages: [{ width: 595276, height: 841890, items: [] }] }, geometry: { width: 595276, height: 841890, margin: {} }, notes: [], embedded: new Map(), images: [], pageMap: [] }
    ),
    sheetFontsNeeded: () => ['sheet-font'],
  }
})

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'plan',
  app: 'computes',
  line: 'main',
  revision: 'main:3',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  lines: [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  welcome = WELCOME
  async connect() {
    return this.welcome
  }
  async request(method: string, params: any = {}) {
    this.calls.push({ method, params })
    const handler = this.handlers[method]
    if (!handler) throw new ProtocolError('unknown_method', method)
    return handler(params)
  }
  onEvent(h: EventHandler) {
    this.events.push(h)
  }
  onClose(_h: CloseHandler) {}
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  last(method: string) {
    return this.calls.filter((c) => c.method === method).at(-1)?.params
  }
}

const PAGE = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait', margins: [70866, 70866, 70866, 70866], page_numbers: false }
const LANDSCAPE: SheetPrintData = { ...DEFAULT_SHEET_PRINT_DATA, orientation: 'landscape' }
const style = (id: string, css: Record<string, string>, extra: object = {}) => ({ id, name: id, purpose: '', based_on: null, css, computed: css, resolved: css, to_name: false, kind: 'paragraph', ...extra })
const OBJECT = (id: string, extra: object = {}) => ({
  id, kind: 'image', w: 120, h: 80, style: 'plain-image', paragraph: null, shape: null, image: 'pic', imported: null, diagram: null, rendered: null, rotation: 0, snap: true, description: 'a picture', decorative: false,
  anchor: { kind: 'cell', container: 's1', row: 2, col: 1 }, ...extra,
})
const CELLS: Record<string, [number, number, any]> = {
  a: [0, 0, { t: 'text', v: 'Item' }],
  b: [1, 0, { t: 'text', v: 'Rent' }],
  c: [1, 1, { t: 'float', v: 1234.5 }],
  d: [1, 2, { t: 'int', v: -3 }],
}
const FORMATS = [{ id: 'money', name: 'Money', code: '#,##0.00 "€";[Red]-#,##0', to_name: false }]
const RANGES = [
  { slot: 'words', layer: 'column', area: [0, 1, 1048575, 1], style: 'money-words' },
  { slot: 'words', layer: 'column', area: [0, 2, 1048575, 2], style: 'money-words' },
  { slot: 'box', layer: 'row', area: [0, 0, 0, 16383], style: 'head-box' },
]

function server(link: FakeLink, extra: Record<string, (p: any) => any> = {}) {
  link.handlers = {
    sheets: () => [{ id: 's1', name: 'Budget', rows: 2, cols: 3 }, { id: 's2', name: 'Plan', rows: 0, cols: 0 }],
    images: () => [{ id: 'pic', format: 'gif', width: 20, height: 10, animated: false, data: 'AA==', first_frame: null }],
    styles: () => [
      style('body-text', { 'font-family': 'Inter', 'font-size': '14px', color: '#111' }),
      style('money-words', { 'font-weight': 'bold' }, { based_on: 'body-text', number_format: 'money', resolved: { 'font-family': 'Inter', 'font-size': '14px', color: '#111', 'font-weight': 'bold' } }),
      style('head-box', { background: '#eee' }, { based_on: 'body-text', kind: 'box', resolved: { background: '#eee', 'font-size': '14px' } }),
    ],
    style_model: () => ({ ...STYLE_MODEL, facets: { box: ['background', 'border', 'padding'], text: ['font-family', 'font-size', 'font-weight', 'color'] } }),
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    objects: (p: any) => ({ revision: 'main:3', sheet: p.sheet, objects: p.sheet === 's1' ? [OBJECT('o1'), OBJECT('o2', { kind: 'diagram', image: null, diagram: 'd1', w: 300, h: 200 })] : [] }),
    diagrams: () => [{ id: 'd1', format: 1, kind: 'bar' }],
    charts: () => [{ id: 'c1', name: 'Rent chart', spec_id: 'd1' }],
    names: () => ({ revision: 'main:3', names: [{ name: 'Rents', scope: null, kind: 'range', purpose: 'input', column_purposes: [], sheet: 's1', sheet_name: 'Budget', region: { sheet: 's1', row0: 1, col0: 1, row1: 1, col1: 1 } }] }),
    random_state: () => ({ seed: 0, draw: 0 }),
    number_formats: () => FORMATS,
    log: () => [], chat_log: () => [], checkpoints: () => [], presence: () => ({}), lock: () => ({}), unlock: () => ({}),
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    lines: () => [], restore_policy: () => ({ policy: 'consensus' }), ping: () => ({ revision: 'main:3', line: 'main' }),
    cells: (p: any) => ({ revision: 'main:3', cells: p.sheet === 's1' ? Object.values(CELLS).filter(([r, c]) => r >= p.row0 && r <= p.row1 && c >= p.col0 && c <= p.col1) : [] }),
    sizes: () => ({ revision: 'main:3', rows: [[0, 40]], cols: [[0, 150]] }),
    cell_styles: () => ({ revision: 'main:3', ranges: RANGES }),
    print_setup: () => ({ revision: 'main:3', page: PAGE, sheets: { s1: LANDSCAPE, s2: DEFAULT_SHEET_PRINT_DATA, c1: { ...DEFAULT_SHEET_PRINT_DATA, orientation: 'landscape' } } }),
    language: () => ({ language: 'de' }),
    set_print_page: () => ({ revision: 'main:4' }),
    set_sheet_print: () => ({ revision: 'main:4' }),
    set_language: () => ({ revision: 'main:4' }),
    ...extra,
  }
}

async function opened(extra: Record<string, (p: any) => any> = {}) {
  const link = new FakeLink()
  server(link, extra)
  const session = new Session(() => link, { retryDelays: [0], storage: { getItem: () => null, setItem: () => {} } })
  await session.open()
  return { link, session }
}

const shown = (id = 's1', kind: 'sheet' | 'chart' = 'sheet') => ({ kind, id })
const ask = (contents: SheetRequest['contents'], at = shown(), selection: SheetRequest['selection'] = null): SheetRequest => ({ contents, shown: at, selection })

// ------------------------------------------------------------------------------ the session
describe('the print setup of a workbook', () => {
  it('is read when the document opens, with the language', async () => {
    const { session } = await opened()
    expect(session.state.printPage).toEqual(PAGE)
    expect(session.state.sheetPrint.s1!.orientation).toBe('landscape')
    expect(session.state.language).toBe('de')
  })

  it('is absent, not guessed, on a server from before printing', async () => {
    const { session } = await opened({ print_setup: () => { throw new ProtocolError('unknown_method', 'print_setup') }, language: () => { throw new ProtocolError('unknown_method', 'language') } })
    expect(session.state.printPage).toBeNull()
    expect(session.state.sheetPrint).toEqual({})
    expect(session.state.language).toBeUndefined()
  })

  it('follows what other people change, and says what a sheet nobody set up prints like', async () => {
    const { session, link } = await opened()
    link.push('print_setup', { type: 'print_setup', page: { ...PAGE, paper: 'letter' } })
    link.push('print_setup', { type: 'print_setup', sheet: 's2', setup: { ...DEFAULT_SHEET_PRINT_DATA, gridlines: true } })
    link.push('language', { type: 'language', language: null })
    expect(session.state.printPage!.paper).toBe('letter')
    expect(session.state.sheetPrint.s2!.gridlines).toBe(true)
    expect(session.state.language).toBeNull()
  })

  it('is changed with the server\'s methods, against the revision the person saw', async () => {
    const { session, link } = await opened()
    expect(await session.setPrintPage({ ...PAGE, page_numbers: true })).toBe(true)
    expect(link.last('set_print_page')).toEqual({ page: { ...PAGE, page_numbers: true }, base: 'main:3' })
    expect(await session.setSheetPrint('s1', DEFAULT_SHEET_PRINT_DATA)).toBe(true)
    expect(link.last('set_sheet_print')).toEqual({ sheet: 's1', setup: DEFAULT_SHEET_PRINT_DATA, base: 'main:3' })
    expect(await session.setLanguage('en-GB')).toBe(true)
    expect(link.last('set_language')).toEqual({ language: 'en-GB', base: 'main:3' })
  })
})

// ------------------------------------------------------------------------------ the bar's choices
describe('the choices of the bar', () => {
  it('fit to width is the default scale, and a percentage the setup holds is listed even if the bar does not offer it', () => {
    expect(SCALES[0]!.scale).toEqual({ kind: 'fit-width' })
    expect(DEFAULT_SHEET_PRINT_DATA.scale).toEqual({ kind: 'fit-width' })
    expect(scaleId({ kind: 'percent', percent: 80 })).toBe('percent-80')
    expect(scaleOf('percent-80')).toEqual({ kind: 'percent', percent: 80 })
    expect(scaleOf('percent-85')).toEqual({ kind: 'percent', percent: 85 })
    expect(scaleOf('fit-page')).toEqual({ kind: 'fit-page' })
    expect(scaleOf('huge')).toBeNull()
    expect(withScale(DEFAULT_SHEET_PRINT_DATA, 'percent-70').scale).toEqual({ kind: 'percent', percent: 70 })
    expect(withScale(DEFAULT_SHEET_PRINT_DATA, 'huge')).toBe(DEFAULT_SHEET_PRINT_DATA)
  })

  it('offers the sheet, the selection and the whole workbook', () => {
    expect(CONTENTS.map((c) => c.value)).toEqual(['sheet', 'selection', 'workbook'])
  })

  it('gives the layout library its own words for a stored setup', () => {
    const stored: SheetPrintData = { ...DEFAULT_SHEET_PRINT_DATA, repeat_rows: [0, 1], footer_name: false, skip_empty: false, scale: { kind: 'percent', percent: 80 } }
    expect(layoutPrint(stored)).toMatchObject({ repeatRows: [0, 1], repeatCols: null, footerName: false, skipEmpty: false, scale: { kind: 'percent', percent: 80 }, orientation: 'portrait', order: 'down-then-across' })
  })

  it('says what the pages are in a line', () => {
    expect(describeSheets(3, 1, 'Budget', 'A4', 'portrait')).toBe('3 pages · Budget · A4 portrait')
    expect(describeSheets(1, 2, 'Budget', 'A4', null)).toBe('1 page · 2 sheets · A4')
  })

  it('reads a chart\'s SVG out of the data URL Plotly makes', () => {
    expect(svgOfDataUrl('data:image/svg+xml,%3Csvg%20a%3D%221%22%2F%3E')).toBe('<svg a="1"/>')
    expect(svgOfDataUrl(`data:image/svg+xml;base64,${btoa('<svg/>')}`)).toBe('<svg/>')
    expect(svgOfDataUrl('data:image/png;base64,AA==')).toBeNull()
    expect(svgOfDataUrl('data:image/svg+xml,%E0%A4%A')).toBeNull()
  })
})

// ------------------------------------------------------------------------------ the workbook for the layout library
describe('the workbook as the layout library reads it', () => {
  it('prints the sheet that is shown, or the selection of it, or every sheet and chart tab in tab order', async () => {
    const { session } = await opened()
    expect(printedIds(session, ask('sheet'))).toEqual([shown()])
    expect(printedIds(session, ask('sheet', shown('c1', 'chart')))).toEqual([shown('c1', 'chart')])
    expect(printedIds(session, ask('sheet', shown('gone')))).toEqual([])
    expect(printedIds(session, ask('workbook'))).toEqual([shown('s1'), shown('s2'), shown('c1', 'chart')])
  })

  it('shows cells the way the grid does: through their number formats, aligned, in the colour the format asks for', async () => {
    const { session } = await opened()
    await loadForPrint(session, ask('sheet'))
    const doc = sheetDocument(session, ask('sheet'))
    const sheet = doc.sheets[0]!
    expect(sheet.kind).toBe('sheet')
    if (sheet.kind !== 'sheet') return
    const at = (row: number, col: number) => sheet.cells.find((c) => c.row === row && c.col === col)
    expect(at(0, 0)).toMatchObject({ text: 'Item', align: 'left' })
    expect(at(1, 0)).toMatchObject({ text: 'Rent', align: 'left' })
    expect(at(1, 1)).toMatchObject({ align: 'right' })
    expect(at(1, 1)!.text).toContain('1,234.50') // the money format; a cell of the money column
    expect(at(1, 2)!.text).toBe('-3') // [Red]-#,##0
    // the red of the format is a style of its own, so the layout library needs no notion of colours
    const red = doc.styles.find((s) => s.id === at(1, 2)!.style)
    expect(red?.resolved.color).toBeTruthy()
    expect(red?.resolved.color).not.toBe('#111')
    expect(at(1, 1)!.style).not.toBe(at(1, 2)!.style)
  })

  it('merges the two styles of a cell, the box and the words, into the one the layout library draws', async () => {
    const { session } = await opened()
    await loadForPrint(session, ask('sheet'))
    const doc = sheetDocument(session, ask('sheet'))
    const sheet = doc.sheets[0]!
    if (sheet.kind !== 'sheet') throw new Error('a sheet')
    const head = sheet.cells.find((c) => c.row === 0 && c.col === 0)!
    const merged = doc.styles.find((s) => s.id === head.style)!
    expect(merged.based_on).toBeNull()
    expect(merged.resolved.background).toBe('#eee') // from the box
    expect(doc.styles.some((s) => s.id === 'body-text')).toBe(true) // the document's own styles come along
    // a cell with no style of its own has none here: the layout library gives it Body text
    expect(sheet.cells.find((c) => c.row === 1 && c.col === 0)!.style).toBeUndefined()
  })

  it('carries the sizes of rows and columns, the setup of the sheet and its floating things', async () => {
    const { session } = await opened()
    await loadForPrint(session, ask('sheet'))
    const doc = sheetDocument(session, ask('sheet'), new Map([['d1', '<svg/>']]))
    const sheet = doc.sheets[0]!
    if (sheet.kind !== 'sheet') throw new Error('a sheet')
    expect(sheet.colWidths).toEqual([[0, 150]])
    expect(sheet.rowHeights).toEqual([[0, 40]])
    expect(sheet.print.orientation).toBe('landscape')
    expect(sheet.area).toBeNull()
    expect(sheet.objects.map((o) => [o.id, o.kind, o.image, o.anchor])).toEqual([
      ['o1', 'image', 'pic', { kind: 'cell', row: 2, col: 1 }],
      ['o2', 'diagram', 'chart:d1', { kind: 'cell', row: 2, col: 1 }],
    ])
    expect(doc.images.find((i) => i.id === 'chart:d1')).toEqual({ id: 'chart:d1', format: 'svg', svg: '<svg/>' })
    expect(doc.images.find((i) => i.id === 'pic')).toEqual({ id: 'pic', format: 'gif' })
    expect(doc.page).toEqual(PAGE)
    expect(doc.language).toBe('de')
  })

  it('leaves a chart that has no picture without an image, so the layout library can say so', async () => {
    const { session } = await opened()
    const doc = sheetDocument(session, ask('workbook'))
    const sheet = doc.sheets[0]!
    if (sheet.kind !== 'sheet') throw new Error('a sheet')
    expect(sheet.objects.find((o) => o.id === 'o2')!.image).toBeNull()
    expect(doc.sheets[2]).toMatchObject({ kind: 'chart', id: 'c1', name: 'Rent chart', image: null, orientation: 'landscape' })
  })

  it('prints a chart tab as one page of its own, and the picture of it when there is one', async () => {
    const { session } = await opened()
    const doc = sheetDocument(session, ask('sheet', shown('c1', 'chart')), new Map([['d1', '<svg/>']]))
    expect(doc.sheets).toEqual([{ kind: 'chart', id: 'c1', name: 'Rent chart', image: 'chart:d1', w: 640, h: 400, orientation: 'landscape' }])
  })

  it('knows which charts it needs and how big to draw them', async () => {
    const { session } = await opened()
    expect(chartSizes(session, ask('sheet'))).toEqual(new Map([['d1', [300, 200]]]))
    expect(chartSizes(session, ask('sheet', shown('c1', 'chart')))).toEqual(new Map([['d1', [640, 400]]]))
    expect(chartSizes(session, ask('sheet', shown('s2')))).toEqual(new Map())
  })

  it('prints only the selection when asked, as a rectangle of the shown sheet whatever way it was dragged', async () => {
    const { session } = await opened()
    await loadForPrint(session, ask('selection'))
    const doc = sheetDocument(session, ask('selection', shown(), [1, 2, 0, 0]))
    const sheet = doc.sheets[0]!
    if (sheet.kind !== 'sheet') throw new Error('a sheet')
    expect(sheet.area).toEqual({ row0: 0, col0: 0, row1: 1, col1: 2 })
    // …but a workbook is printed whole even if a selection is held
    const whole = sheetDocument(session, ask('workbook', shown(), [1, 2, 0, 0]))
    expect(whole.sheets.map((s) => (s.kind === 'sheet' ? s.area : 'chart'))).toEqual([null, null, 'chart'])
  })

  it('tints cells by purpose only where the sheet asks for it (D1005)', async () => {
    const { session } = await opened()
    await loadForPrint(session, ask('sheet'))
    const plain = sheetDocument(session, ask('sheet')).sheets[0]!
    if (plain.kind !== 'sheet') throw new Error('a sheet')
    expect(plain.cells.every((c) => c.purpose === undefined)).toBe(true)
    session.state.sheetPrint.s1 = { ...LANDSCAPE, purposes: true }
    const tinted = sheetDocument(session, ask('sheet')).sheets[0]!
    if (tinted.kind !== 'sheet') throw new Error('a sheet')
    expect(tinted.cells.find((c) => c.row === 1 && c.col === 1)!.purpose).toBe('input')
    expect(tinted.cells.find((c) => c.row === 0 && c.col === 0)!.purpose).toBeUndefined()
  })

  it('loads the cells, sizes and styles of the sheets it prints once, and nothing of the others', async () => {
    const { session, link } = await opened()
    await loadForPrint(session, ask('sheet'))
    expect(link.calls.filter((c) => c.method === 'cells').every((c) => c.params.sheet === 's1')).toBe(true)
    expect(link.last('sizes')).toEqual({ sheet: 's1' })
    await loadForPrint(session, ask('sheet'))
    expect(link.calls.filter((c) => c.method === 'sizes')).toHaveLength(1)
  })
})

// ------------------------------------------------------------------------------ the print source
describe('the print source of a workbook', () => {
  const at = reactive({ shown: shown(), selection: null as SheetRequest['selection'] })
  const make = async (extra: Record<string, (p: any) => any> = {}) => {
    const { session, link } = await opened(extra)
    at.shown = shown()
    at.selection = null
    const charts = vi.fn(async (_spec: string, _w: number, _h: number): Promise<string | null> => '<svg/>')
    const source = sheetSource(session, { shown: () => at.shown, selection: () => at.selection, charts })
    return { session, link, source, charts }
  }
  const assets = { ensure: vi.fn(async () => {}), fonts: {}, resolver: {}, hyphenator: vi.fn() } as unknown as PrintAssets

  it('prints on the workbook\'s page and says "the sheets" when the person goes back', async () => {
    const { source } = await make()
    expect(source.back).toBe('the sheets')
    expect(source.page()).toEqual(PAGE)
    expect(source.title()).toBe('plan')
    expect(source.canChange()).toBe(true)
    expect(source.language()).toBe('de')
    expect(source.producer).toBe('claudia computes')
    expect(source.layouts).toEqual([])
    expect(source.layout()).toBeNull()
  })

  it('does not change anything for a viewer or on an old server', async () => {
    const viewer = await make()
    viewer.session.state.me.role = 'viewer'
    expect(viewer.source.canChange()).toBe(false)
    expect(viewer.source.canSetLanguage()).toBe(false)
    const old = await make({ print_setup: () => { throw new ProtocolError('unknown_method', 'print_setup') } })
    expect(old.source.canChange()).toBe(false)
    expect(old.source.page()).toEqual(DEFAULT_PAGE)
  })

  it('changes the page for the workbook but the orientation and the scale for the sheet that is shown', async () => {
    const { source, link } = await make()
    source.setPage({ ...PAGE, paper: 'letter' })
    expect(link.last('set_print_page').page.paper).toBe('letter')
    expect(source.orientation!.value()).toBe('landscape')
    source.orientation!.set('portrait')
    expect(link.last('set_sheet_print')).toMatchObject({ sheet: 's1', setup: { orientation: 'portrait' } })
    expect(source.scale!.value()).toBe('fit-width')
    source.scale!.set('percent-80')
    expect(link.last('set_sheet_print')).toMatchObject({ sheet: 's1', setup: { scale: { kind: 'percent', percent: 80 }, orientation: 'landscape' } })
    at.shown = shown('c1', 'chart')
    source.orientation!.set('portrait')
    expect(link.last('set_sheet_print').sheet).toBe('c1')
  })

  it('offers the selection only when more than a cell is selected, and a scale only for what has one', async () => {
    const { source } = await make()
    const contents = source.contents!
    expect(contents.options.map((o) => o.value)).toEqual(['sheet', 'selection', 'workbook'])
    expect(contents.value()).toBe('sheet')
    expect(contents.enabled!('selection')).toBe(false)
    at.selection = [0, 0, 1, 1]
    expect(contents.enabled!('selection')).toBe(true)
    at.selection = [1, 1, 1, 1]
    expect(contents.enabled!('selection')).toBe(false)
    expect(contents.enabled!('workbook')).toBe(true)
    at.shown = shown('c1', 'chart')
    at.selection = [0, 0, 3, 3]
    expect(contents.enabled!('selection')).toBe(false) // a chart tab has no cells to select
    expect(source.scale!.enabled!('fit-width')).toBe(false) // …and no scale: it fills the page (D1008)
    contents.set('workbook')
    expect(source.scale!.enabled!('fit-width')).toBe(true)
  })

  it('lays out what the preview asks for, with the pictures of its charts, and counts the sheets for the status line', async () => {
    const { source, charts } = await make()
    layoutCalls.sheets.length = 0
    source.contents!.set('workbook')
    const pages: PrintPages = await source.layOut(assets)
    const [doc] = layoutCalls.sheets[0] as [import('@claudia/layout').SheetDocument]
    expect(doc.sheets.map((s) => s.id)).toEqual(['s1', 's2', 'c1'])
    expect(charts).toHaveBeenCalledTimes(1) // one definition, the floating chart and the tab share its picture
    expect(charts).toHaveBeenCalledWith('d1', 300, 200)
    expect(doc.images.some((i) => i.id === 'chart:d1')).toBe(true)
    expect(pages.printed).toEqual({ sheets: 3, name: 'Budget', orientation: null })
    expect(source.status(pages, PAGE as any)).toBe('1 page · 3 sheets · A4')
    source.contents!.set('sheet')
    const one = await source.layOut(assets)
    expect(one.printed).toEqual({ sheets: 1, name: 'Budget', orientation: 'landscape' })
    expect(source.status(one, PAGE as any)).toBe('1 page · Budget · A4 landscape')
  })

  it('draws a chart again only when the document has moved on, and prints without it when none can be drawn', async () => {
    const { source, session, charts } = await make()
    await source.layOut(assets)
    await source.layOut(assets)
    expect(charts).toHaveBeenCalledTimes(1)
    session.state.revision = 'main:9'
    await source.layOut(assets)
    expect(charts).toHaveBeenCalledTimes(2)
    charts.mockResolvedValue(null)
    session.state.revision = 'main:10'
    layoutCalls.sheets.length = 0
    await source.layOut(assets)
    const [doc] = layoutCalls.sheets[0] as [import('@claudia/layout').SheetDocument]
    expect(doc.images.some((i) => i.id === 'chart:d1')).toBe(false)
  })

  it('tells the preview what to watch: the choices and the revision, never every cell', async () => {
    const { source, session } = await make()
    const before = JSON.stringify(source.watched())
    source.contents!.set('workbook')
    expect(JSON.stringify(source.watched())).not.toBe(before)
    session.state.revision = 'main:12'
    expect(JSON.stringify(source.watched())).not.toBe(before)
  })
})
