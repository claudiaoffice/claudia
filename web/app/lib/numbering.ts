// Lists, numbered headings and numbering schemes as every app's client knows them (E9.21, E9.22; step D of
// claudiaoffice-log/notes/text-structure-across-apps.md). The numbering itself is the server's: what a client asks for
// is structure — make these paragraphs a list, number the headings, change a scheme — and the markers arrive as
// `labels` events. This module holds the shapes of what the server sends and what the menus and the numbering manager
// work out from them; the requests are the sessions' (`BaseSession.numberHeadings` and the others).

/** A list of the document (the server's `lists`): its scheme, the number it starts at and, when it has one, its name. */
export interface ListInfo {
  id: string
  scheme: string
  start: number
  name: string | null
}

/** One level of a scheme: the format of its counter (or a bullet, or nothing), the text around it and the first level
 * whose counter it shows (its own level: `b.`; 0: the whole trail, `2.1.3`). */
export interface LevelFormat {
  format: NumberFormat
  bullet: string
  before: string
  after: string
  from_level: number
}

export type NumberFormat = 'decimal' | 'lower-alpha' | 'upper-alpha' | 'lower-roman' | 'upper-roman' | 'bullet' | 'none'
export const NUMBER_FORMATS: readonly NumberFormat[] = ['decimal', 'lower-alpha', 'upper-alpha', 'lower-roman', 'upper-roman', 'bullet', 'none']
/** The built-in schemes: they can be changed and reset, never removed (`reset_scheme`). */
export const BUILT_IN_SCHEMES: readonly string[] = ['bullets', 'numbers', 'chapters']
export const LEVELS = 9

/** How a list looks (the server's `schemes`): whether it counts, each of its nine levels, how far a level moves the
 * text in and the gap between two items, both in em. */
export interface SchemeInfo {
  id: string
  name: string
  kind: 'bullet' | 'number'
  levels: LevelFormat[]
  indent: number
  gap: number
}

/** What a style says about headings and numbering, as the server's style views carry it. */
export interface NumberedStyle {
  id: string
  name: string
  kind?: string
  /** The heading level it gives (worked out along its parents): 0 the title, 1 to 9 a level, `null` none. */
  heading?: number | null
  /** Its own numbering: a list id, `"none"` (not numbered) or absent (as its parent). */
  numbering?: string | null
  /** The list it numbers its paragraphs in, worked out along its parents; `null` for none. */
  numbered?: string | null
}

const ROMAN: [number, string][] = [[1000, 'm'], [900, 'cm'], [500, 'd'], [400, 'cd'], [100, 'c'], [90, 'xc'], [50, 'l'], [40, 'xl'], [10, 'x'], [9, 'ix'], [5, 'v'], [4, 'iv'], [1, 'i']]

function alpha(n: number): string {
  let out = ''
  while (n > 0) {
    const rest = (n - 1) % 26
    out = String.fromCharCode(97 + rest) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}

function roman(n: number): string {
  if (n < 1 || n > 3999) return String(n)
  let out = ''
  for (const [value, letters] of ROMAN) {
    while (n >= value) {
      out += letters
      n -= value
    }
  }
  return out
}

/** `n` as a level of this format writes it (the trail of a level that writes none uses digits). */
export function counter(format: NumberFormat, n: number): string {
  switch (format) {
    case 'lower-alpha':
      return alpha(n)
    case 'upper-alpha':
      return alpha(n).toUpperCase()
    case 'lower-roman':
      return roman(n)
    case 'upper-roman':
      return roman(n).toUpperCase()
    default:
      return String(n)
  }
}

/** What a scheme draws for the counters `path` (outermost first): the numbering manager's preview. It is the same rule
 * as the server's `Scheme.marker`; the document's markers are never worked out here. */
export function markerOf(scheme: SchemeInfo, path: number[]): string {
  const level = path.length - 1
  const own = scheme.levels[Math.min(level, scheme.levels.length - 1)]
  if (!own) return ''
  if (own.format === 'bullet') return `${own.before}${own.bullet}${own.after}`
  if (own.format === 'none') return `${own.before}${own.after}`
  const trail = path.slice(own.from_level).map((n, i) => counter(scheme.levels[own.from_level + i]?.format ?? 'decimal', n))
  return `${own.before}${trail.join('.')}${own.after}`
}

/** Are the headings numbered: does any style that gives a heading level of 1 or more number its paragraphs? What
 * Number Headings (Number All Slide Titles) is ticked by. */
export function headingsNumbered(styles: readonly NumberedStyle[]): boolean {
  return styles.some((s) => (s.heading ?? 0) >= 1 && !!s.numbered)
}

/** Can the headings be numbered at all: is there a style that gives a heading level of 1 or more? */
export function hasHeadingStyles(styles: readonly NumberedStyle[]): boolean {
  return styles.some((s) => (s.kind ?? 'paragraph') === 'paragraph' && (s.heading ?? 0) >= 1)
}

/** What a scheme is used by: the lists drawn with it and the styles numbered in those lists (the manager's "Used by"). */
export function usersOf(scheme: string, lists: readonly ListInfo[], styles: readonly NumberedStyle[]): { lists: ListInfo[]; styles: NumberedStyle[] } {
  const own = lists.filter((l) => l.scheme === scheme)
  const ids = new Set(own.map((l) => l.id))
  return { lists: own, styles: styles.filter((s) => !!s.numbering && ids.has(s.numbering)) }
}

/** What the numbering manager (`NumberingDialog.vue`) asks of an app: the books, and the session's requests. */
export interface NumberingHost {
  schemes: SchemeInfo[]
  lists: ListInfo[]
  styles: NumberedStyle[]
  readOnly: boolean
  newScheme(like: string, name: string): Promise<string | null>
  changeScheme(scheme: SchemeInfo): Promise<boolean>
  resetScheme(scheme: string): Promise<boolean>
  removeScheme(scheme: string): Promise<boolean>
}

/** A choice of the style editor's Numbering row: `'inherit'`, `'none'` or a list id. */
export interface NumberingChoice {
  value: string
  label: string
}

/** What a list is called in a choice: its name (or id) and its scheme's ("Outline · Chapters"). */
export function listName(list: ListInfo, schemes: readonly SchemeInfo[]): string {
  const scheme = schemes.find((s) => s.id === list.scheme)
  return `${list.name ?? list.id} · ${scheme?.name ?? list.scheme}`
}

/** The choices of the Numbering row for a heading style (E9.22, `composes-numbered-headings.svg`, C): as its parent
 *  (and what that gives), not numbered, or a list of the document. */
export function numberingChoices(
  style: NumberedStyle & { based_on?: string | null },
  styles: readonly NumberedStyle[],
  lists: readonly ListInfo[],
  schemes: readonly SchemeInfo[],
  t: (text: string, values?: Record<string, string | number>) => string,
): NumberingChoice[] {
  const parent = style.based_on ? styles.find((s) => s.id === style.based_on) : undefined
  const given = parent?.numbered ? lists.find((l) => l.id === parent.numbered) : undefined
  const inherited = parent ? t('As “{name}”: {numbering}', { name: parent.name, numbering: given ? listName(given, schemes) : t('not numbered') }) : t('Not numbered (no parent)')
  return [
    { value: 'inherit', label: inherited },
    { value: 'none', label: t('Not numbered') },
    ...lists.map((l) => ({ value: l.id, label: listName(l, schemes) })),
  ]
}

/** The choice that shows a style's own numbering. */
export function numberingValue(style: NumberedStyle): string {
  return style.numbering ?? 'inherit'
}
