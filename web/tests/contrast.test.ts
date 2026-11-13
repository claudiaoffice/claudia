import { describe, expect, it } from 'vitest'
import { contrastRatio, mix, parseHex } from './contrast'

describe('contrast arithmetic', () => {
  it('reads three- and six-digit hex colours', () => {
    expect(parseHex('#1f1a33')).toEqual([31, 26, 51])
    expect(parseHex('#fff')).toEqual([255, 255, 255])
  })

  it('refuses what is not a hex colour', () => {
    expect(() => parseHex('teal')).toThrow('not a hex colour')
  })

  it('gives 21:1 for black on white and 1:1 for a colour on itself', () => {
    expect(contrastRatio(parseHex('#000'), parseHex('#fff'))).toBeCloseTo(21, 5)
    expect(contrastRatio(parseHex('#5b4bc4'), parseHex('#5b4bc4'))).toBe(1)
  })

  it('does not care which colour is given first', () => {
    const a = parseHex('#767676')
    const white = parseHex('#fff')
    expect(contrastRatio(a, white)).toBe(contrastRatio(white, a))
  })

  it('matches the figure WCAG itself quotes: #767676 on white is the lightest grey that passes AA', () => {
    expect(contrastRatio(parseHex('#767676'), parseHex('#fff'))).toBeCloseTo(4.54, 2)
  })

  it('lays a colour over another by its percentage, like color-mix in srgb', () => {
    expect(mix(parseHex('#000'), 50, parseHex('#fff'))).toEqual([128, 128, 128])
    expect(mix(parseHex('#13917f'), 0, parseHex('#fff'))).toEqual([255, 255, 255])
    expect(mix(parseHex('#13917f'), 100, parseHex('#fff'))).toEqual([19, 145, 127])
  })
})
