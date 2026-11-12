// What printing needs from the server and the build: the font catalogue and font files (D905), HarfBuzz as
// WebAssembly (D903), and a text's images. Everything is checked by SHA-256 before the layout library sees it, and
// kept for the life of the page: a font file never changes under its hash.
import { type Catalogue, FontResolver, FontSet, HARFBUZZ_PIN, HarfBuzz, readSfnt, UnusableFont } from '@claudia/layout'

// Copied into public/wasm by `npm run build` (and `dev`) from harfbuzzjs, checked there and again here (D903).
const shapingUrl = `/wasm/${HARFBUZZ_PIN.shaping.file}`
const subsetUrl = `/wasm/${HARFBUZZ_PIN.subset.file}`

export const hex = (buf: ArrayBuffer): string => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
export const sha256 = async (bytes: Uint8Array): Promise<string> => hex(await crypto.subtle.digest('SHA-256', bytes as unknown as ArrayBuffer))

async function bytesOf(url: string): Promise<Uint8Array> {
  const answer = await fetch(url, { credentials: 'same-origin' })
  if (!answer.ok) throw new Error(`${url}: ${answer.status}`)
  return new Uint8Array(await answer.arrayBuffer())
}

/** A font as `GET /api/fonts` lists it. */
export interface ListedFont {
  family: string
  style: string
  weight: number
  italic: boolean
  sha256: string
  axes: { tag: string; min: number; default: number; max: number }[]
  outlines: 'truetype' | 'cff'
  file: string
}

/** The fonts and the shaping engine of one page, loaded once. */
export class PrintAssets {
  private files = new Map<string, Promise<void>>()

  private constructor(
    readonly fonts: FontSet,
    readonly resolver: FontResolver,
    readonly catalogue: Catalogue,
    private readonly listed: Map<string, ListedFont>,
  ) {}

  /** Load the shaping engine and the server's catalogue. `Error` with a message for people if either fails. */
  static async load(): Promise<PrintAssets> {
    if (!globalThis.crypto?.subtle) throw new Error('printing needs a secure connection (https, or this computer)')
    const [shaping, subset, listing] = await Promise.all([
      bytesOf(shapingUrl),
      bytesOf(subsetUrl),
      fetch('/api/fonts', { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`the server lists no fonts (${r.status})`)))),
    ])
    const harfbuzz = await HarfBuzz.load({ shaping, subset }, sha256)
    const fonts: ListedFont[] = listing.fonts ?? []
    if (!fonts.length) throw new Error('the server has no fonts to lay out with; its administrator can add some (python -m claudia_fonts fetch)')
    const catalogue: Catalogue = { fonts, substitutions: listing.substitutions ?? {} }
    return new PrintAssets(new FontSet(harfbuzz), new FontResolver(catalogue), catalogue, new Map(fonts.map((f) => [f.sha256, f])))
  }

  /** Fetch, check and register the font files `hashes` names (those already here are not fetched again). */
  async ensure(hashes: readonly string[]): Promise<void> {
    await Promise.all(
      hashes.map((h) => {
        let pending = this.files.get(h)
        if (!pending) {
          pending = (async () => {
            const listed = this.listed.get(h)
            if (!listed) throw new Error(`font ${h.slice(0, 12)}… is not in the server's catalogue`)
            const bytes = await bytesOf(listed.file)
            if ((await sha256(bytes)) !== h) throw new Error(`the font ${listed.family} ${listed.style} did not arrive intact`)
            try {
              this.fonts.add(h, bytes)
            } catch (e) {
              if (e instanceof UnusableFont) throw new Error(`${listed.family} ${listed.style}: ${e.message}`, { cause: e })
              throw e
            }
          })()
          this.files.set(h, pending)
          pending.catch(() => this.files.delete(h))
        }
        return pending
      }),
    )
  }

  /** The axes of a registered font (for drawing it with the same variations in the page). */
  axesOf(hash: string) {
    return readSfnt(this.fonts.bytes(hash)).axes
  }
}

let shared: Promise<PrintAssets> | null = null
/** The page's one set of print assets (a failed load is tried again next time). */
export function printAssets(): Promise<PrintAssets> {
  if (!shared) {
    shared = PrintAssets.load()
    shared.catch(() => (shared = null))
  }
  return shared
}
