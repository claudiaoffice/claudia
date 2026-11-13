// What the print preview prints (D906, D918): one interface for every app that prints, so the preview — its bar, its
// zoom, Print… and Download PDF — is one component and looks and behaves the same in composes and creates. A source
// says what the document offers (papers, margins, layouts, a language), reads and changes its print setup as the
// session holds it, and lays the document out with the layout library's adapter for its app.
import {
  fontsNeeded,
  layoutSlides,
  layoutText,
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
} from '@claudia/layout'
import type { PrintAssets } from './assets'
import { fromBase64, textDocument } from './document'
import { DEFAULT_PAGE, DEFAULT_PRINT, describe, LAYOUTS, MARGINS, NO_MARGIN, SLIDE_PAPERS, TEXT_PAPERS, withLayout, withSlidePaper, type MarginChoice } from './setup'
import type { PrintExtras, TextSession } from '../text-session'
import type { SlideSession } from '../slide-session'

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
      const doc = textDocument(state.blocks, state.styles, state.page ?? DEFAULT_PAGE, extras, state.language)
      const [hyphenator] = await Promise.all([assets.hyphenator(doc.language), assets.ensure(fontsNeeded(doc, assets.resolver))])
      return layoutText(doc, assets.fonts, assets.resolver, { hyphenator })
    },
    status: (pages, page) => describe(page, pages.list.pages.length),
    producer: 'claudia composes',
  }
}

// ------------------------------------------------------------------------------ creates
/** A presentation as the layout library reads it: the slides in order with their objects, and how it prints. */
export function slideDocument(session: SlideSession): SlideDocument {
  const state = session.state
  return {
    slides: state.slides.map((s) => ({ id: s.id, objects: session.objectsOn(s.id) })),
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
