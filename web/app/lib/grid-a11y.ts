// What the grid says to someone who cannot see it (BITV 1.3.1, 4.1.2; UX-02). The grid is drawn by hand and
// virtualised — only the cells on screen are elements — so a screen reader gets its structure from ARIA: the size of
// the whole sheet, where each drawn row and cell sits in it, and a name for the cell the focus is on. All of that is
// worked out here, as plain functions, so it can be tested without a browser; `SheetGrid.vue` only puts it in the page.

import { translate as t } from './i18n'
import { columnName, rangeLabel } from './cells'

/** The rows of the sheet and the header row above them. */
export const ariaRowCount = (rows: number): number => rows + 1
/** The columns of the sheet and the row numbers beside them. */
export const ariaColCount = (cols: number): number => cols + 1
/** The header row is row 1 and the row numbers column 1, so the sheet's first row and column are 2. */
export const rowIndexOf = (row: number): number => row + 2
export const colIndexOf = (col: number): number => col + 2

/** An id for one cell, unique to its grid (`aria-activedescendant` points at it). */
export const cellDomId = (grid: string, row: number, col: number): string => `${grid}-r${row}c${col}`

/** What a drawn cell is, as far as its name goes. */
export interface CellFacts {
  ref: string
  text: string
  kind: string
  /** The value comes from a formula. */
  formula: boolean
  /** The cell shows a part of a query result and cannot be typed into. */
  spill: boolean
  /** For an error: why, if the server said ('' when it did not); null for anything else. */
  error: string | null
  /** The alternatives of an input cell, as words. */
  alternatives: string[]
  /** What the dots of a result of alternatives mean, as words. */
  outcome: string | null
  /** The part this cell plays in a followed computation, as words. */
  role: string | null
}

/** What a screen reader says on arriving in a cell: where it is first, then what is in it, then what is special about
 * it. Nothing here is only in colour, a shape or a dot: those are said too (BITV 1.4.1). */
export function cellName(cell: CellFacts | null, ref = ''): string {
  if (cell === null) return t('{ref}, empty', { ref })
  const parts: string[] = []
  if (cell.kind === 'error') {
    parts.push(cell.error ? t('error {value}: {why}', { value: cell.text, why: cell.error }) : t('error {value}', { value: cell.text }))
  } else if (cell.alternatives.length > 0) {
    parts.push(t('alternatives: {list}', { list: cell.alternatives.join(', ') }))
  } else {
    parts.push(cell.text === '' ? t('empty') : cell.text)
    if (cell.formula) parts.push(t('formula'))
    if (cell.spill) parts.push(t('part of a result'))
  }
  if (cell.outcome) parts.push(cell.outcome)
  if (cell.role) parts.push(cell.role)
  return `${cell.ref}, ${parts.join(', ')}`
}

/** What to say when the selection grows past one cell, for a polite live region: the cell that is active is already
 * spoken, so one cell needs nothing (null). */
export function selectionAnnouncement(sel: { row: number; col: number; row2: number; col2: number }, rows: number, cols: number): string | null {
  const r0 = Math.min(sel.row, sel.row2)
  const r1 = Math.max(sel.row, sel.row2)
  const c0 = Math.min(sel.col, sel.col2)
  const c1 = Math.max(sel.col, sel.col2)
  if (r0 === r1 && c0 === c1) return null
  const allRows = r0 === 0 && r1 === rows - 1
  const allCols = c0 === 0 && c1 === cols - 1
  if (allRows && allCols) return t('All cells selected')
  if (allRows && c0 === c1) return t('Column {name} selected', { name: columnName(c0) })
  if (allCols && r0 === r1) return t('Row {n} selected', { n: r0 + 1 })
  return t('{range} selected, {count} cells', { range: rangeLabel(r0, c0, r1, c1), count: (r1 - r0 + 1) * (c1 - c0 + 1) })
}
