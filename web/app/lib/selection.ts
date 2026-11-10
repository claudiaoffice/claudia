// The selected cells, moving around the sheet, and the text that travels through the clipboard.
import type { Content } from './cells'

/** The selection is a rectangle between where it started (row, col) and where it was extended to (row2, col2). */
export interface Sel {
  row: number
  col: number
  row2: number
  col2: number
}

export interface Bounds {
  r0: number
  c0: number
  r1: number
  c1: number
}

export interface Size {
  rows: number
  cols: number
}

export const single = (row: number, col: number): Sel => ({ row, col, row2: row, col2: col })

export function bounds(s: Sel): Bounds {
  return { r0: Math.min(s.row, s.row2), c0: Math.min(s.col, s.col2), r1: Math.max(s.row, s.row2), c1: Math.max(s.col, s.col2) }
}

const clamp = (n: number, max: number) => Math.max(0, Math.min(max - 1, n))

/** Arrow keys: move the cell, or with `extend` the far corner. */
export function move(s: Sel, dr: number, dc: number, extend: boolean, size: Size): Sel {
  if (extend) return { ...s, row2: clamp(s.row2 + dr, size.rows), col2: clamp(s.col2 + dc, size.cols) }
  return single(clamp(s.row2 + dr, size.rows), clamp(s.col2 + dc, size.cols))
}

/** Ctrl+arrow: jump to the edge of the data block, or to the next filled cell, or to the edge of the sheet. */
export function jump(s: Sel, dr: number, dc: number, extend: boolean, size: Size, filled: (r: number, c: number) => boolean): Sel {
  let r = s.row2
  let c = s.col2
  const inside = (row: number, col: number) => row >= 0 && col >= 0 && row < size.rows && col < size.cols
  const canStep = () => inside(r + dr, c + dc)
  const step = () => {
    r += dr
    c += dc
  }
  if (canStep()) {
    if (filled(r, c) && filled(r + dr, c + dc)) {
      while (canStep() && filled(r + dr, c + dc)) step()
    } else {
      step()
      while (canStep() && !filled(r, c)) step()
    }
  }
  return extend ? { ...s, row2: r, col2: c } : single(r, c)
}

export interface Summary {
  count: number
  numbers: number
  sum: number
  average: number | null
}

/** Count, sum and average of the numbers in the selection (for the status bar). */
export function summarize(s: Sel, get: (r: number, c: number) => Content, limit = 200_000): Summary {
  const { r0, c0, r1, c1 } = bounds(s)
  let count = 0
  let numbers = 0
  let sum = 0
  if ((r1 - r0 + 1) * (c1 - c0 + 1) <= limit) {
    for (let r = r0; r <= r1; r++) {
      for (let c = c0; c <= c1; c++) {
        const content = get(r, c)
        if (content === null) continue
        count++
        if (content.t === 'int' || content.t === 'float') {
          numbers++
          sum += Number(content.v)
        }
      }
    }
  }
  return { count, numbers, sum, average: numbers ? sum / numbers : null }
}

// ------------------------------------------------------------------------------ clipboard
/** Rows of fields as spreadsheets put them on the clipboard: tabs between, lines apart, quotes when needed. */
export function toTsv(rows: string[][]): string {
  const field = (text: string) => (/[\t\r\n]|^"/.test(text) ? `"${text.replaceAll('"', '""')}"` : text)
  return rows.map((row) => row.map(field).join('\t')).join('\n')
}

export function parseTsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  let i = 0
  const body = text.replace(/\r\n?/g, '\n')
  while (i < body.length) {
    const ch = body[i]!
    if (quoted) {
      if (ch === '"' && body[i + 1] === '"') {
        field += '"'
        i += 2
        continue
      }
      if (ch === '"') quoted = false
      else field += ch
    } else if (ch === '"' && field === '') {
      quoted = true
    } else if (ch === '\t') {
      row.push(field)
      field = ''
    } else if (ch === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else {
      field += ch
    }
    i++
  }
  if (field !== '' || row.length > 0) {
    row.push(field)
    rows.push(row)
  }
  return rows
}
