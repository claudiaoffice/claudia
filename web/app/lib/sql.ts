// The SQL editor's text work (E4.9/E6.5, mock 4): reading the query out of a `=SQL("…")` cell, putting a word where
// the caret is, and how long a preview took. Pure, so every rule is tested (`tests/sql.test.ts`).
import { translate as t } from './i18n'
import { currentLocale } from './locale'

/** The query of a cell that holds exactly `=SQL("…")`, or `null` for any other formula — one with parameters or
 * something around the call is edited as the formula it is, not in the editor, which could not give it back. Inside
 * the string a quote is written `""`. */
export function queryOfFormula(formula: string | null | undefined): string | null {
  if (!formula) return null
  const found = /^=\s*SQL\s*\(\s*"((?:[^"]|"")*)"\s*\)\s*$/i.exec(formula)
  return found ? found[1]!.replace(/""/g, '"') : null
}

/** `text` with `insert` at `caret` (or over the selection `caret..end`), and where the caret ends up. */
export function insertAt(text: string, caret: number, insert: string, end = caret): { text: string; caret: number } {
  const at = Math.max(0, Math.min(caret, text.length))
  const to = Math.max(at, Math.min(end, text.length))
  return { text: text.slice(0, at) + insert + text.slice(to), caret: at + insert.length }
}

/** "12 rows · 0.4 ms", singular and rounded the way the preview chips say it. */
export function previewSummary(rowCount: number, ms: number, capped: boolean): string {
  const count = rowCount.toLocaleString(currentLocale())
  const rows = rowCount === 1 ? t('{count} row', { count }) : t('{count} rows', { count })
  const time = ms < 1 ? '< 1 ms' : `${Math.round(ms)} ms`
  return `${rows}${capped ? '+' : ''} · ${time}`
}

/** How one value of a preview is written in a cell of the preview table. */
export function previewCell(value: string | number | boolean | null): string {
  if (value === null) return ''
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE'
  return String(value)
}
