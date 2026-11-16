// Stand-ins (E3.13): every font of the shared sample document (test-documents/xlsx/stand-in-fonts) is laid out with
// the font its stand-ins.json names, and the resolution says how close that is, in the words claudia_fonts uses.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { CLOSENESS, SAME_WIDTHS, STAND_IN_GENERICS } from '../src/fonts/stand-ins.generated'
import { DEFAULT_GENERICS, FontResolver } from '../src/fonts/resolve'
import { here } from './helpers'
import { world } from './world'

interface SampleFont {
  family: string
  generic: 'serif' | 'sans-serif' | 'monospace'
  stand_in: string | null
  closeness: string
}
const SAMPLE = join(here, '..', '..', 'test-documents', 'xlsx', 'stand-in-fonts', 'stand-ins.json')
const fonts: SampleFont[] = JSON.parse(readFileSync(SAMPLE, 'utf8')).fonts
/** The `font-family` a sheet holds for a font of the file once imported: its name, then its generic family. */
const stackOf = (f: SampleFont) => `${/\s/.test(f.family) ? `'${f.family}'` : f.family}, ${f.generic}`

let resolver: FontResolver
beforeAll(async () => ({ resolver } = await world()))

describe('stand-ins of the shared sample', () => {
  it.each(fonts.map((f) => [f.family, f] as const))('%s', (_name, f) => {
    const r = resolver.resolve(stackOf(f), 400, false, 11000)!
    expect(r.requested).toBe(f.family)
    expect(r.family).toBe(f.stand_in ?? STAND_IN_GENERICS[f.generic])
    expect(r.closeness).toBe(f.closeness)
  })
  it('a stack the importer wrote before E3.13 (with the old twin second) still gets the same stand-in', () => {
    expect(resolver.resolve("Arial, 'Liberation Sans', sans-serif", 400, false, 11000)!).toMatchObject({ family: 'Arimo', how: 'substitute', closeness: 'same-widths' })
  })
})

describe('the table the layout library uses', () => {
  it('is the generated copy of claudia_fonts', () => {
    expect(DEFAULT_GENERICS).toEqual(STAND_IN_GENERICS)
    expect(CLOSENESS).toEqual(['same', 'same-widths', 'other'])
    expect(Object.keys(SAME_WIDTHS)).toContain('Arial')
  })
  it('takes the generic families a server sends over its own', () => {
    const catalogue = { fonts: [{ family: 'Alpha', style: 'Regular', weight: 400, italic: false, sha256: 'a', axes: [] }], substitutions: {}, generics: { serif: 'Alpha', 'sans-serif': 'Alpha', monospace: 'Alpha', fallback: 'Alpha' } }
    expect(new FontResolver(catalogue).resolve('serif', 400, false, 12000)).toMatchObject({ family: 'Alpha', how: 'exact', closeness: 'same' })
  })
})
