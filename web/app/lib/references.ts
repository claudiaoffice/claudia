// References as every app's client knows them (step H of claudiaoffice-log/notes/text-structure-across-apps.md;
// mock-up composes-references.svg). A reference is a field at one U+FFFC of a paragraph's text: the k-th U+FFFC is
// the k-th of the paragraph's `fields`. It stores the id of what it points at and what to show; what it reads as is
// derived by the server (`shown`), so it never goes stale. This module holds the shapes the server sends and what the
// editors and the picker work out from them; the requests are the sessions'.

/** The character a field stands at in a paragraph's text. */
export const FIELD_CHAR = '￼'

/** What a reference shows: the target's number, its words, both, its page (or slide) or its name. */
export type Show = 'number' | 'text' | 'number-text' | 'page' | 'name'
export const SHOWS: readonly Show[] = ['number', 'text', 'number-text', 'page', 'name']

/** A reference as stored (the server's `fields`). */
export interface RefField {
  kind: 'ref'
  target: string
  show: Show
}

/** What a field reads as now: `ok`, `broken` (what it points at is gone) or `page` (the layout fills in the page). */
export interface Shown {
  text: string
  state: 'ok' | 'broken' | 'page'
}

/** Something a reference can point at, as the picker lists it (the server's `reference_targets`). */
export interface ReferenceTarget {
  id: string
  kind: 'heading' | 'item' | 'named'
  level: number | null
  number: string | null
  text: string
  name: string | null
}

/** How many fields stand before `offset` of `text`: the index of the field at `offset`, if one is there. */
export function fieldIndex(text: string, offset: number): number {
  let n = 0
  for (let i = 0; i < offset && i < text.length; i++) if (text[i] === FIELD_CHAR) n++
  return n
}

/** Words a person wrote cannot make a field: `text` without U+FFFC. */
export const plain = (text: string): string => text.split(FIELD_CHAR).join('')

/** The words of a paragraph with each field as what it reads as (`page` and `broken` ones as a mark), for whatever
 * draws or copies them as plain text. */
export function readAs(text: string, shown: readonly Shown[] | undefined, missing = '#'): string {
  let k = 0
  let out = ''
  for (const char of text) {
    if (char !== FIELD_CHAR) out += char
    else {
      const s = shown?.[k++]
      out += s && s.state === 'ok' ? s.text : missing
    }
  }
  return out
}

/** The parts of a stretch of text: words, and the fields in it with their index in the paragraph. */
export type Part = { kind: 'words'; text: string; start: number } | { kind: 'field'; index: number; start: number }

/** Cut `text` (which starts at `start` of a paragraph whose fields before it number `first`) at its fields. */
export function partsOf(text: string, start = 0, first = 0): Part[] {
  const out: Part[] = []
  let index = first
  let from = 0
  for (let i = 0; i < text.length; i++) {
    if (text[i] !== FIELD_CHAR) continue
    if (i > from) out.push({ kind: 'words', text: text.slice(from, i), start: start + from })
    out.push({ kind: 'field', index: index++, start: start + i })
    from = i + 1
  }
  if (from < text.length) out.push({ kind: 'words', text: text.slice(from), start: start + from })
  return out
}

/** What a new reference to `target` shows: its number when it has one, else its words, else its name. */
export function defaultShow(target: ReferenceTarget): Show {
  if (target.number) return 'number'
  return target.kind === 'named' && !target.text ? 'name' : 'text'
}

/** The picker's groups, in order, with the targets of each. */
export function grouped(targets: readonly ReferenceTarget[]): { kind: ReferenceTarget['kind']; targets: ReferenceTarget[] }[] {
  const kinds: ReferenceTarget['kind'][] = ['heading', 'item', 'named']
  return kinds.map((kind) => ({ kind, targets: targets.filter((t) => t.kind === kind) })).filter((g) => g.targets.length)
}

/** What a reference would read as for a target, before the server says (the picker's "Reads:" line). */
export function preview(target: ReferenceTarget, show: Show): string {
  switch (show) {
    case 'number':
      return target.number ?? target.text
    case 'number-text':
      return target.number ? `${target.number} ${target.text}` : target.text
    case 'page':
      return '#'
    case 'name':
      return target.name ?? target.text
    default:
      return target.text
  }
}
