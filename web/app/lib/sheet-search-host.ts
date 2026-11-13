// What the search panel needs from a workbook (E5.15, D282): the `SearchHost` of computes. The panel is one component
// for all three apps; each app gives it a host that says what can be searched, where, how to name a place and how to
// get to it. A place in a workbook is `{ sheet, row, col }` (CODE-18): only this file reads it. Everything else — the
// builder, the sentence, the lists — is shared (`lib/search.ts`, `SearchPanel.vue`).
import { bounds, type Sel } from './selection'
import type { Session, SearchScope } from './session'
import type { Change, Kinds, SearchHost, SearchMatch, SearchPlace, Skipped } from './search'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

export type ScopeId = 'sheet' | 'all' | 'selection'

/** A cell, as every answer of a search in a workbook names it. */
export interface CellPlace {
  sheet: string
  row: number
  col: number
}

/** The cell a place names. A workbook's places are always cells; anything else is a bug, and says so. */
export function cellOf(at: SearchPlace): CellPlace {
  const { sheet, row, col } = at
  if (typeof sheet !== 'string' || typeof row !== 'number' || typeof col !== 'number') throw new Error(`not a cell: ${JSON.stringify(at)}`)
  return { sheet, row, col }
}

const ALL_KINDS: (keyof Kinds)[] = ['text', 'formulas', 'values']
const chosen = (kinds: Kinds) => ALL_KINDS.filter((k) => kinds[k])

export function sheetSearchHost(from: {
  session: Session
  selection: () => Sel
  goTo: (sheet: string, row: number, col: number) => void
  t: Translate
}): SearchHost<SearchScope> {
  const { session, t } = from
  const state = session.state
  return {
    get readonly() {
      return state.me.role === 'viewer'
    },
    kinds: ALL_KINDS,
    scopes: ['sheet', 'all', 'selection'] satisfies ScopeId[],
    extraParts: ['cellref'],
    scopeLabel: (scope) => (scope === 'sheet' ? t('This sheet') : scope === 'all' ? t('All sheets') : t('Selection')),
    scopeOf(scope) {
      if (scope === 'all') return {}
      if (scope === 'sheet') return { sheet: state.activeSheet }
      const b = bounds(from.selection())
      return { sheet: state.activeSheet, range: [b.r0, b.c0, b.r1, b.c1] }
    },
    find: (query, scope) => session.searchFind(query, ALL_KINDS, scope),
    preview: (query, kinds, scope, leave) => session.searchPreview(query, chosen(kinds), scope, leave),
    replace: (query, kinds, scope, leave) => session.searchReplace(query, chosen(kinds), scope, leave),
    keyOf: (at) => {
      const c = cellOf(at)
      return `${c.sheet}!${c.row},${c.col}`
    },
    where: (at) => whereLabel(cellOf(at), (id) => state.sheets.find((s) => s.id === id)?.name ?? id),
    jump: (at) => {
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
    const c = cellOf(m.at)
    if (c.sheet !== sheet) return
    const key = gridKey(c.row, c.col)
    const seen = marks.cells.get(key)
    marks.cells.set(key, { current: index === current || seen?.current === true, formula: m.kind === 'formula' || seen?.formula === true })
  })
  for (const change of preview?.changes ?? []) {
    const c = cellOf(change.at)
    if (c.sheet === sheet && change.kind === 'text') marks.after.set(gridKey(c.row, c.col), change.after)
  }
  for (const skip of preview?.skipped ?? []) {
    const c = cellOf(skip.at)
    if (c.sheet === sheet && skip.reason === 'locked') marks.blocked.set(gridKey(c.row, c.col), skip.by ?? '')
  }
  return marks
}
