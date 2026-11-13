import { describe, expect, it } from 'vitest'
import { atan2, sinCos } from '../src/display/detmath'
import { outlinePath, PathError } from '../src/display/svgpath'

describe('deterministic trigonometry', () => {
  it('agrees with Math to about 1e-12 over many turns', () => {
    for (let a = -20; a <= 20; a += 0.0137) {
      const [s, c] = sinCos(a)
      expect(Math.abs(s - Math.sin(a))).toBeLessThan(1e-12)
      expect(Math.abs(c - Math.cos(a))).toBeLessThan(1e-12)
    }
    for (let y = -3; y <= 3; y += 0.37) for (let x = -3; x <= 3; x += 0.41) expect(Math.abs(atan2(y, x) - Math.atan2(y, x))).toBeLessThan(1e-12)
    expect(atan2(0, -1)).toBeCloseTo(Math.PI, 15)
    expect(atan2(0, 0)).toBe(0)
  })
})

describe('shape outlines', () => {
  it('stretches lines and curves to the box, in whole mpt', () => {
    expect(outlinePath('M0 0 L100 0 L100 100 Z', { x: 1000, y: 2000, w: 50000, h: 20000 })).toEqual([
      ['M', 1000, 2000], ['L', 51000, 2000], ['L', 51000, 22000], ['Z'],
    ])
    expect(outlinePath('M0 50 C0 0 100 0 100 50', { x: 0, y: 0, w: 1000, h: 1000 })).toEqual([['M', 0, 500], ['C', 0, 0, 1000, 0, 1000, 500]])
  })
  it('turns a circle of two arcs into curves through its four extremes', () => {
    const ops = outlinePath('M50 0 A50 50 0 1 1 50 100 A50 50 0 1 1 50 0 Z', { x: 0, y: 0, w: 100000, h: 100000 })
    const ends = ops.filter((o) => o[0] === 'C').map((o) => [o[5], o[6]])
    expect(ends).toEqual([[100000, 50000], [50000, 100000], [0, 50000], [50000, 0]])
    // the classic control point distance of a quarter circle: 0.5523 of the radius
    const c = ops[1]!
    expect(c[1]).toBe(Math.round(50000 + 0.5522847498 * 50000))
  })
  it('refuses relative commands and junk', () => {
    expect(() => outlinePath('M0 0 l10 10', { x: 0, y: 0, w: 1, h: 1 })).toThrow(PathError)
    expect(() => outlinePath('M0 0 L10 x', { x: 0, y: 0, w: 1, h: 1 })).toThrow(PathError)
    expect(() => outlinePath('L0 0', { x: 0, y: 0, w: 1, h: 1 })).toThrow(PathError)
  })
})
