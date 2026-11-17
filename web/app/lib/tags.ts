// Tags in the chat (E5.20, D551): typing `#` lists the named things in sight, and picking one writes a tag into the
// message. A tag keeps the id of the thing and the name it had, written as a link `[#Figure 1](thing:o7)`: a reader
// that knows tags shows the thing's current name and can take you to it; anything else (an older client, the AI, an
// export) reads it as the plain words it is. Pure: no component, no connection, so every rule has a test.

import type { ObjectKind } from '@claudia/layout'

/** What can be named, by what it is: an object's own kind, or the slide, sheet, chart tab or named range it is. */
export type ThingKind =
  | ObjectKind
  | 'slide'
  | 'sheet'
  | 'chart'
  | 'range'
  // the paragraphs of a text (D554)
  | 'heading'
  | 'item'
  | 'paragraph'

/** A thing a tag can point at. */
export interface Thing {
  id: string
  name: string
  kind: ThingKind
  /** Offered, but without a name yet (a paragraph, D554): picking it names it first (`thingToReference`), and `name`
   * is only what the list shows until then. */
  unnamed?: boolean
}

/** A message, cut into plain text and tags. */
export type Segment = { type: 'text'; text: string } | { type: 'tag'; id: string; name: string }

/** The longest name a thing has (the server's `MAX_THING_NAME`). */
export const MAX_NAME = 60
const MAX_LIST = 8

/** What two names are compared by: tidied and in lower case, so that "Figure  1" and "figure 1" are one name. */
export const nameKey = (name: string): string => name.split(/\s+/).filter(Boolean).join(' ').toLowerCase().replace(/ß/g, 'ss')

/** A tag, as it is written into a message. `[`, `]` and `\` in the name are escaped. */
export function encodeTag(id: string, name: string): string {
  return `[#${name.replace(/[\\[\]]/g, '\\$&')}](thing:${id})`
}

const TAG = /\[#((?:\\.|[^\\\]])*)\]\(thing:([^)\s]+)\)/g

/** The message cut into plain text and tags, in order. Anything that only looks like a tag stays text. */
export function splitTags(text: string): Segment[] {
  const out: Segment[] = []
  let from = 0
  for (const m of text.matchAll(TAG)) {
    if (m.index > from) out.push({ type: 'text', text: text.slice(from, m.index) })
    out.push({ type: 'tag', id: m[2]!, name: m[1]!.replace(/\\(.)/g, '$1') })
    from = m.index + m[0].length
  }
  if (from < text.length || out.length === 0) out.push({ type: 'text', text: text.slice(from) })
  return out
}

/** The ids of the things a message points at, in order. */
export function tagIds(text: string): string[] {
  return splitTags(text).flatMap((s) => (s.type === 'tag' ? [s.id] : []))
}

/** The message for somebody who cannot see tags: each as `#name`, with the thing's current name where `nameOf` knows it
 * and the name it had when written where it does not. */
export function plainChat(text: string, nameOf?: (id: string) => string | undefined): string {
  return splitTags(text)
    .map((s) => (s.type === 'text' ? s.text : `#${nameOf?.(s.id) ?? s.name}`))
    .join('')
}

/** A `#` the caret is behind, which starts a word: where it is and what was typed after it. */
export interface Hash {
  start: number
  query: string
}

/** The open `#…` before `caret`, or `null`: the `#` must start the text or follow a space, no line may break between it
 * and the caret, and what follows it is no longer than a name (names have spaces, so the query may). */
export function hashAt(text: string, caret: number): Hash | null {
  const before = text.slice(0, caret)
  const start = before.lastIndexOf('#')
  if (start < 0) return null
  if (start > 0 && !/\s/.test(before[start - 1]!)) return null
  const query = before.slice(start + 1)
  if (query.includes('\n') || query.length > MAX_NAME) return null
  return { start, query }
}

/** The things a query offers: names that start with it, then those that contain it; each group by name. */
export function matches(things: readonly Thing[], query: string, limit = MAX_LIST): Thing[] {
  const wanted = nameKey(query)
  const byName = (a: Thing, b: Thing) => nameKey(a.name).localeCompare(nameKey(b.name), undefined, { numeric: true })
  const starts: Thing[] = []
  const contains: Thing[] = []
  for (const thing of things) {
    const key = nameKey(thing.name)
    if (key.startsWith(wanted)) starts.push(thing)
    else if (key.includes(wanted)) contains.push(thing)
  }
  return [...starts.sort(byName), ...contains.sort(byName)].slice(0, limit)
}

/** The text with a tag for `thing` written at `caret`, a space before it unless there is one (or the text starts there)
 * and a space after it, the caret behind that. What clicking a thing and Edit ▸ Reference in Chat write. */
export function insertTag(text: string, caret: number, thing: Thing): { text: string; caret: number } {
  const before = text.slice(0, caret)
  const after = text.slice(caret)
  const lead = before && !/\s$/.test(before) ? ' ' : ''
  const gap = after.startsWith(' ') ? '' : ' '
  const head = `${before}${lead}${encodeTag(thing.id, thing.name)}${gap}`
  return { text: `${head}${after}`, caret: head.length + (gap === '' ? 1 : 0) }
}

/** The message with every tag written with the name its thing has now (`nameOf`; the name it was written with where it
 * does not know the thing): what is sent, so that a name changed while the message was being written is not sent old. */
export function withCurrentNames(text: string, nameOf: (id: string) => string | undefined): string {
  return splitTags(text)
    .map((s) => (s.type === 'text' ? s.text : encodeTag(s.id, nameOf(s.id) ?? s.name)))
    .join('')
}

/** The text with `thing` as a tag in place of the `#…` that was typed, the caret after it and a space (the one that
 * follows already, if there is one). */
export function withTag(text: string, hash: Hash, caret: number, thing: Thing): { text: string; caret: number } {
  const tag = encodeTag(thing.id, thing.name)
  const after = text.slice(caret)
  const gap = after.startsWith(' ') ? '' : ' '
  const head = `${text.slice(0, hash.start)}${tag}${gap}`
  return { text: `${head}${after}`, caret: head.length + (gap === '' ? 1 : 0) }
}
