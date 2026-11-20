// The anchor mark of an object in a composes text (D1352): where the object hangs, drawn while it is selected and
// while it is dragged, and what the label says about that place. Pure, so that the component only draws.
import type { Frame } from './geometry'

/** The longest word the label quotes; a longer one is cut with an ellipsis. */
const MAX_WORD = 24

/** The word that says where `offset` is in `text`: the word it is inside of (`within`), else the word right before it;
 *  `null` at the start of the paragraph, or when only spaces come before. For the label "after “allotment”" or
 *  "in “allotment”" (D1352). */
export function wordAt(text: string, offset: number): { word: string; within: boolean } | null {
  const at = Math.max(0, Math.min(offset, text.length))
  const within = at > 0 && at < text.length && /\S/.test(text[at - 1]!) && /\S/.test(text[at]!)
  const end = within ? at + (text.slice(at).match(/^\S*/)?.[0].length ?? 0) : at
  const word = text.slice(0, end).trimEnd().split(/\s+/).at(-1) ?? ''
  if (!word) return null
  return { word: word.length > MAX_WORD ? `${word.slice(0, MAX_WORD - 1)}…` : word, within }
}

/** The mark on the layer: a bar as high as the line at the character (`left`, `top`, `height`), and the dotted line
 *  from its foot down (or up) to the object's top edge and along it to the top left corner, as SVG points. */
export interface AnchorMark {
  left: number
  top: number
  height: number
  line: string
}

/** Where the mark of an object goes: `at` is the character's top left on the layer, `frame` the object's box there. */
export function anchorMark(at: { left: number; top: number }, lineHeight: number, frame: Frame): AnchorMark {
  const foot = at.top + lineHeight
  const line = [
    [at.left, frame.y > foot ? foot : at.top],
    [at.left, frame.y],
    [frame.x, frame.y],
  ]
    .map(([x, y]) => `${Math.round(x!)},${Math.round(y!)}`)
    .join(' ')
  return { left: at.left, top: at.top, height: lineHeight, line }
}
