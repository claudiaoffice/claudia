import { describe, expect, it } from 'vitest'
import { bandOf, firstRowAt, slotsAt, type Exclusion } from '../src/flow/exclusions'

// a column 400 000 mpt wide, rows 20 000 tall, an object box of 100 000 × 60 000 at (150 000, 100 000), gap 10 000
const column = { left: 0, right: 400_000 }
const box = { x: 150_000, y: 100_000, w: 100_000, h: 60_000 }
const around: Exclusion = { box, wrap: 'around', gap: 10_000 }
const aboveBelow: Exclusion = { box, wrap: 'above-below', gap: 10_000 }
const MIN = 30_000

describe('the band an object keeps free (D1061)', () => {
  it('is the box grown by the gap on every side for "around"', () => {
    expect(bandOf(around, column)).toEqual({ x: 140_000, y: 90_000, w: 120_000, h: 80_000 })
  })

  it('is the full column width, grown by the gap above and below, for "above and below"', () => {
    expect(bandOf(aboveBelow, column)).toEqual({ x: 0, y: 90_000, w: 400_000, h: 80_000 })
  })

  it('does not exist for "over" and "behind": those take no room', () => {
    expect(bandOf({ box, wrap: 'over', gap: 10_000 }, column)).toBeNull()
    expect(bandOf({ box, wrap: 'behind', gap: 10_000 }, column)).toBeNull()
  })

  it('is clipped to the column, so a box that sticks out does not make a negative stretch', () => {
    const out: Exclusion = { box: { x: 350_000, y: 100_000, w: 100_000, h: 60_000 }, wrap: 'around', gap: 0 }
    expect(bandOf(out, column)).toEqual({ x: 350_000, y: 100_000, w: 50_000, h: 60_000 })
  })
})

describe('the free stretches of a row', () => {
  it('is the whole column when no band reaches the row', () => {
    expect(slotsAt(0, 20_000, column, [around], MIN)).toEqual([{ x: 0, w: 400_000 }])
    expect(slotsAt(170_000, 20_000, column, [around], MIN)).toEqual([{ x: 0, w: 400_000 }])
  })

  it('is the two sides of the object, left to right, on a row inside its band', () => {
    expect(slotsAt(100_000, 20_000, column, [around], MIN)).toEqual([
      { x: 0, w: 140_000 },
      { x: 260_000, w: 140_000 },
    ])
  })

  it('counts a row that only touches the band as reached, and one that ends at its top as not', () => {
    expect(slotsAt(70_000, 20_000, column, [around], MIN)).toEqual([{ x: 0, w: 400_000 }]) // ends at 90 000
    expect(slotsAt(71_000, 20_000, column, [around], MIN)).toHaveLength(2) // overlaps 1 000
    expect(slotsAt(170_000, 20_000, column, [around], MIN)).toEqual([{ x: 0, w: 400_000 }]) // starts at 170 000
  })

  it('drops a stretch narrower than the minimum, so no word is stranded beside an object', () => {
    const wide: Exclusion = { box: { x: 20_000, y: 100_000, w: 360_000, h: 60_000 }, wrap: 'around', gap: 5_000 }
    // left stretch is 15 000, right 15 000: both below 30 000
    expect(slotsAt(100_000, 20_000, column, [wide], MIN)).toEqual([])
    const nearLeft: Exclusion = { box: { x: 20_000, y: 100_000, w: 200_000, h: 60_000 }, wrap: 'around', gap: 5_000 }
    expect(slotsAt(100_000, 20_000, column, [nearLeft], MIN)).toEqual([{ x: 225_000, w: 175_000 }])
  })

  it('is empty on a row inside an "above and below" band', () => {
    expect(slotsAt(100_000, 20_000, column, [aboveBelow], MIN)).toEqual([])
    expect(slotsAt(80_000, 20_000, column, [aboveBelow], MIN)).toEqual([]) // reaches 90 000..100 000
  })

  it('takes two objects on one row apart into three stretches, and ignores "over" and "behind"', () => {
    const second: Exclusion = { box: { x: 300_000, y: 100_000, w: 50_000, h: 60_000 }, wrap: 'around', gap: 10_000 }
    const over: Exclusion = { box: { x: 0, y: 0, w: 400_000, h: 400_000 }, wrap: 'over', gap: 0 }
    expect(slotsAt(100_000, 20_000, column, [second, around, over], MIN)).toEqual([
      { x: 0, w: 140_000 },
      { x: 260_000, w: 30_000 },
      { x: 360_000, w: 40_000 },
    ])
  })

  it('does not depend on the order the objects are given in', () => {
    const second: Exclusion = { box: { x: 300_000, y: 100_000, w: 50_000, h: 60_000 }, wrap: 'around', gap: 10_000 }
    expect(slotsAt(100_000, 20_000, column, [around, second], MIN)).toEqual(slotsAt(100_000, 20_000, column, [second, around], MIN))
  })
})

describe('the first row that has room', () => {
  it('is the top itself when it has room', () => {
    expect(firstRowAt(0, 20_000, column, [aboveBelow], MIN)).toBe(0)
  })

  it('goes on below an "above and below" band, so the object stands alone on its lines', () => {
    expect(firstRowAt(75_000, 20_000, column, [aboveBelow], MIN)).toBe(170_000)
  })

  it('goes on below the lowest band that leaves no stretch, and not below one that leaves room', () => {
    const wide: Exclusion = { box: { x: 20_000, y: 100_000, w: 360_000, h: 60_000 }, wrap: 'around', gap: 5_000 }
    expect(firstRowAt(100_000, 20_000, column, [wide], MIN)).toBe(165_000)
    expect(firstRowAt(100_000, 20_000, column, [around], MIN)).toBe(100_000)
  })

  it('steps over two bands that follow each other', () => {
    const next: Exclusion = { box: { x: 0, y: 175_000, w: 400_000, h: 40_000 }, wrap: 'above-below', gap: 0 }
    expect(firstRowAt(100_000, 20_000, column, [aboveBelow, next], MIN)).toBe(215_000)
  })
})
