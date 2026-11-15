// Pivot tables on the client (E6.30, D620–D626): the wire shapes of the `pivots` method, the rules of the field panel —
// which box a field may be in, what ticking one does — the words a pivot writes into its cells, and which cells of a
// sheet are a pivot's header, label or total (mock 1). Pure: no component and no connection in here, so every rule has
// a test (`tests/pivots.test.ts`).

import { parseCell } from './cells'
import { translate as t } from './i18n'
import { nameProblem, type NameColumn, type NameInfo } from './names'

/** How the values of a field are put together (`claudia_computes.pivot.Aggregation`). */
export type Aggregation = 'sum' | 'count' | 'average' | 'min' | 'max'
/** A member of a field: a value of the source's column. */
export type Member = string | number | null
export interface PivotValueField {
  field: string
  aggregation: Aggregation
  /** The title in the pivot's header; empty for the usual "Sum of Amount". */
  name: string
}
export interface PivotFilter {
  field: string
  /** The members that stay in; `null` keeps them all. */
  keep: Member[] | null
}
/** What a pivot is made from — `claudia_computes.PivotDefinition.to_data`. At most one row and one column field in this
 * version (D621). */
export interface PivotDefinition {
  format: 1
  source: string
  rows: string[]
  columns: string[]
  values: PivotValueField[]
  filters: PivotFilter[]
  total_row: boolean
  total_column: boolean
}
/** The words a pivot writes into its own cells, in the language the person who made it speaks. */
export interface PivotLabels {
  total: string
  blank: string
  row_header: string
  sum_of: string
  count_of: string
  average_of: string
  min_of: string
  max_of: string
}
export type PivotRoleName = 'corner' | 'field' | 'header'
export interface PivotRegion {
  sheet: string
  row0: number
  col0: number
  row1: number
  col1: number
}
/** A pivot as `pivots` sends it. `region` is `null` while it has no result (its source or a field is missing, see
 * `error`); `placed` is `false` when its cell has been written over. */
export interface PivotInfo {
  name: string
  definition: PivotDefinition
  labels: PivotLabels
  anchor: { sheet: string; row: number; col: number } | null
  region: PivotRegion | null
  a1: string | null
  placed: boolean
  error: { code: string; detail: string } | null
  header_rows: number
  header_roles: PivotRoleName[][]
  total_row: boolean
  total_column: boolean
}

/** The four boxes of the field panel, in the order the mock lays them out. */
export type Zone = 'filters' | 'columns' | 'rows' | 'values'
export const ZONES: Zone[] = ['filters', 'columns', 'rows', 'values']

export function zoneLabel(zone: Zone): string {
  switch (zone) {
    case 'filters':
      return t('Filters')
    case 'columns':
      return t('Columns')
    case 'rows':
      return t('Rows')
    case 'values':
      return t('Values')
  }
}

export const AGGREGATIONS: { value: Aggregation; label: string; hint: string }[] = [
  { value: 'sum', get label() { return t('Sum') }, get hint() { return t('adds the values') } },
  { value: 'count', get label() { return t('Count') }, get hint() { return t('how many rows') } },
  { value: 'average', get label() { return t('Average') }, get hint() { return t('the mean of the values') } },
  { value: 'min', get label() { return t('Min') }, get hint() { return t('the smallest value') } },
  { value: 'max', get label() { return t('Max') }, get hint() { return t('the largest value') } },
]

/** What a field is summarized by when it is put into Values: numbers are added up, anything else is counted. */
export function defaultAggregation(type: NameColumn['type'] | undefined): Aggregation {
  return type === 'int' || type === 'real' ? 'sum' : 'count'
}

/** The words a new pivot is given to write into its cells, in the language of this session. `{field}` stays in the
 * words: the server puts the field's name there. */
export function pivotLabels(): PivotLabels {
  const field = '{field}'
  return {
    total: t('Total'),
    blank: t('(blank)'),
    row_header: t('Rows'),
    sum_of: t('Sum of {field}', { field }),
    count_of: t('Count of {field}', { field }),
    average_of: t('Average of {field}', { field }),
    min_of: t('Min of {field}', { field }),
    max_of: t('Max of {field}', { field }),
  }
}

/** The title of a value field in the pivot: its own name, else "Sum of Amount" in the pivot's words. */
export function valueTitle(value: PivotValueField, labels: PivotLabels): string {
  if (value.name) return value.name
  const template = { sum: labels.sum_of, count: labels.count_of, average: labels.average_of, min: labels.min_of, max: labels.max_of }[value.aggregation]
  return template.replace('{field}', value.field)
}

/** A definition with nothing chosen yet: what Create gives (the field panel opens on it). */
export function emptyDefinition(source: string): PivotDefinition {
  return { format: 1, source, rows: [], columns: [], values: [], filters: [], total_row: true, total_column: true }
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase() // the engine finds a field without regard to case

/** The boxes of rows, columns and filters hold a field once at most; Values may hold it besides. */
export function zonesOf(def: PivotDefinition, field: string): Zone[] {
  const zones: Zone[] = []
  if (def.filters.some((f) => same(f.field, field))) zones.push('filters')
  if (def.columns.some((c) => same(c, field))) zones.push('columns')
  if (def.rows.some((r) => same(r, field))) zones.push('rows')
  if (def.values.some((v) => same(v.field, field))) zones.push('values')
  return zones
}

export const isTicked = (def: PivotDefinition, field: string): boolean => zonesOf(def, field).length > 0

/** The box a field is placed in (rows, columns, filters; values when only there), or `null`. */
export function zoneOf(def: PivotDefinition, field: string): Zone | null {
  return zonesOf(def, field)[0] ?? null
}

export const LIMIT: Record<'rows' | 'columns', number> = { rows: 1, columns: 1 }

export interface Placed {
  definition: PivotDefinition
  /** The field that was in the box and has had to go to make room (one row and one column field in this version). */
  displaced: string | null
}

function without(def: PivotDefinition, field: string, keepValues: boolean): PivotDefinition {
  return {
    ...def,
    rows: def.rows.filter((r) => !same(r, field)),
    columns: def.columns.filter((c) => !same(c, field)),
    filters: def.filters.filter((f) => !same(f.field, field)),
    values: keepValues ? def.values : def.values.filter((v) => !same(v.field, field)),
  }
}

/** `field` moved to `zone`. Out of the box it was in (its filter's choice of members goes with it); into Values it is
 * summed or counted as its type says, and stays in the box it was in too. When rows or columns is full, the field that
 * was there goes back to the list and is named in `displaced`. */
export function placeField(def: PivotDefinition, field: string, zone: Zone, type?: NameColumn['type']): Placed {
  if (zone === 'values') {
    if (def.values.some((v) => same(v.field, field))) return { definition: def, displaced: null }
    return { definition: { ...def, values: [...def.values, { field, aggregation: defaultAggregation(type), name: '' }] }, displaced: null }
  }
  const cleared = without(def, field, true)
  if (zone === 'filters') return { definition: { ...cleared, filters: [...cleared.filters, { field, keep: null }] }, displaced: null }
  const room = LIMIT[zone]
  const kept = cleared[zone].slice(0, room - 1)
  const displaced = cleared[zone].length >= room ? (cleared[zone][room - 1] ?? null) : null
  return { definition: { ...cleared, [zone]: [...kept, field] }, displaced }
}

/** A chip dragged, or moved with its ▾ menu, to another box. A value chip that leaves Values goes out of it (one chip, not
 * the field's others); any other chip goes where it is put, and a field put into Values stays where it was too. */
export function moveChip(def: PivotDefinition, from: { zone: Zone; field: string; index: number }, to: Zone, type?: NameColumn['type']): Placed {
  if (from.zone === to) return { definition: def, displaced: null }
  if (from.zone === 'values') return placeField(removeValue(def, from.index), from.field, to, type)
  return placeField(def, from.field, to, type)
}

/** `field` taken out of every box. */
export function removeField(def: PivotDefinition, field: string): PivotDefinition {
  return without(def, field, false)
}

/** Ticking a field in the list, as Excel does: numbers go to Values, text to Rows, then Columns, then Filters; ticking
 * it off takes it out of every box. */
export function toggleField(def: PivotDefinition, field: string, type: NameColumn['type'] | undefined): Placed {
  if (isTicked(def, field)) return { definition: removeField(def, field), displaced: null }
  if (type === 'int' || type === 'real') return placeField(def, field, 'values', type)
  if (def.rows.length < LIMIT.rows) return placeField(def, field, 'rows', type)
  if (def.columns.length < LIMIT.columns) return placeField(def, field, 'columns', type)
  return placeField(def, field, 'filters', type)
}

/** The boxes the ▾ menu of a chip offers: every one but the box the chip is in (a value chip is in Values, and may go
 * to the others too, where it then also stays). */
export function moveTargets(zone: Zone): Zone[] {
  return ZONES.filter((z) => z !== zone)
}

/** A value field changed: another way to summarize it, or another title. */
export function setValue(def: PivotDefinition, index: number, patch: Partial<Pick<PivotValueField, 'aggregation' | 'name'>>): PivotDefinition {
  return { ...def, values: def.values.map((v, i) => (i === index ? { ...v, ...patch } : v)) }
}

/** A value field taken out, one chip (a field may be in Values more than once). */
export function removeValue(def: PivotDefinition, index: number): PivotDefinition {
  return { ...def, values: def.values.filter((_, i) => i !== index) }
}

/** The members of a filter that stay in, changed. `null`, or every member, keeps them all. */
export function setKeep(def: PivotDefinition, field: string, keep: Member[] | null): PivotDefinition {
  return { ...def, filters: def.filters.map((f) => (same(f.field, field) ? { ...f, keep } : f)) }
}

/** What the panel says under the boxes when something is not complete, or `null`. */
export function definitionHint(def: PivotDefinition): string | null {
  if (!def.values.length) return t('Put a field into Values to see numbers.')
  return null
}

/** The chips a box shows: for Values the title of each value field, otherwise the field names. `index` is the place in
 * the definition's own list, which an edit needs. */
export interface Chip {
  zone: Zone
  field: string
  index: number
  label: string
  /** For a filter: "(All)" or how many members stay in. */
  detail: string | null
}
export function chipsOf(def: PivotDefinition, zone: Zone, labels: PivotLabels): Chip[] {
  switch (zone) {
    case 'rows':
      return def.rows.map((field, index) => ({ zone, field, index, label: field, detail: null }))
    case 'columns':
      return def.columns.map((field, index) => ({ zone, field, index, label: field, detail: null }))
    case 'filters':
      return def.filters.map((f, index) => ({
        zone,
        field: f.field,
        index,
        label: f.field,
        detail: f.keep === null ? t('(All)') : t('{count} kept', { count: f.keep.length }),
      }))
    case 'values':
      return def.values.map((v, index) => ({ zone, field: v.field, index, label: valueTitle(v, labels), detail: null }))
  }
}

/** The word of a filter's member as it is listed: nothing is "(blank)". */
export function memberLabel(member: Member, labels: PivotLabels): string {
  return member === null ? labels.blank : String(member)
}

// ------------------------------------------------------------------------------ the source and the place
/** The names a pivot may read: tables, ranges and query results that have columns to be fields — not a pivot's own
 * result (a pivot of a pivot is for later, D626). */
export function sourceChoices(names: NameInfo[], pivots: Pick<PivotInfo, 'name'>[]): NameInfo[] {
  const own = new Set(pivots.map((p) => p.name.toLowerCase()))
  return names
    .filter((n) => n.scope === null && n.columns.length > 0 && (n.header || n.kind === 'result') && !own.has(n.name.toLowerCase()))
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
}

/** The source a dialog starts on: the table the cursor is in, else the only (or first) one. */
export function preselected(choices: NameInfo[], sheet: string, row: number, col: number): NameInfo | null {
  const inside = choices.find((n) => {
    const g = n.region
    return g !== null && g.sheet === sheet && row >= g.row0 && row <= g.row1 && col >= g.col0 && col <= g.col1
  })
  return inside ?? choices[0] ?? null
}

/** A name for a new pivot that is free: "SalesPivot", then "SalesPivot2", … */
export function suggestName(source: string, taken: string[]): string {
  const used = new Set(taken.map((n) => n.toLowerCase()))
  const base = /^[\p{L}_]/u.test(source) ? `${source}${t('Pivot')}` : t('Pivot')
  for (let n = 1; ; n++) {
    const candidate = n === 1 ? base : `${base}${n}`
    if (!used.has(candidate.toLowerCase()) && nameProblem(candidate) === null) return candidate
  }
}

/** The problem with a pivot's name, or `null`: a name a formula can use, and not one of the workbook's already. */
export function pivotNameProblem(text: string, taken: string[]): string | null {
  const own = nameProblem(text)
  if (own) return own
  return taken.some((n) => n.toLowerCase() === text.toLowerCase()) ? t('{text} is a name already', { text }) : null
}

/** "Data!H11" or "H11" read as the cell a pivot starts in on `sheet`; `null` when it names another sheet or no cell. */
export function parsePlace(text: string, sheetName: string): { row: number; col: number } | null {
  const trimmed = text.trim()
  const bang = trimmed.lastIndexOf('!')
  if (bang >= 0) {
    const sheet = trimmed.slice(0, bang).replace(/^'(.*)'$/, '$1').replace(/''/g, "'")
    if (sheet.toLowerCase() !== sheetName.toLowerCase()) return null
  }
  const cell = parseCell(bang >= 0 ? trimmed.slice(bang + 1) : trimmed)
  return cell ? { row: cell[0], col: cell[1] } : null
}

// ------------------------------------------------------------------------------ the cells of a pivot (mock 1)
/** What a cell of a pivot is: the corner (field names), a field's title, a column member's header, a row label, a value
 * or a total. */
export type CellRole = 'corner' | 'field' | 'header' | 'label' | 'value' | 'total'

export function roleLabel(role: CellRole): string {
  switch (role) {
    case 'corner':
      return t('pivot table corner')
    case 'field':
      return t('pivot table field')
    case 'header':
      return t('pivot table column header')
    case 'label':
      return t('pivot table row label')
    case 'value':
      return t('pivot table value')
    case 'total':
      return t('pivot table total')
  }
}

/** The pivot whose cells (those it fills at the moment) contain this cell of `sheet`. */
export function pivotAt(pivots: PivotInfo[], sheet: string, row: number, col: number): PivotInfo | null {
  return (
    pivots.find((p) => {
      const g = p.region
      return g !== null && g.sheet === sheet && row >= g.row0 && row <= g.row1 && col >= g.col0 && col <= g.col1
    }) ?? null
  )
}

/** What the cell is in its pivot. Header rows say it themselves (the engine knows what the column field is); the first
 * column below is the labels, the last row and, with a total column, the last column are totals, the rest values. */
export function roleAt(pivot: PivotInfo, row: number, col: number): CellRole | null {
  const g = pivot.region
  if (!g || row < g.row0 || row > g.row1 || col < g.col0 || col > g.col1) return null
  const r = row - g.row0
  const c = col - g.col0
  if (r < pivot.header_rows) return pivot.header_roles[r]?.[c] ?? 'header'
  if (pivot.total_row && row === g.row1) return 'total'
  if (c === 0) return 'label'
  if (pivot.total_column && col === g.col1) return 'total'
  return 'value'
}

/** One rectangle painted under the cells of a pivot. */
export interface PivotBox {
  key: string
  role: CellRole
  pivot: PivotInfo
  r0: number
  c0: number
  r1: number
  c1: number
}

/** What to draw for the pivots in view: each header cell in its role, the labels' column, the total row and the total
 * column. Clipped to `view`, as `tableBoxes` is, so a pivot of 100 000 rows is a few boxes. */
export function pivotBoxes(pivots: PivotInfo[], sheet: string, view: { r0: number; r1: number; c0: number; c1: number }): PivotBox[] {
  const out: PivotBox[] = []
  for (const pivot of pivots) {
    const g = pivot.region
    if (!g || g.sheet !== sheet || g.row1 < view.r0 || g.row0 > view.r1 || g.col1 < view.c0 || g.col0 > view.c1) continue
    const c0 = Math.max(g.col0, view.c0)
    const c1 = Math.min(g.col1, view.c1)
    const headEnd = g.row0 + pivot.header_rows - 1
    for (let row = g.row0; row <= Math.min(headEnd, view.r1); row++) {
      if (row < view.r0) continue
      for (let col = c0; col <= c1; col++) {
        const role = roleAt(pivot, row, col)
        if (role) out.push({ key: `${pivot.name}:h${row}:${col}`, role, pivot, r0: row, c0: col, r1: row, c1: col })
      }
    }
    const bodyTop = Math.max(headEnd + 1, view.r0)
    const bodyEnd = Math.min(pivot.total_row ? g.row1 - 1 : g.row1, view.r1)
    if (g.col0 >= view.c0 && bodyTop <= bodyEnd) out.push({ key: `${pivot.name}:labels`, role: 'label', pivot, r0: bodyTop, c0: g.col0, r1: bodyEnd, c1: g.col0 })
    if (pivot.total_column && g.col1 <= view.c1 && g.col1 > g.col0 && bodyTop <= bodyEnd) {
      out.push({ key: `${pivot.name}:total-column`, role: 'total', pivot, r0: bodyTop, c0: g.col1, r1: bodyEnd, c1: g.col1 })
    }
    if (pivot.total_row && g.row1 > headEnd && g.row1 >= view.r0 && g.row1 <= view.r1) {
      out.push({ key: `${pivot.name}:total-row`, role: 'total', pivot, r0: g.row1, c0, r1: g.row1, c1 })
    }
  }
  return out
}

/** Which value field the cells of a column show: the one whose title is in the column's header cells (`texts`, top to
 * bottom), else the first. `null` when the pivot has no value field. */
export function valueIndexFor(pivot: Pick<PivotInfo, 'definition' | 'labels'>, texts: string[]): number | null {
  const values = pivot.definition.values
  if (!values.length) return null
  const found = values.findIndex((v) => texts.includes(valueTitle(v, pivot.labels)))
  return found >= 0 ? found : 0
}

/** What a new sheet for a pivot is called: the pivot's name, with a number after it while a sheet has that name. */
export function newSheetName(name: string, sheets: { name: string }[]): string {
  const taken = new Set(sheets.map((s) => s.name.toLowerCase()))
  for (let n = 1; ; n++) {
    const candidate = n === 1 ? name : `${name} ${n}`
    if (!taken.has(candidate.toLowerCase())) return candidate
  }
}

/** The line under the boxes: the cells the pivot fills, and that they are not typed over. */
export function fillsLine(pivot: PivotInfo): string {
  if (pivot.error) return t('It shows {code}: {detail}', { code: pivot.error.code, detail: pivot.error.detail })
  if (!pivot.placed) return t('Its cell was written over, so it shows nothing. Delete it and make it again.')
  return pivot.a1 ? t('Fills {range}. Its cells can’t be typed over.', { range: pivot.a1 }) : t('It fills nothing yet.')
}
