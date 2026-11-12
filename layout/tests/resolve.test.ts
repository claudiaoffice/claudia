import { beforeAll, describe, expect, it } from 'vitest'
import { FontResolver, parseFamilies, weightOf } from '../src/fonts/resolve'
import { world } from './world'

let resolver: FontResolver
beforeAll(async () => ({ resolver } = await world()))

describe('font resolution', () => {
  it('reads a font-family stack', () => {
    expect(parseFamilies(`Inter, system-ui, 'Segoe UI', "Times New Roman" , sans-serif`)).toEqual(['Inter', 'system-ui', 'Segoe UI', 'Times New Roman', 'sans-serif'])
  })
  it('reads weights', () => {
    expect([weightOf('normal'), weightOf('bold'), weightOf('500'), weightOf(undefined)]).toEqual([400, 700, 500, 400])
  })
  it('takes the first family it has, at the asked weight of a variable font, with opsz from the size', () => {
    const r = resolver.resolve("Inter, system-ui, sans-serif", 600, false, 10500)!
    expect(r.family).toBe('Inter')
    expect(r.how).toBe('exact')
    expect(r.face.variations).toEqual({ opsz: 14, wght: 600 }) // Inter's opsz axis starts at 14
    expect(resolver.resolve('Fraunces', 500, false, 10500)!.face.variations).toMatchObject({ opsz: 11, wght: 500 })
  })
  it('picks the italic file when italic is asked for', () => {
    const r = resolver.resolve('Fraunces', 400, true, 12000)!
    expect(r.font.italic).toBe(true)
  })
  it('uses a metric-compatible substitute', () => {
    const r = resolver.resolve('Calibri, sans-serif', 700, false, 12000)!
    expect(r.family).toBe('Carlito')
    expect(r.how).toBe('substitute')
    expect(r.font.weight).toBe(700)
    expect(r.face.variations).toEqual({})
  })
  it('falls through to a later family, a generic one, and then the fallback, and says so', () => {
    expect(resolver.resolve('Georgia, Caladea, serif', 400, false, 12000)!).toMatchObject({ family: 'Caladea', how: 'next', requested: 'Georgia' })
    expect(resolver.resolve('Georgia, serif', 400, false, 12000)!).toMatchObject({ family: 'Fraunces', how: 'next' })
    expect(resolver.resolve('Comic Sans', 400, false, 12000)!).toMatchObject({ family: 'Inter', how: 'fallback' })
  })
  it('chooses the nearest static weight the CSS way', () => {
    expect(resolver.resolve('Carlito', 500, false, 12000)!.font.weight).toBe(400)
    expect(resolver.resolve('Carlito', 600, false, 12000)!.font.weight).toBe(700)
    expect(resolver.resolve('Carlito', 300, false, 12000)!.font.weight).toBe(400)
  })
  it('gives nothing when the catalogue is empty', () => {
    expect(new FontResolver({ fonts: [], substitutions: {} }).resolve('Inter', 400, false, 12000)).toBeNull()
  })
})
