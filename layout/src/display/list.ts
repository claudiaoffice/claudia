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

/**
 * An affine transform `[a, b, c, d, e, f]`: a point (x, y) goes to (a·x + c·y + e, b·x + d·y + f). `a`–`d` are in
 * millionths (1 000 000 is 1), `e` and `f` in mpt, all whole numbers, in page coordinates (y down).
 */
export type Matrix = [number, number, number, number, number, number]
export const IDENTITY: Matrix = [1_000_000, 0, 0, 1_000_000, 0, 0]

/** A colour at a place of a gradient: `offset` from 0 to 1 000 000. */
export interface GradientStop {
  offset: number
  color: Rgba
}

/**
 * A gradient, as SVG and PDF know it. `coords` are in mpt in the gradient's own space, which `matrix` places on
 * the page: `[x1, y1, x2, y2]` for a linear one, `[cx, cy, r, fx, fy, fr]` for a radial one (from the focal circle
 * to the outer one). Beyond its ends the end colours carry on (SVG's `spreadMethod="pad"`).
 */
export interface Gradient {
  kind: 'linear' | 'radial'
  coords: number[]
  stops: GradientStop[]
  matrix: Matrix
}

/** What a path is filled or stroked with: a colour or a gradient. */
export type Paint = Rgba | Gradient

/** True for a gradient paint. */
export const isGradient = (p: Paint): p is Gradient => 'kind' in p

/**
 * A path, filled and/or stroked. `dash`: lengths of dashes and gaps, mpt, starting `dashOffset` into the pattern.
 * `miterLimit` in thousandths (4000 is SVG's default of 4).
 */
export interface PathItem {
  kind: 'path'
  ops: PathOp[]
  fill: Paint | null
  stroke: Paint | null
  lineWidth: number
  dash?: number[]
  dashOffset?: number
  /** `evenodd`: a part is inside when an odd number of edges lie around it (SVG `fill-rule`); default nonzero */
  fillRule?: 'evenodd'
  lineCap?: 'round' | 'square'
  lineJoin?: 'round' | 'bevel'
  miterLimit?: number
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

/**
 * Items drawn together: rotated by `rotation` whole degrees about `origin`, then (if given) transformed by
 * `matrix`, clipped to `clip` and to `clipPath` (in the group's own coordinates), and, with `opacity` (0–255),
 * drawn as one layer that much transparent.
 */
export interface GroupItem {
  kind: 'group'
  clip: Rect | null
  rotation: number
  origin: { x: number; y: number }
  items: DisplayItem[]
  matrix?: Matrix
  clipPath?: { ops: PathOp[]; evenOdd?: boolean }
  opacity?: number
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
  /** the hyphenation patterns used (their id: the SHA-256 the server lists them by), if any */
  hyphenation?: string
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
