// Where a list item sits (E9.21, E9.22): how far a level moves the text in, the box its marker is drawn in, and the gap
// to the next item of its list. One rule for every place a list is drawn: the editor makes its CSS from it (the web
// app's `list-layout.ts`), the layout lays out pages with it, so a list looks the same on screen and printed.
import type { Css } from './css'

/** The indent of a level when the list's scheme has not said, in em. */
export const DEFAULT_STEP = 1.6
/** The gap between two items of one list when the scheme has not said, in em. */
export const DEFAULT_GAP = 0.25
/** The space between a marker's right edge and the text, in em. */
export const MARKER_GAP_EM = 0.45

/** A paragraph's place in a list: which list, and how deep. */
export interface ListItemRef {
  list: string
  level: number
}
/** A list as the server sends it: which scheme it is drawn with. */
export interface ListRef {
  id: string
  scheme: string
}
/** What of a scheme the geometry needs: its indent per level and the gap between items, both in em. */
export interface SchemeGeometry {
  id: string
  indent?: number
  gap?: number
}

/** Where the item at `index` sits, all in em of its own font size: the marker's box starts at `left` and is `step`
 *  wide, the text starts at `pad`; `gap` is the space to the next paragraph when that is an item of the same list,
 *  else `null` (the paragraph keeps its own space after). `null` for a paragraph that is no item. */
export interface ItemGeometry {
  left: number
  step: number
  pad: number
  gap: number | null
}

export function itemGeometry(
  paragraphs: readonly { item?: ListItemRef | null }[],
  index: number,
  lists: readonly ListRef[],
  schemes: readonly SchemeGeometry[],
): ItemGeometry | null {
  const item = paragraphs[index]?.item
  if (!item) return null
  const scheme = schemes.find((s) => s.id === lists.find((l) => l.id === item.list)?.scheme)
  const step = scheme?.indent ?? DEFAULT_STEP
  const next = paragraphs[index + 1]?.item
  return {
    left: item.level * step,
    step,
    pad: (item.level + 1) * step,
    gap: next && next.list === item.list ? (scheme?.gap ?? DEFAULT_GAP) : null,
  }
}

/** A marker is drawn upright and in the regular weight, whatever its paragraph's style is (as the editor's
 *  `::before` is): the style's CSS with those two set. */
export function markerCss(css: Css): Css {
  return { ...css, 'font-weight': '400', 'font-style': 'normal' }
}
