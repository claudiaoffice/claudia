/**
 * Text in a box of fixed size: a creates text box or shape label, a composes floating object, a computes cell.
 *
 * A box never grows, scrolls or shrinks its text: the paragraph is laid out to the box's inner width and whatever
 * lies past the box's border is not drawn (D182). The display group carries the border box as its clip, so the PDF
 * and the screen cut at the same place, even through the middle of a line.
 *
 * @module
 */
import { decorationItems, insets, lineItems } from '../display/text'
import type { DisplayItem, GroupItem, Rect } from '../display/list'
import type { FontSet } from '../fonts/fontset'
import { type BoxDecoration, NO_DECORATION } from './css'
import { layoutParagraph, type ParagraphLayout } from './paragraph'
import type { ParagraphStyle } from './style'

export interface BoxLayout {
  /** the border box, relative to the box's own origin (0, 0) */
  width: number
  height: number
  decoration: BoxDecoration
  /** the content box, relative to the box */
  content: Rect
  paragraph: ParagraphLayout | null
  /** top of the first line, relative to the box (after vertical alignment) */
  textTop: number
  /** lines that can be seen at least in part */
  visibleLines: number
  /** true when some text lies outside the box and is cut off */
  clipped: boolean
}

/**
 * Lay out `text` (or no text: `null`) in a box of `width` × `height` mpt with `style` and `decoration`, aligned
 * to the top, middle or bottom of the content box.
 */
export function layoutBox(
  fonts: FontSet,
  text: string | null,
  style: ParagraphStyle | null,
  width: number,
  height: number,
  decoration: BoxDecoration = NO_DECORATION,
  verticalAlign: 'top' | 'middle' | 'bottom' = 'top',
): BoxLayout {
  const inset = insets(decoration)
  const content: Rect = { x: inset.left, y: inset.top, w: Math.max(0, width - inset.left - inset.right), h: Math.max(0, height - inset.top - inset.bottom) }
  if (text === null || !style) return { width, height, decoration, content, paragraph: null, textTop: content.y, visibleLines: 0, clipped: false }
  const paragraph = layoutParagraph(fonts, style, text, content.w)
  const free = content.h - paragraph.height
  const shift = verticalAlign === 'middle' ? Math.floor(free / 2) : verticalAlign === 'bottom' ? free : 0
  // a paragraph taller than its box starts at the top, whatever the alignment, so its first words can be read
  const textTop = content.y + (free < 0 ? 0 : shift)
  let visible = 0
  let y = textTop
  for (const _ of paragraph.lines) {
    if (y < height) visible++
    y += style.lineHeight
  }
  const clipped = paragraph.overflows || textTop + paragraph.height > height
  return { width, height, decoration, content, paragraph, textTop, visibleLines: visible, clipped }
}

/** The display group of a box placed with its top left at (`x`, `y`) and rotated by `rotation` degrees about its centre. */
export function boxItems(fonts: FontSet, box: BoxLayout, x: number, y: number, rotation = 0): GroupItem {
  const items: DisplayItem[] = decorationItems({ x, y, w: box.width, h: box.height }, box.decoration)
  const p = box.paragraph
  if (p) {
    let top = y + box.textTop
    for (let i = 0; i < box.visibleLines; i++) {
      const line = p.lines[i]!
      items.push(...lineItems(fonts, p, line, x + box.content.x, top))
      top += line.height
    }
  }
  return {
    kind: 'group',
    clip: { x, y, w: box.width, h: box.height },
    rotation: Math.round(rotation),
    origin: { x: x + Math.floor(box.width / 2), y: y + Math.floor(box.height / 2) },
    items,
  }
}
