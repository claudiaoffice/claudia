// What printing loads from the server (lib/print/assets.ts): the shaping engine, the font catalogue and font files,
// and the hyphenation patterns of a language — each checked by SHA-256 before the layout library sees it.
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HARFBUZZ_PIN } from '@claudia/layout'
import { PrintAssets, hex, sha256 } from '../app/lib/print/assets'

const layout = join(dirname(new URL(import.meta.url).pathname), '..', '..', 'layout')
// harfbuzzjs is the layout library's own dependency (installed in layout/node_modules by web's postinstall)
const dist = join(layout, 'node_modules', 'harfbuzzjs', 'dist')
const wasm = {
  [`/wasm/${HARFBUZZ_PIN.shaping.file}`]: readFileSync(join(dist, HARFBUZZ_PIN.shaping.file)),
  [`/wasm/${HARFBUZZ_PIN.subset.file}`]: readFileSync(join(dist, HARFBUZZ_PIN.subset.file)),
}
const digest = (b: Uint8Array | string) => createHash('sha256').update(b).digest('hex')
const PATTERNS = '1ba 1be\n'
const EXCEPTIONS = 'ta-ble\n'
const FONT = { family: 'Test Sans', style: 'Regular', weight: 400, italic: false, sha256: 'f'.repeat(64), axes: [], outlines: 'truetype', file: '/api/fonts/' + 'f'.repeat(64) }

/** A server with one listed font (whose file does not match its hash) and one language. */
function serve(routes: Record<string, unknown> = {}) {
  const all: Record<string, unknown> = {
    ...wasm,
    '/api/fonts': { fonts: [FONT], substitutions: {} },
    [FONT.file]: new Uint8Array([1, 2, 3]),
    '/api/hyphenation': {
      languages: [{ tag: 'xx', aliases: [], name: 'Test', licence: 'MIT', patterns: { sha256: digest(PATTERNS), size: 8 }, exceptions: { sha256: digest(EXCEPTIONS), size: 7 } }],
    },
    [`/api/hyphenation/${digest(PATTERNS)}`]: PATTERNS,
    [`/api/hyphenation/${digest(EXCEPTIONS)}`]: EXCEPTIONS,
    ...routes,
  }
  const fetched: string[] = []
  vi.stubGlobal('fetch', async (url: string) => {
    fetched.push(url)
    const body = all[url]
    if (body === undefined) return new Response('no', { status: 404 })
    if (typeof body === 'string' || body instanceof Uint8Array) return new Response(body as BodyInit)
    return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
  })
  return fetched
}
afterEach(() => vi.unstubAllGlobals())

describe('print assets', () => {
  it('hashes bytes the way the server names them', async () => {
    expect(await sha256(new TextEncoder().encode('abc'))).toBe(digest('abc'))
    expect(hex(new Uint8Array([0, 255, 16]).buffer)).toBe('00ff10')
  })

  it('loads the shaping engine, the catalogue and the languages, and builds a language’s hyphenator once', async () => {
    const fetched = serve()
    const assets = await PrintAssets.load()
    expect(assets.catalogue.fonts).toHaveLength(1)
    expect(assets.languages.map((l) => l.tag)).toEqual(['xx'])
    const h = await assets.hyphenator('xx-YY')
    expect(h!.points('abababe')).toEqual([1, 3, 5])
    expect(h!.points('table')).toEqual([2])
    expect(await assets.hyphenator('xx')).toBe(h)
    expect(fetched.filter((u) => u.startsWith('/api/hyphenation/'))).toHaveLength(2)
    expect(await assets.hyphenator('fr')).toBeNull()
    expect(await assets.hyphenator(null)).toBeNull()
  })

  it('refuses a font or patterns that did not arrive intact', async () => {
    serve({ [`/api/hyphenation/${digest(PATTERNS)}`]: 'something else' })
    const assets = await PrintAssets.load()
    await expect(assets.ensure([FONT.sha256])).rejects.toThrow(/did not arrive intact/)
    await expect(assets.ensure(['0'.repeat(64)])).rejects.toThrow(/not in the server's catalogue/)
    await expect(assets.hyphenator('xx')).rejects.toThrow(/did not arrive intact/)
  })

  it('works without hyphenation on the server, and says what is missing otherwise', async () => {
    serve({ '/api/hyphenation': undefined })
    expect((await PrintAssets.load()).languages).toEqual([])
    serve({ '/api/fonts': { fonts: [], substitutions: {} } })
    await expect(PrintAssets.load()).rejects.toThrow(/no fonts to lay out with/)
    serve({ '/api/fonts': undefined })
    await expect(PrintAssets.load()).rejects.toThrow(/lists no fonts/)
  })
})
