// Names, tables and queries on the client (E6.5, D600): the wire shapes of the `names` method, what a person may call
// a name, how a table's cells are tinted by purpose, and the small pieces of text the Name Box, the SQL editor and the
// chart source picker write (a structured reference, a quoted identifier). Pure: no component and no connection in
// here, so every rule has a test (`tests/names.test.ts`).

import { cellLabel, rangeLabel } from './cells'

import { translate as t } from './i18n'
/** What a table (or one of its columns) is for; the cells of it are tinted by it (mock 2). `calc` is shown as
 * "Calculation". */
export type Purpose = 'input' | 'data' | 'calc' | 'result'
export const PURPOSES: { value: Purpose; label: string; hint: string }[] = [
  { value: 'input', get label() { return t('Input') }, get hint() { return t('Values people type and change') } },
  { value: 'data', get label() { return t('Data') }, get hint() { return t('Plain data, nothing to tell') } },
  { value: 'calc', get label() { return t('Calculation') }, get hint() { return t('Cells that are worked out from others') } },
  { value: 'result', get label() { return t('Result') }, get hint() { return t('What a query gave') } },
]

export function purposeLabel(purpose: Purpose): string {
  return PURPOSES.find((p) => p.value === purpose)?.label ?? purpose
}

export interface NameRegion {
  sheet: string
  row0: number
  col0: number
  row1: number
  col1: number
}
export interface NameColumn {
  name: string
  type: 'int' | 'real' | 'text' | 'mixed'
  purpose: Purpose
}
/** A name as `names` sends it. A `result` is the table a `SQL()` cell fills (`anchor` is that cell). `region` is
 * `null` for a result that has no table at the moment (the query failed or is gone). */
export interface NameInfo {
  name: string
  scope: string | null
  kind: 'range' | 'result'
  header: boolean
  grows: boolean
  purpose: Purpose
  column_purposes: [number, Purpose][]
  sheet: string
  sheet_name: string
  region: NameRegion | null
  a1: string | null
  anchor: { sheet: string; row: number; col: number } | null
  columns: NameColumn[]
  rows: number
}

/** What `define_name` is given. */
export interface NameDraft {
  name: string
  scope: string | null
  range?: NameRegion
  header: boolean
  grows: boolean
  purpose: Purpose
  column_purposes?: [number, Purpose][]
}

const MAX_NAME = 255
const NAME = /^[\p{L}_][\p{L}\p{M}\p{N}_.]*$/u // Python's \w: letters, marks, digits, _ (the server's own rule)
const CELL_LIKE = /^([A-Za-z]{1,3})([0-9]+)$/
const MAX_ROWS = 1_048_576
const MAX_COLS = 16_384

function columnOf(letters: string): number {
  let n = 0
  for (const ch of letters.toUpperCase()) n = n * 26 + (ch.charCodeAt(0) - 64)
  return n - 1
}

/** Why `text` cannot be a name, or `null` when it can — the server's own rule (`claudia_computes.names`), asked
 * here too so the Name Box can tell a name from a cell address or a typo without a round trip. */
export function nameProblem(text: string): string | null {
  if (text === '') return t('a name needs some text')
  if (text.length > MAX_NAME) return t('a name has at most {max} characters', { max: MAX_NAME })
  if (!NAME.test(text)) return t('a name starts with a letter and has only letters, digits, _ and .')
  if (text.toUpperCase() === 'TRUE' || text.toUpperCase() === 'FALSE') return t('{text} is a value, not a name', { text })
  const cell = CELL_LIKE.exec(text)
  if (cell && columnOf(cell[1]!) < MAX_COLS && Number(cell[2]) > 0 && Number(cell[2]) <= MAX_ROWS) return t('{text} is a cell, not a name', { text })
  return null
}

/** The name a person sees for `text` when the cursor is on it, sheet-scoped names shadowing workbook-wide ones. */
export function visibleNames(names: NameInfo[], sheet: string): NameInfo[] {
  const seen = new Map<string, NameInfo>()
  for (const n of names) if (n.scope === null) seen.set(n.name.toLowerCase(), n)
  for (const n of names) if (n.scope === sheet) seen.set(n.name.toLowerCase(), n)
  return [...seen.values()].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
}

/** The name `text` means for a formula on `sheet`: the sheet's own, else the workbook's. */
export function resolveName(names: NameInfo[], sheet: string, text: string): NameInfo | null {
  const folded = text.toLowerCase()
  const own = names.find((n) => n.scope === sheet && n.name.toLowerCase() === folded)
  return own ?? names.find((n) => n.scope === null && n.name.toLowerCase() === folded) ?? null
}

/** What the Name Box shows when the selection is exactly a named region (header row included), else `null`. */
export function nameAt(names: NameInfo[], sheet: string, r0: number, c0: number, r1: number, c1: number): NameInfo | null {
  return (
    visibleNames(names, sheet).find((n) => {
      const g = n.region
      return g !== null && g.sheet === sheet && g.row0 === r0 && g.col0 === c0 && g.row1 === r1 && g.col1 === c1
    }) ?? null
  )
}

/** The table a cell is inside (header row included), the one defined last when two overlap. */
export function tableAt(names: NameInfo[], sheet: string, row: number, col: number): { table: NameInfo; header: boolean; purpose: Purpose } | null {
  let found: { table: NameInfo; header: boolean; purpose: Purpose } | null = null
  for (const table of visibleNames(names, sheet)) {
    const g = table.region
    if (!g || g.sheet !== sheet || row < g.row0 || row > g.row1 || col < g.col0 || col > g.col1) continue
    const header = table.header && row === g.row0
    found = { table, header, purpose: columnPurpose(table, col - g.col0) }
  }
  return found
}

/** A column's purpose: its own when it was given one, else the table's. */
export function columnPurpose(table: Pick<NameInfo, 'purpose' | 'column_purposes'>, offset: number): Purpose {
  return table.column_purposes.find(([o]) => o === offset)?.[1] ?? table.purpose
}

/** The CSS custom property a purpose is tinted with (`assets/tokens.css`). Data stays white. */
export function purposeVar(purpose: Purpose): string {
  return `var(--purpose-${purpose})`
}

/** The text of a column in a structured reference: a `[`, `]`, `#` or `'` in it is written with a `'` in front. */
export function escapeColumn(text: string): string {
  return text.replace(/(['[\]#])/g, "'$1")
}

/** `Sales[Unit price]` — Excel's notation for a column of a table. */
export function structuredRef(table: string, column: string): string {
  return `${table}[${escapeColumn(column)}]`
}

/** A word as SQL wants it: plain identifiers stay as they are, anything else is quoted with `"`. */
export function quoteIdentifier(text: string): string {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(text) ? text : `"${text.replace(/"/g, '""')}"`
}

/** The cells a name is on, in A1 notation without a sheet; `null` for a result that has no table right now. */
export function regionLabel(region: NameRegion | null): string | null {
  return region ? rangeLabel(region.row0, region.col0, region.row1, region.col1) : null
}

/** What the Name Box offers when typed text is not a cell: jump to a name, make a name of the selection, or say why
 * it cannot be one. The selection is `r0..r1 × c0..c1`. */
export type NameBoxAction =
  | { kind: 'cell'; row: number; col: number }
  | { kind: 'range'; row: number; col: number; row2: number; col2: number }
  | { kind: 'goto'; name: NameInfo }
  | { kind: 'define'; name: string; scope: string | null }
  | { kind: 'redefine'; name: NameInfo }
  | { kind: 'problem'; message: string }

/** The Name Box's rule (mock 1). Typing `B3` goes to the cell; typing the name of something goes there; typing a new
 * word with cells selected names them. Typing the name of something that exists while *more than the cursor cell* is
 * selected asks whether to move the name to the selection. `parseCell` is injected to keep this module free of
 * `cells.ts`'s own limits. */
export function nameBoxAction(
  typed: string,
  sheet: string,
  names: NameInfo[],
  selectionIsOneCell: boolean,
  parseCell: (text: string) => [number, number] | null,
): NameBoxAction {
  const text = typed.trim()
  const cell = parseCell(text)
  if (cell) return { kind: 'cell', row: cell[0], col: cell[1] }
  const [from, to, ...rest] = text.split(':')
  const first = from === undefined ? null : parseCell(from)
  const last = to === undefined ? null : parseCell(to)
  if (first && last && rest.length === 0) return { kind: 'range', row: first[0], col: first[1], row2: last[0], col2: last[1] }
  const known = resolveName(names, sheet, text)
  if (known && (selectionIsOneCell || known.kind === 'result')) return known.region ? { kind: 'goto', name: known } : { kind: 'problem', message: t('{name} has no cells right now', { name: known.name }) }
  if (known) return { kind: 'redefine', name: known }
  const problem = nameProblem(text)
  return problem ? { kind: 'problem', message: problem } : { kind: 'define', name: text, scope: null }
}

/** A short label for a region, as the Names manager's "Refers to" column shows it: `Data!A1:D4`. */
export function referLabel(info: NameInfo): string {
  if (info.a1) return info.a1
  return info.anchor ? t('{cell} (no table right now)', { cell: `${info.sheet_name}!${cellLabel(info.anchor.row, info.anchor.col)}` }) : '—'
}

/** One piece of how a table is drawn under its cells (mock 2). */
export interface TableBox {
  key: string
  kind: 'column' | 'head' | 'frame' | 'ghost'
  table: NameInfo
  /** Which column of the table this piece belongs to (0 for a frame or a ghost row, which span them all). */
  offset: number
  purpose: Purpose
  r0: number
  c0: number
  r1: number
  c1: number
}

const MAX_ROW = 1_048_575

/** What to draw for the tables in view: per column a body in the column's purpose tint, the header row over them, a
 * frame round the whole, and below a table that grows with its last row a ghost row ("type here to add a row").
 * `view` is the rows and columns on screen; pieces are clipped to it (a result of 100 000 rows is not 100 000 rows
 * of pixels). */
export function tableBoxes(names: NameInfo[], sheet: string, view: { r0: number; r1: number; c0: number; c1: number }): TableBox[] {
  const out: TableBox[] = []
  for (const table of visibleNames(names, sheet)) {
    const g = table.region
    if (!g || g.sheet !== sheet || g.row1 < view.r0 || g.row0 > view.r1 || g.col1 < view.c0 || g.col0 > view.c1) continue
    const header = table.header
    const top = Math.max(g.row0, view.r0 - 1)
    const bottom = Math.min(g.row1, view.r1 + 1)
    out.push({ key: `${table.name}:frame`, kind: 'frame', table, offset: 0, purpose: table.purpose, r0: top, c0: g.col0, r1: bottom, c1: g.col1 })
    for (let c = Math.max(g.col0, view.c0); c <= Math.min(g.col1, view.c1); c++) {
      const offset = c - g.col0
      const purpose = columnPurpose(table, offset)
      const bodyTop = Math.max(header ? g.row0 + 1 : g.row0, view.r0 - 1)
      if (bodyTop <= bottom) out.push({ key: `${table.name}:col${c}`, kind: 'column', table, offset, purpose, r0: bodyTop, c0: c, r1: bottom, c1: c })
      if (header && g.row0 >= view.r0 - 1 && g.row0 <= view.r1) out.push({ key: `${table.name}:head${c}`, kind: 'head', table, offset, purpose, r0: g.row0, c0: c, r1: g.row0, c1: c })
    }
    const below = g.row1 + 1
    if (table.grows && table.kind === 'range' && below <= MAX_ROW && below >= view.r0 && below <= view.r1) {
      out.push({ key: `${table.name}:ghost`, kind: 'ghost', table, offset: 0, purpose: table.purpose, r0: below, c0: g.col0, r1: below, c1: g.col1 })
    }
  }
  return out
}

/** The word of a `#SQL!` message that names something missing — `no such column: Revnue` — and the nearest column that
 * the tables in view have (edit distance of at most a third of the word, rounded up; ties to the first), if one is near enough. */
export function didYouMean(detail: string, names: NameInfo[]): { wrong: string; right: string } | null {
  const found = /no such column: (?:[\w]+\.)?(.+)$/i.exec(detail.trim())
  if (!found) return null
  const wrong = found[1]!.replace(/^"|"$/g, '')
  let best: { right: string; distance: number } | null = null
  for (const table of names) {
    for (const column of table.columns) {
      const distance = editDistance(wrong.toLowerCase(), column.name.toLowerCase())
      if (distance > 0 && distance <= Math.max(1, Math.ceil(wrong.length / 3)) && (best === null || distance < best.distance)) best = { right: column.name, distance }
    }
  }
  return best ? { wrong, right: best.right } : null
}

function editDistance(a: string, b: string): number {
  let row = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const next = [i]
    for (let j = 1; j <= b.length; j++) next[j] = Math.min(row[j]! + 1, next[j - 1]! + 1, row[j - 1]! + (a[i - 1] === b[j - 1] ? 0 : 1))
    row = next
  }
  return row[b.length]!
}

/** `wrong` as a whole word of the query, replaced by `right` (quoted when it has to be); other words stay. */
export function replaceWord(query: string, wrong: string, right: string): string {
  const escaped = wrong.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return query.replace(new RegExp(`(?<![\\w"])"?${escaped}"?(?![\\w"])`, 'g'), quoteIdentifier(right))
}

/** The A1 cell a `#SPILL!` message says is in the way (`… but B5 holds a value`), as `[row, col]`. */
export function blockerOf(detail: string, parse: (text: string) => [number, number] | null): [number, number] | null {
  const found = /but ([A-Z]{1,3}[0-9]+) holds a value/.exec(detail)
  return found ? parse(found[1]!) : null
}

/** Whether the first row of a block reads as a header: more than one row, and every cell of the first is some text.
 * Only the default the define popover starts from — the person ticks it either way. `kinds[r][c]` is a cell's type
 * (`'text'`, `'int'`, …) or `null` for an empty one, `texts` what it shows. */
export function guessHeader(kinds: (string | null)[][], texts: string[][]): boolean {
  if (kinds.length < 2) return false
  return kinds[0]!.every((kind, c) => kind === 'text' && texts[0]![c]!.trim() !== '')
}

/** What the define popover sends: a table (header, growing) or plain named cells. A header row makes a table; growing
 * only means something with one, so it is dropped otherwise. */
export function draftOf(fields: { name: string; scope: string | null; region: NameRegion; header: boolean; grows: boolean; purpose: Purpose }): NameDraft {
  return {
    name: fields.name.trim(),
    scope: fields.scope,
    range: fields.region,
    header: fields.header,
    grows: fields.header && fields.grows,
    purpose: fields.purpose,
  }
}

/** A table's definition as `define_name` wants it back with one column's purpose (or, with `offset` `null`, the whole
 * table's) changed: what the header chip's menu sends. A column that is given the table's own purpose again has no
 * purpose of its own any more. */
export function withPurpose(table: NameInfo, offset: number | null, purpose: Purpose): NameDraft {
  const base = {
    name: table.name,
    scope: table.scope,
    range: table.region ?? undefined,
    header: table.header,
    grows: table.grows,
  }
  if (offset === null) return { ...base, purpose, column_purposes: [] }
  const others = table.column_purposes.filter(([o]) => o !== offset)
  return { ...base, purpose: table.purpose, column_purposes: purpose === table.purpose ? others : [...others, [offset, purpose]] }
}

/** One thing the formula editor offers to finish what is typed. */
export interface Completion {
  /** What the list shows. */
  label: string
  /** What replaces the typed word (`from` up to the caret). */
  insert: string
  /** The small grey text after it: what it is. */
  detail: string
  /** Whether the bracket of the reference ends with it (a column, `#All`), so that the `]` is put behind it. */
  closes: boolean
}
export interface Completions {
  /** Where the word being completed starts. */
  from: number
  items: Completion[]
}

const SPECIAL_ITEMS: Completion[] = [
  { label: '#All', insert: '#All', get detail() { return t('the whole table, header included') }, closes: true },
  { label: '#Data', insert: '#Data', get detail() { return t('the rows without the header') }, closes: true },
  { label: '#Headers', insert: '#Headers', get detail() { return t('the header row') }, closes: true },
  { label: '@', insert: '@', get detail() { return t('this row') }, closes: false },
]
const MAX_COMPLETIONS = 8

/** What to offer while a formula is typed (mock 5): after `Name[` the columns of that table and the special items,
 * after `Name[#` the special ones, after `Name[@` the columns, and for a word the names that start with it. Nothing
 * inside a string, after a sheet name or when the text is not a formula. `names` are the ones the formula's sheet sees. */
export function completionsAt(text: string, caret: number, names: NameInfo[], sheet: string): Completions | null {
  if (!text.startsWith('=')) return null
  const before = text.slice(0, Math.min(caret, text.length))
  if ((before.match(/"/g)?.length ?? 0) % 2 === 1) return null // inside a text
  const inBrackets = /([\p{L}_][\p{L}\p{M}\p{N}_.]*)\[(@|#)?([^[\]]*)$/u.exec(before)
  if (inBrackets) {
    const table = resolveName(names, sheet, inBrackets[1]!)
    if (!table) return null
    const lead = inBrackets[2] ?? ''
    const typed = inBrackets[3]!
    const wanted = typed.toLowerCase()
    const columns: Completion[] = table.columns.map((c) => ({ label: c.name, insert: escapeColumn(c.name), detail: c.type, closes: true }))
    const start = before.length - typed.length
    if (lead === '#') {
      const items = SPECIAL_ITEMS.filter((i) => i.insert.startsWith('#') && i.label.slice(1).toLowerCase().startsWith(wanted) && i.label.slice(1).toLowerCase() !== wanted)
      return items.length ? { from: start - 1, items } : null
    }
    const pool = lead === '@' ? columns : [...columns, ...SPECIAL_ITEMS]
    const items = pool.filter((i) => i.label.toLowerCase().startsWith(wanted) && i.label.toLowerCase() !== wanted)
    return items.length ? { from: start, items: items.slice(0, MAX_COMPLETIONS) } : null
  }
  const word = /(?<![\p{L}\p{N}_.!'])([\p{L}_][\p{L}\p{M}\p{N}_.]*)$/u.exec(before)
  if (!word) return null
  const typed = word[1]!.toLowerCase()
  const items = visibleNames(names, sheet)
    .filter((n) => n.region !== null && n.name.toLowerCase().startsWith(typed) && n.name.toLowerCase() !== typed)
    .map((n) => ({ label: n.name, insert: n.name, detail: n.kind === 'result' ? t('query result') : n.header ? t('table · {rows} rows', { rows: n.rows }) : t('cells'), closes: false }))
  return items.length ? { from: before.length - word[1]!.length, items: items.slice(0, MAX_COMPLETIONS) } : null
}

/** The text and caret after taking a completion: the typed word replaced, and for a column or `#All` and the like the
 * closing bracket put behind it — or, when the text has one there already, the caret moved past it. */
export function applyCompletion(text: string, caret: number, found: Completions, item: Completion): { text: string; caret: number } {
  const tail = text.slice(caret)
  const head = text.slice(0, found.from) + item.insert
  if (!item.closes) return { text: head + tail, caret: head.length }
  if (tail.startsWith(']')) return { text: head + tail, caret: head.length + 1 }
  return { text: `${head}]${tail}`, caret: head.length + 1 }
}
