// What computes tells the shared object interaction (`object-interaction.ts`, D1221) and what it does with the answer.
// The gesture works on boxes in sheet pixels (the sheet's own, from its top-left corner, without the headers or the
// scroll); the model keeps *the cell an object hangs from* and its size in pixels. This is the translation, as pure
// functions: the preview moves freely, and on release the object's top-left corner becomes the nearest cell (the contract
// note's "what each app does on release"); the size is kept.
import type { Commit } from './object-gestures'
import type { Frame } from './geometry'
import { indexAt, lineStart, type SizeTable } from './line-sizes'

export interface Cell {
  row: number
  col: number
}
/** What the release of a gesture asks of the server. */
export type Step =
  | { kind: 'move'; row: number; col: number }
  | { kind: 'resize'; row: number; col: number; w: number; h: number }
  | { kind: 'rotate'; rotation: number }

/** The line (row or column) whose start is nearest to `pos`, so that a corner dropped half a cell over goes to the
 * nearer one and not always the one it is in. `size` is the axis' default size; clamped to `[0, limit - 1]`. */
export function nearestLine(table: SizeTable, size: number, pos: number, limit: number): number {
  const index = indexAt(table, size, pos, limit)
  const next = index + 1
  if (next >= limit) return index
  return lineStart(table, size, next) - pos < pos - lineStart(table, size, index) ? next : index
}

/** The one request a release makes, or `null` when it changes nothing. `cellAt` says which cell the corner at (x, y)
 * belongs to. A handle on the right or the bottom edge keeps the corner, so the anchor cell stays as it is. */
export function stepFor(
  change: Commit,
  at: { start: Frame; anchor: Cell; cellAt: (x: number, y: number) => Cell },
): Step | null {
  switch (change.kind) {
    case 'rotate':
      return { kind: 'rotate', rotation: change.rotation }
    case 'move': {
      const cell = at.cellAt(change.x, change.y)
      return cell.row === at.anchor.row && cell.col === at.anchor.col ? null : { kind: 'move', ...cell }
    }
    case 'resize': {
      const { frame } = change
      const cornerMoved = frame.x !== at.start.x || frame.y !== at.start.y
      const cell = cornerMoved ? at.cellAt(frame.x, frame.y) : at.anchor
      const same = cell.row === at.anchor.row && cell.col === at.anchor.col && frame.w === at.start.w && frame.h === at.start.h
      return same ? null : { kind: 'resize', ...cell, w: frame.w, h: frame.h }
    }
  }
}
