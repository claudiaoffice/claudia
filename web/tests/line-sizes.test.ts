import { describe, expect, it } from 'vitest'
import {
  buildSizeTable,
  DEFAULT_COL_WIDTH,
  DEFAULT_ROW_HEIGHT,
  formatPercent,
  indexAt,
  lineRange,
  lineSize,
  lineStart,
  offsetOf,
  percentChange,
  proportionalResize,
  SIZE_LIMITS,
} from '~/lib/line-sizes'

describe('lineSize', () => {
  it('is the default when a line has no override', () => {
    expect(lineSize(undefined, 3, 'row')).toBe(DEFAULT_ROW_HEIGHT)
    expect(lineSize(new Map([[1, 52]]), 3, 'col')).toBe(DEFAULT_COL_WIDTH)
  })
  it('is the override when there is one, including zero-ish small sizes', () => {
    expect(lineSize(new Map([[3, 52]]), 3, 'row')).toBe(52)
  })
})

describe('buildSizeTable / offsetOf', () => {
  it('adds no offset at all with no overrides', () => {
    const table = buildSizeTable(undefined, DEFAULT_ROW_HEIGHT)
    expect(offsetOf(table, 0)).toBe(0)
    expect(offsetOf(table, 9_999)).toBe(0)
  })

  it('accumulates the difference from the default for every override strictly before the index', () => {
    // row 3: 26 -> 52 (+26), row 5: 26 -> 78 (+52)
    const table = buildSizeTable(new Map([[3, 52], [5, 78]]), DEFAULT_ROW_HEIGHT)
    expect(offsetOf(table, 0)).toBe(0)
    expect(offsetOf(table, 3)).toBe(0) // nothing strictly before row 3 yet
    expect(offsetOf(table, 4)).toBe(26) // row 3's +26 now counts
    expect(offsetOf(table, 5)).toBe(26)
    expect(offsetOf(table, 6)).toBe(26 + 52)
    expect(offsetOf(table, 1_000)).toBe(78)
  })

  it('handles a line shrunk below the default too', () => {
    const table = buildSizeTable(new Map([[2, 13]]), DEFAULT_ROW_HEIGHT) // 26 -> 13: -13
    expect(offsetOf(table, 3)).toBe(-13)
  })
})

describe('lineStart / indexAt', () => {
  it('round-trips through pixel positions with no overrides', () => {
    const table = buildSizeTable(undefined, DEFAULT_COL_WIDTH)
    expect(lineStart(table, DEFAULT_COL_WIDTH, 0)).toBe(0)
    expect(lineStart(table, DEFAULT_COL_WIDTH, 5)).toBe(5 * DEFAULT_COL_WIDTH)
    expect(indexAt(table, DEFAULT_COL_WIDTH, 5 * DEFAULT_COL_WIDTH, 702)).toBe(5)
    expect(indexAt(table, DEFAULT_COL_WIDTH, 5 * DEFAULT_COL_WIDTH + DEFAULT_COL_WIDTH - 1, 702)).toBe(5)
    expect(indexAt(table, DEFAULT_COL_WIDTH, 5 * DEFAULT_COL_WIDTH + DEFAULT_COL_WIDTH, 702)).toBe(6)
  })

  it('clamps out-of-range pixel positions to the first and last line', () => {
    const table = buildSizeTable(undefined, DEFAULT_COL_WIDTH)
    expect(indexAt(table, DEFAULT_COL_WIDTH, -50, 702)).toBe(0)
    expect(indexAt(table, DEFAULT_COL_WIDTH, 999_999_999, 702)).toBe(701)
  })

  it('finds the right line around resized rows, including inside a resized row itself', () => {
    // row 3: 26 -> 52px tall. Row 3 now spans [3*26, 3*26+52) = [78, 130); row 4 starts at 130.
    const table = buildSizeTable(new Map([[3, 52]]), DEFAULT_ROW_HEIGHT)
    expect(lineStart(table, DEFAULT_ROW_HEIGHT, 3)).toBe(78)
    expect(lineStart(table, DEFAULT_ROW_HEIGHT, 4)).toBe(130)
    expect(indexAt(table, DEFAULT_ROW_HEIGHT, 77, 10_000)).toBe(2)
    expect(indexAt(table, DEFAULT_ROW_HEIGHT, 78, 10_000)).toBe(3)
    expect(indexAt(table, DEFAULT_ROW_HEIGHT, 129, 10_000)).toBe(3)
    expect(indexAt(table, DEFAULT_ROW_HEIGHT, 130, 10_000)).toBe(4)
  })
})

describe('percentChange / formatPercent', () => {
  it('rounds the percentage, signed', () => {
    expect(percentChange(26, 39)).toBe(50)
    expect(percentChange(96, 48)).toBe(-50)
    expect(percentChange(26, 26)).toBe(0)
  })
  it('treats a non-positive starting size as no percentage at all', () => {
    expect(percentChange(0, 10)).toBe(0)
  })
  it('formats with a leading sign except for no change', () => {
    expect(formatPercent(50)).toBe('+50%')
    expect(formatPercent(-33)).toBe('-33%')
    expect(formatPercent(0)).toBe('0%')
  })
})

describe('lineRange', () => {
  it('is inclusive of both ends, even a single line', () => {
    expect(lineRange(3, 5)).toEqual([3, 4, 5])
    expect(lineRange(3, 3)).toEqual([3])
  })
})

describe('proportionalResize', () => {
  const sizes = new Map([[3, 26], [4, 52], [5, 78]])
  const sizeOf = (i: number) => sizes.get(i) ?? DEFAULT_ROW_HEIGHT

  it('scales every other line by the same percentage the first line changed by (mockup 2 / 4\'s numbers)', () => {
    const out = proportionalResize([3, 4, 5], sizeOf, 3, 39, SIZE_LIMITS.row) // row 3: 26 -> 39, +50%
    expect(out).toEqual([
      [3, 39],
      [4, 78],
      [5, 117],
    ])
  })

  it('is the trivial single-line case when there is only one line', () => {
    expect(proportionalResize([3], sizeOf, 3, 39, SIZE_LIMITS.row)).toEqual([[3, 39]])
  })

  it('shrinking the first line shrinks the others by the same percentage', () => {
    const out = proportionalResize([3, 4], sizeOf, 3, 13, SIZE_LIMITS.row) // 26 -> 13, -50%
    expect(out).toEqual([
      [3, 13],
      [4, 26],
    ])
  })

  it('clamps the typed/dragged line into the limits', () => {
    const out = proportionalResize([3], sizeOf, 3, 5, SIZE_LIMITS.row) // below MIN_ROW_HEIGHT (8)
    expect(out).toEqual([[3, 8]])
  })

  it('clamps a line that the percentage would push outside the limits, without rejecting the rest', () => {
    const sizes2 = new Map([[0, 900], [1, 26]])
    const sizeOf2 = (i: number) => sizes2.get(i) ?? DEFAULT_ROW_HEIGHT
    // line 0 goes from 900 to 950 (a small +5.5%); line 1 would become ~27.4, fine; but scale line 0 by a lot more:
    const out = proportionalResize([0, 1], sizeOf2, 0, 990, SIZE_LIMITS.row) // +10% -> line 1 would be ~28.6, still fine
    expect(out[0]).toEqual([0, 990])
    // now push line 0 far enough that line 1's proportional size would exceed MAX_ROW_HEIGHT is unrealistic for rows,
    // so check the clamp the other direction: a tiny first line dragged tiny, scaling a big other line down past MIN
    const sizes3 = new Map([[0, 10], [1, 8]])
    const sizeOf3 = (i: number) => sizes3.get(i) ?? DEFAULT_ROW_HEIGHT
    const out2 = proportionalResize([0, 1], sizeOf3, 0, 5, SIZE_LIMITS.row) // asked for 5, clamped to MIN (8); ratio 8/10
    expect(out2).toEqual([
      [0, 8],
      [1, 8], // 8 * (8/10) = 6.4, clamped up to MIN_ROW_HEIGHT (8)
    ])
    void out
  })

  it('treats a zero-size first line as no-op scaling for the others (defensive; the server never stores zero)', () => {
    const sizes2 = new Map([[3, 0]])
    const sizeOf2 = (i: number) => sizes2.get(i) ?? DEFAULT_ROW_HEIGHT
    const out = proportionalResize([3, 4], sizeOf2, 3, 20, SIZE_LIMITS.row)
    expect(out).toEqual([
      [3, 20],
      [4, DEFAULT_ROW_HEIGHT],
    ])
  })
})
