import { describe, expect, it } from 'vitest'
import type { Exclusion } from '../src/flow/exclusions'
import { Rows, type RowsInit } from '../src/flow/rows'

// a column 400 000 wide, rows 20 000 tall, pages 200 000 tall; one object on page 0: 100 000 × 60 000 at (150 000, 100 000)
const object = { x: 150_000, y: 100_000, w: 100_000, h: 60_000 }
const init = (wrap: Exclusion['wrap'], start = { page: 0, top: 0 }, extra: Partial<RowsInit> = {}): RowsInit => ({
  start,
  lineHeight: 20_000,
  pageHeight: 200_000,
  column: { left: 0, right: 400_000 },
  exclusions: (page) => (page === 0 ? [{ box: object, wrap, gap: 10_000 }] : []),
  minWidth: 30_000,
  ...extra,
})

describe('the rows a paragraph is poured into', () => {
  it('are whole rows stacked from the start while nothing is in the way', () => {
    const r = new Rows(init('around'))
    expect(r.at(0)).toEqual({ x: 0, w: 400_000, row: 0, lead: 0 })
    expect(r.place(0)).toEqual({ page: 0, y: 0 })
    expect(r.place(3)).toEqual({ page: 0, y: 60_000 })
  })

  it('have a left and a right slot, in that order, on the rows beside an "around" object', () => {
    const r = new Rows(init('around'))
    // rows start at 0, 20k, 40k, 60k, 80k (band from 90k), so row 4 (80k..100k) is the first beside the object
    expect(r.at(4)).toMatchObject({ x: 0, w: 140_000, row: 4 })
    expect(r.at(5)).toMatchObject({ x: 260_000, w: 140_000, row: 4 })
    expect(r.place(4)).toEqual({ page: 0, y: 80_000 })
    expect(r.place(5)).toEqual({ page: 0, y: 80_000 })
    expect(r.at(6)).toMatchObject({ x: 0, w: 140_000, row: 5, lead: 0 })
    expect(r.place(6).y).toBe(100_000)
  })

  it('go on whole below an "above and below" object, and the first row there says how far it was pushed', () => {
    const r = new Rows(init('above-below'))
    // rows 0..60k are free; the row at 80k reaches the band (90k..170k): the next free row is at 170k
    expect(r.at(4)).toMatchObject({ x: 0, w: 400_000, row: 4, lead: 90_000 })
    expect(r.place(4)).toEqual({ page: 0, y: 170_000 })
  })

  it('start where the paragraph starts, also below the top of a page', () => {
    const r = new Rows(init('around', { page: 0, top: 50_000 }))
    expect(r.place(0)).toEqual({ page: 0, y: 50_000 })
    expect(r.at(0).lead).toBe(0)
  })

  it('continue on the next page, from its top, when a row would pass the bottom', () => {
    const r = new Rows(init('around', { page: 0, top: 170_000 }))
    expect(r.place(0)).toEqual({ page: 0, y: 170_000 })
    expect(r.place(1)).toEqual({ page: 1, y: 0 }) // 190 000 + 20 000 would pass 200 000
    expect(r.at(1)).toMatchObject({ row: 1, lead: 0 })
    expect(r.place(2)).toEqual({ page: 1, y: 20_000 })
  })

  it('see the objects of the page a row is on, so a page without any is plain', () => {
    const r = new Rows(init('above-below', { page: 1, top: 0 }))
    expect(r.at(7)).toEqual({ x: 0, w: 400_000, row: 7, lead: 0 })
  })

  it('carry a push at the top of a page as the lead of its first row', () => {
    const top = (page: number): Exclusion[] => (page === 1 ? [{ box: { x: 0, y: 0, w: 100_000, h: 40_000 }, wrap: 'above-below', gap: 0 }] : [])
    const r = new Rows(init('over', { page: 0, top: 180_000 }, { exclusions: top }))
    expect(r.place(0)).toEqual({ page: 0, y: 180_000 })
    expect(r.at(1)).toMatchObject({ row: 1, lead: 40_000 })
    expect(r.place(1)).toEqual({ page: 1, y: 40_000 })
  })

  it('accept a row that is taller than a page at the top of one, rather than looping', () => {
    const r = new Rows(init('over', { page: 0, top: 0 }, { lineHeight: 300_000 }))
    expect(r.place(0)).toEqual({ page: 0, y: 0 })
    expect(r.place(1)).toEqual({ page: 1, y: 0 })
  })

  it('answer any line in any order with the same slot', () => {
    const r = new Rows(init('around'))
    const late = r.at(9)
    expect(new Rows(init('around')).at(2)).toEqual(r.at(2))
    expect(r.at(9)).toEqual(late)
  })
})
