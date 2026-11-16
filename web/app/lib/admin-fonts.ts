// Server settings ▸ Fonts (E3.13 f, D1041): what the page and the Add fonts… dialog show of `GET /api/admin/fonts` and
// `POST /api/admin/fonts/check`, as plain functions the components call and the tests check without a DOM.
//
// The server says *what* (codes, counts, names); the words are made here, through the catalog, so the page speaks the
// App Language. Who may receive a collection's fonts is always a sign and a word (BITV: never colour alone).

type T = (msgid: string, vars?: Record<string, string | number>) => string

export type MayGo = 'anywhere' | 'this-server'
export type Origin = 'shipped' | 'operator' | 'added'

export interface FontStyleView {
  style: string
  weight: number
  italic: boolean
  sha256: string
  outlines: 'truetype' | 'cff'
  variable: boolean
}

export interface FontProblemView {
  file: string
  code: string
  detail: string
  family: string | null
  style: string | null
  collection?: string
}

export interface FontFamilyView {
  family: string
  styles: FontStyleView[]
  collection: string
  collection_id: string
  may_go: MayGo
  /** the office fonts (Arial) and generic families (sans-serif) this family is shown for */
  stands_in_for: string[]
  problems: FontProblemView[]
}

export interface FontCollectionView {
  id: string
  name: string
  origin: Origin
  editable: boolean
  licence: string
  may_go: MayGo
  families: string[]
  files: number
  problems: number
  added_by: string
  added: string
  source: string
}

export interface FontsPage {
  format: number
  counts: { families: number; files: number; collections: number; not_usable: number }
  collections: FontCollectionView[]
  families: FontFamilyView[]
  /** every font file not used, with the family when it could be read that far */
  problems: FontProblemView[]
  access_secret_set: boolean
  can_add: boolean
}

export interface FileCheckView {
  name: string
  verdict: 'added' | 'left-out'
  code: string
  detail: string
  family: string | null
  style: string | null
  outlines: 'truetype' | 'cff' | null
  licence: string
}

export interface CheckAnswer {
  files: FileCheckView[]
  adds: number
  families: string[]
}

export type FamilyFilter = 'all' | 'stand-ins' | 'not-usable'

export type FamilyRow = { kind: 'family'; family: FontFamilyView } | { kind: 'file'; problem: FontProblemView }

const GENERIC = new Set(['serif', 'sans-serif', 'monospace'])

/** Whether a family stands in for an office font (Arimo for Arial), not only for a generic family (Inter). */
function standsInForAFont(family: FontFamilyView): boolean {
  return family.stands_in_for.some((name) => !GENERIC.has(name))
}

function matches(family: FontFamilyView, query: string): boolean {
  const q = query.trim().toLocaleLowerCase()
  return !q || [family.family, ...family.stands_in_for].some((name) => name.toLocaleLowerCase().includes(q))
}

/** The rows of the families table for a filter and a search: the families, and for Not usable also the files no
 *  family could be read from. */
export function familyRows(page: FontsPage, filter: FamilyFilter, query: string): FamilyRow[] {
  const families = page.families.filter((f) => {
    if (filter === 'stand-ins') return standsInForAFont(f)
    if (filter === 'not-usable') return f.problems.length > 0
    return true
  })
  const rows: FamilyRow[] = families.filter((f) => matches(f, query)).map((family) => ({ kind: 'family', family }))
  if (filter === 'not-usable') {
    const q = query.trim().toLocaleLowerCase()
    for (const problem of page.problems) {
      if (problem.family === null && (!q || problem.file.toLocaleLowerCase().includes(q))) rows.push({ kind: 'file', problem })
    }
  }
  return rows
}

/** How many rows each filter has, without a search. */
export function filterCounts(page: FontsPage): Record<FamilyFilter, number> {
  return {
    all: page.families.length,
    'stand-ins': page.families.filter(standsInForAFont).length,
    'not-usable': page.counts.not_usable,
  }
}

/** The Styles column: how many there are, "3 of 4" when the files of more are not used, "variable · 2" for a
 *  variable family. */
export function stylesLabel(family: FontFamilyView, t: T): string {
  const n = family.styles.length
  if (family.problems.length) return t('{n} of {total}', { n, total: n + family.problems.length })
  if (family.styles.some((s) => s.variable)) return t('variable · {n}', { n })
  return String(n)
}

/** The style a family's name is shown in: upright and closest to regular weight. */
export function previewStyle(family: FontFamilyView): FontStyleView | undefined {
  return [...family.styles].sort((a, b) => Number(a.italic) - Number(b.italic) || Math.abs(a.weight - 400) - Math.abs(b.weight - 400))[0]
}

/** Who may receive the fonts, in a word; the page puts its sign before it (a tick, a half-filled circle), so the
 *  answer is never told by colour alone. */
export function mayGoLabel(mayGo: MayGo, t: T): string {
  return mayGo === 'anywhere' ? t('Anywhere') : t('This server')
}

/** Why a font is not used, in words. */
export function problemText(problem: FontProblemView, t: T): string {
  const font = problem.style ?? problem.file
  switch (problem.code) {
    case 'forbids-embedding':
      return t('{font} is not used: the file forbids embedding (fsType {fsType}), so no PDF could carry it.', { font, fsType: problem.detail })
    case 'not-a-font':
      return t('{file} is not a font that can be read.', { file: problem.file })
    case 'no-family':
      return t('{file} has no family name.', { file: problem.file })
    case 'wildcard':
      return t('{file} has * or ? in its name; rename the file on the server.', { file: problem.file })
    case 'unreadable':
      return t('{file} cannot be read on the server.', { file: problem.file })
    case 'record':
      return t('{file} has no usable collection.json, so none of its fonts are used.', { file: problem.file })
    default:
      return t('{file} is not used.', { file: problem.file })
  }
}

/** The line under a collection's name: where it comes from, and how many of its files are not used. */
export function collectionMeta(collection: FontCollectionView, t: T): string {
  const parts: string[] = []
  if (collection.origin === 'shipped') parts.push(t('Always here. A font of the same family and style in another collection is used instead.'))
  else if (collection.origin === 'operator') parts.push(t('Set up by whoever runs the server; changed on its disk only.'))
  else parts.push(collection.added_by ? t('Added by {by}, {date}.', { by: collection.added_by, date: collection.added }) : t('Added in the server settings.'))
  if (collection.problems === 1) parts.push(t('1 file not used.'))
  else if (collection.problems > 1) parts.push(t('{n} files not used.', { n: collection.problems }))
  return parts.join(' ')
}

/** "3 families · OFL-1.1" */
export function collectionSummary(collection: FontCollectionView, t: T): string {
  const n = collection.families.length
  const families = n === 1 ? t('1 family') : t('{n} families', { n })
  return collection.licence ? `${families} · ${collection.licence}` : families
}

export interface CheckLine {
  badge: string
  tone: 'ok' | 'warn' | 'bad'
  note: string
}

/** What one file of Add fonts… becomes, in words: a badge and, where it needs one, a sentence. */
export function checkLine(check: FileCheckView, t: T): CheckLine {
  if (check.verdict === 'left-out') {
    const notes: Record<string, string> = {
      'forbids-embedding': t('The file forbids embedding (fsType {fsType}), so no PDF could carry it.', { fsType: check.detail }),
      duplicate: t('The same font as {file}: added once.', { file: check.detail }),
      'not-a-font-file': t('Not a font file: TrueType or OpenType (.ttf, .otf), or a .zip of them.'),
      'not-a-zip': t('This .zip cannot be opened.'),
      'no-family': t('The font has no family name.'),
      wildcard: t('A file name with * or ? cannot be used; rename the file.'),
    }
    return { badge: t('Left out'), tone: 'bad', note: notes[check.code] ?? t('Not a font that can be read.') }
  }
  if (check.code === 'replaces') {
    return {
      badge: t('Replaces a font'),
      tone: 'warn',
      note: t('Replaces {family} {style} from {collection}, for every document on this server.', { family: check.family ?? '', style: check.style ?? '', collection: check.detail }),
    }
  }
  const note = check.outlines === 'cff' ? t('Shown on screen; print and PDF cannot use its outlines yet and use a stand-in.') : ''
  return { badge: t('Will be added'), tone: 'ok', note }
}

/** "Hausschrift Sans · Regular · TrueType" */
export function checkDescription(check: FileCheckView, t: T): string {
  if (!check.family) return ''
  const outlines = check.outlines === 'cff' ? t('OpenType (CFF)') : t('TrueType')
  return [check.family, check.style, outlines].filter(Boolean).join(' · ')
}

/** What adding will do, said before it happens: the server, the fonts, and who receives them. */
export function scopeSentences(
  scope: { adds: number; families: string[]; server: string; mayGo: MayGo; accessSecretSet: boolean },
  t: T,
): string[] {
  const fonts = scope.adds === 1 ? t('1 font') : t('{n} fonts', { n: scope.adds })
  const families = scope.families.length === 1 ? t('1 family') : t('{n} families', { n: scope.families.length })
  const lines = [
    t('Adds {fonts} in {families} to {server}. From now on every document here that asks for {names} is laid out, shown and printed with them.', {
      fonts,
      families,
      server: scope.server,
      names: scope.families.join(', '),
    }),
  ]
  if (scope.mayGo === 'anywhere') lines.push(t('Anyone who opens a document here receives them.'))
  else {
    lines.push(t('Only people using this server receive them.'))
    if (!scope.accessSecretSet) lines.push(t('This server has no access secret, so everyone who can reach it counts as its people.'))
  }
  return lines
}

/** The licence the checked fonts name, if they all name the same one. */
export function suggestedLicence(checks: FileCheckView[]): string {
  const named = new Set(checks.filter((c) => c.verdict === 'added').map((c) => c.licence))
  return named.size === 1 ? [...named][0]! : ''
}

const loaded = new Map<string, Promise<string | null>>()

/** Loads a font of the catalogue for showing a family's name in its own face; the CSS family to use, or `null` when it
 *  cannot be loaded (the name is then shown in the page's own font). Fetched with the administrator's session, as a
 *  font for this server only is not handed out without it (D1041). */
export function loadPreview(sha256: string, token: string, fetchImpl: typeof fetch = fetch): Promise<string | null> {
  let found = loaded.get(sha256)
  if (!found) {
    found = (async () => {
      try {
        const response = await fetchImpl(`/api/fonts/${sha256}.woff2`, { headers: { authorization: `Bearer ${token}` } })
        if (!response.ok || typeof FontFace === 'undefined') return null
        const name = `claudia-preview-${sha256.slice(0, 16)}`
        const face = new FontFace(name, await response.arrayBuffer())
        document.fonts.add(await face.load())
        return name
      } catch {
        return null
      }
    })()
    loaded.set(sha256, found)
  }
  return found
}
