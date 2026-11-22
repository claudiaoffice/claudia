// How a workbook prints, as the bar of the print preview offers it (E6.19, D1001–D1009): what to print, at which scale,
// and the setup of one sheet as the server stores it (snake_case, `print_setup`) next to the layout library's own
// (`SheetPrint`, camelCase). Plain functions, so the bar and the stored setup cannot disagree.
import type { SheetPrint, SheetScale } from '@claudia/layout'

import { translate as t } from '../i18n'

/** The scale as the server stores it: a percentage only for `percent`. */
export type ScaleData = { kind: 'fit-width' } | { kind: 'fit-page' } | { kind: 'percent'; percent: number }

/** The print setup of one sheet or chart tab, as `print_setup` sends it and `set_sheet_print` takes it. */
export interface SheetPrintData {
  orientation: 'portrait' | 'landscape'
  scale: ScaleData
  order: 'down-then-across' | 'across-then-down'
  repeat_rows: [number, number] | null
  repeat_cols: [number, number] | null
  gridlines: boolean
  headings: boolean
  purposes: boolean
  footer_name: boolean
  objects: boolean
  skip_empty: boolean
}

/** What a sheet nobody has set up prints like (the server's default, for a sheet it has not sent a setup for). */
export const DEFAULT_SHEET_PRINT_DATA: SheetPrintData = {
  orientation: 'portrait',
  scale: { kind: 'fit-width' },
  order: 'down-then-across',
  repeat_rows: null,
  repeat_cols: null,
  gridlines: false,
  headings: false,
  purposes: false,
  footer_name: true,
  objects: true,
  skip_empty: true,
}

/** The setup in the layout library's words. */
export function layoutPrint(data: SheetPrintData): SheetPrint {
  return {
    orientation: data.orientation,
    scale: data.scale as SheetScale,
    order: data.order,
    repeatRows: data.repeat_rows,
    repeatCols: data.repeat_cols,
    gridlines: data.gridlines,
    headings: data.headings,
    purposes: data.purposes,
    footerName: data.footer_name,
    objects: data.objects,
    skipEmpty: data.skip_empty,
  }
}

// ------------------------------------------------------------------------------ what to print
/** What the preview prints: the sheet that is shown, the cells that are selected on it, or every sheet (D1002). The
 * print area (a named range) joins them with E6.19.5. */
export type Contents = 'sheet' | 'selection' | 'workbook'

export const CONTENTS: readonly { value: Contents; label: string }[] = [
  { value: 'sheet', get label() { return t('This sheet') } },
  { value: 'selection', get label() { return t('Selection') } },
  { value: 'workbook', get label() { return t('Whole workbook') } },
]

// ------------------------------------------------------------------------------ scale
/** The scales the bar offers, the default first (D1001): fit to the width of the page, or of one page, or a percentage. */
export const SCALES: readonly { id: string; label: string; scale: ScaleData }[] = [
  { id: 'fit-width', get label() { return t('Fit to width') }, scale: { kind: 'fit-width' } },
  { id: 'fit-page', get label() { return t('Fit to one page') }, scale: { kind: 'fit-page' } },
  ...[150, 125, 100, 90, 80, 70, 60, 50, 40].map((percent) => ({ id: `percent-${percent}`, label: `${percent} %`, scale: { kind: 'percent', percent } as ScaleData })),
]

/** The id of the choice a scale is, or `percent-N` for one the list does not have (a setup made elsewhere). */
export function scaleId(scale: ScaleData): string {
  return scale.kind === 'percent' ? `percent-${scale.percent}` : scale.kind
}

/** The scale a choice of the bar means; `null` for an id that is not one. */
export function scaleOf(id: string): ScaleData | null {
  const listed = SCALES.find((s) => s.id === id)
  if (listed) return listed.scale
  const own = /^percent-(\d+)$/.exec(id)
  return own ? { kind: 'percent', percent: Number(own[1]) } : null
}

/** A setup with another scale. */
export function withScale(setup: SheetPrintData, id: string): SheetPrintData {
  const scale = scaleOf(id)
  return scale ? { ...setup, scale } : setup
}

/** The status line under the pages: "3 pages · Sheet1 · A4 portrait" or, for more than one sheet, "5 pages · 2 sheets ·
 * A4" (the sheets lie each their way, so no orientation is said). */
/** "1 sheet", "3 slides": a count of tabs of one kind, for the status line. */
function counted(count: number, kind: 'sheet' | 'slide'): string {
  if (kind === 'sheet') return count === 1 ? t('1 sheet') : t('{count} sheets', { count })
  return count === 1 ? t('1 slide') : t('{count} slides', { count })
}

export function describeSheets(pages: number, sheets: number, name: string, paper: string, orientation: 'portrait' | 'landscape' | null, slides = 0): string {
  const what = pages === 1 ? t('1 page') : t('{count} pages', { count: pages })
  const of = sheets + slides === 1 ? name : slides === 0 ? t('{count} sheets', { count: sheets }) : t('{sheets} and {slides}', { sheets: counted(sheets, 'sheet'), slides: counted(slides, 'slide') })
  const lies = orientation === null ? '' : ` ${orientation === 'landscape' ? t('landscape') : t('portrait')}`
  return `${what} · ${of} · ${paper}${lies}`
}
