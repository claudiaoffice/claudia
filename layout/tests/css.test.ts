import { beforeAll, describe, expect, it } from 'vitest'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { boxDecorationFromCss, paragraphStyleFromCss, parseColor } from '../src/text/css'
import { cssLengthToMpt, fmt3, mulDivRound, umToMpt } from '../src/units'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

describe('units', () => {
  it('rounds exactly, also near the limit, like BigInt arithmetic', () => {
    let seed = 7
    const rnd = (n: number) => ((seed = (Math.imul(seed, 1103515245) + 12345) >>> 0) % n)
    for (let i = 0; i < 50000; i++) {
      const a = rnd(2 ** 26) - 2 ** 25
      const b = rnd(2 ** 25) + 1
      const c = rnd(1 << 20) + 1
      const n = 2n * BigInt(a) * BigInt(b) + BigInt(c)
      const d = 2n * BigInt(c)
      const exact = n >= 0n ? n / d : -((-n + d - 1n) / d)
      expect(mulDivRound(a, b, c)).toBe(Number(exact))
    }
    expect(() => mulDivRound(2 ** 30, 2 ** 22, 3)).toThrow(RangeError)
  })
  it('prints thousandths', () => {
    expect([fmt3(12500), fmt3(-5), fmt3(0), fmt3(595276)]).toEqual(['12.5', '-0.005', '0', '595.276'])
  })
  it('reads CSS lengths', () => {
    expect(cssLengthToMpt('12pt', 0)).toBe(12000)
    expect(cssLengthToMpt('16px', 0)).toBe(12000)
    expect(cssLengthToMpt('1.5em', 10000)).toBe(15000)
    expect(cssLengthToMpt('25.4mm', 0)).toBe(72000)
    expect(cssLengthToMpt('2.54cm', 0)).toBe(72000)
    expect(cssLengthToMpt('150%', 10000)).toBe(15000)
    expect(cssLengthToMpt('0', 0)).toBe(0)
    expect(cssLengthToMpt('12', 0)).toBeNull()
    expect(cssLengthToMpt('calc(1px)', 0)).toBeNull()
    expect(umToMpt(210_000)).toBe(595276)
  })
})

describe('CSS', () => {
  it('reads colours', () => {
    expect(parseColor('#D6477A')).toEqual({ r: 214, g: 71, b: 122, a: 255 })
    expect(parseColor('#fff8')).toEqual({ r: 255, g: 255, b: 255, a: 136 })
    expect(parseColor('rgb(10, 20, 30)')).toEqual({ r: 10, g: 20, b: 30, a: 255 })
    expect(parseColor('rgba(10 20 30 / 50%)')).toEqual({ r: 10, g: 20, b: 30, a: 128 })
    expect(parseColor('hsl(0, 100%, 50%)')).toEqual({ r: 255, g: 0, b: 0, a: 255 })
    expect(parseColor('rebeccapurple')).toEqual({ r: 102, g: 51, b: 153, a: 255 })
    expect(parseColor('@accent')).toBeNull()
  })
  it('turns composes body text CSS into a resolved style', () => {
    const r = paragraphStyleFromCss(
      { 'font-family': "Inter, system-ui, 'Segoe UI', sans-serif", 'font-size': '12pt', 'line-height': '1.75', 'text-align': 'justify', 'margin-top': '0', 'margin-bottom': '0.9em', color: '#1f1a33' },
      resolver,
      fonts,
    )!
    expect(r.style).toMatchObject({ size: 12000, lineHeight: 21000, align: 'justify', spaceBefore: 0, spaceAfter: 10800, color: { r: 31, g: 26, b: 51, a: 255 } })
    expect(r.font.family).toBe('Inter')
  })
  it('gives line-height: normal the font’s own line spacing', () => {
    const r = paragraphStyleFromCss({ 'font-family': 'Carlito', 'font-size': '10pt' }, resolver, fonts)!
    const m = fonts.metrics(r.style.face)
    expect(r.style.lineHeight).toBe(mulDivRound(m.ascender - m.descender + m.lineGap, 10000, m.unitsPerEm))
  })
  it('reads padding, borders and a background for a box', () => {
    const d = boxDecorationFromCss({ 'padding-top': '4pt', 'border-left': '3px solid #D6477A', 'background-color': 'transparent' }, 12000)
    expect(d.padding.top).toBe(4000)
    expect(d.border.left).toEqual({ width: 2250, style: 'solid', color: { r: 214, g: 71, b: 122, a: 255 } })
    expect(d.background).toBeNull()
  })
})
