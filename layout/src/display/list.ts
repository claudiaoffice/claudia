/**
 * The display list: what a page shows, as drawing commands in page coordinates (mpt, origin top left, y down).
 *
 * It is the one interface between layout and output. The PDF writer reads it, a screen painter reads it, and every
 * app makes it its own way (composes from a text flow, creates from a slide, computes from a grid), so whatever an
 * app lays out, it prints the same way.
 *
 * @module
 */
import { canonicalJson } from '../canonical'
import type { FaceRef } from '../fonts/fontset'
import type { Rgba } from '../text/style'

/** A rectangle in mpt. */
export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

/** One glyph of a run: its id, where it is drawn (from the run's `x`), and the text it stands for. */
export interface RunGlyph {
  gid: number
  dx: number
  chars: string
}

/** Glyphs of one face, size and colour on one baseline (`y`), starting at `x`. */
export interface GlyphRun {
  kind: 'glyphs'
  face: FaceRef
  size: number
  color: Rgba
  x: number
  y: number
  glyphs: RunGlyph[]
  /** the run's text, for search and accessibility */
  text: string
}

/** Path commands: move, line, cubic curve, close. */
export type PathOp = ['M', number, number] | ['L', number, number] | ['C', number, number, number, number, number, number] | ['Z']

/** A path, filled and/or stroked. `dash`: lengths of dashes and gaps, mpt. */
export interface PathItem {
  kind: 'path'
  ops: PathOp[]
  fill: Rgba | null
  stroke: Rgba | null
  lineWidth: number
  dash?: number[]
}

/** A raster image (an asset, by id) drawn into a rectangle. */
export interface ImageItem {
  kind: 'image'
  image: string
  x: number
  y: number
  w: number
  h: number
}

/** Items drawn together: clipped to `clip` (if any) and rotated by `rotation` whole degrees about `origin`. */
export interface GroupItem {
  kind: 'group'
  clip: Rect | null
  rotation: number
  origin: { x: number; y: number }
  items: DisplayItem[]
}

export type DisplayItem = GlyphRun | PathItem | ImageItem | GroupItem

/** One page of output. */
export interface DisplayPage {
  width: number
  height: number
  items: DisplayItem[]
}

/** A whole document's display list, with what produced it. */
export interface DisplayList {
  /** the layout rules' version, the shaping engine and the fonts used (by face id → file hash) */
  layoutVersion: string
  shaper: string
  pages: DisplayPage[]
}

/** A rectangle as a closed path. */
export function rectPath(r: Rect): PathOp[] {
  return [['M', r.x, r.y], ['L', r.x + r.w, r.y], ['L', r.x + r.w, r.y + r.h], ['L', r.x, r.y + r.h], ['Z']]
}

/** Every item of a list, groups opened, in drawing order. */
export function* walk(items: readonly DisplayItem[]): Generator<DisplayItem> {
  for (const it of items) {
    yield it
    if (it.kind === 'group') yield* walk(it.items)
  }
}

/** Canonical JSON of a display list: hash it to compare outputs across machines. */
export const fingerprintText = (list: DisplayList): string => canonicalJson(list)
