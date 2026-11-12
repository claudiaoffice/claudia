import { describe, expect, it } from 'vitest'
import { HarfBuzz, WasmMismatch } from '../src/fonts/harfbuzz'
import { readSfnt } from '../src/fonts/sfnt'
import { fixture } from './fonts'
import { harfbuzz, sha256, wasm } from './helpers'

describe('HarfBuzz', () => {
  it('refuses WebAssembly that does not match the pin', async () => {
    const changed = wasm.shaping.slice()
    changed[changed.length - 1] = changed.at(-1)! ^ 1
    await expect(HarfBuzz.load({ ...wasm, shaping: changed }, sha256)).rejects.toThrow(WasmMismatch)
  })

  it('shapes text with kerning and ligatures, in font units', async () => {
    const hb = await harfbuzz()
    const font = hb.open(fixture('Carlito-Regular'))
    expect(font.upem).toBe(2048)
    const glyphs = hb.shape(font, 'AV')
    expect(glyphs).toHaveLength(2)
    expect(glyphs.map((g) => g.cluster)).toEqual([0, 1])
    // A and V kern: the pair is narrower than the sum of the two advance widths
    const info = readSfnt(fixture('Carlito-Regular'))
    const plain = glyphs.reduce((s, g) => s + info.advances[g.gid]!, 0)
    expect(glyphs.reduce((s, g) => s + g.xAdvance, 0)).toBeLessThan(plain)
    hb.close(font)
  })

  it('gives a variable font the weight it is asked for', async () => {
    const hb = await harfbuzz()
    const light = hb.open(fixture('InterVariable'), { wght: 300 })
    const bold = hb.open(fixture('InterVariable'), { wght: 700 })
    const w = (f: typeof light) => hb.shape(f, 'Seiten').reduce((s, g) => s + g.xAdvance, 0)
    expect(w(bold)).toBeGreaterThan(w(light))
  })

  it('subsets with glyph ids kept and the axes pinned, into a static TrueType font', async () => {
    const hb = await harfbuzz()
    const font = hb.open(fixture('InterVariable'), { wght: 700 })
    const gids = hb.shape(font, 'Hallo').map((g) => g.gid)
    const subset = hb.subset(fixture('InterVariable'), gids, { wght: 700 })
    const info = readSfnt(subset)
    expect(info.outlines).toBe('truetype')
    expect(info.axes).toEqual([])
    expect(info.numGlyphs).toBeGreaterThan(Math.max(...gids))
    expect(subset.length).toBeLessThan(fixture('InterVariable').length / 10)
    // the instanced advance widths are those HarfBuzz shaped with
    const shaped = hb.shape(font, 'Hallo')
    for (const g of shaped) expect(info.advances[g.gid]).toBe(g.xAdvance)
    // the same input gives the same bytes
    expect(sha256(hb.subset(fixture('InterVariable'), gids, { wght: 700 }))).toBe(sha256(subset))
  })
})
