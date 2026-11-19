// The place a view says it is showing at the top, in its own words, for the way back (D1312): composes says a paragraph
// id and creates a slide id (both are plain ids); computes says the cell at the top left, which is written here.

/** The anchor of a grid whose top-left visible cell is (`row`, `col`). */
export const cellAnchor = (row: number, col: number): string => `${row}:${col}`

/** The cell an anchor of `cellAnchor` names, `null` for anything else. */
export function parseCellAnchor(anchor: string): { row: number; col: number } | null {
  const found = /^(\d+):(\d+)$/.exec(anchor)
  return found ? { row: Number(found[1]), col: Number(found[2]) } : null
}
