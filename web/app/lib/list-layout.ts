// Where a list item sits (E9.21): how far a level moves the text in, and the gap to the next item of its list.
// The marker itself is drawn by CSS from the paragraph's `data-marker` (see `TextEditor.vue`); this turns the layout
// library's `itemGeometry` into the CSS custom properties it needs, so that the editor and the printed pages read one
// rule and a list looks the same in both (E9.22).
import { itemGeometry, MARKER_GAP_EM } from '@claudia/layout'
import type { Block } from './blocks'
import type { ListInfo, SchemeInfo } from './text-session'

/** After the style's own left padding, if it has one: where the printed page puts the marker and the text too. */
function after(own: string | undefined, em: number): string {
  return own && own !== '0' && own !== '0px' ? `calc(${own} + ${em}em)` : `${em}em`
}

/** The CSS of the list item at `index`, or `null` for a paragraph that is no item. `own` is the CSS of the paragraph's
 * style. `--item-left` is where the marker's box starts, `--item-step` its width and `--marker-gap` the space between the
 * marker and the text; `--item-pad` is where the text starts. The text's own `padding-left` and, while the next paragraph
 * is an item of the same list, its `margin-bottom` (the scheme's gap, also as `--item-gap`) are given here, not by a class
 * rule: the style's own CSS sits on the paragraph too, and a rule would lose against it (a quote's padding, body text's
 * space after). */
export function itemLayout(blocks: Block[], index: number, lists: ListInfo[], schemes: SchemeInfo[], own: Record<string, string> = {}): Record<string, string> | null {
  const at = itemGeometry(blocks, index, lists, schemes)
  if (!at) return null
  const css: Record<string, string> = {
    '--item-left': after(own['padding-left'], at.left),
    '--item-step': `${at.step}em`,
    '--item-pad': `${at.pad}em`,
    '--marker-gap': `${MARKER_GAP_EM}em`,
    'padding-left': after(own['padding-left'], at.pad),
  }
  if (at.gap !== null) {
    css['--item-gap'] = `${at.gap}em`
    css['margin-bottom'] = `${at.gap}em`
  }
  return css
}
