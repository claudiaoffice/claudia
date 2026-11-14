// Printing a presentation (D917, D918): the slide session's print setup and language, the bar's choices for slides,
// and the print sources that let one preview print a text and a presentation alike.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import type { PrintSetupData } from '@claudia/layout'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { SlideSession } from '~/lib/slide-session'
import type { TextSession } from '~/lib/text-session'
import {
  DEFAULT_PAGE,
  DEFAULT_PRINT,
  LAYOUTS,
  MARGINS,
  NO_MARGIN,
  SLIDE_PAPERS,
  TEXT_PAPERS,
  describe as describePage,
  marginPreset,
  withLayout,
  withSlidePaper,
} from '~/lib/print/setup'
import { pdfOfPages, slideDocument, slideSource, textSource, type PrintPages } from '~/lib/print/source'
import { usePrint } from '~/lib/print/use-print'
import type { PrintAssets } from '~/lib/print/assets'

const layoutCalls = vi.hoisted(() => ({ slides: [] as unknown[], text: [] as unknown[], pdf: [] as unknown[] }))
vi.mock('@claudia/layout', async (original) => {
  const real = await original<typeof import('@claudia/layout')>()
  const pages = (slides?: number) => ({ list: { version: 'x', pages: [{ width: 1, height: 1, items: [] }] }, geometry: {}, notes: [], embedded: new Map(), images: [], ...(slides === undefined ? {} : { slides, perPage: 1 }) })
  return {
    ...real,
    layoutSlides: (doc: unknown, ...rest: unknown[]) => (layoutCalls.slides.push([doc, ...rest]), pages(3)),
    layoutText: (doc: unknown, ...rest: unknown[]) => (layoutCalls.text.push([doc, ...rest]), pages()),
    slideFontsNeeded: () => ['slide-font'],
    fontsNeeded: () => ['text-font'],
    writePdf: (...args: unknown[]) => (layoutCalls.pdf.push(args), new Uint8Array([37])),
  }
})

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'talk',
  app: 'creates',
  line: 'main',
  revision: 'main:0',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  lines: [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  async connect() {
    return WELCOME
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
  onClose(h: CloseHandler) {
    this.closers.push(h)
  }
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  sent(method: string) {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }
}

const STYLE = { id: 'body-text', name: 'Body text', purpose: '', based_on: null, to_name: false, kind: 'paragraph', css: {}, computed: {}, resolved: { color: '#1f1a33' } }
const SVG = { id: 'v'.repeat(64), format: 'svg', width: 10, height: 10, animated: false, data: btoa('<svg/>'), first_frame: null }
const PNG = { id: 'p'.repeat(64), format: 'png', width: 10, height: 10, animated: false, data: 'iVBO', first_frame: null }
const box = (id: string, slide: string) => ({ id, kind: 'text', w: 400, h: 100, style: 'plain-box', paragraph: { style: 'body-text', text: id, runs: [] }, shape: null, image: null, imported: null, rotation: 0, snap: true, anchor: { kind: 'slide', container: slide, x: 0, y: 0 } })
const HANDOUTS: PrintSetupData = { layout: 'handouts-6', page: { ...DEFAULT_PAGE, margins: [36000, 36000, 36000, 36000] } }

function server(link: FakeLink, extra: Record<string, (params: any) => any> = {}) {
  link.handlers = {
    slides: () => [
      { id: 's1', objects: 1 },
      { id: 's2', objects: 1 },
    ],
    slide: ({ slide }) => ({ revision: 'main:0', slide, objects: [box(`${slide}-box`, slide)] }),
    shapes: () => ({ library: [], document: [] }),
    images: () => [SVG, PNG],
    styles: () => [STYLE],
    style_model: () => ({}),
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    lines: () => [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    presence: () => ({}),
    ...extra,
  }
}

async function opened(extra: Record<string, (params: any) => any> = {}) {
  const link = new FakeLink()
  server(link, extra)
  const session = new SlideSession(() => link, { retryDelays: [1] })
  await session.open()
  return { link, session, state: session.state }
}
const PRINTING = {
  print_setup: () => DEFAULT_PRINT,
  language: () => ({ language: 'de' }),
  set_print_setup: () => ({ revision: 'main:1' }),
  set_language: () => ({ revision: 'main:1' }),
}

afterEach(() => {
  layoutCalls.slides.length = 0
  layoutCalls.text.length = 0
  layoutCalls.pdf.length = 0
})

describe('a presentation knows how it prints (D917)', () => {
  it('loads its print setup and language, and follows them', async () => {
    const { link, state, session } = await opened(PRINTING)
    expect(state.printSetup).toEqual(DEFAULT_PRINT)
    expect(state.language).toBe('de')
    link.push('print_setup', { type: 'print_setup', setup: HANDOUTS })
    expect(state.printSetup).toEqual(HANDOUTS)
    link.push('language', { type: 'language', language: null })
    expect(state.language).toBeNull()
    session.close()
  })
  it('changes them in one step each; one who only looks cannot', async () => {
    const { link, session, state } = await opened(PRINTING)
    expect(await session.setPrintSetup(HANDOUTS)).toBe(true)
    expect(link.sent('set_print_setup').at(-1)).toMatchObject({ setup: HANDOUTS, base: 'main:0' })
    expect(await session.setLanguage('fr')).toBe(true)
    expect(link.sent('set_language').at(-1)).toMatchObject({ language: 'fr' })
    state.me.role = 'viewer'
    expect(await session.setPrintSetup(DEFAULT_PRINT)).toBe(false)
    expect(await session.setLanguage(null)).toBe(false)
    expect(link.sent('set_print_setup')).toHaveLength(1)
    session.close()
  })
  it('on a server that does not print slides, knows neither', async () => {
    const { state, session } = await opened()
    expect(state.printSetup).toBeNull()
    expect(state.language).toBeUndefined()
    session.close()
  })
})

describe('the bar for slides (D917, D918)', () => {
  it('offers the slide-sized paper to presentations only, first', () => {
    expect(SLIDE_PAPERS[0]!.id).toBe('slide')
    expect(TEXT_PAPERS.some((p) => p.id === 'slide')).toBe(false)
    expect(SLIDE_PAPERS.slice(1)).toEqual(TEXT_PAPERS)
  })
  it('lists the layouts, slides first', () => {
    expect(LAYOUTS.map((l) => l.value)).toEqual(['slides', 'handouts-2', 'handouts-3', 'handouts-4', 'handouts-6', 'handouts-9'])
  })
  it('moves handouts off the slide-sized paper to A4 portrait with narrow margins', () => {
    const next = withLayout(DEFAULT_PRINT, 'handouts-3')
    const m = MARGINS[0]!.mpt
    expect(next).toEqual({ layout: 'handouts-3', page: { ...DEFAULT_PRINT.page, paper: 'a4', width: 595276, height: 841890, orientation: 'portrait', margins: [m, m, m, m] } })
    expect(withLayout(next, 'handouts-3')).toBe(next)
    // on any other paper, the page stays; slides lie landscape
    expect(withLayout(next, 'handouts-9').page).toEqual(next.page)
    expect(withLayout(next, 'slides')).toEqual({ layout: 'slides', page: { ...next.page, orientation: 'landscape' } })
  })
  it('makes the slide-sized paper the slide itself: landscape, no margins', () => {
    expect(withSlidePaper(DEFAULT_PAGE)).toEqual(DEFAULT_PRINT.page)
    expect(marginPreset(DEFAULT_PRINT.page, [NO_MARGIN, ...MARGINS])).toBe('none')
    expect(marginPreset(DEFAULT_PRINT.page)).toBeNull()
  })
  it('counts the slides in the status line', () => {
    expect(describePage(DEFAULT_PAGE, 2, 7)).toBe('7 slides on 2 pages · A4 portrait')
    expect(describePage(DEFAULT_PRINT.page, 1, 1)).toBe('1 slide on 1 page · Slide size landscape')
  })
})

function fakeAssets() {
  return {
    hyphenator: vi.fn(async (language: string | null | undefined) => (language ? ({ language } as never) : null)),
    ensure: vi.fn(async () => {}),
    fonts: { fonts: true },
    resolver: { resolver: true },
  } as unknown as PrintAssets & { hyphenator: ReturnType<typeof vi.fn>; ensure: ReturnType<typeof vi.fn> }
}

describe('printing a presentation: its print source', () => {
  it('hands the layout library the slides in order, the styles and the pictures (an SVG one as its text)', async () => {
    const { session } = await opened(PRINTING)
    const doc = slideDocument(session)
    expect(doc.slides.map((s) => [s.id, s.objects.map((o) => o.id)])).toEqual([
      ['s1', ['s1-box']],
      ['s2', ['s2-box']],
    ])
    expect(doc.styles).toEqual([{ id: 'body-text', based_on: null, resolved: { color: '#1f1a33' } }])
    expect(doc.images).toEqual([
      { id: SVG.id, format: 'svg', svg: '<svg/>' },
      { id: PNG.id, format: 'png' },
    ])
    expect(doc).toMatchObject({ print: DEFAULT_PRINT, language: 'de' })
    session.close()
  })
  it('prints a rendered text container as the picture it shows, and leaves out one nothing has drawn yet (D390)', async () => {
    const rendered = (id: string, image: string | null) => ({ ...box(id, 's1'), kind: 'rendered', paragraph: null, rendered: 'r1', image })
    const { session } = await opened({
      ...PRINTING,
      slide: ({ slide }) => ({ revision: 'main:0', slide, objects: slide === 's1' ? [rendered('drawn', PNG.id), rendered('pending', null)] : [] }),
    })
    const [first] = slideDocument(session).slides
    expect(first!.objects.map((o) => [o.id, o.kind, o.image])).toEqual([['drawn', 'image', PNG.id]])
    session.close()
  })
  it('reads and changes the print setup through the session', async () => {
    const { link, session, state } = await opened(PRINTING)
    const source = slideSource(session)
    expect(source.title()).toBe('talk')
    expect(source.back).toBe('the slides')
    expect(source.canChange()).toBe(true)
    expect(source.layout()).toBe('slides')
    expect(source.margins[0]).toBe(NO_MARGIN)
    expect(source.papers).toBe(SLIDE_PAPERS)
    source.setLayout('handouts-6')
    expect(link.sent('set_print_setup').at(-1)!.setup).toEqual(withLayout(DEFAULT_PRINT, 'handouts-6'))
    source.setPage({ ...DEFAULT_PRINT.page, page_numbers: true })
    expect(link.sent('set_print_setup').at(-1)!.setup).toEqual({ layout: 'slides', page: { ...DEFAULT_PRINT.page, page_numbers: true } })
    expect(source.withPaper!(DEFAULT_PAGE, 'slide')).toEqual(DEFAULT_PRINT.page)
    expect(source.withPaper!(DEFAULT_PAGE, 'a4')).toBeNull()
    source.setLanguage('it')
    expect(link.sent('set_language').at(-1)).toMatchObject({ language: 'it' })
    expect(source.language()).toBe('de')
    expect(source.canSetLanguage()).toBe(true)
    expect(source.images().map((i) => i.id)).toEqual([SVG.id, PNG.id])
    await source.prepare()
    state.me.role = 'viewer'
    expect(source.canChange()).toBe(false)
    expect(source.canSetLanguage()).toBe(false)
    session.close()
  })
  it('cannot change printing on a server that does not know it, and prints slide-sized meanwhile', async () => {
    const { session } = await opened()
    const source = slideSource(session)
    expect(source.canChange()).toBe(false)
    expect(source.page()).toEqual(DEFAULT_PRINT.page)
    expect(source.canSetLanguage()).toBe(false)
    session.close()
  })
  it('fetches the fonts and the patterns the slides need, then lays them out', async () => {
    const { session } = await opened(PRINTING)
    const source = slideSource(session)
    const assets = fakeAssets()
    const pages = await source.layOut(assets)
    expect(assets.ensure).toHaveBeenCalledWith(['slide-font'])
    expect(assets.hyphenator).toHaveBeenCalledWith('de')
    const [doc, fonts, resolver, options] = layoutCalls.slides[0] as unknown[]
    expect((doc as { slides: unknown[] }).slides).toHaveLength(2)
    expect([fonts, resolver]).toEqual([assets.fonts, assets.resolver])
    expect(options).toEqual({ hyphenator: { language: 'de' } })
    expect(source.status(pages, DEFAULT_PRINT.page)).toBe('3 slides on 1 page · Slide size landscape')
    pdfOfPages(assets, pages, new Map(), source)
    expect(layoutCalls.pdf[0]).toMatchObject([pages.list.pages, assets.fonts, expect.any(Function), { title: 'talk', lang: 'de', producer: 'claudia creates' }])
    session.close()
  })
  it('watches everything the pages are drawn from', async () => {
    const { link, session } = await opened(PRINTING)
    const source = slideSource(session)
    const before = JSON.stringify(source.watched())
    link.push('print_setup', { type: 'print_setup', setup: HANDOUTS })
    expect(JSON.stringify(source.watched())).not.toBe(before)
    session.close()
  })
})

describe('printing a text: its print source', () => {
  function textSession(over: Partial<Record<string, unknown>> = {}) {
    const state = reactive({ doc: 'essay', blocks: [{ id: 'b1', style: 'body', text: 'Hi', runs: [] }], styles: [], page: DEFAULT_PAGE, language: null as string | null | undefined, ...over })
    const session = {
      state,
      readOnly: false,
      setPage: vi.fn(),
      setLanguage: vi.fn(),
      printExtras: vi.fn(async () => ({ objects: [], shapes: [], images: [PNG] })),
    }
    return session as unknown as TextSession & typeof session
  }
  it('offers no layouts and no slide-sized paper, and changes the page and the language through the session', async () => {
    const session = textSession()
    const source = textSource(session)
    expect([source.layouts, source.layout(), source.papers, source.margins, source.back]).toEqual([[], null, TEXT_PAPERS, MARGINS, 'the text'])
    source.setLayout('handouts-2') // nothing to change
    source.setPage({ ...DEFAULT_PAGE, orientation: 'landscape' })
    expect(session.setPage).toHaveBeenCalledWith({ ...DEFAULT_PAGE, orientation: 'landscape' })
    source.setLanguage('de')
    expect(session.setLanguage).toHaveBeenCalledWith('de')
    expect(source.canChange()).toBe(true)
    expect(source.canSetLanguage()).toBe(true)
    expect(source.title()).toBe('essay')
  })
  it('fetches the objects once, and lays the text out with them', async () => {
    const session = textSession({ language: 'en-GB' })
    const source = textSource(session)
    expect(source.images()).toEqual([])
    await source.prepare()
    expect(source.images()).toEqual([PNG])
    const assets = fakeAssets()
    const pages = await source.layOut(assets)
    expect(assets.ensure).toHaveBeenCalledWith(['text-font'])
    expect(assets.hyphenator).toHaveBeenCalledWith('en-GB')
    expect(source.status(pages, DEFAULT_PAGE)).toBe('1 page · A4 portrait')
    pdfOfPages(assets, pages, new Map(), source)
    expect(layoutCalls.pdf[0]).toMatchObject([pages.list.pages, assets.fonts, expect.any(Function), { title: 'essay', lang: 'en-GB', producer: 'claudia composes' }])
  })
  it('prints the text without its objects when they cannot be fetched', async () => {
    const session = textSession({ page: null, language: undefined, doc: '' })
    session.printExtras.mockRejectedValue(new Error('old server'))
    const source = textSource(session)
    await source.prepare()
    expect(source.images()).toEqual([])
    expect(source.canChange()).toBe(false)
    expect(source.canSetLanguage()).toBe(false)
    expect(source.page()).toBe(DEFAULT_PAGE)
    expect(source.title()).toBe('document')
    const pages: PrintPages = { list: { version: 'x', pages: [] }, geometry: {} as never, notes: [], embedded: new Map([['e', new Uint8Array([1])]]) }
    pdfOfPages(fakeAssets(), pages, new Map(), source)
    const [, , image, options] = layoutCalls.pdf[0] as [unknown, unknown, (id: string) => unknown, object]
    expect(image('e')).toEqual(new Uint8Array([1]))
    expect(options).not.toHaveProperty('lang')
  })
})

describe('what every window that prints has (D906, D918)', () => {
  it('opens the preview, prints from it once open, and goes back', () => {
    vi.useFakeTimers()
    const focus = vi.fn()
    const p = usePrint(focus)
    expect(p.shortcut).toMatchObject({ id: 'file.print', chord: { key: 'p', ctrl: true } })
    p.shortcut.run()
    expect(p.printing.value).toBe(true)
    const print = vi.fn(async () => {})
    p.preview.value = { print }
    p.open()
    expect(print).toHaveBeenCalledOnce()
    p.close()
    expect(p.printing.value).toBe(false)
    vi.runAllTimers()
    expect(focus).toHaveBeenCalledOnce()
    usePrint().close() // nothing to focus
    vi.useRealTimers()
  })
})
