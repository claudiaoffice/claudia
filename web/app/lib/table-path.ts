// The tables of a composes text are on the same path for the arrow keys as its paragraphs (D1330, D1331): a table
// hangs from a paragraph and is shown after it, several in the order of their anchors. These say where the caret goes
// when it leaves a table, and which table it goes into from the words; the editor does what they say.

/** A paragraph of the text, as far as this path needs it: its id, its length and the tables shown after it. */
export interface PathBlock {
  id: string
  length: number
  tables: readonly string[] // object ids, in the order they are shown
}

/** Where the caret goes: into a table (`first` box, first box of the `lastRow`, the end of the `lastBox`), to a
 *  place in a paragraph, or to a paragraph that is to be made after `after` because the text ends there. */
export type Landing =
  | { kind: 'table'; object: string; where: 'first' | 'lastRow' | 'lastBox' }
  | { kind: 'text'; block: string; offset: number }
  | { kind: 'new'; after: string }

/** Where the caret goes when it leaves the table `object` to `side`. `null` if the table is not on the path. */
export function pastTable(blocks: readonly PathBlock[], object: string, side: 'before' | 'after'): Landing | null {
  const i = blocks.findIndex((b) => b.tables.includes(object))
  if (i < 0) return null
  const block = blocks[i]!
  const j = block.tables.indexOf(object)
  if (side === 'before') {
    const previous = block.tables[j - 1]
    return previous ? { kind: 'table', object: previous, where: 'lastRow' } : { kind: 'text', block: block.id, offset: block.length }
  }
  const next = block.tables[j + 1]
  if (next) return { kind: 'table', object: next, where: 'first' }
  const following = blocks[i + 1]
  return following ? { kind: 'text', block: following.id, offset: 0 } : { kind: 'new', after: block.id }
}

/** The table the down arrow goes into from the last line of `block`, if one hangs from it. */
export function tableBelow(blocks: readonly PathBlock[], block: string): string | null {
  return blocks.find((b) => b.id === block)?.tables[0] ?? null
}

/** The table the up arrow (and Backspace at the start) goes into from the first line of `block`: the last one that
 *  hangs from the paragraph before it, if any. */
export function tableAbove(blocks: readonly PathBlock[], block: string): string | null {
  const i = blocks.findIndex((b) => b.id === block)
  return i > 0 ? (blocks[i - 1]!.tables.at(-1) ?? null) : null
}

/** Whether the text ends with a table: then the end of the text is after it, in a paragraph still to be made. */
export function endsWithTable(blocks: readonly PathBlock[]): boolean {
  return (blocks.at(-1)?.tables.length ?? 0) > 0
}
