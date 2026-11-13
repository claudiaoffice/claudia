// The choices of the print preview's bar (layout, paper, orientation, margins) and the setup they make (D904, D906,
// D917). Plain functions over the layout library's paper sizes, so the menu and the stored setup cannot disagree, and
// the same for every app that prints: only what an app offers differs, never what a choice means.
import { PAPER_SIZES, umToMpt, type PageSetupData, type PaperSize, type PrintSetupData, type SlideLayout } from '@claudia/layout'

import { translate as t } from '../i18n'

/** A new text's page (the server's default, for a server that does not know pages yet). */
export const DEFAULT_PAGE: PageSetupData = {
  paper: 'a4',
  width: 595276,
  height: 841890,
  orientation: 'portrait',
  margins: [70866, 70866, 70866, 70866],
  page_numbers: false,
}

export interface MarginChoice {
  id: string
  label: string
  mpt: number
}
/** The margins the bar offers, all four sides alike. */
export const MARGINS: readonly MarginChoice[] = [
  { id: 'narrow', label: '1.27 cm', mpt: umToMpt(12_700) },
  { id: 'normal', label: '2.5 cm', mpt: umToMpt(25_000) },
  { id: 'wide', label: '3.5 cm', mpt: umToMpt(35_000) },
]
/** No margin at all: a slide printed edge to edge (creates only; a text needs room around it). */
export const NO_MARGIN: MarginChoice = { id: 'none', get label() { return t('None') }, mpt: 0 }

/** The papers a text is printed on: every preset but the slide-sized one. */
export const TEXT_PAPERS: readonly PaperSize[] = PAPER_SIZES.filter((p) => p.id !== 'slide')
/** The papers a presentation is printed on: the slide-sized one first, then the others. */
export const SLIDE_PAPERS: readonly PaperSize[] = [...PAPER_SIZES.filter((p) => p.id === 'slide'), ...TEXT_PAPERS]

/** A new presentation's print setup (the server's default, for a server that does not know printing yet). */
export const DEFAULT_PRINT: PrintSetupData = {
  layout: 'slides',
  page: { paper: 'slide', width: 540000, height: 960000, orientation: 'landscape', margins: [0, 0, 0, 0], page_numbers: false },
}

/** The layouts the bar offers a presentation, in order; the handouts are listed under "Handouts". */
export const LAYOUTS: readonly { value: SlideLayout; label: string }[] = [
  { value: 'slides', get label() { return t('Slides') } },
  { value: 'handouts-2', get label() { return t('2 per page') } },
  { value: 'handouts-3', get label() { return t('3 per page, with lines') } },
  { value: 'handouts-4', get label() { return t('4 per page') } },
  { value: 'handouts-6', get label() { return t('6 per page') } },
  { value: 'handouts-9', get label() { return t('9 per page') } },
]

/**
 * A presentation printed another way. Handouts are paper-first: on the slide-sized paper they move to A4 portrait
 * with narrow margins. Slides lie landscape. The rest of the page stays as it was.
 */
export function withLayout(setup: PrintSetupData, layout: SlideLayout): PrintSetupData {
  if (layout === setup.layout) return setup
  let page = setup.page
  if (layout !== 'slides' && page.paper === 'slide') {
    const m = MARGINS[0]!.mpt
    page = { ...withPaper(page, 'a4'), orientation: 'portrait', margins: [m, m, m, m] }
  }
  if (layout === 'slides') page = { ...page, orientation: 'landscape' }
  return { layout, page }
}

/** The page on the slide-sized paper lies landscape with no margins: the page is the slide. */
export function withSlidePaper(page: PageSetupData): PageSetupData {
  return { ...withPaper(page, 'slide'), orientation: 'landscape', margins: [0, 0, 0, 0] }
}

/** The bar's label for a paper: "A4 · 210 × 297 mm", or the custom size. */
export function paperLabel(page: PageSetupData): string {
  const preset = PAPER_SIZES.find((p) => p.id === page.paper)
  if (preset) return `${preset.name} · ${preset.label}`
  return `${mm(page.width)} × ${mm(page.height)} mm`
}

/** mpt to whole millimetres, for people. */
export const mm = (mpt: number): number => Math.round((mpt * 25.4) / 72000)

/** The setup on another preset paper (`custom` keeps the current size). */
export function withPaper(page: PageSetupData, id: string): PageSetupData {
  const preset = PAPER_SIZES.find((p) => p.id === id)
  return preset ? { ...page, paper: preset.id, width: preset.width, height: preset.height } : { ...page, paper: 'custom' }
}

/** The setup on a custom paper of `width` × `height` millimetres (either order; short side first in the result). */
export function withCustomSize(page: PageSetupData, width: number, height: number): PageSetupData {
  const [a, b] = [umToMpt(Math.round(width * 1000)), umToMpt(Math.round(height * 1000))]
  return { ...page, paper: 'custom', width: Math.min(a, b), height: Math.max(a, b) }
}

/** The margin preset the setup uses among `choices`, or `null` when its four margins are not one of them. */
export function marginPreset(page: PageSetupData, choices: readonly MarginChoice[] = MARGINS): string | null {
  const [top, r, b, l] = page.margins
  return choices.find((m) => [top, r, b, l].every((v) => v === m.mpt))?.id ?? null
}

/** A one-line description for the status line: "3 pages · A4 portrait"; with `slides`, "7 slides on 2 pages · …". */
export function describe(page: PageSetupData, pages: number, slides?: number): string {
  const preset = PAPER_SIZES.find((p) => p.id === page.paper)
  const what = pages === 1 ? t('1 page') : t('{count} pages', { count: pages })
  const counted = slides === undefined ? what : slides === 1 ? t('1 slide on {pages}', { pages: what }) : t('{count} slides on {pages}', { count: slides, pages: what })
  const size = preset?.name ?? `${mm(page.width)} × ${mm(page.height)} mm`
  return `${counted} · ${size} ${page.orientation === 'landscape' ? t('landscape') : t('portrait')}`
}
