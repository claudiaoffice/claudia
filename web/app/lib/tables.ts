// Tables in a text (E9.32), client side: the table the server sends (`tables`, event `table`) as the rows and boxes a
// `<table>` is drawn from, and the steps between boxes with the keyboard. Pure, so a test can check it without a page.
//
// A table is words in boxes named by ids, never by place: the id of a box, to type in it, is `<table>/<row>/<column>`
// (the server's `entry_id`). A box is one line (D1212). A merged box is the first box of the rectangle it joins, and the
// boxes it covers are not drawn.

/** A column as `tables` gives it: `width` is a share of the table in hundredths of a percent, or `null`. */
export interface TableColumn {
  id: string
  kind: 'text' | 'number'
  total: string | null
  width: number | null
}
/** The boxes that have words (or a style of their own): `[row, column, paragraph]`. */
export type TableEntry = [string, string, { id?: string; style: string; text: string }]
export interface TableMerge {
  row: string
  col: string
  rows: number
  cols: number
}
/** One table as the server sends it (`tables`), with the objects that show it and the words of its total row. */
export interface TableInfo {
  format: number
  id: string
  columns: TableColumn[]
  rows: string[]
  entries: TableEntry[]
  merges: TableMerge[]
  header_rows: number
  banded: boolean
  look: string
  placement: 'flow' | 'float'
  width: number | null
  next_row: number
  next_col: number
  used_by: string[]
  totals: Record<string, string>
}

/** The event `table`: the whole table after a change, or `null` when it went. */
export interface TableEvent {
  type: 'table'
  id: string
  definition: Omit<TableInfo, 'used_by' | 'totals'> | null
}

/** The server's one-line form of a box's words: a line break is a space (D1212). */
export const oneLine = (text: string): string => text.replace(/[\r\n]+/g, ' ')

/** The id of a box, to type in it. */
export const boxId = (table: string, row: string, col: string): string => `${table}/${row}/${col}`

/** A box on screen: where it is, what it holds and how far it reaches. */
export interface Box {
  /** the id to type in it */
  id: string
  row: string
  col: string
  rowIndex: number
  colIndex: number
  /** how many rows and columns it joins (1 and 1 unless merged) */
  rows: number
  cols: number
  text: string
  /** the style the person chose for it, or `''` to follow the look */
  style: string
  kind: 'text' | 'number'
}
export interface Grid {
  /** the header rows, then the body rows; each a list of the boxes that start in it */
  header: Box[][]
  body: Box[][]
  /** the total row, if any column has a total: the words are derived, never typed */
  total: { col: string; colIndex: number; text: string; kind: 'text' | 'number' }[] | null
}

const entryText = (t: TableInfo): Map<string, { text: string; style: string }> =>
  new Map(t.entries.map(([row, col, p]) => [`${row}\n${col}`, { text: p.text, style: p.style }]))

/** The rows and boxes of a table, merges taken in: a covered box has no entry and the merged one is as wide and high as
 *  the boxes it joins. */
export function gridOf(t: TableInfo): Grid {
  const words = entryText(t)
  const rowAt = new Map(t.rows.map((r, i) => [r, i]))
  const colAt = new Map(t.columns.map((c, i) => [c.id, i]))
  const span = new Map<string, { rows: number; cols: number }>()
  const covered = new Set<string>()
  for (const m of t.merges) {
    const r = rowAt.get(m.row)
    const c = colAt.get(m.col)
    if (r === undefined || c === undefined) continue
    span.set(`${r}\n${c}`, { rows: m.rows, cols: m.cols })
    for (let i: number = r; i < r + m.rows; i++) {
      for (let j: number = c; j < c + m.cols; j++) if (i !== r || j !== c) covered.add(`${i}\n${j}`)
    }
  }
  const rows = t.rows.map((row, i): Box[] =>
    t.columns.flatMap((col, j): Box[] => {
      if (covered.has(`${i}\n${j}`)) return []
      const own = words.get(`${row}\n${col.id}`)
      const joined = span.get(`${i}\n${j}`) ?? { rows: 1, cols: 1 }
      return [{ id: boxId(t.id, row, col.id), row, col: col.id, rowIndex: i, colIndex: j, ...joined, text: own?.text ?? '', style: own?.style ?? '', kind: col.kind }]
    }),
  )
  const head = Math.min(t.header_rows, rows.length)
  const total = t.columns.some((c) => c.total !== null)
    ? t.columns.map((c, j) => ({ col: c.id, colIndex: j, text: t.totals[c.id] ?? '', kind: c.kind }))
    : null
  return { header: rows.slice(0, head), body: rows.slice(head), total }
}

/** The words of a column's name: the last header box of it, or "Column n" when there are none. */
export function columnName(t: TableInfo, col: string, fallback: (n: number) => string): string {
  const at = t.columns.findIndex((c) => c.id === col)
  const last = t.header_rows > 0 ? t.rows[Math.min(t.header_rows, t.rows.length) - 1] : undefined
  const named = last ? t.entries.find(([r, c]) => r === last && c === col)?.[2].text : ''
  return named || fallback(at + 1)
}

/** A step from a box with the keyboard. `next` and `prev` are Tab and Shift+Tab, the others the arrow keys. */
export type Step = 'next' | 'prev' | 'up' | 'down' | 'left' | 'right'
/** Where a step goes: a box, `'end'` when `next` leaves the last box (Tab there adds a row, D603), or `null` when
 *  there is nowhere to go (the edge of the table). */
export function stepBox(t: TableInfo, from: { row: string; col: string }, step: Step): { row: string; col: string } | 'end' | null {
  const boxes = gridOf(t)
  const all = [...boxes.header, ...boxes.body].flat()
  const at = all.findIndex((b) => b.row === from.row && b.col === from.col)
  if (at < 0) return null
  if (step === 'next') return all[at + 1] ? { row: all[at + 1]!.row, col: all[at + 1]!.col } : 'end'
  if (step === 'prev') return all[at - 1] ? { row: all[at - 1]!.row, col: all[at - 1]!.col } : null
  const here = all[at]!
  // up and down stay in the column the person is in (the first column the box starts in), left and right in the row
  const target = (rowIndex: number, colIndex: number) => all.find((b) => b.rowIndex <= rowIndex && rowIndex < b.rowIndex + b.rows && b.colIndex <= colIndex && colIndex < b.colIndex + b.cols)
  const to = step === 'up' ? target(here.rowIndex - 1, here.colIndex) : step === 'down' ? target(here.rowIndex + here.rows, here.colIndex) : step === 'left' ? target(here.rowIndex, here.colIndex - 1) : target(here.rowIndex, here.colIndex + here.cols)
  return to ? { row: to.row, col: to.col } : null
}

/** What Merge Cells joins for the box the caret is in (there is no selection of several boxes yet): the box and the one
 *  to its right, else the one below it. Only boxes of the same size and in line are joined, a header box is never joined
 *  with a body box, and a box that is joined already is split first. `null` when there is nothing to join. */
export function mergeRect(t: TableInfo, from: { row: string; col: string }): TableMerge | null {
  const grid = gridOf(t)
  const all = [...grid.header, ...grid.body].flat()
  const here = all.find((b) => b.row === from.row && b.col === from.col)
  if (!here || here.rows > 1 || here.cols > 1) return null
  const right = all.find((b) => b.rowIndex === here.rowIndex && b.colIndex === here.colIndex + here.cols)
  if (right && right.rows === here.rows) return { row: here.row, col: here.col, rows: here.rows, cols: here.cols + right.cols }
  const below = all.find((b) => b.colIndex === here.colIndex && b.rowIndex === here.rowIndex + here.rows)
  const sameBlock = (a: number, b: number) => (a < t.header_rows) === (b < t.header_rows)
  if (below && below.cols === here.cols && sameBlock(here.rowIndex, below.rowIndex)) return { row: here.row, col: here.col, rows: here.rows + below.rows, cols: here.cols }
  return null
}

/** Which rows an Insert Above or Below goes next to: the id the server's `insert_rows` takes (`before` / `after`). */
export const rowPlace = (row: string, where: 'above' | 'below'): { before: string } | { after: string } => (where === 'above' ? { before: row } : { after: row })
/** The same for columns: `before` for the left, `after` for the right. */
export const columnPlace = (col: string, where: 'left' | 'right'): { before: string } | { after: string } => (where === 'left' ? { before: col } : { after: col })

/** The table an object of the text shows, if it is a table and the replica has it. */
export function tableOf(tables: Readonly<Record<string, TableInfo>>, object: { kind: string; ref?: string | null }): TableInfo | null {
  return object.kind === 'table' && object.ref ? (tables[object.ref] ?? null) : null
}

/** A table as the server's event says it is: the event's definition, with what the server derives kept from before
 *  until the table is asked for again (`used_by` is the objects that show it; the totals are derived from the boxes). */
export function withEvent(tables: Record<string, TableInfo>, ev: TableEvent): void {
  if (!ev.definition) {
    delete tables[ev.id]
    return
  }
  const before = tables[ev.id]
  tables[ev.id] = { ...ev.definition, used_by: before?.used_by ?? [], totals: before?.totals ?? {} }
}

/** `true` for the id of a box of a table (`<table>/<row>/<column>`), which is not a paragraph of the text. */
export const isBoxId = (id: string): boolean => id.split('/').length === 3

/** The most rows and columns a table has (the server's `MAX_ROWS`, `MAX_COLUMNS`; D1207). */
export const MAX_ROWS = 100
export const MAX_COLUMNS = 10
/** The looks a text starts with, by id (the server's `TABLE_LOOKS`), for the choice in Table options. */
export const LOOKS = ['rules', 'grid', 'plain'] as const
