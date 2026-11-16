// The words of one paragraph cut into the pieces every view draws them in (E9.22, step A of
// claudiaoffice-log/notes/text-structure-across-apps.md): today the stretches a search found; the marker of a list
// item and the references in the text (E9.30) join them here, so that the slide, its thumbnail, the presenter and the
// editor all draw a paragraph from one function, and none of them can be left without what the others show.

/** Where a search found something in the words: from `start` to `end`, the one being looked at `current`. */
export interface Mark {
  start: number
  end: number
  current: boolean
}

/** A piece of the words of a paragraph, and how a search marks it. */
export interface Piece {
  text: string
  found: 'match' | 'current' | null
}

/** The words cut where the marks begin and end: the pieces joined are the words again. Marks that overlap or lie outside
 *  the words are fitted to them (a stale mark must not break the slide). */
export function piecesOf(words: string, marks: readonly Mark[]): Piece[] {
  const pieces: Piece[] = []
  let at = 0
  for (const m of [...marks].sort((a, b) => a.start - b.start)) {
    const start = Math.max(at, Math.min(m.start, words.length))
    const end = Math.max(start, Math.min(m.end, words.length))
    if (end === start) continue
    if (start > at) pieces.push({ text: words.slice(at, start), found: null })
    pieces.push({ text: words.slice(start, end), found: m.current ? 'current' : 'match' })
    at = end
  }
  if (at < words.length || pieces.length === 0) pieces.push({ text: words.slice(at), found: null })
  return pieces
}
