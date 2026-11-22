// The tables of a composes text are on the same path for the arrow keys as its paragraphs (D1330, D1331): a table
// hangs from a paragraph and is shown after it, several in the order of their anchors. These say where the caret goes
// when it leaves a table, and which table it goes into from the words; the editor does what they say.

/** A paragraph of the text, as far as this path needs it: its id, its length and the tables shown after it. */
export interface PathParagraph {
  id: string
  length: number
  tables: readonly string[] // object ids, in the order they are shown
}

/** Where the caret goes: into a table (`first` box, first box of the `lastRow`, the end of the `lastBox`), to a
 *  place in a paragraph, or to a paragraph that is to be made after `after` because the text ends there. */
export type Landing =
  | { kind: 'table'; object: string; where: 'first' | 'lastRow' | 'lastBox' }
  | { kind: 'text'; paragraph: string; offset: number }
  | { kind: 'new'; after: string }

/** Where the caret goes when it leaves the table `object` to `side`. `null` if the table is not on the path. */
export function pastTable(paragraphs: readonly PathParagraph[], object: string, side: 'before' | 'after'): Landing | null {
  const i = paragraphs.findIndex((b) => b.tables.includes(object))
  if (i < 0) return null
  const paragraph = paragraphs[i]!
  const j = paragraph.tables.indexOf(object)
  if (side === 'before') {
    const previous = paragraph.tables[j - 1]
    return previous ? { kind: 'table', object: previous, where: 'lastRow' } : { kind: 'text', paragraph: paragraph.id, offset: paragraph.length }
  }
  const next = paragraph.tables[j + 1]
  if (next) return { kind: 'table', object: next, where: 'first' }
  const following = paragraphs[i + 1]
  return following ? { kind: 'text', paragraph: following.id, offset: 0 } : { kind: 'new', after: paragraph.id }
}

/** The table the down arrow goes into from the last line of `paragraph`, if one hangs from it. */
export function tableBelow(paragraphs: readonly PathParagraph[], paragraph: string): string | null {
  return paragraphs.find((b) => b.id === paragraph)?.tables[0] ?? null
}

/** The table the up arrow (and Backspace at the start) goes into from the first line of `paragraph`: the last one that
 *  hangs from the paragraph before it, if any. */
export function tableAbove(paragraphs: readonly PathParagraph[], paragraph: string): string | null {
  const i = paragraphs.findIndex((b) => b.id === paragraph)
  return i > 0 ? (paragraphs[i - 1]!.tables.at(-1) ?? null) : null
}

/** Whether the text ends with a table: then the end of the text is after it, in a paragraph still to be made. */
export function endsWithTable(paragraphs: readonly PathParagraph[]): boolean {
  return (paragraphs.at(-1)?.tables.length ?? 0) > 0
}
