// The text replica: paragraphs with authorship runs, kept up to date by applying the server's state events, and the rules
// by which positions (my caret, a colleague's zone, a suggestion) move through those events. Every rule mirrors the
// `follow` of the command in claudia_composes, so that what the screen shows is what the server holds.

/** `[length, author, via]`: who wrote this stretch, and whose suggestion it came through. */
export type Run = [number, string | null, string | null]
/** A paragraph's place in a list: which list (an id of the document's lists) and the level, 0 being the outermost. */
export interface ListItem {
  list: string
  level: number
}
/** What is drawn in front of an item (derived by the server, never typed): a bullet or a number; `path` is the trail of
 * counters ("2.a" is `[2, 1]`), `null` for bullets. */
export interface Label {
  marker: string
  path: number[] | null
}
export interface Block {
  id: string
  style: string
  text: string
  runs: Run[]
  /** Set when the paragraph is a list item. */
  item?: ListItem | null
  /** Set when it is one and the server has counted it. */
  label?: Label
}
export interface Pos {
  block: string
  offset: number
}
export interface Span {
  block: string
  start: number
  end: number
}

/** The events of the text app (the part of the wire protocol that carries the document). */
export type TextEvent =
  | { type: 'text'; block: string; offset: number; removed: number; inserted: string; runs: Run[] }
  | { type: 'split'; block: string; offset: number; new_id: string; style: string }
  | { type: 'join'; block: string; into: string; at: number }
  | { type: 'style'; block: string; style: string }
  | { type: 'item'; block: string; item: ListItem | null }
  | { type: 'labels'; labels: Record<string, Label | null> }

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
export const indexOf = (blocks: Block[], id: string) => blocks.findIndex((b) => b.id === id)

/** Apply one event of the server to the paragraphs. `false` if the event does not fit (the replica is out of step). */
export function applyEvent(blocks: Block[], ev: TextEvent): boolean {
  if (ev.type === 'labels') {
    for (const [id, label] of Object.entries(ev.labels)) {
      const found = blocks[indexOf(blocks, id)]
      if (!found) continue // a paragraph that went away in the same step
      if (label) found.label = label
      else delete found.label
    }
    return true
  }
  const i = indexOf(blocks, ev.type === 'join' ? ev.into : ev.block)
  const block = blocks[i]
  if (!block) return false
  switch (ev.type) {
    case 'text': {
      if (ev.offset < 0 || ev.offset + ev.removed > block.text.length) return false
      block.text = block.text.slice(0, ev.offset) + ev.inserted + block.text.slice(ev.offset + ev.removed)
      const cut = ev.removed ? deleteRuns(block.runs, ev.offset, ev.offset + ev.removed) : block.runs
      block.runs = ev.inserted ? insertRuns(cut, ev.offset, ev.runs) : cut
      return true
    }
    case 'split': {
      if (ev.offset < 0 || ev.offset > block.text.length) return false
      const rest: Block = {
        id: ev.new_id,
        style: ev.style,
        text: block.text.slice(ev.offset),
        runs: sliceRuns(block.runs, ev.offset, block.text.length),
        ...(block.item ? { item: { ...block.item } } : {}), // an item makes an item; its label comes with the server's count
      }
      block.text = block.text.slice(0, ev.offset)
      block.runs = sliceRuns(block.runs, 0, ev.offset)
      blocks.splice(i + 1, 0, rest)
      return true
    }
    case 'join': {
      const next = blocks[i + 1]
      if (!next || next.id !== ev.block || block.text.length !== ev.at) return false
      block.text += next.text
      block.runs = insertRuns(block.runs, ev.at, next.runs)
      blocks.splice(i + 1, 1)
      return true
    }
    case 'style':
      block.style = ev.style
      return true
    case 'item':
      block.item = ev.item
      if (!ev.item) delete block.label
      return true
  }
}

// ------------------------------------------------------------------------------ where things go
/** Where a stretch of text is after an event (`follow` of the commands). A cut-away stretch becomes empty. */
export function followSpan(span: Span, ev: TextEvent): Span {
  const { block, start, end } = span
  switch (ev.type) {
    case 'text': {
      if (block !== ev.block) return span
      if (ev.inserted && !ev.removed) {
        const n = ev.inserted.length
        if (ev.offset <= start) return { block, start: start + n, end: end + n }
        if (ev.offset < end) return { block, start, end: end + n }
        return span
      }
      const moved = (p: number) => p - Math.min(Math.max(p - ev.offset, 0), ev.removed)
      return { block, start: moved(start), end: moved(end) }
    }
    case 'split':
      if (block !== ev.block) return span
      if (start >= ev.offset) return { block: ev.new_id, start: start - ev.offset, end: end - ev.offset }
      return { block, start, end: Math.min(end, ev.offset) }
    case 'join':
      return block === ev.block ? { block: ev.into, start: start + ev.at, end: end + ev.at } : span
    case 'style':
    case 'item':
    case 'labels':
      return span
  }
}

export function followPos(pos: Pos, ev: TextEvent): Pos {
  const moved = followSpan({ block: pos.block, start: pos.offset, end: pos.offset }, ev)
  return { block: moved.block, offset: moved.start }
}

/** Is `a` before `b` in the document? */
export function before(blocks: Block[], a: Pos, b: Pos): boolean {
  const [i, j] = [indexOf(blocks, a.block), indexOf(blocks, b.block)]
  return i < j || (i === j && a.offset < b.offset)
}

export function ordered(blocks: Block[], a: Pos, b: Pos): [Pos, Pos] {
  return before(blocks, b, a) ? [b, a] : [a, b]
}

/** The text between two positions, paragraphs separated by line breaks. */
export function textBetween(blocks: Block[], from: Pos, to: Pos): string {
  const [a, b] = ordered(blocks, from, to)
  const [i, j] = [indexOf(blocks, a.block), indexOf(blocks, b.block)]
  if (i < 0 || j < 0) return ''
  if (i === j) return blocks[i]!.text.slice(a.offset, b.offset)
  return [blocks[i]!.text.slice(a.offset), ...blocks.slice(i + 1, j).map((x) => x.text), blocks[j]!.text.slice(0, b.offset)].join('\n')
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
export function countWords(blocks: Block[]): number {
  let n = 0
  for (const b of blocks) n += b.text.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)?.length ?? 0
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
export function eventInUnits(blocks: Block[], ev: TextEvent): TextEvent {
  if (ev.type === 'labels') return ev
  const text = blocks.find((b) => b.id === (ev.type === 'join' ? ev.into : ev.block))?.text ?? ''
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
      return ev
  }
}
