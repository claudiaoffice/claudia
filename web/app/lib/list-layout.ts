// Where a list item sits (E9.21): how far a level moves the text in, and the gap to the next item of its list.
// The marker itself is drawn by CSS from the paragraph's `data-marker` (see `TextEditor.vue`); this only works out the
// numbers the CSS needs, from the scheme the server sent, so that the indent of a level is one place's decision.
import type { Block } from './blocks'
import type { ListInfo, SchemeInfo } from './text-session'

const DEFAULT_STEP = 1.6
const DEFAULT_GAP = 0.25

/** The CSS custom properties of the list item at `index`, or `null` for a paragraph that is no item.
 * `--item-left` is where the marker's box starts, `--item-pad` where the text does, `--item-step` is the width of the
 * box in between; `--item-gap` is only there while the next paragraph is an item of the same list. */
export function itemLayout(blocks: Block[], index: number, lists: ListInfo[], schemes: SchemeInfo[]): Record<string, string> | null {
  const item = blocks[index]?.item
  if (!item) return null
  const scheme = schemes.find((s) => s.id === lists.find((l) => l.id === item.list)?.scheme)
  const step = scheme?.indent ?? DEFAULT_STEP
  const css: Record<string, string> = {
    '--item-left': `${item.level * step}em`,
    '--item-step': `${step}em`,
    '--item-pad': `${(item.level + 1) * step}em`,
  }
  if (blocks[index + 1]?.item?.list === item.list) css['--item-gap'] = `${scheme?.gap ?? DEFAULT_GAP}em`
  return css
}
