// Following a computation (E6.23, D297): which cells take part in one with the cell being looked at, and what each is
// there as. The server finds them (`trace`); this module is what a grid asks to draw them. Nothing is drawn between
// the cells: they only light up, and every other cell is dimmed.
import { cellLabel } from './cells'

/** The part of a cell in a computation, relative to the cells connected to it. */
export type Role = 'input' | 'calc' | 'output'
export type Reach = 'group' | 'chain'

/** The answer of `trace`. */
export interface Trace {
  sheet: string
  row: number
  col: number
  reach: Reach
  cells: [number, number, Role][]
  /** For each other sheet, how many connected cells it has. */
  other: Record<string, number>
  total: number
  connected: boolean
  truncated: boolean
}

/** A window of the sheet: first row, first column, last row, last column (both included). */
export type Window = [number, number, number, number]

/** The shape that says a part without colour (BITV): a dot, a diamond, a square. */
export const ROLE_SHAPE: Record<Role, 'dot' | 'diamond' | 'square'> = { input: 'dot', calc: 'diamond', output: 'square' }

const lookups = new WeakMap<Trace, Map<number, Role>>()
const STRIDE = 16_384

function lookup(trace: Trace): Map<number, Role> {
  let found = lookups.get(trace)
  if (!found) {
    found = new Map(trace.cells.map(([row, col, role]) => [row * STRIDE + col, role]))
    lookups.set(trace, found)
  }
  return found
}

/** The part of the cell at (`row`, `col`), or `null` when it is not connected (or nothing is followed). */
export function roleAt(trace: Trace | null, row: number, col: number): Role | null {
  return trace ? (lookup(trace).get(row * STRIDE + col) ?? null) : null
}

export function roleCounts(trace: Trace | null): Record<Role, number> {
  const counts: Record<Role, number> = { input: 0, calc: 0, output: 0 }
  for (const [, , role] of trace?.cells ?? []) counts[role]++
  return counts
}

/** The sheets the connection goes on to, with how many cells they have in it, for a marker on their tabs. */
export function tabMarks(trace: Trace | null): Record<string, number> {
  return Object.fromEntries(Object.entries(trace?.other ?? {}).filter(([, n]) => n > 0))
}

/** The window to ask the server about: what is visible and one screen more on every side, inside the sheet. So
 * scrolling a little does not ask again. */
export function windowAround(view: { r0: number; r1: number; c0: number; c1: number }, rows: number, cols: number): Window {
  const high = view.r1 - view.r0 + 1
  const wide = view.c1 - view.c0 + 1
  return [Math.max(0, view.r0 - high), Math.max(0, view.c0 - wide), Math.min(rows - 1, view.r1 + high), Math.min(cols - 1, view.c1 + wide)]
}

/** Whether what was asked for covers what is visible now. */
export function coversWindow(asked: Window | null, view: { r0: number; r1: number; c0: number; c1: number }): boolean {
  return asked !== null && view.r0 >= asked[0] && view.c0 >= asked[1] && view.r1 <= asked[2] && view.c1 <= asked[3]
}

/** The address of the cell that is followed, "B8". */
export function followLabel(trace: Trace | null): string {
  return trace ? cellLabel(trace.row, trace.col) : ''
}
