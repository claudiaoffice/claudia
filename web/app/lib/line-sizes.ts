// Row heights and column widths (D135 on the server; this is the client's half): sparse like the server's own
// storage — only the lines that were resized away from the sheet's default are known here, everything else shows
// at the default. This module is the pure math behind two things SheetGrid.vue needs: converting between a line's
// index and its pixel position when most lines share one size but a few don't, and the proportional multi-line
// resize rule agreed over the mockups (round 2, Nov 2026): typing or dragging the top-most (rows) or left-most
// (columns) line of a selection to a new size scales every other selected line by that same percentage, keeping
// its own shape, rather than pushing every line to the same pixel value.

export const DEFAULT_ROW_HEIGHT = 26
export const DEFAULT_COL_WIDTH = 96
export const MIN_ROW_HEIGHT = 8
export const MAX_ROW_HEIGHT = 1_000
export const MIN_COL_WIDTH = 16
export const MAX_COL_WIDTH = 2_000

export type Axis = 'row' | 'col'

export interface SizeLimits {
  lo: number
  hi: number
}

export const SIZE_LIMITS: Record<Axis, SizeLimits> = {
  row: { lo: MIN_ROW_HEIGHT, hi: MAX_ROW_HEIGHT },
  col: { lo: MIN_COL_WIDTH, hi: MAX_COL_WIDTH },
}

export const DEFAULT_SIZE: Record<Axis, number> = { row: DEFAULT_ROW_HEIGHT, col: DEFAULT_COL_WIDTH }

/** The size of one line: its own override, or the axis' default. */
export function lineSize(overrides: Map<number, number> | undefined, index: number, axis: Axis): number {
  return overrides?.get(index) ?? DEFAULT_SIZE[axis]
}

export interface SizeTable {
  idxs: number[]
  cum: number[]
}

const EMPTY_TABLE: SizeTable = { idxs: [], cum: [0] }

/** Built once from a sheet's sparse overrides, so a line's pixel position can be found without walking every line
 * before it (`offsetOf`) and vice versa (`indexAt`). `base` is the axis' default size. */
export function buildSizeTable(overrides: Map<number, number> | undefined, base: number): SizeTable {
  if (!overrides || overrides.size === 0) return EMPTY_TABLE
  const entries = [...overrides.entries()].sort((a, b) => a[0] - b[0])
  const idxs = entries.map(([i]) => i)
  const cum = [0]
  for (const [, size] of entries) cum.push(cum[cum.length - 1]! + (size - base))
  return { idxs, cum }
}

/** How much extra space (positive or negative) the overridden lines strictly before `index` add, versus every line
 * being the axis' default. */
export function offsetOf(table: SizeTable, index: number): number {
  let lo = 0
  let hi = table.idxs.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (table.idxs[mid]! < index) lo = mid + 1
    else hi = mid
  }
  return table.cum[lo]!
}

/** Where line `index` starts, in pixels from the start of the axis (row 0 / column 0), ignoring scroll and the
 * header's own size. */
export function lineStart(table: SizeTable, base: number, index: number): number {
  return index * base + offsetOf(table, index)
}

/** The index of the line that pixel position `pos` (same units as `lineStart`) falls in, clamped to
 * `[0, limit - 1]`. The inverse of `lineStart`. */
export function indexAt(table: SizeTable, base: number, pos: number, limit: number): number {
  let lo = 0
  let hi = limit - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (lineStart(table, base, mid) <= pos) lo = mid
    else hi = mid - 1
  }
  return lo
}

/** The percentage change from `from` to `to`, rounded to a whole number for a live readout ("+50%"). 0 when `from`
 * is not positive (there is nothing to take a percentage of). */
export function percentChange(from: number, to: number): number {
  return from > 0 ? Math.round(((to - from) / from) * 100) : 0
}

/** "+50%", "-33%", "0%" — always signed except for no change. */
export function formatPercent(pct: number): string {
  return `${pct > 0 ? '+' : ''}${pct}%`
}

/**
 * Resizing the top-most or left-most line of a selection (`first`) to `to` px: every other line in `lines` keeps
 * its own current size (from `sizeOf`), scaled by the same percentage that `first` changed by. A line that would
 * land outside `limits` is clamped rather than rejecting the whole change — only the dragged or typed line was
 * asked for directly, so the others should do their best rather than block it. `lines` must include `first` and
 * need not be sorted; a single-line selection is the trivial case where only `first` changes.
 */
export function proportionalResize(
  lines: readonly number[],
  sizeOf: (index: number) => number,
  first: number,
  to: number,
  limits: SizeLimits,
): [number, number][] {
  const clamp = (n: number) => Math.min(limits.hi, Math.max(limits.lo, n))
  const target = clamp(to)
  const from = sizeOf(first)
  const ratio = from > 0 ? target / from : 1
  return lines.map((i) => [i, i === first ? target : clamp(sizeOf(i) * ratio)])
}

/** `first, first+1, …, last` inclusive, for turning a selection's bounds into the line list `proportionalResize`
 * (and a drag or dialog submit) needs. */
export function lineRange(first: number, last: number): number[] {
  const out: number[] = []
  for (let i = first; i <= last; i++) out.push(i)
  return out
}
