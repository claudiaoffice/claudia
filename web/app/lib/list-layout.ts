// Where a list item sits (E9.21): how far a level moves the text in, and the gap to the next item of its list.
// The marker itself is drawn by CSS from the paragraph's `data-marker` (see `TextEditor.vue`); this turns the layout
// library's `itemGeometry` into the CSS custom properties it needs, so that the editor and the printed pages read one
// rule and a list looks the same in both (E9.22).
import { itemGeometry, MARKER_GAP_EM } from '@claudia/layout'
import type { Block } from './blocks'
import type { ListInfo, SchemeInfo } from './text-session'

/** The CSS custom properties of the list item at `index`, or `null` for a paragraph that is no item.
 * `--item-left` is where the marker's box starts, `--item-pad` where the text does, `--item-step` is the width of the
 * box in between and `--marker-gap` the space between the marker and the text; `--item-gap` is only there while the
 * next paragraph is an item of the same list. */
export function itemLayout(blocks: Block[], index: number, lists: ListInfo[], schemes: SchemeInfo[]): Record<string, string> | null {
  const at = itemGeometry(blocks, index, lists, schemes)
  if (!at) return null
  const css: Record<string, string> = {
    '--item-left': `${at.left}em`,
    '--item-step': `${at.step}em`,
    '--item-pad': `${at.pad}em`,
    '--marker-gap': `${MARKER_GAP_EM}em`,
  }
  if (at.gap !== null) css['--item-gap'] = `${at.gap}em`
  return css
}
