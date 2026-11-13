import { describe, expect, it } from 'vitest'
import {
  DISTRIBUTIONS,
  defaultParams,
  distribution,
  histogram,
  parseDiscrete,
  previewRequest,
  spanOf,
  validate,
} from '~/lib/random-generator'

describe('the distributions on offer', () => {
  it('has the twelve of RANDOM, in the order of the mock-up', () => {
    expect(DISTRIBUTIONS.map((d) => d.id)).toEqual([
      'uniform', 'normal', 'lognormal', 'triangular', 'pert', 'exponential', 'weibull', 'beta', 'gamma', 'binomial', 'poisson', 'discrete',
    ])
  })
  it('says which have no formula in Excel', () => {
    expect(DISTRIBUTIONS.filter((d) => !d.excel).map((d) => d.id)).toEqual(['triangular', 'poisson'])
  })
  it('lets only the continuous ones be cut', () => {
    for (const d of DISTRIBUTIONS) expect(d.continuous).toBe(!['binomial', 'poisson', 'discrete'].includes(d.id))
  })
  it('starts every distribution with parameters it accepts', () => {
    for (const d of DISTRIBUTIONS.filter((x) => x.id !== 'discrete')) {
      expect(defaultParams(d)).toHaveLength(d.params.length)
      expect(validate(d, defaultParams(d), null, null)).toBeNull()
    }
  })
  it('finds a distribution by id', () => {
    expect(distribution('normal').params.map((p) => p.key)).toEqual(['mean', 'spread'])
  })
})

describe('checking what is typed', () => {
  const normal = distribution('normal')
  it('wants numbers', () => {
    expect(validate(normal, [1000, Number.NaN], null, null)).toBe('number')
  })
  it('wants a spread above zero', () => {
    expect(validate(normal, [1000, 0], null, null)).toBe('positive')
  })
  it('wants the low limit below the high one', () => {
    expect(validate(normal, [1000, 150], 1200, 900)).toBe('limits')
    expect(validate(normal, [1000, 150], 900, null)).toBeNull()
  })
  it('wants a mode between the ends of a triangle', () => {
    expect(validate(distribution('triangular'), [9, 15, 14], null, null)).toBe('order')
    expect(validate(distribution('triangular'), [9, 11, 14], null, null)).toBeNull()
  })
  it('wants a chance between 0 and 1 for a binomial', () => {
    expect(validate(distribution('binomial'), [10, 1.5], null, null)).toBe('chance')
    expect(validate(distribution('binomial'), [10, 0.5], null, null)).toBeNull()
  })
})

describe('asking the server for a preview', () => {
  it('sends the numbers and only the limits that are on', () => {
    expect(previewRequest('normal', [1000, 150], { on: false, low: 0, high: null })).toEqual({ distribution: 'normal', params: [1000, 150] })
    expect(previewRequest('normal', [1000, 150], { on: true, low: 0, high: null })).toEqual({
      distribution: 'normal',
      params: [1000, 150],
      low: 0,
      high: null,
    })
  })
})

describe('discrete values', () => {
  it('reads a value and its weight from each line', () => {
    expect(parseDiscrete('10 1\n20 3\n')).toEqual([10, 1, 20, 3])
    expect(parseDiscrete('10, 1\n20; 3')).toEqual([10, 1, 20, 3])
  })
  it('gives a value without a weight the weight 1', () => {
    expect(parseDiscrete('10\n20 2')).toEqual([10, 1, 20, 2])
  })
  it('reports a line it cannot read', () => {
    expect(parseDiscrete('10 1\nabc')).toEqual({ line: 2 })
    expect(parseDiscrete('')).toEqual({ line: 1 })
  })
})

describe('the picture of the preview', () => {
  it('counts the draws in each bin', () => {
    const bins = histogram([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 5)
    expect(bins).toHaveLength(5)
    expect(bins.map((b) => b.count)).toEqual([2, 2, 2, 2, 2])
    expect(bins[0]!.from).toBe(0)
    expect(bins.at(-1)!.to).toBe(9)
  })
  it('puts the greatest draw into the last bin', () => {
    const bins = histogram([1, 1, 1, 5], 4)
    expect(bins.reduce((n, b) => n + b.count, 0)).toBe(4)
  })
  it('makes one bin of draws that are all the same', () => {
    expect(histogram([3, 3, 3], 5)).toEqual([{ from: 3, to: 3, count: 3 }])
    expect(histogram([], 5)).toEqual([])
  })
  it('finds the span that holds the middle two thirds of the draws', () => {
    const draws = Array.from({ length: 200 }, (_, i) => i)
    const [lo, hi] = spanOf(draws, 0.68)!
    expect(lo).toBeGreaterThan(30)
    expect(lo).toBeLessThan(40)
    expect(hi).toBeGreaterThan(160)
    expect(hi).toBeLessThan(170)
    expect(spanOf([], 0.68)).toBeNull()
  })
})
