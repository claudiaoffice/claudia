// What the print preview prints (D906, D918): one interface for every app that prints, so the preview — its bar, its
// zoom, Print… and Download PDF — is one component and looks and behaves the same in composes and creates. A source
// says what the document offers (papers, margins, layouts, a language), reads and changes its print setup as the
// session holds it, and lays the document out with the layout library's adapter for its app.
import { ref } from 'vue'
import {
  fontsNeeded,
  layoutSheet,
  layoutSlides,
  layoutText,
  PAPER_SIZES,
  sheetFontsNeeded,
  slideFontsNeeded,
  utf8Decode,
  writePdf,
  type DisplayList,
  type Note,
  type PageGeometry,
  type PageSetupData,
  type PaperSize,
  type SlideDocument,
  type SlideLayout,
  type SlideObject as LayoutSlideObject,
} from '@claudia/layout'
import type { PrintAssets } from './assets'
import { fromBase64, textDocument } from './document'
import { DEFAULT_PAGE, DEFAULT_PRINT, describe, LAYOUTS, MARGINS, mm, NO_MARGIN, SLIDE_PAPERS, TEXT_PAPERS, withLayout, withSlidePaper, type MarginChoice } from './setup'
import type { PrintExtras, TextSession } from '../text-session'
import type { SlideObject, SlideSession } from '../slide-session'
import type { Session } from '../session'
import { plotlyPictures } from './chart-picture'
import { chartSizes, loadForPrint, setupOf, sheetDocument, type ChartPictures, type SheetRequest } from './sheet-document'
import { CONTENTS, describeSheets, SCALES, scaleId, withScale, type Contents } from './sheet'

import { translate as t } from '../i18n'
/** A picture the document holds, as the server sends it: `data` is base64. */
export interface PrintImage {
  id: string
  format: string
  data: string
}

/** Pages ready to show and to write as a PDF, whichever app laid them out. */
export interface PrintPages {
  list: DisplayList
  geometry: PageGeometry
  notes: Note[]
  /** the bytes of pictures that SVG pictures carry inside them */
  embedded: Map<string, Uint8Array>
  /** a presentation's slide count, for the status line */
  slides?: number
  /** a workbook's sheets and chart tabs that were printed, for the status line */
  printed?: { sheets: number; name: string; orientation: 'portrait' | 'landscape' | null }
}

/** A choice the bar of the preview offers on top of the page: a list of options and the one that is chosen. */
export interface PrintChoice {
  readonly options: readonly { value: string; label: string }[]
  value(): string
  set(value: string): void
  /** whether the choice can be made at the moment (a selection needs cells selected, a chart tab has no scale) */
  enabled?(value: string): boolean
}

export interface PrintSource {
  /** what goes back from the preview: "the text", "the slides" */
  readonly back: string
  /** the document's name, for the PDF's title and file name */
  title(): string
  /** whether this person may change how the document prints (a viewer may not; an old server cannot) */
  canChange(): boolean
  page(): PageSetupData
  setPage(page: PageSetupData): void
  readonly papers: readonly PaperSize[]
  readonly margins: readonly MarginChoice[]
  /** the layouts offered, or none where the document has only one way to print */
  readonly layouts: readonly { value: SlideLayout; label: string }[]
  layout(): SlideLayout | null
  setLayout(layout: SlideLayout): void
  /** what a sheet prints: the sheet, the selection or the whole workbook (computes) */
  readonly contents?: PrintChoice
  /** how big the cells are drawn (computes) */
  readonly scale?: PrintChoice
  /** which way the page lies, where that is not a thing of the whole document: a workbook's sheets lie each their way
   * (D1004), so the bar's Portrait and Landscape change the sheet that is shown */
  readonly orientation?: { value(): 'portrait' | 'landscape'; set(orientation: 'portrait' | 'landscape'): void }
  /** a paper chosen from the list: some papers bring an orientation and margins with them */
  withPaper?(page: PageSetupData, id: string): PageSetupData | null
  /** the language, `null` when not set; `undefined` when the server does not know languages */
  language(): string | null | undefined
  canSetLanguage(): boolean
  setLanguage(tag: string | null): void
  /** what the pages depend on: the preview lays out again when it changes */
  watched(): unknown
  /** fetch what the session does not keep (composes' objects); once, before the first layout */
  prepare(): Promise<void>
  /** the pictures the document holds */
  images(): readonly PrintImage[]
  layOut(assets: PrintAssets): Promise<PrintPages>
  /** the status line under the pages */
  status(pages: PrintPages, page: PageSetupData): string
  /** the PDF's producer */
  readonly producer: string
}

/** The PDF of laid-out pages. No date is written into it, so the same document gives the same file everywhere. */
export function pdfOfPages(assets: PrintAssets, pages: PrintPages, images: Map<string, Uint8Array>, source: PrintSource): Uint8Array {
  const lang = source.language()
  return writePdf(pages.list.pages, assets.fonts, (id) => images.get(id) ?? pages.embedded.get(id), { title: source.title(), ...(lang ? { lang } : {}), producer: source.producer })
}

/** No layout choice: the `layouts`/`layout`/`setLayout` of a document that prints one way. */
const ONE_WAY = { layouts: [] as const, layout: () => null, setLayout: () => {} }

// ------------------------------------------------------------------------------ composes
/** A text (composes): its paragraphs flow over the pages; floating objects are fetched once for the preview. */
export function textSource(session: TextSession): PrintSource {
  const state = session.state
  let extras: PrintExtras | null = null
  return {
    back: t('the text'),
    title: () => state.doc || 'document',
    canChange: () => !session.readOnly && state.page !== null,
    page: () => state.page ?? DEFAULT_PAGE,
    setPage: (page) => void session.setPage(page),
    papers: TEXT_PAPERS,
    margins: MARGINS,
    ...ONE_WAY,
    language: () => state.language,
    canSetLanguage: () => !session.readOnly && state.language !== undefined,
    setLanguage: (tag) => void session.setLanguage(tag),
    watched: () => [state.blocks, state.styles, state.page, state.language],
    async prepare() {
      try {
        extras = await session.printExtras()
      } catch {
        extras = null // objects are not printed; the text is
      }
    },
    images: () => extras?.images ?? [],
    async layOut(assets) {
      const doc = textDocument(state.blocks, state.styles, state.page ?? DEFAULT_PAGE, extras, state.language, { lists: state.lists, schemes: state.schemes })
      const [hyphenator] = await Promise.all([assets.hyphenator(doc.language), assets.ensure(fontsNeeded(doc, assets.resolver))])
      return layoutText(doc, assets.fonts, assets.resolver, { hyphenator })
    },
    status: (pages, page) => describe(page, pages.list.pages.length),
    producer: 'claudia composes',
  }
}

// ------------------------------------------------------------------------------ creates
/** The objects of a slide as the layout library knows them. A rendered text container (D390) prints as the picture it
 * shows; one nothing has drawn a picture for yet is left out, as the office exports leave it out. The words of a list
 * item or a numbered title carry their marker, so the pages draw what the slide does (E9.21, E9.22). */
function printable(objects: readonly SlideObject[], markOf: (id: string) => { marker: string; indent: number } | null = () => null): LayoutSlideObject[] {
  return objects.flatMap((o) => {
    if (o.kind === 'rendered') return o.image ? [{ ...o, kind: 'image' as const } as LayoutSlideObject] : []
    const mark = o.paragraph ? markOf(o.id) : null
    return [(mark && o.paragraph ? { ...o, paragraph: { ...o.paragraph, mark } } : o) as LayoutSlideObject]
  })
}

/** A presentation as the layout library reads it: the slides in order with their objects, and how it prints. */
export function slideDocument(session: SlideSession): SlideDocument {
  const state = session.state
  return {
    slides: state.slides.map((s) => ({ id: s.id, objects: printable(session.objectsOn(s.id), (id) => session.markOf(id)) })),
    styles: Object.values(state.styles).map((s) => ({ id: s.id, based_on: s.based_on, resolved: s.resolved })),
    shapes: Object.values(state.shapes),
    // an SVG picture is drawn from its text (D914); the others from their bytes
    images: Object.values(state.images).map((i) => ({ id: i.id, format: i.format, ...(i.format === 'svg' ? { svg: utf8Decode(fromBase64(i.data)) } : {}) })),
    print: state.printSetup ?? DEFAULT_PRINT,
    language: state.language ?? null,
  }
}

/** A presentation (creates): slides one to a page or as handouts (D917); everything it needs is in the session. */
export function slideSource(session: SlideSession): PrintSource {
  const state = session.state
  const setup = () => state.printSetup ?? DEFAULT_PRINT
  const canChange = () => !session.readOnly && state.printSetup !== null
  return {
    back: t('the slides'),
    title: () => state.doc || 'presentation',
    canChange,
    page: () => setup().page,
    setPage: (page) => void session.setPrintSetup({ ...setup(), page }),
    papers: SLIDE_PAPERS,
    margins: [NO_MARGIN, ...MARGINS],
    layouts: LAYOUTS,
    layout: () => setup().layout,
    setLayout: (layout) => void session.setPrintSetup(withLayout(setup(), layout)),
    withPaper: (page, id) => (id === 'slide' ? withSlidePaper(page) : null),
    language: () => state.language,
    canSetLanguage: () => !session.readOnly && state.language !== undefined,
    setLanguage: (tag) => void session.setLanguage(tag),
    watched: () => [state.slides, state.objects, state.order, state.styles, state.shapes, state.images, state.printSetup, state.language],
    prepare: async () => {},
    images: () => Object.values(state.images),
    async layOut(assets) {
      const doc = slideDocument(session)
      const [hyphenator] = await Promise.all([assets.hyphenator(doc.language ?? null), assets.ensure(slideFontsNeeded(doc, assets.resolver))])
      return layoutSlides(doc, assets.fonts, assets.resolver, { hyphenator })
    },
    status: (pages, page) => describe(page, pages.list.pages.length, pages.slides),
    producer: 'claudia creates',
  }
}

// ------------------------------------------------------------------------------ computes
/** What a workbook's print needs of its window: which sheet or chart tab is shown and which cells are selected. */
export interface SheetWindow {
  shown(): { kind: 'sheet' | 'chart'; id: string }
  /** first row, first column, last row, last column of the selection on the shown sheet, or `null` */
  selection(): [number, number, number, number] | null
  /** the SVG pictures of charts; Plotly's unless a test gives its own */
  charts?: ChartPictures
}

/** A workbook (computes): its sheets, each one the way it is set up, on the workbook's page (E6.19, D1001–D1009). */
export function sheetSource(session: Session, window: SheetWindow): PrintSource {
  const state = session.state
  const contents = ref<Contents>('sheet')
  const pictures = window.charts ?? plotlyPictures(session)
  const made = new Map<string, string | null>() // the pictures of charts for one revision of the document
  let madeAt: string | null = null
  const request = (): SheetRequest => ({ contents: contents.value, shown: window.shown(), selection: window.selection() })
  const setup = () => setupOf(session, window.shown().id)
  const canChange = () => !session.readOnly && state.printPage !== null
  const selected = () => {
    const [r0, c0, r1, c1] = window.selection() ?? [0, 0, 0, 0]
    return window.shown().kind === 'sheet' && (r0 !== r1 || c0 !== c1)
  }
  return {
    back: t('the sheets'),
    title: () => state.doc || 'workbook',
    canChange,
    page: () => state.printPage ?? DEFAULT_PAGE,
    setPage: (page) => void session.setPrintPage(page),
    papers: TEXT_PAPERS,
    margins: MARGINS,
    ...ONE_WAY,
    contents: {
      options: CONTENTS,
      value: () => contents.value,
      set: (value) => void (contents.value = value as Contents),
      enabled: (value) => value !== 'selection' || selected(),
    },
    scale: {
      options: SCALES.map((s) => ({ value: s.id, label: s.label })),
      value: () => scaleId(setup().scale),
      set: (id) => void session.setSheetPrint(window.shown().id, withScale(setup(), id)),
      enabled: () => window.shown().kind === 'sheet' || contents.value === 'workbook',
    },
    orientation: {
      value: () => setup().orientation,
      set: (orientation) => void session.setSheetPrint(window.shown().id, { ...setup(), orientation }),
    },
    language: () => state.language,
    canSetLanguage: () => !session.readOnly && state.language !== undefined,
    setLanguage: (tag) => void session.setLanguage(tag),
    // The cells themselves are not watched (a map of every cell would be walked on every look): any step of the history
    // moves the revision, and a preview that is open lays out again.
    watched: () => [contents.value, window.shown(), window.selection(), state.revision, state.generation, state.sheets, state.charts, state.sheetPrint, state.printPage, state.language, state.styles, state.cellStyles, state.numberFormats, state.names, state.order, state.objects, state.images, state.rowHeights, state.colWidths],
    prepare: async () => {},
    images: () => Object.values(state.images),
    async layOut(assets) {
      const asked = request()
      await loadForPrint(session, asked)
      if (madeAt !== state.revision) {
        made.clear()
        madeAt = state.revision
      }
      const sizes = chartSizes(session, asked)
      await Promise.all([...sizes].filter(([spec]) => !made.has(spec)).map(async ([spec, [w, h]]) => void made.set(spec, await pictures(spec, w, h))))
      const drawn = new Map<string, string>()
      for (const spec of sizes.keys()) {
        const svg = made.get(spec)
        if (svg) drawn.set(spec, svg)
      }
      const doc = sheetDocument(session, asked, drawn)
      await assets.ensure(sheetFontsNeeded(doc, assets.resolver))
      const out = layoutSheet(doc, assets.fonts, assets.resolver)
      const first = doc.sheets[0]
      return {
        list: out.list,
        geometry: out.geometry,
        notes: out.notes,
        embedded: out.embedded,
        printed: { sheets: doc.sheets.length, name: first?.name ?? '', orientation: doc.sheets.length === 1 && first ? (first.kind === 'sheet' ? first.print.orientation : first.orientation) : null },
      }
    },
    status: (pages, page) => (pages.printed ? describeSheets(pages.list.pages.length, pages.printed.sheets, pages.printed.name, PAPER_SIZES.find((p) => p.id === page.paper)?.name ?? `${mm(page.width)} × ${mm(page.height)} mm`, pages.printed.orientation) : describe(page, pages.list.pages.length)),
    producer: 'claudia computes',
  }
}
