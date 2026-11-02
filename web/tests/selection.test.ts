import { describe, expect, it } from 'vitest'
import { bounds, jump, move, parseTsv, single, summarize, toTsv } from '~/lib/selection'

const SIZE = { rows: 10, cols: 5 }

describe('moving', () => {
  it('moves one cell and stays on the sheet', () => {
    expect(move(single(2, 2), 1, 0, false, SIZE)).toEqual(single(3, 2))
    expect(move(single(0, 0), -1, -1, false, SIZE)).toEqual(single(0, 0))
    expect(move(single(9, 4), 1, 1, false, SIZE)).toEqual(single(9, 4))
  })
  it('extends from where it started', () => {
    const s = move(move(single(2, 2), 1, 0, true, SIZE), 0, 1, true, SIZE)
    expect(s).toEqual({ row: 2, col: 2, row2: 3, col2: 3 })
    expect(bounds({ row: 3, col: 3, row2: 1, col2: 0 })).toEqual({ r0: 1, c0: 0, r1: 3, c1: 3 })
  })
  it('moving after extending starts from the far corner', () => {
    expect(move({ row: 0, col: 0, row2: 3, col2: 0 }, 1, 0, false, SIZE)).toEqual(single(4, 0))
  })
})

describe('jumping', () => {
  const data = new Set(['1,0', '2,0', '3,0', '6,0'])
  const filled = (r: number, c: number) => data.has(`${r},${c}`)
  it('runs to the end of a block', () => {
    expect(jump(single(1, 0), 1, 0, false, SIZE, filled)).toEqual(single(3, 0))
  })
  it('goes to the next filled cell from an empty one or the end of a block', () => {
    expect(jump(single(3, 0), 1, 0, false, SIZE, filled)).toEqual(single(6, 0))
    expect(jump(single(0, 0), 1, 0, false, SIZE, filled)).toEqual(single(1, 0))
  })
  it('ends at the edge when there is nothing more', () => {
    expect(jump(single(6, 0), 1, 0, false, SIZE, filled)).toEqual(single(9, 0))
    expect(jump(single(1, 0), -1, 0, false, SIZE, filled)).toEqual(single(0, 0))
  })
})

describe('summary', () => {
  it('counts and adds the numbers', () => {
    const cells: Record<string, any> = { '0,0': { t: 'int', v: 2 }, '1,0': { t: 'float', v: 4 }, '2,0': { t: 'text', v: 'x' } }
    const get = (r: number, c: number) => cells[`${r},${c}`] ?? null
    expect(summarize({ row: 0, col: 0, row2: 3, col2: 0 }, get)).toEqual({ count: 3, numbers: 2, sum: 6, average: 3 })
    expect(summarize(single(5, 5), get)).toEqual({ count: 0, numbers: 0, sum: 0, average: null })
  })
  it('skips huge selections instead of freezing', () => {
    expect(summarize({ row: 0, col: 0, row2: 100000, col2: 100 }, () => null).count).toBe(0)
  })
})

describe('clipboard', () => {
  it('round-trips text with tabs, new lines and quotes', () => {
    const rows = [['a', 'b\tc'], ['line\nbreak', '"quoted"'], ['', 'x']]
    expect(parseTsv(toTsv(rows))).toEqual(rows)
  })
  it('reads what spreadsheets put there', () => {
    expect(parseTsv('1\t2\n3\t4\n')).toEqual([['1', '2'], ['3', '4']])
    expect(parseTsv('1\t2\r\n3\t4')).toEqual([['1', '2'], ['3', '4']])
    expect(parseTsv('single')).toEqual([['single']])
    expect(parseTsv('')).toEqual([])
    expect(parseTsv('a\t\tb')).toEqual([['a', '', 'b']])
  })
})
