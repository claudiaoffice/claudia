// How the browser's own lines are made to go round an object (CODE-64, D1068). The layout engine does this for the
// printed pages and the print preview (D1062); the flowing editor is the browser's, so it is told with CSS floats: an
// invisible box in the paragraph an object hangs from, as wide and as high as the room the object takes from the lines.
//
// A float can only take room from one side of a line, from the edge of the paragraph to the object: the words the
// engine sets *beside* the object on the far side are not set there by the browser (the printed page shows them). A
// float also cannot start above the paragraph it is in. Both are the browser's limits, and are said here, not hidden.
import type { Wrap } from '@claudia/layout'

/** A rectangle, in the coordinates of the page the editor is shown on. */
export interface Rect {
  left: number
  top: number
  width: number
  height: number
}

/** The room an object takes from the lines of the paragraph it hangs from, as a CSS float. */
export interface WrapFloat {
  /** The side of the paragraph the box floats to. */
  side: 'left' | 'right'
  /** How far it reaches in from that side (`px`). */
  width: number
  /** How tall it is (`px`). */
  height: number
  /** How far below the top of the paragraph it begins (`px`, never negative: a float cannot rise above its paragraph). */
  top: number
}

/** The modes that take room from the lines. */
export const takesRoom = (wrap: Wrap): boolean => wrap === 'around' || wrap === 'above-below'

/**
 * The box of an object `w` by `h` anchored at `spot`, moved by `away`, kept inside the text `column` across (as the
 * printed pages keep it): where the object is drawn (`floatBox` of text-containers.ts, in page coordinates).
 */
export function objectRect(spot: { left: number; top: number }, away: { dx?: number; dy?: number }, w: number, h: number, column?: Rect): Rect {
  let left = spot.left + (away.dx ?? 0)
  if (column) left = Math.max(column.left, Math.min(left, column.left + column.width - w))
  return { left, top: spot.top + (away.dy ?? 0), width: w, height: h }
}

const clamp = (value: number, least: number, most: number) => Math.max(least, Math.min(value, most))

/**
 * The float that makes the lines of a paragraph (content box `paragraph`) keep `gap` pixels from `box`, or `null` for
 * a mode that takes no room. *Above and below* takes the whole width, so that the words stop above and go on below;
 * *around* takes the side the object is nearer to, from the paragraph's edge to the far side of the object.
 */
export function floatFor(wrap: Wrap, gap: number, box: Rect, paragraph: Pick<Rect, 'left' | 'top' | 'width'>): WrapFloat | null {
  if (!takesRoom(wrap)) return null
  const top = Math.max(0, box.top - gap - paragraph.top)
  const height = box.height + 2 * gap
  if (wrap === 'above-below') return { side: 'left', width: paragraph.width, height, top }
  const edge = paragraph.left + paragraph.width
  const nearer = box.left + box.width / 2 < paragraph.left + paragraph.width / 2 ? 'left' : 'right'
  const width = nearer === 'left' ? box.left + box.width + gap - paragraph.left : edge - (box.left - gap)
  return { side: nearer, width: clamp(width, 0, paragraph.width), height, top }
}

/** The style of the box a float is drawn with. */
export function floatStyle(f: WrapFloat | undefined): Record<string, string> {
  if (!f) return { display: 'none' }
  return { float: f.side, width: `${f.width}px`, height: `${f.height}px`, marginTop: `${f.top}px` }
}

/** An object the words go round, with what decides how: where it hangs, how it is moved off there, how large it is. */
export interface Hung {
  id: string
  block: string
  offset: number
  wrap: Wrap
  gap: number
  dx?: number
  dy?: number
  w: number
  h: number
}

/** What measuring needs of the page: the browser's in the editor, an invented one in the tests. */
export interface WrapPage {
  /** Take every float out of the lines. */
  clear(): void
  /** The top-left corner of the text, as the lines are now: the page can shift under a measurement (taking the floats
   * out shortens it, and the browser keeps the view where it was), so each place is measured from here, at the same
   * moment, and kept from here, not from the screen. */
  origin(): { left: number; top: number }
  /** The text column objects are kept inside across, as the lines are now. */
  column(): Rect
  /** The top-left corner of the character an object hangs from, as the lines are now. */
  spotOf(block: string, offset: number): { left: number; top: number } | null
  /** The content box of a paragraph, as the lines are now. */
  paragraphOf(block: string): Pick<Rect, 'left' | 'top' | 'width'> | null
  /** Put the float of `id` into the lines (`null`: it takes no room). */
  put(id: string, f: WrapFloat | null): void
}

/** The floats of `hung` (in the order of the text) and the place each object hangs at, from the top left of the text
 * (`WrapPage.origin`). Each is measured with the floats
 * before it in the lines and its own out of them, so that no object is measured against its own box, and the same text
 * always gives the same boxes. */
export function measureFloats(
  hung: readonly Hung[],
  page: WrapPage,
): { floats: Record<string, WrapFloat>; spots: Map<string, { left: number; top: number }> } {
  const floats: Record<string, WrapFloat> = {}
  const spots = new Map<string, { left: number; top: number }>()
  page.clear()
  for (const h of hung) {
    // all of it read at the same moment: the lines do not change between the reads
    const origin = page.origin()
    const spot = page.spotOf(h.block, h.offset)
    const paragraph = page.paragraphOf(h.block)
    if (!spot || !paragraph) continue
    spots.set(`${h.block}:${h.offset}`, { left: spot.left - origin.left, top: spot.top - origin.top })
    const f = floatFor(h.wrap, h.gap, objectRect(spot, h, h.w, h.h, page.column()), paragraph)
    page.put(h.id, f)
    if (f) floats[h.id] = f
  }
  return { floats, spots }
}
