// The chat box shows a tag as a chip, but the message is still the text `[#name](thing:id)` (E5.20, D551). These are the
// rules for going between what the box holds and that text, and between a place in the box and a place in the text.
// Pure, so that each has a test; `ChatInput.vue` only does the DOM.
import { encodeTag } from './tags'

/** What a box holds, in order: words typed, and chips. A browser may split words over several pieces (or leave an empty
 * one), so the pieces are the box's children one by one. */
export type Piece = { type: 'text'; text: string } | { type: 'tag'; id: string; name: string }

/** The longest message (the chat's own limit). */
export const MAX_MESSAGE = 2000

/** The text of one piece: the words, or the tag as it is written into a message. */
export const textOf = (piece: Piece): string => (piece.type === 'text' ? piece.text : encodeTag(piece.id, piece.name))

/** The message the pieces make. */
export const messageOf = (pieces: readonly Piece[]): string => pieces.map(textOf).join('')

/** A place in the box: before the `inner`th character of a piece of words, or, for a chip, before it (`0`) or after it
 * (`1`). */
export interface Place {
  index: number
  inner: number
}

/** Where in the message a place is. */
export function offsetOf(pieces: readonly Piece[], place: Place): number {
  let offset = 0
  for (let i = 0; i < place.index && i < pieces.length; i++) offset += textOf(pieces[i]!).length
  const piece = pieces[place.index]
  if (!piece) return offset
  return offset + (piece.type === 'text' ? Math.min(place.inner, piece.text.length) : place.inner > 0 ? textOf(piece).length : 0)
}

/** The place at a position in the message. A position inside the text of a chip is after the chip: a chip is never
 * entered. */
export function placeOf(pieces: readonly Piece[], offset: number): Place {
  let from = 0
  for (let i = 0; i < pieces.length; i++) {
    const piece = pieces[i]!
    const length = textOf(piece).length
    const end = from + length
    if (piece.type === 'text' ? offset <= end : offset < end) {
      if (piece.type === 'text') return { index: i, inner: offset - from }
      return { index: i, inner: offset === from ? 0 : 1 }
    }
    from = end
  }
  const last = pieces.length - 1
  if (last < 0) return { index: 0, inner: 0 }
  const piece = pieces[last]!
  return { index: last, inner: piece.type === 'text' ? piece.text.length : 1 }
}
