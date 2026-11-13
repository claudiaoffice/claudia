// Cells as people see and type them: A1 labels, how a stored value is shown, and what typing it again would need.
import type { Alt, Summary } from './outcomes'
import { render, type NumberSymbols, type Rendered } from './number-format'

/** What a cell holds as the server sends it. A formula comes as the value it gave, with its text under `f`; an error
 * (`t: 'error'`) has its code in `v` and may say why under `d`. */
export type Content = {
  t: 'int' | 'float' | 'text' | 'bool' | 'error'
  v: number | string | boolean
  f?: string
  d?: string
  /** The cell shows a part of a query result: it is not stored and cannot be typed into (E6.5). */
  spill?: boolean
  /** For such a cell, the `[row, col]` of the formula that fills it. */
  from?: [number, number]
  /** An input with alternatives, `{800, 1000, 1300}` (E6.21): each alternative as typed content. `f` is what was typed. */
  alts?: Alt[]
  /** A result of alternatives: what came out of running each of them through the calculation (E6.21). */
  out?: Summary
} | null

export const MAX_ROWS = 1_048_576
export const MAX_COLS = 16_384

/** 0 → A, 25 → Z, 26 → AA */
export function columnName(index: number): string {
  let name = ''
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + ((n - 1) % 26)) + name
  return name
}

export function columnIndex(letters: string): number {
  let n = 0
  for (const ch of letters.toUpperCase()) n = n * 26 + (ch.charCodeAt(0) - 64)
  return n - 1
}

export function cellLabel(row: number, col: number): string {
  return `${columnName(col)}${row + 1}`
}

export function rangeLabel(r0: number, c0: number, r1: number, c1: number): string {
  const a = cellLabel(Math.min(r0, r1), Math.min(c0, c1))
  const b = cellLabel(Math.max(r0, r1), Math.max(c0, c1))
  return a === b ? a : `${a}:${b}`
}

/** `B3` → [2, 1]; null if it is not a cell label */
export function parseCell(text: string): [number, number] | null {
  const m = /^([A-Za-z]{1,3})([0-9]{1,7})$/.exec(text.trim())
  if (!m) return null
  const row = Number(m[2]) - 1
  const col = columnIndex(m[1]!)
  return row >= 0 && row < MAX_ROWS && col < MAX_COLS ? [row, col] : null
}

/** The text a cell shows through a number format (`code`, Excel's; `null`: General) in the reader's way of writing
 * numbers (D348). Errors and TRUE/FALSE are never formatted; text only by a code with a text section. */
export function showFormatted(content: Content, code: string | null, symbols: NumberSymbols): Rendered {
  if (content === null) return { text: '', colour: null }
  if (code === null || content.t === 'error' || content.t === 'bool') return { text: show(content), colour: null }
  const value = content.t === 'text' ? String(content.v) : Number(content.v)
  return render(value, code, symbols)
}

/** The text a cell shows. */
export function show(content: Content): string {
  if (content === null) return ''
  if (content.t === 'bool') return content.v ? 'TRUE' : 'FALSE'
  if (content.t === 'float') return Number(content.v).toLocaleString('en-US', { maximumFractionDigits: 10, useGrouping: false })
  return String(content.v)
}

export function alignment(content: Content): 'left' | 'right' | 'center' {
  if (content === null) return 'left'
  if (content.t === 'int' || content.t === 'float') return 'right'
  return content.t === 'bool' || content.t === 'error' ? 'center' : 'left'
}

/** The formula of a cell, or null if it holds a plain value. */
export function formulaOf(content: Content): string | null {
  return content?.f ?? null
}

const INT = /^[+-]?[0-9]+$/
const FLOAT = /^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/

/** What to type to get exactly this content: text that would be read as something else gets the apostrophe. */
export function inputOf(content: Content): string {
  if (content === null) return ''
  if (content.f !== undefined) return content.f // a formula is edited as the formula, not as what it gave
  if (content.t === 'bool') return content.v ? 'TRUE' : 'FALSE'
  if (content.t === 'int' || content.t === 'float') return String(content.v)
  const text = String(content.v)
  const word = text.trim()
  const ambiguous =
    text.startsWith("'") ||
    word === '' ||
    word.startsWith('=') ||
    INT.test(word) ||
    FLOAT.test(word) ||
    /^(true|false)$/i.test(word)
  return ambiguous ? `'${text}` : text
}

/** The part of the sheet the grid lets people scroll to (the server allows more). */
export const VIEW_ROWS = 10_000
export const VIEW_COLS = 702
