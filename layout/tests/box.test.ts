import { beforeAll, describe, expect, it } from 'vitest'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { boxItems, layoutBox } from '../src/text/box'
import { boxDecorationFromCss } from '../src/text/css'
import { paragraphStyle } from '../src/text/style'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))
const style = () => paragraphStyle(resolver.resolve('Carlito', 400, false, 12000)!.face, 12000, { lineHeight: 15000 })
const TEXT = 'Text in einem Kasten wird an seinem Rand abgeschnitten, nie verschoben, nie verkleinert und nie gescrollt.'

describe('text in a box', () => {
  it('lays text out to the inner width and says when it is cut off', () => {
    const b = layoutBox(fonts, TEXT, style(), 100000, 40000, boxDecorationFromCss({ 'padding-left': '5pt', 'padding-right': '5pt', 'padding-top': '2pt' }, 12000))
    expect(b.content).toEqual({ x: 5000, y: 2000, w: 90000, h: 38000 })
    expect(b.paragraph!.width).toBe(90000)
    expect(b.clipped).toBe(true)
    expect(b.visibleLines).toBe(3) // tops at 2, 17, 32 pt are inside the 40 pt box; the next one is not
  })
  it('centres and bottom-aligns text that fits', () => {
    const mid = layoutBox(fonts, 'Mitte', style(), 100000, 45000, undefined, 'middle')
    expect(mid.textTop).toBe(15000)
    expect(mid.clipped).toBe(false)
    expect(layoutBox(fonts, 'Unten', style(), 100000, 45000, undefined, 'bottom').textTop).toBe(30000)
  })
  it('clips the group at the border box and rotates it about its centre', () => {
    const b = layoutBox(fonts, TEXT, style(), 100000, 40000)
    const g = boxItems(fonts, b, 50000, 60000, 30.4)
    expect(g.clip).toEqual({ x: 50000, y: 60000, w: 100000, h: 40000 })
    expect(g.rotation).toBe(30)
    expect(g.origin).toEqual({ x: 100000, y: 80000 })
    expect(g.items.filter((i) => i.kind === 'glyphs').length).toBeGreaterThan(5)
  })
  it('draws only the decoration of a box without text', () => {
    const b = layoutBox(fonts, null, null, 20000, 20000, boxDecorationFromCss({ 'background-color': '#ff0000' }, 12000))
    expect(boxItems(fonts, b, 0, 0).items).toHaveLength(1)
  })
})
