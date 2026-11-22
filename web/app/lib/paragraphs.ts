// The text replica: paragraphs with authorship runs, kept up to date by applying the server's state events, and the rules
// by which positions (my caret, a colleague's zone, a suggestion) move through those events. Every rule mirrors the
// `follow` of the command in claudia_composes, so that what the screen shows is what the server holds.

import type { ContentsEntry, Toc } from './contents'
import { fieldIndex, type RefField, type Shown } from './references'

/** `[length, author, via]`: who wrote this stretch, and whose suggestion it came through. */
export type Run = [number, string | null, string | null]
/** A paragraph's place in a list: which list (an id of the document's lists) and the level, 0 being the outermost. */
export interface ListItem {
  list: string
  level: number
}
/** What is drawn in front of an item or a numbered heading (derived by the server, never typed): a bullet or a number;
 * `path` is the trail of counters ("2.a" is `[2, 1]`) and `number` what a reference prints ("2.a"), both `null` for
 * bullets. */
export interface Label {
  marker: string
  path: number[] | null
  number?: string | null
}
export interface Paragraph {
  id: string
  style: string
  text: string
  runs: Run[]
  /** Set when the paragraph is a list item. */
  item?: ListItem | null
  /** Set when it is one, or its style numbers it (a numbered heading), and the server has counted it. */
  label?: Label
  /** Its name, when somebody has pointed at it or named it (D554). */
  name?: string
  /** Set when the paragraph is a table of contents (E9.31): its options. Such a paragraph holds no text. */
  generated?: Toc | null
  /** A table of contents' lines, derived by the server from the headings. */
  entries?: ContentsEntry[]
  /** The references in the words, one for each U+FFFC of `text`, in order (step H). */
  fields?: RefField[]
  /** What each of them reads as now, derived by the server. */
  shown?: Shown[]
}
export interface Pos {
  paragraph: string
  offset: number
}
export interface Span {
  paragraph: string
  start: number
  end: number
}

/** The events of the text app (the part of the wire protocol that carries the document). */
export type TextEvent =
  | { type: 'text'; paragraph: string; offset: number; removed: number; inserted: string; runs: Run[] }
  | { type: 'split'; paragraph: string; offset: number; new_id: string; style: string }
  | { type: 'join'; paragraph: string; into: string; at: number }
  | { type: 'style'; paragraph: string; style: string }
  | { type: 'item'; paragraph: string; item: ListItem | null }
  | { type: 'labels'; labels: Record<string, Label | null> }
  | { type: 'paragraph_generated'; paragraph: string; generated: Toc | null }
  | { type: 'generated'; paragraph: string; entries: ContentsEntry[] | null }
  | { type: 'paragraph_fields'; paragraph: string; fields: RefField[] }
  | { type: 'fields'; paragraph: string; fields: Shown[] }

// ------------------------------------------------------------------------------ runs
export function normalizeRuns(runs: Run[]): Run[] {
  const out: Run[] = []
  for (const run of runs) {
    if (run[0] <= 0) continue
    const last = out.at(-1)
    if (last && last[1] === run[1] && last[2] === run[2]) last[0] += run[0]
    else out.push([...run])
  }
  return out
}

export function sliceRuns(runs: Run[], start: number, end: number): Run[] {
  const out: Run[] = []
  let position = 0
  for (const [length, author, via] of runs) {
    const lo = Math.max(start, position)
    const hi = Math.min(end, position + length)
    if (lo < hi) out.push([hi - lo, author, via])
    position += length
  }
  return normalizeRuns(out)
}

export const runsLength = (runs: Run[]) => runs.reduce((n, r) => n + r[0], 0)

export function deleteRuns(runs: Run[], start: number, end: number): Run[] {
  return normalizeRuns([...sliceRuns(runs, 0, start), ...sliceRuns(runs, end, runsLength(runs))])
}

export function insertRuns(runs: Run[], offset: number, added: Run[]): Run[] {
  return normalizeRuns([...sliceRuns(runs, 0, offset), ...added, ...sliceRuns(runs, offset, runsLength(runs))])
}

// ------------------------------------------------------------------------------ the document
export const indexOf = (paragraphs: Paragraph[], id: string) => paragraphs.findIndex((b) => b.id === id)

/** Apply one event of the server to the paragraphs. `false` if the event does not fit (the replica is out of step). */
export function applyEvent(paragraphs: Paragraph[], ev: TextEvent): boolean {
  if (ev.type === 'labels') {
    for (const [id, label] of Object.entries(ev.labels)) {
      const found = paragraphs[indexOf(paragraphs, id)]
      if (!found) continue // a paragraph that went away in the same step
      if (label) found.label = label
      else delete found.label
    }
    return true
  }
  if (ev.type === 'fields') {
    const found = paragraphs[indexOf(paragraphs, ev.paragraph)]
    if (found) found.shown = ev.fields
    return true // the words of a floating object, or a paragraph that went away in the same step
  }
  if (ev.type === 'generated') {
    const found = paragraphs[indexOf(paragraphs, ev.paragraph)]
    if (found && ev.entries) found.entries = ev.entries
    else if (found) delete found.entries
    return true // a table that went away in the same step needs nothing
  }
  const i = indexOf(paragraphs, ev.type === 'join' ? ev.into : ev.paragraph)
  const paragraph = paragraphs[i]
  if (!paragraph) return false
  switch (ev.type) {
    case 'text': {
      if (ev.offset < 0 || ev.offset + ev.removed > paragraph.text.length) return false
      paragraph.text = paragraph.text.slice(0, ev.offset) + ev.inserted + paragraph.text.slice(ev.offset + ev.removed)
      const cut = ev.removed ? deleteRuns(paragraph.runs, ev.offset, ev.offset + ev.removed) : paragraph.runs
      paragraph.runs = ev.inserted ? insertRuns(cut, ev.offset, ev.runs) : cut
      return true
    }
    case 'split': {
      if (ev.offset < 0 || ev.offset > paragraph.text.length) return false
      const rest: Paragraph = {
        id: ev.new_id,
        style: ev.style,
        text: paragraph.text.slice(ev.offset),
        runs: sliceRuns(paragraph.runs, ev.offset, paragraph.text.length),
        ...(paragraph.item ? { item: { ...paragraph.item } } : {}), // an item makes an item; its label comes with the server's count
      }
      if (paragraph.fields?.length) {
        // the fields go with their characters; what they read as comes again from the server
        const at = fieldIndex(paragraph.text, ev.offset)
        rest.fields = paragraph.fields.slice(at)
        rest.shown = paragraph.shown?.slice(at)
        paragraph.fields = paragraph.fields.slice(0, at)
        paragraph.shown = paragraph.shown?.slice(0, at)
      }
      paragraph.text = paragraph.text.slice(0, ev.offset)
      paragraph.runs = sliceRuns(paragraph.runs, 0, ev.offset)
      paragraphs.splice(i + 1, 0, rest)
      return true
    }
    case 'join': {
      const next = paragraphs[i + 1]
      if (!next || next.id !== ev.paragraph || paragraph.text.length !== ev.at) return false
      paragraph.text += next.text
      paragraph.runs = insertRuns(paragraph.runs, ev.at, next.runs)
      if (next.fields?.length) {
        paragraph.fields = [...(paragraph.fields ?? []), ...next.fields]
        paragraph.shown = [...(paragraph.shown ?? []), ...(next.shown ?? [])]
      }
      paragraphs.splice(i + 1, 1)
      return true
    }
    case 'style':
      paragraph.style = ev.style
      return true
    case 'item':
      paragraph.item = ev.item
      if (!ev.item) delete paragraph.label
      return true
    case 'paragraph_fields':
      paragraph.fields = ev.fields
      return true
    case 'paragraph_generated':
      if (ev.generated && paragraph.text) return false // a table of contents holds no text: the replica is out of step
      paragraph.generated = ev.generated
      if (!ev.generated) delete paragraph.entries
      return true
  }
}

// ------------------------------------------------------------------------------ where things go
/** Where a stretch of text is after an event (`follow` of the commands). A cut-away stretch becomes empty. */
export function followSpan(span: Span, ev: TextEvent): Span {
  const { paragraph, start, end } = span
  switch (ev.type) {
    case 'text': {
      if (paragraph !== ev.paragraph) return span
      if (ev.inserted && !ev.removed) {
        const n = ev.inserted.length
        if (ev.offset <= start) return { paragraph, start: start + n, end: end + n }
        if (ev.offset < end) return { paragraph, start, end: end + n }
        return span
      }
      const moved = (p: number) => p - Math.min(Math.max(p - ev.offset, 0), ev.removed)
      return { paragraph, start: moved(start), end: moved(end) }
    }
    case 'split':
      if (paragraph !== ev.paragraph) return span
      if (start >= ev.offset) return { paragraph: ev.new_id, start: start - ev.offset, end: end - ev.offset }
      return { paragraph, start, end: Math.min(end, ev.offset) }
    case 'join':
      return paragraph === ev.paragraph ? { paragraph: ev.into, start: start + ev.at, end: end + ev.at } : span
    case 'style':
    case 'item':
    case 'labels':
    case 'paragraph_generated':
    case 'generated':
    case 'paragraph_fields':
    case 'fields':
      return span
  }
}

export function followPos(pos: Pos, ev: TextEvent): Pos {
  const moved = followSpan({ paragraph: pos.paragraph, start: pos.offset, end: pos.offset }, ev)
  return { paragraph: moved.paragraph, offset: moved.start }
}

/** Is `a` before `b` in the document? */
export function before(paragraphs: Paragraph[], a: Pos, b: Pos): boolean {
  const [i, j] = [indexOf(paragraphs, a.paragraph), indexOf(paragraphs, b.paragraph)]
  return i < j || (i === j && a.offset < b.offset)
}

export function ordered(paragraphs: Paragraph[], a: Pos, b: Pos): [Pos, Pos] {
  return before(paragraphs, b, a) ? [b, a] : [a, b]
}

/** The text between two positions, paragraphs separated by line breaks. */
export function textBetween(paragraphs: Paragraph[], from: Pos, to: Pos): string {
  const [a, b] = ordered(paragraphs, from, to)
  const [i, j] = [indexOf(paragraphs, a.paragraph), indexOf(paragraphs, b.paragraph)]
  if (i < 0 || j < 0) return ''
  if (i === j) return paragraphs[i]!.text.slice(a.offset, b.offset)
  return [paragraphs[i]!.text.slice(a.offset), ...paragraphs.slice(i + 1, j).map((x) => x.text), paragraphs[j]!.text.slice(0, b.offset)].join('\n')
}

/** The start of the word before `offset` (or of the whitespace and punctuation in between), as Ctrl+Backspace goes. */
export function wordStart(text: string, offset: number): number {
  let i = offset
  while (i > 0 && !/\w/u.test(text[i - 1]!)) i--
  while (i > 0 && /\w/u.test(text[i - 1]!)) i--
  return i
}

/** The end of the word after `offset`, as Ctrl+Delete goes. */
export function wordEnd(text: string, offset: number): number {
  let i = offset
  while (i < text.length && !/\w/u.test(text[i]!)) i++
  while (i < text.length && /\w/u.test(text[i]!)) i++
  return i
}

/** Words in a text: the count the footer shows. */
export function countWords(paragraphs: Paragraph[]): number {
  let n = 0
  for (const b of paragraphs) n += b.text.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)?.length ?? 0
  return n
}

// ------------------------------------------------------------------------------ characters
// The server counts code points (Python), JavaScript counts UTF-16 units: they differ for emoji and the like. The replica
// works in units; everything that crosses the wire is converted here, with the text it refers to at hand.

/** The UTF-16 offset of the `cp`-th code point of `text`. */
export function unitOf(text: string, cp: number): number {
  let unit = 0
  for (let n = 0; n < cp && unit < text.length; n++) unit += text.codePointAt(unit)! > 0xffff ? 2 : 1
  return unit
}

/** The code point offset of the UTF-16 offset `unit` of `text`. */
export function pointOf(text: string, unit: number): number {
  let n = 0
  for (let i = 0; i < unit && i < text.length; n++) i += text.codePointAt(i)! > 0xffff ? 2 : 1
  return n
}

/** Runs counted in code points, as `text` has them in UTF-16 units. */
export function runsToUnits(text: string, runs: Run[]): Run[] {
  let at = 0
  return runs.map(([length, author, via]) => {
    const end = unitOf(text.slice(at), length)
    const run: Run = [end, author, via]
    at += end
    return run
  })
}

/** Runs in UTF-16 units, as the server counts them (code points). */
export function runsToPoints(text: string, runs: Run[]): Run[] {
  let at = 0
  return runs.map(([length, author, via]) => {
    const run: Run = [pointOf(text.slice(at, at + length), length), author, via]
    at += length
    return run
  })
}

/** An event as the server sent it (code points) in UTF-16 units, judged against the paragraphs it will be applied to. */
export function eventInUnits(paragraphs: Paragraph[], ev: TextEvent): TextEvent {
  if (ev.type === 'labels' || ev.type === 'generated' || ev.type === 'fields') return ev
  const text = paragraphs.find((b) => b.id === (ev.type === 'join' ? ev.into : ev.paragraph))?.text ?? ''
  switch (ev.type) {
    case 'text': {
      const offset = unitOf(text, ev.offset)
      const removed = unitOf(text.slice(offset), ev.removed)
      return { ...ev, offset, removed, runs: runsToUnits(ev.inserted, ev.runs) }
    }
    case 'split':
      return { ...ev, offset: unitOf(text, ev.offset) }
    case 'join':
      return { ...ev, at: unitOf(text, ev.at) }
    case 'style':
    case 'item':
    case 'paragraph_generated':
    case 'paragraph_fields':
      return ev
  }
}
