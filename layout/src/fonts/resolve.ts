/**
 * Which font file a CSS font request gets: the matching part of CSS font selection, done over a server's font
 * catalogue instead of the fonts a computer happens to have, so every client picks the same file.
 *
 * @module
 */
import type { FaceRef } from './fontset'
import type { Axis } from './sfnt'

/** A font as the server's catalogue lists it (`GET /api/fonts`). */
export interface CatalogueFont {
  family: string
  style: string
  weight: number
  italic: boolean
  sha256: string
  /** variation axes, empty for a static font */
  axes: Axis[]
  /** `truetype` or `cff`; only TrueType outlines can be used yet */
  outlines?: 'truetype' | 'cff'
}

export interface Catalogue {
  fonts: CatalogueFont[]
  /** metric-compatible open fonts for common office fonts: `Arial` → `Liberation Sans` */
  substitutions: Readonly<Record<string, string>>
}

/** The family each CSS generic family stands for (and the last resort, `fallback`). */
export interface Generics {
  serif: string
  'sans-serif': string
  monospace: string
  fallback: string
}

export const DEFAULT_GENERICS: Generics = {
  serif: 'Fraunces',
  'sans-serif': 'Inter',
  monospace: 'JetBrains Mono',
  fallback: 'Inter',
}

const GENERIC_ALIASES: Record<string, keyof Generics> = {
  serif: 'serif',
  'sans-serif': 'sans-serif',
  monospace: 'monospace',
  'system-ui': 'sans-serif',
  'ui-sans-serif': 'sans-serif',
  'ui-serif': 'serif',
  'ui-monospace': 'monospace',
  cursive: 'serif',
  fantasy: 'serif',
}

/** What a request got. */
export interface Resolution {
  face: FaceRef
  font: CatalogueFont
  /** the first family the request named */
  requested: string
  /** the family that was used */
  family: string
  /** `exact`: the first family named; `substitute`: its metric-compatible replacement; `next`: a later family of the
   *  stack; `fallback`: none of them, the catalogue's fallback */
  how: 'exact' | 'substitute' | 'next' | 'fallback'
}

/** The family names of a CSS `font-family` value, unquoted, in order. */
export function parseFamilies(value: string): string[] {
  const out: string[] = []
  const re = /\s*(?:"([^"]*)"|'([^']*)'|([^,]+))\s*(?:,|$)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(value)) !== null && m[0] !== '') {
    const name = (m[1] ?? m[2] ?? m[3] ?? '').trim().replace(/\s+/g, ' ')
    if (name) out.push(name)
  }
  return out
}

/** A CSS `font-weight` as a number (normal 400, bold 700; bolder/lighter relative to 400). */
export function weightOf(value: string | undefined): number {
  const v = (value ?? '').trim().toLowerCase()
  if (v === '' || v === 'normal') return 400
  if (v === 'bold' || v === 'bolder') return 700
  if (v === 'lighter') return 100
  const n = Number(v)
  return Number.isFinite(n) ? Math.min(1000, Math.max(1, Math.round(n))) : 400
}

/** The CSS weight matching order for a family's faces (CSS Fonts 4, §5.2 step 4). */
function weightDistance(want: number, have: number): number {
  if (have === want) return 0
  if (want >= 400 && want <= 500) {
    if (have > want && have <= 500) return have - want
    if (have < want) return 1000 + (want - have)
    return 2000 + (have - want)
  }
  if (want < 400) return have < want ? want - have : 1000 + (have - want)
  return have > want ? have - want : 1000 + (want - have)
}

/** Picks fonts from a catalogue the way a browser picks from installed fonts, but the same everywhere. */
export class FontResolver {
  private readonly byFamily = new Map<string, CatalogueFont[]>()
  private readonly substitutions = new Map<string, string>()

  constructor(
    catalogue: Catalogue,
    private readonly generics: Generics = DEFAULT_GENERICS,
  ) {
    for (const f of catalogue.fonts) {
      if (f.outlines && f.outlines !== 'truetype') continue
      const key = f.family.toLowerCase()
      const list = this.byFamily.get(key) ?? []
      list.push(f)
      this.byFamily.set(key, list)
    }
    for (const list of this.byFamily.values()) list.sort((a, b) => a.weight - b.weight || Number(a.italic) - Number(b.italic) || (a.sha256 < b.sha256 ? -1 : 1))
    for (const [from, to] of Object.entries(catalogue.substitutions)) this.substitutions.set(from.toLowerCase(), to)
  }

  /** Whether the catalogue has a usable font of `family`. */
  has(family: string): boolean {
    return this.byFamily.has(family.toLowerCase())
  }

  /**
   * The face for a `font-family` stack, a weight, an italic flag and a size (mpt, for the `opsz` axis).
   * `null` only when the catalogue has no usable font at all.
   */
  resolve(stack: string | readonly string[], weight: number, italic: boolean, size: number): Resolution | null {
    const families = typeof stack === 'string' ? parseFamilies(stack) : [...stack]
    const requested = families[0] ?? this.generics.fallback
    for (let i = 0; i < families.length; i++) {
      const name = families[i]!
      const generic = GENERIC_ALIASES[name.toLowerCase()]
      const family = generic ? this.generics[generic] : name
      let found = this.pick(family, weight, italic, size)
      let how: Resolution['how'] = i === 0 && !generic ? 'exact' : 'next'
      if (!found && !generic) {
        const sub = this.substitutions.get(name.toLowerCase())
        if (sub) {
          found = this.pick(sub, weight, italic, size)
          if (found) how = i === 0 ? 'substitute' : 'next'
        }
      }
      if (found) return { ...found, requested, how: i === 0 && generic ? 'exact' : how }
    }
    const last = this.pick(this.generics.fallback, weight, italic, size) ?? this.any(weight, italic, size)
    return last ? { ...last, requested, how: 'fallback' } : null
  }

  private any(weight: number, italic: boolean, size: number) {
    const first = [...this.byFamily.keys()].sort()[0]
    return first ? this.pick(first, weight, italic, size) : null
  }

  private pick(family: string, weight: number, italic: boolean, size: number): { face: FaceRef; font: CatalogueFont; family: string } | null {
    const all = this.byFamily.get(family.toLowerCase())
    if (!all?.length) return null
    const slanted = all.filter((f) => f.italic === italic)
    const pool = slanted.length ? slanted : all
    const reach = (f: CatalogueFont) => {
      const w = f.axes.find((a) => a.tag === 'wght')
      return w && weight >= w.min && weight <= w.max ? 0 : weightDistance(weight, f.weight)
    }
    const best = [...pool].sort((a, b) => reach(a) - reach(b) || (a.sha256 < b.sha256 ? -1 : 1))[0]!
    const variations: Record<string, number> = {}
    for (const axis of best.axes) {
      if (axis.tag === 'wght') variations.wght = Math.round(Math.min(axis.max, Math.max(axis.min, weight)))
      else if (axis.tag === 'opsz') variations.opsz = Math.round(Math.min(axis.max, Math.max(axis.min, size / 1000)))
    }
    return { face: { sha256: best.sha256, variations }, font: best, family: best.family }
  }
}
