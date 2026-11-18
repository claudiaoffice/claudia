/**
 * The rows a paragraph beside floating objects is poured into (D1061, D1062).
 *
 * Line breaking needs to know how wide line `i` may be, and that depends on where line `i` falls on the page, which
 * depends on the lines before it. Rows break the circle: from where the paragraph starts (a page and a top), the rows
 * it will occupy follow without looking at its words, since every row is as tall as a line. A row is one or more
 * free stretches left to right ({@link Slot}s); a row an object keeps free is skipped, and the space skipped is the
 * `lead` of the row after it; a row that would pass the bottom of a page goes to the top of the next.
 *
 * Lines are placed by these rows and not by the page's own pouring, so the caller checks, after paginating, that every
 * line landed where its row said it would (the paragraph moved, or a page break came earlier), and lays the paragraph
 * out again from where it now starts.
 *
 * @module
 */
import type { Slot, SlotSource } from '../text/paragraph'
import { type Column, type Exclusion, firstRowAt, slotsAt } from './exclusions'

export interface RowsInit {
  /** where the first line would stand: a page (from 0) and a top in that page's content box, mpt */
  start: { page: number; top: number }
  lineHeight: number
  /** the height of a page's content box */
  pageHeight: number
  /** the paragraph's own column, `left` 0, in the coordinates of the paragraph's content box */
  column: Column
  /** the objects of a page, in the coordinates of the paragraph's content box (`y` from the top of the page's box) */
  exclusions: (page: number) => readonly Exclusion[]
  /** a stretch narrower than this is not used */
  minWidth: number
}

/** Where a line's row is: the page (from 0) and the top in that page's content box. */
export interface RowPlace {
  page: number
  y: number
}

export class Rows implements SlotSource {
  private readonly slots: Slot[] = []
  private readonly places: RowPlace[] = []
  private page: number
  private y: number
  private row = 0

  constructor(private readonly init: RowsInit) {
    this.page = init.start.page
    this.y = init.start.top
  }

  /** The slot line `line` goes into. */
  at(line: number): Slot {
    this.fill(line)
    return this.slots[line]!
  }

  /** Where line `line`'s row is. */
  place(line: number): RowPlace {
    this.fill(line)
    return this.places[line]!
  }

  private fill(line: number): void {
    while (this.slots.length <= line) this.nextRow()
  }

  private nextRow(): void {
    const { lineHeight: h, pageHeight, column, minWidth } = this.init
    for (;;) {
      const objects = this.init.exclusions(this.page)
      const top = firstRowAt(this.y, h, column, objects, minWidth)
      // a row that does not fit goes to the next page; one that cannot fit anywhere is taken at the top of a page
      if (top + h > pageHeight && top > 0) {
        this.page++
        this.y = 0
        continue
      }
      const free = slotsAt(top, h, column, objects, minWidth)
      const row = this.row++
      const lead = top - this.y
      const at = { page: this.page, y: top }
      if (free.length === 0) free.push({ x: column.left, w: column.right - column.left }) // a column narrower than minWidth
      free.forEach((s, i) => {
        this.slots.push({ x: s.x, w: s.w, row, lead: i === 0 ? lead : 0 })
        this.places.push(at)
      })
      this.y = top + h
      return
    }
  }
}
