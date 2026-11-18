/**
 * The room an object takes from the text round it (D1061): which stretches of a row of text are free.
 *
 * A floating object with a wrap of *around* or *above and below* keeps a **band** free: its box grown by a gap (the
 * full width of the column for *above and below*). A row of text asks one question, "how wide am I here?", and the
 * answer is the stretches of the column that no band reaching the row covers. *Over the text* and *behind the text*
 * take no room. Everything here is a pure function of whole mpt, so print, the print preview and any later editor
 * stage compute the same rows.
 *
 * The caller places the object first, from the layout without this object's wrap (its character's spot plus the
 * offset), so an object never moves the line it hangs from and no loop is possible (the rules on the mock-up).
 *
 * @module
 */

/** How text flows round an object; the model's `wrap` (D1061). */
export type Wrap = 'over' | 'around' | 'above-below' | 'behind'

/** An area in the page's content box, mpt. */
export interface Area {
  x: number
  y: number
  w: number
  h: number
}

/** An object's box with its wrap and the distance the text keeps from it. */
export interface Exclusion {
  box: Area
  wrap: Wrap
  /** mpt, kept on every side of the box */
  gap: number
}

/** The column the text runs in: from `left` to `right`, mpt. */
export interface Column {
  left: number
  right: number
}

/** A free stretch of a row. */
export interface Slot {
  x: number
  w: number
}

/** A stretch narrower than this many ems is not used, so no single word is stranded beside an object. */
export const MIN_SLOT_EM = 3

/** The band `e` keeps free, clipped to `column`, or `null` when it takes no room (*over*, *behind*, or outside). */
export function bandOf(e: Exclusion, column: Column): Area | null {
  if (e.wrap !== 'around' && e.wrap !== 'above-below') return null
  const y = e.box.y - e.gap
  const h = e.box.h + 2 * e.gap
  const left = e.wrap === 'above-below' ? column.left : Math.max(column.left, e.box.x - e.gap)
  const right = e.wrap === 'above-below' ? column.right : Math.min(column.right, e.box.x + e.box.w + e.gap)
  if (right <= left || h <= 0) return null
  return { x: left, y, w: right - left, h }
}

/** The bands that reach the row `[top, top + height)`: a row that only touches a band's edge is not reached. */
function reaching(top: number, height: number, column: Column, exclusions: readonly Exclusion[]): Area[] {
  const out: Area[] = []
  for (const e of exclusions) {
    const b = bandOf(e, column)
    if (b && top < b.y + b.h && top + height > b.y) out.push(b)
  }
  return out
}

/** The free stretches of the row `[top, top + height)`, left to right, each at least `minWidth` wide. */
export function slotsAt(top: number, height: number, column: Column, exclusions: readonly Exclusion[], minWidth: number): Slot[] {
  const bands = reaching(top, height, column, exclusions).sort((a, b) => a.x - b.x)
  const slots: Slot[] = []
  let at = column.left
  for (const b of bands) {
    if (b.x > at && b.x - at >= minWidth) slots.push({ x: at, w: b.x - at })
    at = Math.max(at, b.x + b.w)
  }
  if (column.right > at && column.right - at >= minWidth) slots.push({ x: at, w: column.right - at })
  return slots
}

/**
 * The top of the first row, at or below `top`, that has a free stretch: where the text goes on below an *above and
 * below* object, or below an object that leaves no stretch wide enough. When no band reaches the row the answer is
 * `top` itself, even if the column is narrower than `minWidth`: that is the caller's to handle, not a wrap.
 */
export function firstRowAt(top: number, height: number, column: Column, exclusions: readonly Exclusion[], minWidth: number): number {
  let at = top
  for (;;) {
    if (slotsAt(at, height, column, exclusions, minWidth).length > 0) return at
    const bands = reaching(at, height, column, exclusions)
    if (bands.length === 0) return at
    at = Math.min(...bands.map((b) => b.y + b.h))
  }
}
