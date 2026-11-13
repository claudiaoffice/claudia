// Search & replace, the part that needs no Vue and no DOM (E5.15, D281–D286): what a person builds in the panel, what
// is asked of the server for it, the sentence that says in her words what it does, and what the answers are. Nothing
// here knows sheets: every place is the app's own `at` (CODE-18), and the app's `SearchHost` reads it (computes:
// `sheet-search-host.ts`, which also draws the matches on the grid). The panel (`SearchPanel.vue`) is thin around this.
//
// The person never reads the word "regular expression": the quick field is plain text, the builder is parts and
// conditions, and a pattern is something she writes herself, deliberately, from the ⋯ menu. The server compiles all
// three the same way (`claudia_search`, with a time limit on every pattern).

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

// ---------------------------------------------------------------------------------------------------------- the model
export type PartWhat = 'text' | 'any_of' | 'none_of' | 'letter' | 'digit' | 'space' | 'any' | 'number' | 'start' | 'end' | 'cellref'
export type Count = 'once' | 'optional' | 'one_or_more' | 'any' | 'exactly' | 'between'
export type ConditionKind = 'contains' | 'not_contains' | 'starts_with' | 'ends_with' | 'is' | 'contains_any_of' | 'not_contains_any_of'
export type Whole = 'none' | 'entire' | 'word'
export type Kinds = { text: boolean; formulas: boolean; values: boolean }

/** One thing to find: what, how many of it, and a name if the replacement wants it back. */
export interface Part {
  id: number
  what: PartWhat
  /** The text of a `text` part, or the characters of an `any_of` / `none_of`. */
  value: string
  chars: string
  count: Count
  n: number
  m: number
  /** The name the part is kept under; empty if it is not kept. */
  keep: string
}

/** A demand on the whole cell. `text` holds the text, or for the "one of" conditions the characters. */
export interface Condition {
  id: number
  kind: ConditionKind
  text: string
}

export type ReplaceItem = { text: string } | { keep: string }

export interface SearchModel {
  /** `quick`: the plain field; `builder`: parts and conditions; `pattern`: the person's own text. */
  mode: 'quick' | 'builder' | 'pattern'
  quick: string
  parts: Part[]
  conditions: Condition[]
  combine: 'all' | 'any'
  pattern: { find: string; filter: string; replace: string }
  replace: ReplaceItem[]
  matchCase: boolean
  whole: Whole
}

let counter = 0

export function emptyModel(): SearchModel {
  return {
    mode: 'quick',
    quick: '',
    parts: [],
    conditions: [],
    combine: 'all',
    pattern: { find: '', filter: '', replace: '' },
    replace: [],
    matchCase: false,
    whole: 'none',
  }
}

export function newPart(what: PartWhat): Part {
  return { id: ++counter, what, value: '', chars: '', count: 'once', n: 2, m: 3, keep: '' }
}

export function newCondition(kind: ConditionKind): Condition {
  return { id: ++counter, kind, text: '' }
}

/** What each part needs filled in before it means something. */
const needsText = (what: PartWhat) => what === 'text'
const needsChars = (what: PartWhat) => what === 'any_of' || what === 'none_of'
const isPlace = (what: PartWhat) => what === 'start' || what === 'end'

function usable(part: Part): boolean {
  if (needsText(part.what)) return part.value !== ''
  if (needsChars(part.what)) return part.chars !== ''
  return true
}

const usableParts = (model: SearchModel) => model.parts.filter(usable)
const usableConditions = (model: SearchModel) => model.conditions.filter((c) => c.text !== '')

/** The names parts are kept under, once each, in the order of the parts. */
export function keptNames(model: SearchModel): string[] {
  const names: string[] = []
  for (const part of model.parts) {
    const name = part.keep.trim()
    if (name && !names.includes(name)) names.push(name)
  }
  return names
}

/** Keeps the part at `index` under a name that no other part has: its own kind of thing ("number"), numbered if taken. */
export function addKept(model: SearchModel, index: number): SearchModel {
  const taken = new Set(model.parts.filter((_, i) => i !== index).map((p) => p.keep.trim()))
  const base = model.parts[index]!.what === 'any_of' || model.parts[index]!.what === 'none_of' ? 'characters' : model.parts[index]!.what
  let name = base
  for (let k = 2; taken.has(name); k++) name = `${base} ${k}`
  return { ...model, parts: model.parts.map((p, i) => (i === index ? { ...p, keep: name } : p)) }
}

/** A replacement without its empty texts. */
export function normalizeReplacement(items: ReplaceItem[]): ReplaceItem[] {
  return items.filter((item) => 'keep' in item || item.text !== '')
}

// ------------------------------------------------------------------------------------------------------- the question
export type WirePart = { what: PartWhat; value?: string; chars?: string; count?: Count; n?: number; m?: number; keep?: string }
export type WireCondition = { kind: ConditionKind; text?: string; chars?: string }
export interface SearchQuery {
  mode: 'text' | 'builder' | 'pattern'
  text?: string
  parts?: WirePart[]
  conditions?: WireCondition[]
  combine?: 'all' | 'any'
  find?: string
  filter?: string
  replace?: ReplaceItem[] | string
  match_case: boolean
  whole?: Whole
}

function wirePart(part: Part, keep: string | null): WirePart {
  const wire: WirePart = { what: part.what }
  if (needsText(part.what)) wire.value = part.value
  if (needsChars(part.what)) wire.chars = part.chars
  if (part.count !== 'once' && !isPlace(part.what)) {
    wire.count = part.count
    if (part.count === 'exactly') wire.n = Math.max(1, Math.floor(part.n))
    if (part.count === 'between') {
      wire.n = Math.max(0, Math.floor(part.n))
      wire.m = Math.max(wire.n, Math.floor(part.m))
    }
  }
  if (keep) wire.keep = keep
  return wire
}

function wireCondition(condition: Condition): WireCondition {
  const chars = condition.kind === 'contains_any_of' || condition.kind === 'not_contains_any_of'
  return chars ? { kind: condition.kind, chars: condition.text } : { kind: condition.kind, text: condition.text }
}

/**
 * What to ask the server for this model, or `null` while there is nothing to look for yet. `replace` adds the
 * replacement (the server then also says what each match would become); without it the same search only finds.
 */
export function toQuery(model: SearchModel, options: { replace?: boolean } = {}): SearchQuery | null {
  const replace = options.replace === true
  if (model.mode === 'pattern') {
    if (model.pattern.find.trim() === '') return null
    const query: SearchQuery = { mode: 'pattern', find: model.pattern.find, filter: model.pattern.filter, match_case: model.matchCase }
    if (replace) query.replace = model.pattern.replace
    return query
  }
  if (model.mode === 'quick') {
    if (model.quick === '') return null
    const query: SearchQuery = { mode: 'text', text: model.quick, match_case: model.matchCase, whole: model.whole }
    if (replace) query.replace = normalizeReplacement(model.replace).filter((item) => 'text' in item)
    return query
  }
  const parts = usableParts(model)
  const conditions = usableConditions(model)
  if (parts.length === 0 && conditions.length === 0) return null
  const seen = new Set<string>()
  const wireParts = parts.map((part) => {
    const name = part.keep.trim()
    const keep = name && !seen.has(name) ? name : null
    if (keep) seen.add(keep)
    return wirePart(part, keep)
  })
  const query: SearchQuery = {
    mode: 'builder',
    parts: wireParts,
    conditions: conditions.map(wireCondition),
    combine: model.combine,
    match_case: model.matchCase,
    whole: model.whole,
  }
  if (replace) query.replace = normalizeReplacement(model.replace).filter((item) => 'text' in item || seen.has(item.keep))
  return query
}

// -------------------------------------------------------------------------------------------- the sentence (D283)
// Every phrase is a whole translatable string with placeholders: word order differs between languages, so nothing is
// built from loose words. The pieces are phrases that are themselves whole: a part's, a count's, a condition's.

function partPhrase(part: Part, t: Translate): string {
  let phrase: string
  switch (part.what) {
    case 'text':
      phrase = t('the text “{text}”', { text: part.value })
      break
    case 'any_of':
      phrase = t('any one of {chars}', { chars: part.chars })
      break
    case 'none_of':
      phrase = t('any character except {chars}', { chars: part.chars })
      break
    case 'letter':
      phrase = t('a letter')
      break
    case 'digit':
      phrase = t('a digit')
      break
    case 'space':
      phrase = t('a space')
      break
    case 'any':
      phrase = t('any character')
      break
    case 'number':
      phrase = t('a number')
      break
    case 'start':
      phrase = t('the start of the cell')
      break
    case 'end':
      phrase = t('the end of the cell')
      break
    case 'cellref':
      phrase = t('a cell reference')
      break
  }
  const what = phrase
  if (!isPlace(part.what)) {
    if (part.count === 'optional') phrase = t('{what}, optionally', { what })
    else if (part.count === 'one_or_more') phrase = t('{what}, one or more times', { what })
    else if (part.count === 'any') phrase = t('{what}, any number of times', { what })
    else if (part.count === 'exactly') phrase = t('{what}, exactly {n} times', { what, n: Math.max(1, Math.floor(part.n)) })
    else if (part.count === 'between') {
      const n = Math.max(0, Math.floor(part.n))
      phrase = t('{what}, {n} to {m} times', { what, n, m: Math.max(n, Math.floor(part.m)) })
    }
  }
  const name = part.keep.trim()
  return name ? t('{what} (kept as “{name}”)', { what: phrase, name }) : phrase
}

function conditionPhrase(condition: Condition, t: Translate): string {
  const text = condition.text
  switch (condition.kind) {
    case 'contains':
      return t('contain “{text}”', { text })
    case 'not_contains':
      return t('do not contain “{text}”', { text })
    case 'starts_with':
      return t('start with “{text}”', { text })
    case 'ends_with':
      return t('end with “{text}”', { text })
    case 'is':
      return t('are exactly “{text}”', { text })
    case 'contains_any_of':
      return t('contain one of {chars}', { chars: text })
    case 'not_contains_any_of':
      return t('contain none of {chars}', { chars: text })
  }
}

/** The builder, said back to the person in a sentence; empty while there is nothing to say. */
export function sentence(model: SearchModel, t: Translate): string {
  const parts = usableParts(model).map((p) => partPhrase(p, t))
  const conditions = usableConditions(model).map((c) => conditionPhrase(c, t))
  if (parts.length === 0 && conditions.length === 0) return ''
  const then = (first: string, next: string) => t('{first}, then {next}', { first, next })
  const join = model.combine === 'any' ? (first: string, next: string) => t('{first} or {next}', { first, next }) : (first: string, next: string) => t('{first} and {next}', { first, next })
  const partsText = parts.length ? parts.reduce(then) : ''
  const conditionsText = conditions.length ? conditions.reduce(join) : ''
  let said: string
  if (parts.length && conditions.length) said = t('Finds {parts} in cells that {conditions}.', { parts: partsText, conditions: conditionsText })
  else if (parts.length) said = t('Finds {parts}.', { parts: partsText })
  else said = t('Finds the cells that {conditions}.', { conditions: conditionsText })
  if (model.whole === 'entire') said += ' ' + t('Only when it is the whole cell.')
  else if (model.whole === 'word') said += ' ' + t('Only whole words.')
  return said
}

// ----------------------------------------------------------------------------------------------------- the answers
/** Where something is, in the app's own words: a cell is `{ sheet, row, col }`. Only the app's host reads it; the panel
 *  keys and names it through the host and sends it back unchanged (CODE-18). */
export type SearchPlace = Readonly<Record<string, string | number | boolean | null>>

export interface SearchMatch {
  at: SearchPlace
  kind: 'text' | 'formula' | 'value'
  /** Its place among the matches of its text. */
  number: number
  start: number
  end: number
  parts: string[]
  /** What a replacement would make of it: `null` for a value, or when there is no replacement. */
  after: string | null
  /** The stretch of the text around the match, `excerpt` being the match inside it. */
  text: string
  excerpt: [number, number]
  /** Whether the text goes on before, and after, `text`. */
  clipped: [boolean, boolean]
}

export interface LeftOut {
  at: SearchPlace
  kind: string
  /** Why: the condition that failed, as it was sent, or `{ kind: 'filter' }`. */
  why: { kind: string; text?: string; chars?: string }
}

export interface PatternProblem {
  message: string
  field: string
  position: number | null
}

export interface SearchAnswer {
  revision: string | null
  matches: SearchMatch[]
  left_out: LeftOut[]
  /** How many matches each kind has, whichever are switched on. */
  counts: { text: number; formulas: number; values: number }
  total: number
  truncated: boolean
  /** The search stopped at its time limit; what it had found by then is listed. */
  timed_out: boolean
  pattern?: { find: string; filter: string; replace: string }
  error?: PatternProblem
}

export interface Change {
  at: SearchPlace
  kind: string
  before: string
  after: string
}

export interface Skipped {
  at: SearchPlace
  kind: string
  reason: 'locked' | 'formula' | 'too_long'
  by: string | null
}

export interface PreviewAnswer {
  revision: string | null
  changes: Change[]
  skipped: Skipped[]
  total: number
  /** The preview stopped at its time limit and is not complete; replacing would be refused. */
  timed_out?: boolean
  error?: PatternProblem
}

export interface ReplaceAnswer {
  revision: string | null
  replaced: number
  skipped: Skipped[]
}

/** A match, or with `match: null` everything at a place, that a replacement leaves alone. */
export interface SearchLeave {
  at: SearchPlace
  match: number | null
}

/** What the panel needs from an app (E5.15, D282): what can be searched, where, and how to name and show a place. */
export interface SearchHost<Scope = unknown> {
  /** Can only look: Replace is off. */
  readonly readonly: boolean
  /** What can be looked in, and where. */
  readonly kinds: (keyof Kinds)[]
  readonly scopes: string[]
  /** Parts of the builder that only this app has (a cell reference). */
  readonly extraParts: PartWhat[]
  /** What the scope is called in the list: "This sheet". */
  scopeLabel(scope: string): string
  /** The scope as the server wants it. */
  scopeOf(scope: string): Scope
  /** Looks in every kind; which are shown is the panel's choice. `null`: no answer. */
  find(query: SearchQuery, scope: Scope): Promise<SearchAnswer | null>
  preview(query: SearchQuery, kinds: Kinds, scope: Scope, leave: SearchLeave[]): Promise<PreviewAnswer | null>
  replace(query: SearchQuery, kinds: Kinds, scope: Scope, leave: SearchLeave[]): Promise<ReplaceAnswer | false>
  /** One string per place, for lists and sets: the same place always gives the same key. */
  keyOf(at: SearchPlace): string
  /** The place as a person reads it: `Costs!B2`. */
  where(at: SearchPlace): string
  /** Show the place in the document. */
  jump(at: SearchPlace): void
  /** Changes when the document does, so that a search that is showing can run again. */
  revision(): string | null
}

const KIND_OF: Record<keyof Kinds, SearchMatch['kind']> = { text: 'text', formulas: 'formula', values: 'value' }

/** The matches of the kinds that are switched on (the server counts all of them, so the switches can show numbers). */
export function shownMatches(matches: SearchMatch[], kinds: Kinds): SearchMatch[] {
  const wanted = new Set((Object.keys(KIND_OF) as (keyof Kinds)[]).filter((k) => kinds[k]).map((k) => KIND_OF[k]))
  return matches.filter((m) => wanted.has(m.kind))
}

export function excerptOf(match: SearchMatch): { before: string; hit: string; after: string } {
  const [from, to] = match.excerpt
  return {
    before: (match.clipped[0] ? '…' : '') + match.text.slice(0, from),
    hit: match.text.slice(from, to),
    after: match.text.slice(to) + (match.clipped[1] ? '…' : ''),
  }
}

/** What a cell left out does that a condition did not allow ("contain “EUR”"): the answer to "why is it not here". */
export function whyLeftOut(why: LeftOut['why'], t: Translate): string {
  const text = why.text ?? ''
  const chars = why.chars ?? ''
  switch (why.kind) {
    case 'not_contains':
      return t('contain “{text}”', { text })
    case 'contains':
      return t('do not contain “{text}”', { text })
    case 'starts_with':
      return t('do not start with “{text}”', { text })
    case 'ends_with':
      return t('do not end with “{text}”', { text })
    case 'is':
      return t('are not exactly “{text}”', { text })
    case 'contains_any_of':
      return t('contain none of {chars}', { chars })
    case 'not_contains_any_of':
      return t('contain one of {chars}', { chars })
    default:
      return t('do not match the pattern for cells')
  }
}

/** The same search as the person's own pattern, starting from the three fields the builder made (⋯ ▸ Write the
 *  pattern yourself…). The builder's own model is untouched, so that she can go back to it. */
export function toPattern(model: SearchModel, fields: { find: string; filter: string; replace: string }): SearchModel {
  return { ...model, mode: 'pattern', pattern: { ...fields } }
}

// ----------------------------------------------------------------------------------------------- mistakes in words
const FIELDS = ['find', 'filter', 'replace'] as const

/** What a mistake in a typed pattern says, in a sentence and where it is: the server's own English sentence is
 *  the fallback for anything this does not know. */
export function explainError(problem: PatternProblem, t: Translate): { headline: string; detail: string; where: string; field: string } {
  const where = problem.field === 'filter' ? t('Only in cells matching') : problem.field === 'replace' ? t('Replace with') : problem.field === 'find' ? t('Find') : ''
  const field = (FIELDS as readonly string[]).includes(problem.field) ? problem.field : 'find'
  const at = problem.position === null ? null : problem.position + 1 // people count from 1
  const message = problem.message
  let headline = message
  let detail = ''
  if (message.startsWith('missing ), unterminated subpattern')) {
    headline = t('A bracket is never closed.')
    detail = at === null ? t('Nothing is replaced.') : t('The “(” at character {position} has no “)”. Nothing is replaced.', { position: at })
  } else if (message.startsWith('unbalanced parenthesis')) {
    headline = t('A closing bracket has no opening one.')
    detail = at === null ? t('Nothing is replaced.') : t('The “)” at character {position} has no “(”. Nothing is replaced.', { position: at })
  } else if (message.startsWith('nothing to repeat') || message.startsWith('multiple repeat')) {
    headline = t('Something is repeated that is not there.')
    detail = at === null ? t('Nothing is replaced.') : t('The repeat at character {position} has nothing before it. Nothing is replaced.', { position: at })
  } else if (message.startsWith('unterminated character set')) {
    headline = t('A square bracket is never closed.')
    detail = at === null ? t('Nothing is replaced.') : t('The “[” at character {position} has no “]”. Nothing is replaced.', { position: at })
  } else if (message.startsWith('bad escape')) {
    headline = t('This backslash does not mean anything here.')
    detail = at === null ? t('Nothing is replaced.') : t('Look at the backslash at character {position}. Nothing is replaced.', { position: at })
  } else if (message.startsWith('this pattern is nested too deeply')) {
    headline = t('This pattern has too many brackets inside each other.')
    detail = t('It is not run, so nothing is found or replaced.')
  } else if (message.startsWith('invalid group reference') || message.startsWith('unknown group name') || message.startsWith('there is no group')) {
    headline = t('The replacement uses a kept part that the pattern does not have.')
    detail = t('Nothing is replaced.')
  }
  return { headline, detail, where, field }
}

// ------------------------------------------------------------------------------------------------ newest answer wins
/** Runs requests so that only the newest one's answer is used: an older answer that arrives late is `null`, and so
 *  is a failure — a search while typing is never worth interrupting her for. */
export function latest<T>(): (run: () => Promise<T>) => Promise<T | null> {
  let newest = 0
  return async (run) => {
    const mine = ++newest
    try {
      const answer = await run()
      return mine === newest ? answer : null
    } catch {
      return null
    }
  }
}
