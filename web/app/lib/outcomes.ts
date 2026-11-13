// What a cell with alternatives and a cell that depends on them show, and what the outcome pop-over works out (E6.21,
// D294–D296). The server runs the alternatives through the calculation; this module only turns what it sends into
// the chips, the median and the dots a person reads. No Vue and no DOM, so it is tested in Node.
import { createTranslator } from './i18n'
import { show, type Content } from './cells'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string
const plain: Translate = createTranslator({})

/** An alternative of an input as `cells` sends it: typed content, and `l` when it has a name (a scenario). */
export type Alt = NonNullable<Content> & { l?: string }

/** What the server says of the outcomes of a result cell (`Summary.to_data`). */
export interface Summary {
  n: number
  errors: number
  sampled: boolean
  min: number | null
  max: number | null
  median: number | null
  mean: number | null
  points: number[]
}

export interface OutcomeInput {
  sheet: string
  row: number
  col: number
  count: number
  labels: (string | null)[]
  /** The text next to the input cell, which names it. */
  label: string | null
}
export interface OutcomeRow {
  /** For each input of the table, the position of its alternative in this outcome. */
  choice: number[]
  value: Content
}
export interface Swing {
  input: number
  low: number
  high: number
  low_choice: number
  high_choice: number
}
/** The answer of `outcome_table`. */
export interface OutcomeTable {
  inputs: OutcomeInput[]
  rows: OutcomeRow[]
  sampled: boolean
  sensitivity: Swing[]
}

/** One alternative as a person reads it: its value, and its name before it for a named scenario ("low: 800"). */
export function altText(alt: Alt): string {
  const value = show(alt)
  return alt.l ? `${alt.l}: ${value}` : value
}

/** The chips of an input cell: each alternative's value, a scenario's name in front of it. */
export function chipsOf(alts: Alt[]): string[] {
  return alts.map((alt) => (alt.l ? `${alt.l} ${show(alt)}` : show(alt)))
}

/** "9 outcomes", "2000 samples", "9 outcomes, 2 errors". */
export function outcomeCaption(summary: Summary, t: Translate = plain): string {
  const what = summary.sampled
    ? t('{n} samples', { n: summary.n })
    : summary.n === 1
      ? t('{n} outcome', { n: summary.n })
      : t('{n} outcomes', { n: summary.n })
  if (summary.errors === 0) return what
  return summary.errors === 1 ? t('{what}, {n} error', { what, n: summary.errors }) : t('{what}, {n} errors', { what, n: summary.errors })
}

/** Where the dots of a result cell go, as fractions from the least (0) to the greatest (1) outcome. More outcomes than
 * fit are thinned, evenly through the sorted ones. Equal outcomes sit in the middle. */
export function dotFractions(points: number[], most = 24): number[] {
  if (points.length === 0) return []
  let chosen = points
  if (points.length > most) {
    const sorted = [...points].sort((a, b) => a - b)
    chosen = Array.from({ length: most }, (_, i) => sorted[Math.round((i * (sorted.length - 1)) / (most - 1))]!)
  }
  const low = Math.min(...points)
  const high = Math.max(...points)
  return chosen.map((p) => (high === low ? 0.5 : (p - low) / (high - low)))
}

/** A statistic as the pop-over writes it: grouped thousands, two decimals at most, a real minus sign. */
export function stat(value: number | null): string {
  if (value === null) return '–'
  const text = value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return text.replace('-', '−')
}

/** How many outcomes lie below `threshold`. */
export function shareBelow(points: number[], threshold: number): { below: number; total: number; percent: number } {
  const below = points.filter((p) => p < threshold).length
  return { below, total: points.length, percent: points.length === 0 ? 0 : Math.round((below / points.length) * 100) }
}

/** The inputs' names: the text beside each input cell, else "Input 2". */
export function inputNames(table: OutcomeTable, t: Translate = plain): string[] {
  return table.inputs.map((input, i) => input.label ?? t('Input {n}', { n: i + 1 }))
}

/** Whether "pair by position" can be asked for: several inputs with as many alternatives each. */
export function canPair(table: OutcomeTable): boolean {
  return table.inputs.length >= 2 && table.inputs.every((i) => i.count === table.inputs[0]!.count)
}

/** How dark the dot of alternative `index` of `count` is, from 0 (the first) to 1 (the last). */
export function shadeOf(index: number, count: number): number {
  return count <= 1 ? 1 : index / (count - 1)
}

export interface Bar {
  input: number
  name: string
  low: number
  high: number
  /** The bar from `from` to `to`, as fractions of the axis (the least low to the greatest high). */
  from: number
  to: number
  /** Where the average outcome is on that axis. */
  mean: number
}

/** "What moves the result most": one bar per input, widest first as the server sends them, on one axis. */
export function tornado(table: OutcomeTable, t: Translate = plain): Bar[] {
  if (table.sensitivity.length === 0) return []
  const names = inputNames(table, t)
  const low = Math.min(...table.sensitivity.map((s) => s.low))
  const high = Math.max(...table.sensitivity.map((s) => s.high))
  const values = table.rows.map((r) => r.value).filter((v): v is NonNullable<Content> => v !== null && (v.t === 'int' || v.t === 'float'))
  const average = values.length ? values.reduce((sum, v) => sum + Number(v.v), 0) / values.length : (low + high) / 2
  const at = (v: number) => (high === low ? 0.5 : (v - low) / (high - low))
  return table.sensitivity.map((s) => ({ input: s.input, name: names[s.input] ?? '', low: s.low, high: s.high, from: at(s.low), to: at(s.high), mean: at(average) }))
}

/** The outcomes as text a spreadsheet takes on paste: a column per input and the result's. `altOf` says what an
 * input's alternative is called. */
export function outcomesToTsv(table: OutcomeTable, altOf: (input: number, choice: number) => string, result: string, t: Translate = plain): string {
  const head = [...inputNames(table, t), result].join('\t')
  const lines = table.rows.map((row) => [...row.choice.map((c, i) => altOf(i, c)), show(row.value)].join('\t'))
  return [head, ...lines].join('\n')
}

export interface TypingHint {
  kind: 'list' | 'range' | 'named'
  count: number
}

/** The items of `{…}` split at the commas that are not inside brackets, braces or quotes. */
function items(inner: string): string[] {
  const out: string[] = []
  let depth = 0
  let quote = false
  let start = 0
  for (let i = 0; i < inner.length; i++) {
    const ch = inner[i]
    if (ch === '"') quote = !quote
    else if (!quote && (ch === '(' || ch === '{' || ch === '[')) depth++
    else if (!quote && (ch === ')' || ch === '}' || ch === ']')) depth--
    else if (!quote && depth === 0 && ch === ',') {
      out.push(inner.slice(start, i))
      start = i + 1
    }
  }
  out.push(inner.slice(start))
  return out
}

const RANGE = /^\s*(-?\d+(?:\.\d+)?)\s*\.\.\s*(-?\d+(?:\.\d+)?)(?:\s+step\s+(-?\d+(?:\.\d+)?))?\s*$/
const NAMED = /^\s*[A-Za-z_][\w ]*:/

/** What typing `{…}` into a cell means, for the hint under the cell: how many alternatives, and of which kind. `null`
 * for anything that is not alternatives or not complete yet. */
export function typingHint(text: string): TypingHint | null {
  const word = text.trim()
  if (!word.startsWith('{') || !word.endsWith('}')) return null
  const inner = word.slice(1, -1)
  if (inner.trim() === '') return null
  const parts = items(inner)
  if (parts.length === 1) {
    const range = RANGE.exec(parts[0]!)
    if (range) {
      const [from, to, step] = [Number(range[1]), Number(range[2]), range[3] === undefined ? 1 : Number(range[3])]
      if (step === 0 || (to - from) * step < 0) return null
      return { kind: 'range', count: Math.floor((to - from) / step + 1e-9) + 1 }
    }
  }
  if (parts.every((p) => NAMED.test(p))) return { kind: 'named', count: parts.length }
  return { kind: 'list', count: parts.length }
}
