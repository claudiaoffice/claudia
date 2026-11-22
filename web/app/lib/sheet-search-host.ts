// What the search panel needs from a workbook (E5.15, D282): the `SearchHost` of computes. The panel is one component
// for all three apps; each app gives it a host that says what can be searched, where, how to name a place and how to
// get to it. A place in a workbook is a cell, `{ sheet, row, col }`, or the words of an object on a slide,
// `{ slide, object, source }` (CODE-18, UX-72): only this file reads it. Everything else — the builder, the sentence,
// the lists — is shared (`lib/search.ts`, `SearchPanel.vue`).
import { bounds, type Sel } from './selection'
import type { Session, SearchScope } from './session'
import type { Change, Kinds, SearchHost, SearchMatch, SearchPlace, SearchSwitch, Skipped } from './search'
import { lookOnly } from './replay'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

export type ScopeId = 'sheet' | 'all' | 'selection'

/** A cell, as every answer of a search in a workbook names it. */
export interface CellPlace {
  sheet: string
  row: number
  col: number
}

/** Is the place the words of an object on a slide (not a cell)? */
const onSlide = (at: SearchPlace): boolean => typeof at.slide === 'string'

/** The cell a place names; anything but a cell is a bug, and says so. */
export function cellOf(at: SearchPlace): CellPlace {
  const { sheet, row, col } = at
  if (typeof sheet !== 'string' || typeof row !== 'number' || typeof col !== 'number') throw new Error(`not a cell: ${JSON.stringify(at)}`)
  return { sheet, row, col }
}

const SWITCHES: SearchSwitch[] = [
  { key: 'text', matchKind: 'text', replaceable: true, whileReplacing: true },
  { key: 'formulas', matchKind: 'formula', replaceable: true, whileReplacing: false },
  { key: 'values', matchKind: 'value', replaceable: false, whileReplacing: false },
]
const ALL_KINDS = SWITCHES.map((s) => s.key)
const chosen = (kinds: Kinds) => ALL_KINDS.filter((k) => kinds[k])

export function sheetSearchHost(from: {
  session: Session
  selection: () => Sel
  goTo: (sheet: string, row: number, col: number) => void
  /** Show a slide with this object of it selected. */
  goToObject: (slide: string, object: string) => void
  t: Translate
}): SearchHost<SearchScope> {
  const { session, t } = from
  const state = session.state
  const hasSlides = () => state.tabs.some((tab) => tab.kind === 'slide')
  return {
    get readonly() {
      return lookOnly(state)
    },
    unit: 'cell',
    switches: SWITCHES,
    scopes: ['sheet', 'all', 'selection'] satisfies ScopeId[],
    helpTopic: 'computes.searching-and-replacing',
    extraParts: ['cellref'],
    scopeLabel(scope) {
      if (scope === 'all') return hasSlides() ? t('All sheets and slides') : t('All sheets')
      if (scope === 'sheet') return state.activeSlide ? t('This slide') : t('This sheet')
      return t('Selection')
    },
    scopeOf(scope) {
      if (scope === 'all') return {}
      if (state.activeSlide) return { slide: state.activeSlide } // (a slide has no cells to select)
      if (scope === 'sheet') return { sheet: state.activeSheet }
      const b = bounds(from.selection())
      return { sheet: state.activeSheet, range: [b.r0, b.c0, b.r1, b.c1] }
    },
    find: (query, scope) => session.searchFind(query, ALL_KINDS, scope),
    preview: (query, kinds, scope, leave) => session.searchPreview(query, chosen(kinds), scope, leave),
    replace: (query, kinds, scope, leave) => session.searchReplace(query, chosen(kinds), scope, leave),
    keyOf: (at) => {
      if (onSlide(at)) return `${at.slide}/${at.object}/${at.source}`
      const c = cellOf(at)
      return `${c.sheet}!${c.row},${c.col}`
    },
    where(at) {
      if (!onSlide(at)) return whereLabel(cellOf(at), (id) => state.sheets.find((s) => s.id === id)?.name ?? id)
      const slide = state.tabs.find((tab) => tab.id === at.slide)?.name ?? String(at.slide)
      const name = state.objects[String(at.object)]?.name
      return name ? `${slide}: ${name}` : t('An object on “{slide}”', { slide })
    },
    jump: (at) => {
      if (onSlide(at)) return from.goToObject(String(at.slide), String(at.object))
      const c = cellOf(at)
      from.goTo(c.sheet, c.row, c.col)
    },
    revision: () => state.revision,
  }
}

/** The cell with its sheet, as a formula would name it: `Costs!B2`. */
export function whereLabel(cell: CellPlace, sheetName: (id: string) => string): string {
  return `${sheetName(cell.sheet)}!${columnLetters(cell.col)}${cell.row + 1}`
}

function columnLetters(col: number): string {
  let name = ''
  for (let n = col; n >= 0; n = Math.floor(n / 26) - 1) name = String.fromCharCode(65 + (n % 26)) + name
  return name
}

// --------------------------------------------------------------------------------------------------- on the sheet
const gridKey = (row: number, col: number) => row * 100_000 + col // as `SheetGrid.vue` keys a cell

export interface CellMark {
  current: boolean
  /** The match is in a formula, not in what the cell shows: drawn with a corner mark too. */
  formula: boolean
}

/** What the grid draws for a search: the cells with matches, what a replacement would show instead, and the cells it skips. */
export interface SearchMarks {
  cells: Map<number, CellMark>
  after: Map<number, string>
  blocked: Map<number, string>
}

export const NO_MARKS: SearchMarks = { cells: new Map(), after: new Map(), blocked: new Map() }

/** The marks for one sheet; `current` is the index in `matches` of the match being looked at. */
export function marksFor(
  matches: SearchMatch[],
  sheet: string,
  current: number | null,
  preview?: { changes: Change[]; skipped: Skipped[] } | null,
): SearchMarks {
  const marks: SearchMarks = { cells: new Map(), after: new Map(), blocked: new Map() }
  matches.forEach((m, index) => {
    if (onSlide(m.at)) return // (the slide view draws those)
    const c = cellOf(m.at)
    if (c.sheet !== sheet) return
    const key = gridKey(c.row, c.col)
    const seen = marks.cells.get(key)
    marks.cells.set(key, { current: index === current || seen?.current === true, formula: m.kind === 'formula' || seen?.formula === true })
  })
  for (const change of preview?.changes ?? []) {
    if (onSlide(change.at)) continue
    const c = cellOf(change.at)
    if (c.sheet === sheet && change.kind === 'text') marks.after.set(gridKey(c.row, c.col), change.after)
  }
  for (const skip of preview?.skipped ?? []) {
    if (onSlide(skip.at)) continue
    const c = cellOf(skip.at)
    if (c.sheet === sheet && skip.reason === 'locked') marks.blocked.set(gridKey(c.row, c.col), skip.by ?? '')
  }
  return marks
}
