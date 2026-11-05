// Pointing at cells while typing a formula: where a reference may go, how a selection is written as one, and which
// references a formula holds (so that the grid can outline them).
import { cellLabel, columnIndex, columnName, MAX_COLS, MAX_ROWS } from './cells'
import { bounds, type Sel, type Size } from './selection'

/** The part of the text a picked reference replaces (empty when it is only inserted). */
export interface Slot {
  start: number
  end: number
}

const CELL = String.raw`\$?[A-Za-z]{1,3}\$?\d+`
const COLUMN = String.raw`\$?[A-Za-z]{1,3}`
const ROW = String.raw`\$?\d+`
const AREA = `(?:${CELL}(?::${CELL})?|${COLUMN}:${COLUMN}|${ROW}:${ROW})`
const SHEET = String.raw`(?:(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?`
const BEFORE = String.raw`(?<![A-Za-z0-9_.$'!])` // (a reference does not start inside a word)
const REFERENCE_AT_END = new RegExp(`${BEFORE}${SHEET}${AREA}$`)
const REFERENCE = new RegExp(`${BEFORE}(?:(?<sheet>'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)?(?<area>${AREA})(?![A-Za-z0-9_.(!])`, 'g')

/** After these a value is expected, so a picked reference fits there. */
const EXPECTING = '=(,+-*/^&<>'

/**
 * Where would a reference picked with the mouse go if the caret is at `caret` in `text`? It goes after a character
 * that expects a value (`=SUM(`, a comma, an operator); it replaces the reference that ends at the caret (the
 * previous pick, or one that was typed). Nowhere else: not in a text, not after a name, a number or a bracket.
 */
export function slotAt(text: string, caret: number): Slot | null {
  if (!text.startsWith('=') || caret < 1 || caret > text.length) return null
  const before = text.slice(0, caret)
  if ((before.match(/"/g)?.length ?? 0) % 2 === 1) return null // inside a text
  if (caret < text.length && !/[\s),+\-*/^&<>=%]/.test(text[caret]!)) return null // directly in front of a name
  const found = REFERENCE_AT_END.exec(before)
  if (found && found.index >= 1) return { start: found.index, end: caret }
  const last = before.trimEnd().slice(-1)
  return last !== '' && EXPECTING.includes(last) ? { start: caret, end: caret } : null
}

/** The text with the picked reference in place, and where the caret goes; null if nothing may be picked there. */
export function pointTo(text: string, caret: number, reference: string): { text: string; caret: number } | null {
  const slot = slotAt(text, caret)
  if (!slot) return null
  return { text: text.slice(0, slot.start) + reference + text.slice(slot.end), caret: slot.start + reference.length }
}

/** `Name!`, quoted when the name could be taken for something else (as the server writes it). */
export function sheetPrefix(name: string): string {
  const plain = /^[A-Za-z_][A-Za-z0-9_.]*$/.test(name) && !/^\$?[A-Za-z]{1,3}\$?\d+$/.test(name) && !/^(true|false)$/i.test(name)
  return `${plain ? name : `'${name.replaceAll("'", "''")}'`}!`
}

/** A selection as a reference: `B2`, `B2:C5`, `B:B` for whole columns, `3:4` for whole rows; null for the whole sheet. */
export function refOf(sel: Sel, size: Size, prefix = ''): string | null {
  const { r0, c0, r1, c1 } = bounds(sel)
  const wholeColumns = r0 === 0 && r1 === size.rows - 1
  const wholeRows = c0 === 0 && c1 === size.cols - 1
  if (wholeColumns && wholeRows) return null
  if (wholeColumns) return `${prefix}${columnName(c0)}:${columnName(c1)}`
  if (wholeRows) return `${prefix}${r0 + 1}:${r1 + 1}`
  const first = cellLabel(r0, c0)
  return prefix + (r0 === r1 && c0 === c1 ? first : `${first}:${cellLabel(r1, c1)}`)
}

/** A reference in a formula: where it stands in the text, its sheet (null: the sheet of the formula) and its cells. */
export interface Reference {
  start: number
  end: number
  sheet: string | null
  r0: number
  c0: number
  r1: number
  c1: number
}

function corner(part: string): { row: number | null; col: number | null } {
  const m = /^\$?([A-Za-z]+)?\$?(\d+)?$/.exec(part)!
  return { col: m[1] ? columnIndex(m[1]) : null, row: m[2] ? Number(m[2]) - 1 : null }
}

/** The references of a formula, in the order they stand; texts are not looked into. */
export function referencesIn(text: string): Reference[] {
  if (!text.startsWith('=')) return []
  const masked = text.replace(/"(?:[^"]|"")*"?/g, (s) => ' '.repeat(s.length))
  const out: Reference[] = []
  for (const m of masked.matchAll(REFERENCE)) {
    const ends = m.groups!.area!.split(':')
    const a = corner(ends[0]!)
    const b = corner(ends[1] ?? ends[0]!)
    const rows = [a.row, b.row].filter((n): n is number => n !== null)
    const cols = [a.col, b.col].filter((n): n is number => n !== null)
    const quoted = m.groups!.sheet
    out.push({
      start: m.index,
      end: m.index + m[0].length,
      sheet: quoted === undefined ? null : quoted.startsWith("'") ? quoted.slice(1, -1).replaceAll("''", "'") : quoted,
      r0: rows.length ? Math.min(...rows) : 0,
      r1: rows.length ? Math.max(...rows) : MAX_ROWS - 1,
      c0: cols.length ? Math.min(...cols) : 0,
      c1: cols.length ? Math.max(...cols) : MAX_COLS - 1,
    })
  }
  return out
}

/** Colours for outlining the references of a formula, in turn (the same order in the grid and in the text). */
export const REFERENCE_COLORS = ['var(--iris)', 'var(--rose)', 'var(--apricot)', 'var(--teal)', 'var(--app-dark)']
