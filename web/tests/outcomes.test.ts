import { describe, expect, it } from 'vitest'
import {
  altText,
  canPair,
  chipsOf,
  dotFractions,
  inputNames,
  outcomeCaption,
  outcomesToTsv,
  shadeOf,
  shareBelow,
  stat,
  tornado,
  typingHint,
  type OutcomeTable,
  type Summary,
} from '~/lib/outcomes'

const summary = (extra: Partial<Summary> = {}): Summary => ({
  n: 9,
  errors: 0,
  sampled: false,
  min: -500,
  max: 10350,
  median: 4500,
  mean: 4416.67,
  points: [-500, 1500, 1900, 3100, 4500, 4500, 6000, 8400, 10350],
  ...extra,
})

// the pricing model of the mock-ups: Units sold {800, 1000, 1300} x Variable cost {9.5, 11, 14} -> Profit
const table = (): OutcomeTable => ({
  inputs: [
    { sheet: 's1', row: 2, col: 1, count: 3, labels: [null, null, null], label: 'Units sold' },
    { sheet: 's1', row: 3, col: 1, count: 3, labels: [null, null, null], label: 'Var. cost' },
  ],
  rows: [
    { choice: [0, 0], value: { t: 'int', v: 3100 } },
    { choice: [0, 1], value: { t: 'int', v: 1900 } },
    { choice: [0, 2], value: { t: 'int', v: -500 } },
    { choice: [1, 0], value: { t: 'int', v: 6000 } },
    { choice: [1, 1], value: { t: 'int', v: 4500 } },
    { choice: [1, 2], value: { t: 'int', v: 1500 } },
    { choice: [2, 0], value: { t: 'int', v: 10350 } },
    { choice: [2, 1], value: { t: 'int', v: 8400 } },
    { choice: [2, 2], value: { t: 'int', v: 4500 } },
  ],
  sampled: false,
  sensitivity: [
    { input: 0, low: 1500, high: 7800, low_choice: 0, high_choice: 2 },
    { input: 1, low: 1800, high: 6500, low_choice: 2, high_choice: 0 },
  ],
})

describe('what a cell with alternatives shows', () => {
  it('writes each alternative as the chip people read', () => {
    expect(chipsOf([{ t: 'int', v: 800 }, { t: 'float', v: 9.5 }, { t: 'text', v: 'low' }])).toEqual(['800', '9.5', 'low'])
  })
  it('keeps the name of a scenario next to its value', () => {
    expect(chipsOf([{ t: 'int', v: 800, l: 'low' }, { t: 'int', v: 1000, l: 'base' }])).toEqual(['low 800', 'base 1000'])
    expect(altText({ t: 'int', v: 800, l: 'low' })).toBe('low: 800')
  })
  it('says an error and a truth value as the grid does', () => {
    expect(altText({ t: 'error', v: '#DIV/0!' })).toBe('#DIV/0!')
    expect(altText({ t: 'bool', v: true })).toBe('TRUE')
  })
})

describe('what a result cell shows', () => {
  it('counts outcomes, samples and errors', () => {
    expect(outcomeCaption(summary())).toBe('9 outcomes')
    expect(outcomeCaption(summary({ n: 1 }))).toBe('1 outcome')
    expect(outcomeCaption(summary({ n: 2000, sampled: true }))).toBe('2000 samples')
    expect(outcomeCaption(summary({ errors: 2 }))).toBe('9 outcomes, 2 errors')
    expect(outcomeCaption(summary({ errors: 1 }))).toBe('9 outcomes, 1 error')
  })
  it('places the dots between the least and the greatest outcome', () => {
    const at = dotFractions([0, 5, 10])
    expect(at).toEqual([0, 0.5, 1])
  })
  it('puts all the dots in the middle when every outcome is the same', () => {
    expect(dotFractions([7, 7, 7])).toEqual([0.5, 0.5, 0.5])
    expect(dotFractions([])).toEqual([])
  })
  it('draws at most as many dots as fit, spread over all of them', () => {
    const many = Array.from({ length: 1000 }, (_, i) => i)
    const dots = dotFractions(many, 20)
    expect(dots).toHaveLength(20)
    expect(dots[0]).toBe(0)
    expect(dots.at(-1)).toBe(1)
  })
  it('formats a statistic for a cell and for a popover', () => {
    expect(stat(4500)).toBe('4,500')
    expect(stat(4416.6666)).toBe('4,416.67')
    expect(stat(-500)).toBe('−500')
    expect(stat(null)).toBe('–')
  })
})

describe('the threshold in the dot plot', () => {
  it('counts the outcomes below a value', () => {
    expect(shareBelow(summary().points, 0)).toEqual({ below: 1, total: 9, percent: 11 })
    expect(shareBelow(summary().points, 4500)).toEqual({ below: 4, total: 9, percent: 44 })
  })
  it('has no share without outcomes', () => {
    expect(shareBelow([], 0)).toEqual({ below: 0, total: 0, percent: 0 })
  })
})

describe('the outcome table', () => {
  it('names the inputs by the text beside them, else by position', () => {
    expect(inputNames(table())).toEqual(['Units sold', 'Var. cost'])
    const unnamed = table()
    unnamed.inputs[1]!.label = null
    expect(inputNames(unnamed)).toEqual(['Units sold', 'Input 2'])
  })
  it('lets inputs be paired only when there are several and they have as many alternatives each', () => {
    expect(canPair(table())).toBe(true)
    const uneven = table()
    uneven.inputs[1]!.count = 2
    expect(canPair(uneven)).toBe(false)
    expect(canPair({ ...table(), inputs: [table().inputs[0]!] })).toBe(false)
  })
  it('shades the dot of an alternative from light to dark', () => {
    expect(shadeOf(0, 3)).toBe(0)
    expect(shadeOf(2, 3)).toBe(1)
    expect(shadeOf(1, 3)).toBe(0.5)
    expect(shadeOf(0, 1)).toBe(1)
  })
  it('scales the bars of what moves the result most to one axis', () => {
    const bars = tornado(table())
    expect(bars.map((b) => b.name)).toEqual(['Units sold', 'Var. cost'])
    expect(bars[0]).toMatchObject({ low: 1500, high: 7800 })
    expect(bars[0]!.from).toBeCloseTo(0, 5)
    expect(bars[0]!.to).toBeCloseTo(1, 5)
    expect(bars[1]!.from).toBeGreaterThan(0)
    expect(bars[1]!.to).toBeLessThan(1)
    expect(bars[0]!.mean).toBeCloseTo(bars[1]!.mean, 5)
  })
  it('has no bars without sensitivity', () => {
    expect(tornado({ ...table(), sensitivity: [] })).toEqual([])
  })
  it('writes the outcomes as tab-separated text for a spreadsheet', () => {
    const tsv = outcomesToTsv(table(), (input, choice) => [['800', '1000', '1300'], ['9.5', '11', '14']][input]![choice]!, 'Profit')
    const lines = tsv.split('\n')
    expect(lines[0]).toBe('Units sold\tVar. cost\tProfit')
    expect(lines[1]).toBe('800\t9.5\t3100')
    expect(lines).toHaveLength(10)
  })
})

describe('typing alternatives', () => {
  it('counts the alternatives of what is typed', () => {
    expect(typingHint('{800, 1000, 1300}')).toEqual({ kind: 'list', count: 3 })
    expect(typingHint('{800..1300 step 250}')).toEqual({ kind: 'range', count: 3 })
    expect(typingHint('{low: 800, base: 1000, high: 1300}')).toEqual({ kind: 'named', count: 3 })
    expect(typingHint('{=B2*2, 5}')).toEqual({ kind: 'list', count: 2 })
  })
  it('does not count commas inside a formula', () => {
    expect(typingHint('{=SUM(A1,A2), 5}')).toEqual({ kind: 'list', count: 2 })
  })
  it('says nothing about anything that is not in braces', () => {
    expect(typingHint('=SUM(A1:A3)')).toBeNull()
    expect(typingHint('1000')).toBeNull()
    expect(typingHint('{800, 1000')).toBeNull() // still being typed
    expect(typingHint('{}')).toBeNull()
  })
})
