/**
 * The fonts a layout uses, and shaping with them.
 *
 * A **file** is identified by the SHA-256 of its bytes. A **face** is a file at one location of its variation axes
 * (a static font has no axes, so its face is the file): `Inter[opsz,wght].ttf` at `wght=600, opsz=12` is one face.
 * Every metric and every shaped advance comes from a face, so a layout depends on nothing but the bytes, the axis
 * values and the HarfBuzz build — and records all three.
 *
 * @module
 */
import { canonicalJson } from '../canonical'
import { type Glyph, type HarfBuzz, type HbFont, type ShapeOptions, SHAPER_ID, type Variations } from './harfbuzz'
import { readSfnt, type SfntInfo } from './sfnt'

/** A file at an axis location. `variations` holds integers only (they become part of fingerprints). */
export interface FaceRef {
  sha256: string
  variations: Variations
}

/** The id of a face: the file's hash, plus `@tag=value,…` (sorted) when the face has axis values. */
export function faceId(face: FaceRef): string {
  const entries = Object.entries(face.variations).sort(([a], [b]) => (a < b ? -1 : 1))
  return entries.length ? `${face.sha256}@${entries.map(([t, v]) => `${t}=${v}`).join(',')}` : face.sha256
}

/** What layout needs to know about a face. Lengths in font units. */
export interface FaceMetrics {
  id: string
  ref: FaceRef
  unitsPerEm: number
  ascender: number
  /** negative, below the baseline */
  descender: number
  lineGap: number
  capHeight: number
  italicAngle: number
  postscriptName: string
}

/** One shaped piece of text in font units; arrays are parallel, one entry per glyph. */
export interface Shaped {
  gids: number[]
  advances: number[]
  xOffsets: number[]
  /** the text each glyph stands for: the whole cluster on its first glyph, `''` on the others */
  chars: string[]
  /** UTF-16 index in the shaped text where each glyph's cluster starts */
  clusters: number[]
}

/** A font file the set cannot use, and why (a WOFF2, CFF outlines, a font that forbids embedding…). */
export class UnusableFont extends Error {}

/**
 * The fonts of one layout. Register file bytes with {@link add} (after checking their hash), then shape with
 * {@link shape}. Results are cached per face and text, which makes a re-layout after an edit cheap.
 */
export class FontSet {
  private readonly files = new Map<string, { bytes: Uint8Array; info: SfntInfo }>()
  private readonly faces = new Map<string, { font: HbFont; metrics: FaceMetrics; cache: Map<string, Shaped> }>()
  /** shape calls and cache hits, for performance checks */
  readonly stats = { shapes: 0, hits: 0 }

  constructor(readonly harfbuzz: HarfBuzz) {}

  /** The shaping engine's id, part of every layout result. */
  get shaperId(): string {
    return SHAPER_ID
  }

  /**
   * Register the bytes of a file whose SHA-256 is `sha256`. The caller checks the hash with the platform's crypto;
   * {@link UnusableFont} if the file is not a TrueType font that may be embedded.
   */
  add(sha256: string, bytes: Uint8Array): SfntInfo {
    const known = this.files.get(sha256)
    if (known) return known.info
    let info: SfntInfo
    try {
      info = readSfnt(bytes)
    } catch (e) {
      throw new UnusableFont((e as Error).message)
    }
    if (info.outlines !== 'truetype') throw new UnusableFont('a font with CFF outlines (an .otf); only TrueType outlines are supported yet')
    if (info.fsType & 0x0002) throw new UnusableFont('the font forbids embedding')
    this.files.set(sha256, { bytes, info })
    return info
  }

  has(sha256: string): boolean {
    return this.files.has(sha256)
  }

  /** The bytes of a registered file. */
  bytes(sha256: string): Uint8Array {
    const f = this.files.get(sha256)
    if (!f) throw new Error(`font ${sha256.slice(0, 12)}… is not in the set`)
    return f.bytes
  }

  /** What the file of a registered hash says about itself. */
  info(sha256: string): SfntInfo {
    const f = this.files.get(sha256)
    if (!f) throw new Error(`font ${sha256.slice(0, 12)}… is not in the set`)
    return f.info
  }

  private open(ref: FaceRef) {
    const id = faceId(ref)
    let face = this.faces.get(id)
    if (face) return face
    const file = this.files.get(ref.sha256)
    if (!file) throw new Error(`font ${ref.sha256.slice(0, 12)}… is not in the set`)
    for (const v of Object.values(ref.variations)) if (!Number.isSafeInteger(v)) throw new RangeError(`axis values must be integers: ${canonicalJson(ref.variations)}`)
    const font = this.harfbuzz.open(file.bytes, ref.variations)
    const e = this.harfbuzz.extents(font)
    const metrics: FaceMetrics = {
      id,
      ref: { sha256: ref.sha256, variations: { ...ref.variations } },
      unitsPerEm: file.info.unitsPerEm,
      ascender: e.ascender || file.info.ascender,
      descender: e.descender || file.info.descender,
      lineGap: e.lineGap,
      capHeight: file.info.capHeight,
      italicAngle: file.info.italicAngle,
      postscriptName: file.info.postscriptName,
    }
    face = { font, metrics, cache: new Map() }
    this.faces.set(id, face)
    return face
  }

  /** The metrics of a face. */
  metrics(ref: FaceRef): FaceMetrics {
    return this.open(ref).metrics
  }

  /** Shape `text` with a face. The same text and options always give the same (cached) result. */
  shape(ref: FaceRef, text: string, options: ShapeOptions = {}): Shaped {
    const face = this.open(ref)
    this.stats.shapes++
    const key = options.features?.length || options.language ? `${text}\u0000${options.language ?? ''}\u0000${(options.features ?? []).join(',')}` : text
    const hit = face.cache.get(key)
    if (hit) {
      this.stats.hits++
      return hit
    }
    const glyphs = this.harfbuzz.shape(face.font, text, options)
    const out = toShaped(glyphs, text)
    face.cache.set(key, out)
    return out
  }

  /** Free the HarfBuzz fonts of every face; the set can still be used, faces are reopened as needed. */
  release(): void {
    for (const f of this.faces.values()) this.harfbuzz.close(f.font)
    this.faces.clear()
  }
}

function toShaped(glyphs: Glyph[], text: string): Shaped {
  const starts = [...new Set(glyphs.map((g) => g.cluster))].sort((a, b) => a - b)
  const seen = new Set<number>()
  const out: Shaped = { gids: [], advances: [], xOffsets: [], chars: [], clusters: [] }
  for (const g of glyphs) {
    if (g.yOffset !== 0 || g.yAdvance !== 0) throw new Error('glyphs with vertical offsets (stacked marks) are not supported yet')
    out.gids.push(g.gid)
    out.advances.push(g.xAdvance)
    out.xOffsets.push(g.xOffset)
    out.clusters.push(g.cluster)
    if (seen.has(g.cluster)) out.chars.push('')
    else {
      seen.add(g.cluster)
      const next = starts[starts.indexOf(g.cluster) + 1] ?? text.length
      out.chars.push(text.slice(g.cluster, next))
    }
  }
  return out
}
