import { describe, expect, it } from 'vitest'
import {
  coversWindow,
  followLabel,
  roleAt,
  roleCounts,
  tabMarks,
  windowAround,
  type Trace,
} from '~/lib/follow'

const trace = (extra: Partial<Trace> = {}): Trace => ({
  sheet: 's1',
  row: 7,
  col: 1,
  reach: 'group',
  cells: [
    [1, 1, 'input'],
    [2, 1, 'input'],
    [6, 1, 'calc'],
    [7, 1, 'calc'],
    [9, 1, 'output'],
  ],
  other: { s2: 2 },
  total: 7,
  connected: true,
  truncated: false,
  ...extra,
})

describe('which cells light up', () => {
  it('finds the part of a cell in the trace', () => {
    const t = trace()
    expect(roleAt(t, 1, 1)).toBe('input')
    expect(roleAt(t, 7, 1)).toBe('calc')
    expect(roleAt(t, 9, 1)).toBe('output')
  })
  it('knows no part for a cell that is not connected', () => {
    expect(roleAt(trace(), 0, 0)).toBeNull()
    expect(roleAt(null, 1, 1)).toBeNull()
  })
  it('counts the cells of each part', () => {
    expect(roleCounts(trace())).toEqual({ input: 2, calc: 2, output: 1 })
    expect(roleCounts(null)).toEqual({ input: 0, calc: 0, output: 0 })
  })
  it('marks the sheets where the connection goes on', () => {
    expect(tabMarks(trace())).toEqual({ s2: 2 })
    expect(tabMarks(trace({ other: {} }))).toEqual({})
    expect(tabMarks(null)).toEqual({})
  })
})

describe('what the server is asked about', () => {
  it('asks for the visible cells and one screen more around them', () => {
    expect(windowAround({ r0: 10, r1: 30, c0: 2, c1: 8 }, 10_000, 702)).toEqual([0, 0, 51, 15])
  })
  it('stays inside the sheet', () => {
    expect(windowAround({ r0: 0, r1: 9_990, c0: 0, c1: 700 }, 10_000, 702)).toEqual([0, 0, 9_999, 701])
  })
  it('asks again only when the screen has moved beyond what was asked for', () => {
    const asked: [number, number, number, number] = [0, 0, 50, 15]
    expect(coversWindow(asked, { r0: 10, r1: 30, c0: 2, c1: 8 })).toBe(true)
    expect(coversWindow(asked, { r0: 40, r1: 60, c0: 2, c1: 8 })).toBe(false)
    expect(coversWindow(null, { r0: 0, r1: 1, c0: 0, c1: 1 })).toBe(false)
  })
})

describe('what the pill says', () => {
  it('names the cell and the reach', () => {
    expect(followLabel(trace())).toBe('B8')
    expect(followLabel(null)).toBe('')
  })
})
