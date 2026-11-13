/**
 * SVG to display items (D914): any SVG picture, drawn into a box the way a browser would draw it there, as the
 * paths, glyph runs and images every output of the library understands. It is not tied to any app: composes draws
 * an SVG picture with it, and computes and creates will draw charts and formulas the same way.
 *
 * {@link parseSvg} reads the text once; {@link svgFonts} says which font files its text needs, so the caller can
 * fetch them; {@link drawSvg} draws it into a rectangle of a page. What it does not draw is named in the result's
 * `notes`, once each, in words for people.
 *
 * Drawn: the shapes, paths, groups, `use` and `symbol`, nested `svg`, transforms, fill and stroke (colours, linear
 * and radial gradients, opacity, dashes, line ends and corners, fill rules), group opacity, clip paths, text in the
 * server's fonts (with `tspan`, `text-anchor`), and pictures inside the SVG (PNG, JPEG, GIF, BMP and SVG, as data
 * URLs). Not drawn: filters, masks, patterns, markers, `foreignObject`, text on a path, and pictures linked from
 * outside the file.
 *
 * @module
 */
import { fromBase64, sha256Hex, utf8Decode, utf8Encode } from '../bytes'
import { type DisplayItem, type Gradient, type GradientStop, type GroupItem, type Matrix, type Paint, type PathItem, type PathOp, type Rect } from '../display/list'
import type { FaceRef, FontSet } from '../fonts/fontset'
import type { FontResolver } from '../fonts/resolve'
import { decodeBmp, isBmp } from '../image/bmp'
import { decodeGif, isGif } from '../image/gif'
import { isJpeg, readJpeg } from '../image/jpeg'
import { decodePng, isPng } from '../image/png'
import { parseColor } from '../text/css'
import type { Rgba } from '../text/style'
import { mulDivRound } from '../units'
import { type Affine, apply, bounds, ellipse, fitViewBox, length, type LengthContext, multiply, numbers, parsePath, parseTransform, poly, rect, scaleOf, type Segment, UNIT } from './geometry'
import { computeStyle, INITIAL, type Style, StyleSheet } from './style'
import { parseXml, textOf, type XmlElement } from './xml'

/** An SVG read and ready to draw. */
export interface SvgDocument {
  root: XmlElement
  /** elements by `id` */
  ids: Map<string, XmlElement>
  sheet: StyleSheet
}

/** The SVG cannot be read at all (not XML, not an `<svg>`). */
export class SvgError extends Error {}

/** What drawing needs besides the SVG: fonts for its text. Without them its text is left out (and noted). */
export interface SvgContext {
  fonts?: FontSet
  resolver?: FontResolver
}

/** An SVG drawn: one group, what it could not draw, and the bytes of the pictures inside it by image id. */
export interface SvgDrawing {
  item: GroupItem
  notes: string[]
  images: Map<string, Uint8Array>
}

/** Read the text of an SVG file. */
export function parseSvg(text: string): SvgDocument {
  let root: XmlElement
  try {
    root = parseXml(text)
  } catch (e) {
    throw new SvgError(`not an SVG that can be read: ${(e as Error).message}`)
  }
  if (root.name !== 'svg') throw new SvgError('not an SVG: the root element must be <svg>')
  const ids = new Map<string, XmlElement>()
  const sheet = new StyleSheet()
  const visit = (el: XmlElement) => {
    const id = el.attrs.get('id')
    if (id && !ids.has(id)) ids.set(id, el)
    if (el.name === 'style') sheet.add(textOf(el))
    for (const c of el.children) if (typeof c !== 'string') visit(c)
  }
  visit(root)
  return { root, ids, sheet }
}

/** The SHA-256 of every font file the text of `doc` needs, as `resolver` picks them. */
export function svgFonts(doc: SvgDocument, resolver: FontResolver): string[] {
  const out = new Set<string>()
  const visit = (el: XmlElement, parent: Style) => {
    const style = computeStyle(el, parent, doc.sheet)
    if (el.name === 'text' || el.name === 'tspan') {
      const r = resolver.resolve(style['font-family'] ?? 'sans-serif', weightOf(style['font-weight']), italicOf(style['font-style']), 12000)
      if (r) out.add(r.face.sha256)
    }
    for (const c of el.children) if (typeof c !== 'string') visit(c, style)
  }
  visit(doc.root, INITIAL)
  return [...out].sort()
}

const weightOf = (v: string | undefined): number => {
  const w = (v ?? 'normal').toLowerCase()
  return w === 'bold' || w === 'bolder' ? 700 : w === 'normal' || w === 'lighter' ? 400 : Number(w) || 400
}
const italicOf = (v: string | undefined) => /^(italic|oblique)/i.test(v ?? '')

const NOTES = {
  filter: 'filters (blurs, shadows) are left out',
  mask: 'masks are left out',
  pattern: 'pattern fills are left out',
  marker: 'markers (arrowheads) are left out',
  foreign: 'embedded HTML (foreignObject) is left out',
  textPath: 'text along a path is left out',
  textLayout: 'some text spacing is simplified',
  font: 'its text is left out: no font to draw it with',
  link: 'pictures linked from outside the file are left out',
  picture: 'a picture inside it cannot be read',
  spread: 'repeating gradients are drawn as plain ones',
  style: 'some of its style rules are not understood',
  textStroke: 'outlined text is drawn filled',
  depth: 'it is nested too deeply to draw completely',
} as const

const MAX_DEPTH = 48
const PX = 750 // mpt per CSS px

interface State {
  ctm: Affine
  style: Style
  viewport: { w: number; h: number }
  depth: number
  /** `use` elements being drawn, against cycles */
  using: Set<XmlElement>
}

/** Draw `doc` into `box` (mpt, page coordinates), as a browser draws an SVG picture into an image box. */
export function drawSvg(doc: SvgDocument, box: Rect, context: SvgContext = {}): SvgDrawing {
  const notes = new Set<string>()
  const images = new Map<string, Uint8Array>()
  if (doc.sheet.skipped) notes.add(NOTES.style)
  const items = drawInto(doc, box, context, notes, images, 0)
  return { item: { kind: 'group', clip: box, rotation: 0, origin: { x: box.x, y: box.y }, items }, notes: [...notes], images }
}

function drawInto(doc: SvgDocument, box: Rect, context: SvgContext, notes: Set<string>, images: Map<string, Uint8Array>, nesting: number): DisplayItem[] {
  const root = doc.root
  const px: LengthContext = { fontSize: 16, width: box.w / PX, height: box.h / PX }
  const vb = numbers(root.attrs.get('viewBox') ?? '')
  let view: { x: number; y: number; w: number; h: number }
  if (vb.length === 4 && vb[2]! > 0 && vb[3]! > 0) view = { x: vb[0]!, y: vb[1]!, w: vb[2]!, h: vb[3]! }
  else {
    const w = length(root.attrs.get('width'), px, 'x', NaN)
    const h = length(root.attrs.get('height'), px, 'y', NaN)
    const absolute = (v: string | undefined) => v !== undefined && !v.trim().endsWith('%')
    view = { x: 0, y: 0, w: absolute(root.attrs.get('width')) && w > 0 ? w : box.w / PX, h: absolute(root.attrs.get('height')) && h > 0 ? h : box.h / PX }
  }
  const ctm = fitViewBox(view, box, root.attrs.get('preserveAspectRatio'))
  const drawer = new Drawer(doc, context, notes, images, nesting)
  return drawer.children(root, { ctm, style: computeStyle(root, INITIAL, doc.sheet), viewport: { w: view.w, h: view.h }, depth: 0, using: new Set() })
}

const group = (items: DisplayItem[], extra: Partial<GroupItem> = {}): GroupItem => ({ kind: 'group', clip: null, rotation: 0, origin: { x: 0, y: 0 }, items, ...extra })

/** A transform in the display list's whole numbers. */
function toMatrix(m: Affine): Matrix {
  return [Math.round(m[0] * 1e6), Math.round(m[1] * 1e6), Math.round(m[2] * 1e6), Math.round(m[3] * 1e6), Math.round(m[4]), Math.round(m[5])]
}

/**
 * A transform split into a scale `s` and the rest: local lengths are user lengths times `s` (so they are about mpt
 * and can be whole numbers), and `matrix` places them on the page. `null` when the transform squashes everything.
 */
function split(m: Affine): { s: number; matrix: Matrix; plain: boolean } | null {
  const s = scaleOf(m)
  if (!(s > 0) || !Number.isFinite(s)) return null
  const n: Affine = [m[0] / s, m[1] / s, m[2] / s, m[3] / s, m[4], m[5]]
  const matrix = toMatrix(n)
  const plain = matrix[0] === 1_000_000 && matrix[1] === 0 && matrix[2] === 0 && matrix[3] === 1_000_000
  return { s, matrix, plain }
}

class Drawer {
  constructor(
    private readonly doc: SvgDocument,
    private readonly context: SvgContext,
    private readonly notes: Set<string>,
    private readonly images: Map<string, Uint8Array>,
    private readonly nesting: number,
  ) {}

  children(el: XmlElement, state: State): DisplayItem[] {
    const out: DisplayItem[] = []
    for (const c of el.children) if (typeof c !== 'string') out.push(...this.element(c, state))
    return out
  }

  element(el: XmlElement, parent: State): DisplayItem[] {
    if (el.name.startsWith('{')) return []
    switch (el.name) {
      case 'defs':
      case 'symbol':
      case 'clipPath':
      case 'linearGradient':
      case 'radialGradient':
      case 'style':
      case 'title':
      case 'desc':
      case 'metadata':
      case 'script':
        return []
      case 'mask':
        return []
      case 'pattern':
        return []
      case 'marker':
        return []
      case 'filter':
        return []
      case 'foreignObject':
        this.notes.add(NOTES.foreign)
        return []
    }
    if (parent.depth >= MAX_DEPTH) {
      this.notes.add(NOTES.depth)
      return []
    }
    const style = computeStyle(el, parent.style, this.doc.sheet)
    if ((style.display ?? '').trim() === 'none') return []
    const transform = parseTransform(el.attrs.get('transform'))
    if (!transform) return []
    const state: State = { ...parent, ctm: multiply(parent.ctm, transform), style, depth: parent.depth + 1 }
    if (style.filter && style.filter !== 'none') this.notes.add(NOTES.filter)
    if (style.mask && style.mask !== 'none') this.notes.add(NOTES.mask)

    let items: DisplayItem[]
    switch (el.name) {
      case 'svg':
        items = this.nestedSvg(el, state)
        break
      case 'g':
      case 'a':
        items = this.children(el, state)
        break
      case 'switch': {
        const first = el.children.find((c): c is XmlElement => typeof c !== 'string' && !c.name.startsWith('{'))
        items = first ? this.element(first, state) : []
        break
      }
      case 'use':
        items = this.use(el, state)
        break
      case 'text':
        items = this.text(el, state)
        break
      case 'image':
        items = this.image(el, state)
        break
      default: {
        const segments = this.outline(el, state)
        if (!segments) return []
        items = this.shape(el, segments, state)
      }
    }
    if (!items.length) return []
    // the element's clip path and opacity apply to all of it at once
    const clip = this.clipFor(el, style, state)
    if (clip === 'empty') return []
    const opacity = clamp01(Number.parseFloat(style.opacity ?? '1'))
    if (clip || opacity < 1) {
      const g = group(items)
      if (clip) g.clipPath = clip
      if (opacity < 1) g.opacity = Math.round(opacity * 255)
      return [g]
    }
    return items
  }

  private lengths(state: State): LengthContext {
    return { fontSize: Number.parseFloat(state.style['font-size'] ?? '16') || 16, width: state.viewport.w, height: state.viewport.h }
  }

  /** The outline of a basic shape or a path, in user units; `null` if it draws nothing. */
  outline(el: XmlElement, state: State): Segment[] | null {
    const L = this.lengths(state)
    const a = (name: string, axis: 'x' | 'y' | 'xy') => length(el.attrs.get(name), L, axis)
    let segments: Segment[]
    switch (el.name) {
      case 'path':
        segments = parsePath(el.attrs.get('d') ?? '')
        break
      case 'rect': {
        const w = a('width', 'x')
        const h = a('height', 'y')
        if (w <= 0 || h <= 0) return null
        const rxs = el.attrs.get('rx')
        const rys = el.attrs.get('ry')
        const rx = rxs !== undefined && rxs !== 'auto' ? a('rx', 'x') : rys !== undefined && rys !== 'auto' ? a('ry', 'y') : 0
        const ry = rys !== undefined && rys !== 'auto' ? a('ry', 'y') : rx
        segments = rect(a('x', 'x'), a('y', 'y'), w, h, rx, ry)
        break
      }
      case 'circle': {
        const r = a('r', 'xy')
        if (r <= 0) return null
        segments = ellipse(a('cx', 'x'), a('cy', 'y'), r, r)
        break
      }
      case 'ellipse': {
        const rx = a('rx', 'x')
        const ry = a('ry', 'y')
        if (rx <= 0 || ry <= 0) return null
        segments = ellipse(a('cx', 'x'), a('cy', 'y'), rx, ry)
        break
      }
      case 'line':
        segments = [
          ['M', a('x1', 'x'), a('y1', 'y')],
          ['L', a('x2', 'x'), a('y2', 'y')],
        ]
        break
      case 'polyline':
        segments = poly(el.attrs.get('points'), false)
        break
      case 'polygon':
        segments = poly(el.attrs.get('points'), true)
        break
      default:
        return null
    }
    return segments.length ? segments : null
  }

  private ops(segments: readonly Segment[], m: Affine): PathOp[] {
    const out: PathOp[] = []
    const P = (x: number, y: number): [number, number] => {
      const [px, py] = apply(m, x, y)
      return [Math.round(px), Math.round(py)]
    }
    for (const s of segments) {
      if (s[0] === 'Z') out.push(['Z'])
      else if (s[0] === 'C') out.push(['C', ...P(s[1], s[2]), ...P(s[3], s[4]), ...P(s[5], s[6])])
      else out.push([s[0], ...P(s[1], s[2])])
    }
    return out
  }

  shape(el: XmlElement, segments: Segment[], state: State): DisplayItem[] {
    const style = state.style
    if ((style.visibility ?? 'visible') !== 'visible') return []
    const box = bounds(segments)
    // a line has no inside to fill
    const fill = el.name === 'line' ? null : this.paint(style.fill, style['fill-opacity'], box, state)
    const s = scaleOf(state.ctm)
    const L = this.lengths(state)
    const width = Math.round(length(style['stroke-width'], L, 'xy', 1) * s)
    const stroke = width > 0 ? this.paint(style.stroke, style['stroke-opacity'], box, state) : null
    if (!fill && !stroke) return []
    if (['marker-start', 'marker-mid', 'marker-end'].some((k) => style[k] && style[k] !== 'none')) this.notes.add(NOTES.marker)
    const item: PathItem = { kind: 'path', ops: this.ops(segments, state.ctm), fill, stroke, lineWidth: stroke ? width : 0 }
    if (style['fill-rule'] === 'evenodd') item.fillRule = 'evenodd'
    if (stroke) {
      const cap = style['stroke-linecap']
      if (cap === 'round' || cap === 'square') item.lineCap = cap
      const join = style['stroke-linejoin']
      if (join === 'round' || join === 'bevel') item.lineJoin = join
      const limit = Number.parseFloat(style['stroke-miterlimit'] ?? '4')
      item.miterLimit = Math.round((Number.isFinite(limit) && limit >= 1 ? limit : 4) * 1000)
      const dashes = (style['stroke-dasharray'] ?? 'none') === 'none' ? [] : (style['stroke-dasharray'] ?? '').split(/[\s,]+/).filter(Boolean).map((d) => length(d, L, 'xy', -1))
      if (dashes.length && dashes.every((d) => d >= 0) && dashes.some((d) => d > 0)) {
        const pattern = dashes.length % 2 ? [...dashes, ...dashes] : dashes
        item.dash = pattern.map((d) => Math.round(d * s))
        const offset = length(style['stroke-dashoffset'], L, 'xy', 0)
        if (offset) item.dashOffset = Math.round(offset * s)
      }
    }
    if (!item.fill && !item.stroke) return []
    return [item]
  }

  /** A `fill` or `stroke` value as a paint, with the matching opacity; `null` for none. */
  paint(value: string | undefined, opacityValue: string | undefined, box: ReturnType<typeof bounds>, state: State): Paint | null {
    const opacity = clamp01(Number.parseFloat(opacityValue ?? '1'))
    const v = (value ?? 'none').trim()
    if (!v || v === 'none' || opacity <= 0) return null
    const url = /^url\(\s*['"]?#([^'")\s]+)['"]?\s*\)\s*(.*)$/.exec(v)
    if (url) {
      const target = this.doc.ids.get(url[1]!)
      if (target && (target.name === 'linearGradient' || target.name === 'radialGradient')) return this.gradient(target, opacity, box, state)
      if (target?.name === 'pattern') this.notes.add(NOTES.pattern)
      return url[2] ? this.paint(url[2], opacityValue, box, state) : null
    }
    const c = this.colour(v, state.style)
    return c ? { ...c, a: Math.round(c.a * opacity) } : null
  }

  private colour(value: string, style: Style): Rgba | null {
    const v = value.trim().toLowerCase()
    if (v === 'transparent') return null
    if (v === 'currentcolor') return parseColor(style.color ?? 'black')
    const c = parseColor(v)
    return c && c.a > 0 ? c : null
  }

  /** A gradient element (with what it takes from those its `href` points to) as a paint. */
  gradient(el: XmlElement, opacity: number, box: ReturnType<typeof bounds>, state: State): Paint | null {
    // the attributes and stops, following href; the first with stops gives them
    const chain: XmlElement[] = []
    for (let g: XmlElement | undefined = el; g && chain.length < 16 && !chain.includes(g); ) {
      chain.push(g)
      const href = g.attrs.get('href')
      g = href?.startsWith('#') ? this.doc.ids.get(href.slice(1)) : undefined
      if (g && g.name !== 'linearGradient' && g.name !== 'radialGradient') g = undefined
    }
    const attr = (name: string) => chain.find((g) => g.attrs.has(name))?.attrs.get(name)
    const withStops = chain.find((g) => g.children.some((c) => typeof c !== 'string' && c.name === 'stop'))
    const stops: GradientStop[] = []
    let last = 0
    for (const c of withStops?.children ?? []) {
      if (typeof c === 'string' || c.name !== 'stop') continue
      const st = computeStyle(c, state.style, this.doc.sheet)
      const raw = (c.attrs.get('offset') ?? '0').trim()
      let offset = raw.endsWith('%') ? Number.parseFloat(raw) / 100 : Number.parseFloat(raw)
      offset = Math.max(last, clamp01(Number.isFinite(offset) ? offset : 0))
      last = offset
      const colour = this.colour(st['stop-color'] ?? 'black', st) ?? { r: 0, g: 0, b: 0, a: 0 }
      const a = Math.round(colour.a * clamp01(Number.parseFloat(st['stop-opacity'] ?? '1')) * opacity)
      stops.push({ offset: Math.round(offset * 1_000_000), color: { ...colour, a } })
    }
    if (!stops.length) return null
    if (stops.length === 1) return stops[0]!.color.a > 0 ? stops[0]!.color : null
    const spread = attr('spreadMethod')
    if (spread === 'reflect' || spread === 'repeat') this.notes.add(NOTES.spread)
    const objectBox = (attr('gradientUnits') ?? 'objectBoundingBox') !== 'userSpaceOnUse'
    const gt = parseTransform(attr('gradientTransform')) ?? UNIT
    let space: Affine
    let L: LengthContext
    if (objectBox) {
      if (!box || box.w <= 0 || box.h <= 0) return null
      space = multiply(multiply(state.ctm, [box.w, 0, 0, box.h, box.x, box.y]), gt)
      L = { fontSize: 1, width: 1, height: 1 }
    } else {
      space = multiply(state.ctm, gt)
      L = this.lengths(state)
    }
    const fraction = (name: string, fallback: string, axis: 'x' | 'y' | 'xy') => {
      const v = attr(name) ?? fallback
      return objectBox && v.trim().endsWith('%') ? Number.parseFloat(v) / 100 : length(v, L, axis)
    }
    const parts = split(space)
    if (!parts) return null
    const k = (v: number) => Math.round(v * parts.s)
    let coords: number[]
    if (el.name === 'linearGradient') {
      coords = [fraction('x1', '0%', 'x'), fraction('y1', '0%', 'y'), fraction('x2', '100%', 'x'), fraction('y2', '0%', 'y')].map(k)
    } else {
      const cx = fraction('cx', '50%', 'x')
      const cy = fraction('cy', '50%', 'y')
      const r = fraction('r', '50%', 'xy')
      coords = [cx, cy, r, attr('fx') !== undefined ? fraction('fx', '50%', 'x') : cx, attr('fy') !== undefined ? fraction('fy', '50%', 'y') : cy, fraction('fr', '0%', 'xy')].map(k)
      if (coords[2]! <= 0) return stops.at(-1)!.color
    }
    const gradient: Gradient = { kind: el.name === 'linearGradient' ? 'linear' : 'radial', coords, stops, matrix: parts.matrix }
    return gradient
  }

  /** The clip path of an element, in page coordinates; `'empty'` when it lets nothing through. */
  clipFor(el: XmlElement, style: Style, state: State): GroupItem['clipPath'] | 'empty' | undefined {
    const value = style['clip-path']
    const url = value && /^url\(\s*['"]?#([^'")\s]+)['"]?\s*\)/.exec(value)
    if (!url) return undefined
    const clip = this.doc.ids.get(url[1]!)
    if (!clip || clip.name !== 'clipPath') return undefined
    let base = state.ctm
    if (clip.attrs.get('clipPathUnits') === 'objectBoundingBox') {
      const segments = this.outline(el, state)
      const box = segments ? bounds(segments) : null
      if (!box) return 'empty'
      base = multiply(base, [box.w, 0, 0, box.h, box.x, box.y])
    }
    const own = parseTransform(clip.attrs.get('transform'))
    if (!own) return 'empty'
    base = multiply(base, own)
    const ops: PathOp[] = []
    let evenOdd = false
    const add = (child: XmlElement, m: Affine, parentStyle: Style) => {
      const st = computeStyle(child, parentStyle, this.doc.sheet)
      if ((st.display ?? '') === 'none') return
      const t = parseTransform(child.attrs.get('transform'))
      if (!t) return
      const ctm = multiply(m, t)
      if (child.name === 'use') {
        const href = child.attrs.get('href')
        const target = href?.startsWith('#') ? this.doc.ids.get(href.slice(1)) : undefined
        if (target && target !== child) {
          const L = this.lengths({ ...state, style: st })
          add(target, multiply(ctm, [1, 0, 0, 1, length(child.attrs.get('x'), L, 'x'), length(child.attrs.get('y'), L, 'y')]), st)
        }
        return
      }
      const segments = this.outline(child, { ...state, ctm, style: st })
      if (!segments) return
      if (!ops.length && (st['clip-rule'] ?? 'nonzero') === 'evenodd') evenOdd = true
      ops.push(...this.ops(segments, ctm))
    }
    for (const c of clip.children) if (typeof c !== 'string') add(c, base, computeStyle(clip, INITIAL, this.doc.sheet))
    if (!ops.length) return 'empty'
    return evenOdd ? { ops, evenOdd } : { ops }
  }

  nestedSvg(el: XmlElement, state: State): DisplayItem[] {
    const L = this.lengths(state)
    const port = { x: length(el.attrs.get('x'), L, 'x'), y: length(el.attrs.get('y'), L, 'y'), w: length(el.attrs.get('width') ?? '100%', L, 'x'), h: length(el.attrs.get('height') ?? '100%', L, 'y') }
    return this.viewport(el, port, state)
  }

  /** Children of `el` drawn in a new viewport, clipped to it, through `el`'s viewBox. */
  private viewport(el: XmlElement, port: { x: number; y: number; w: number; h: number }, state: State): DisplayItem[] {
    if (port.w <= 0 || port.h <= 0) return []
    const vb = numbers(el.attrs.get('viewBox') ?? '')
    const view = vb.length === 4 && vb[2]! > 0 && vb[3]! > 0 ? { x: vb[0]!, y: vb[1]!, w: vb[2]!, h: vb[3]! } : { x: 0, y: 0, w: port.w, h: port.h }
    const fit = vb.length === 4 ? fitViewBox(view, port, el.attrs.get('preserveAspectRatio')) : ([1, 0, 0, 1, port.x, port.y] as Affine)
    const inner: State = { ...state, ctm: multiply(state.ctm, fit), viewport: { w: view.w, h: view.h } }
    const items = this.children(el, inner)
    if (!items.length) return []
    const overflow = (el.attrs.get('overflow') ?? computeStyle(el, state.style, this.doc.sheet).overflow ?? 'hidden').trim()
    if (overflow === 'visible' || overflow === 'auto') return items
    return [group(items, { clipPath: { ops: this.ops(rect(port.x, port.y, port.w, port.h, 0, 0), state.ctm) } })]
  }

  use(el: XmlElement, state: State): DisplayItem[] {
    const href = el.attrs.get('href')
    const target = href?.startsWith('#') ? this.doc.ids.get(href.slice(1)) : undefined
    if (!href) return []
    if (!href.startsWith('#')) {
      this.notes.add(NOTES.link)
      return []
    }
    if (!target || state.using.has(target) || target === el) return []
    const L = this.lengths(state)
    const x = length(el.attrs.get('x'), L, 'x')
    const y = length(el.attrs.get('y'), L, 'y')
    const using = new Set(state.using).add(target)
    const moved: State = { ...state, ctm: multiply(state.ctm, [1, 0, 0, 1, x, y]), using }
    if (target.name === 'symbol' || target.name === 'svg') {
      const port = { x: 0, y: 0, w: length(el.attrs.get('width') ?? target.attrs.get('width') ?? '100%', L, 'x'), h: length(el.attrs.get('height') ?? target.attrs.get('height') ?? '100%', L, 'y') }
      const styled: State = { ...moved, style: computeStyle(target, state.style, this.doc.sheet) }
      if (target.name === 'svg') {
        const sx = length(target.attrs.get('x'), L, 'x')
        const sy = length(target.attrs.get('y'), L, 'y')
        return this.viewport(target, { ...port, x: sx, y: sy }, styled)
      }
      return this.viewport(target, port, styled)
    }
    return this.element(target, moved)
  }

  text(el: XmlElement, state: State): DisplayItem[] {
    const fonts = this.context.fonts
    const resolver = this.context.resolver
    // pieces of text with their style and position, gathered in order
    interface Piece {
      text: string
      style: Style
      x: number | null
      y: number | null
      dx: number
      dy: number
    }
    const pieces: Piece[] = []
    const preserve = (el.attrs.get('xml:space') ?? '') === 'preserve'
    const L0 = this.lengths(state)
    const first = (v: string | undefined, axis: 'x' | 'y') => {
      const n = (v ?? '').trim().split(/[\s,]+/)[0]
      return n ? length(n, L0, axis, 0) : null
    }
    const collect = (node: XmlElement, style: Style, top: boolean) => {
      let x = first(node.attrs.get('x'), 'x')
      let y = first(node.attrs.get('y'), 'y')
      let dx = first(node.attrs.get('dx'), 'x') ?? 0
      let dy = first(node.attrs.get('dy'), 'y') ?? 0
      if (top) {
        // the text element's own position starts the first piece
        x ??= 0
        y ??= 0
      }
      if ((node.attrs.get('x') ?? '').trim().split(/[\s,]+/).length > 1 || node.attrs.has('rotate') || node.attrs.has('textLength') || node.attrs.has('letter-spacing')) this.notes.add(NOTES.textLayout)
      for (const c of node.children) {
        if (typeof c === 'string') {
          pieces.push({ text: c, style, x, y, dx, dy })
          x = y = null
          dx = dy = 0
        } else if (c.name === 'tspan' || c.name === 'a') {
          const st = computeStyle(c, style, this.doc.sheet)
          if ((st.display ?? '') === 'none') continue
          const before = pieces.length
          collect(c, st, false)
          // a tspan's position belongs to its first piece; a position not used yet goes to the next one
          if (pieces.length === before && (x !== null || y !== null)) continue
          if (pieces.length > before && (x !== null || y !== null || dx || dy)) {
            const p = pieces[before]!
            p.x ??= x
            p.y ??= y
            p.dx += dx
            p.dy += dy
          }
          x = y = null
          dx = dy = 0
        } else if (c.name === 'textPath') this.notes.add(NOTES.textPath)
      }
    }
    collect(el, state.style, true)
    // white space: collapsed and trimmed at both ends of the text (xml:space default)
    if (!preserve) {
      for (const p of pieces) p.text = p.text.replace(/[\n\r\t]/g, ' ').replace(/ {2,}/g, ' ')
      for (let i = 1; i < pieces.length; i++) if (pieces[i - 1]!.text.endsWith(' ') && pieces[i]!.text.startsWith(' ')) pieces[i]!.text = pieces[i]!.text.slice(1)
      if (pieces.length) {
        pieces[0]!.text = pieces[0]!.text.replace(/^ +/, '')
        pieces.at(-1)!.text = pieces.at(-1)!.text.replace(/ +$/, '')
      }
    }
    const visible = pieces.filter((p) => p.text.length > 0)
    if (!visible.length) return []
    if (!fonts || !resolver) {
      this.notes.add(NOTES.font)
      return []
    }
    const parts = split(state.ctm)
    if (!parts) return []
    // lay out the pieces along the baseline, in chunks that start at an absolute position (for text-anchor)
    interface Run {
      face: FaceRef
      size: number
      color: Rgba
      x: number
      y: number
      gids: number[]
      dx: number[]
      chars: string[]
      text: string
      width: number
    }
    const chunks: { anchor: string; runs: Run[] }[] = []
    let penX = 0
    let penY = 0
    for (const p of visible) {
      const st = p.style
      const sizePx = Number.parseFloat(st['font-size'] ?? '16') || 16
      const size = Math.round(sizePx * parts.s)
      if (size <= 0) continue
      const r = resolver.resolve(st['font-family'] ?? 'sans-serif', weightOf(st['font-weight']), italicOf(st['font-style']), Math.round(sizePx * PX))
      if (!r || !fonts.has(r.face.sha256)) {
        this.notes.add(NOTES.font)
        continue
      }
      if (p.x !== null || !chunks.length) chunks.push({ anchor: (st['text-anchor'] ?? 'start').trim(), runs: [] })
      if (p.x !== null) penX = p.x
      if (p.y !== null) penY = p.y
      penX += p.dx
      penY += p.dy
      if ((st.stroke ?? 'none') !== 'none') this.notes.add(NOTES.textStroke)
      const paint = this.paint(st.fill, st['fill-opacity'], null, { ...state, style: st })
      const color: Rgba | null = paint ? ('kind' in paint ? paint.stops[0]!.color : paint) : null
      const shaped = fonts.shape(r.face, p.text)
      const upem = fonts.metrics(r.face).unitsPerEm
      let adv = 0
      const dx: number[] = []
      for (let g = 0; g < shaped.gids.length; g++) {
        dx.push(mulDivRound(adv + shaped.xOffsets[g]!, size, upem))
        adv += shaped.advances[g]!
      }
      const width = mulDivRound(adv, size, upem)
      const run: Run = { face: r.face, size, color: color ?? { r: 0, g: 0, b: 0, a: 0 }, x: Math.round(penX * parts.s), y: Math.round(penY * parts.s), gids: shaped.gids, dx, chars: shaped.chars, text: p.text, width }
      if (color) chunks.at(-1)!.runs.push(run)
      else chunks.at(-1)!.runs.push({ ...run, gids: [] })
      penX += width / parts.s
    }
    const items: DisplayItem[] = []
    for (const chunk of chunks) {
      if (!chunk.runs.length) continue
      const start = chunk.runs[0]!.x
      const end = Math.max(...chunk.runs.map((r) => r.x + r.width))
      const shift = chunk.anchor === 'middle' ? -Math.round((end - start) / 2) : chunk.anchor === 'end' ? -(end - start) : 0
      for (const run of chunk.runs) {
        if (!run.gids.length) continue
        items.push({
          kind: 'glyphs',
          face: run.face,
          size: run.size,
          color: run.color,
          x: run.x + shift,
          y: run.y,
          glyphs: run.gids.map((gid, i) => ({ gid, dx: run.dx[i]!, chars: run.chars[i]! })),
          text: run.text,
        })
      }
    }
    if (!items.length) return []
    return [this.placed(items, parts)]
  }

  /** Items in a local frame (user units times `s`) placed on the page by `parts.matrix`. */
  private placed(items: DisplayItem[], parts: { matrix: Matrix; plain: boolean }): DisplayItem {
    if (parts.plain) {
      const [, , , , e, f] = parts.matrix
      return group(items.map((it) => moveBy(it, e, f)))
    }
    return group(items, { matrix: parts.matrix })
  }

  image(el: XmlElement, state: State): DisplayItem[] {
    if ((state.style.visibility ?? 'visible') !== 'visible') return []
    const href = (el.attrs.get('href') ?? '').trim()
    if (!href) return []
    const L = this.lengths(state)
    const port = { x: length(el.attrs.get('x'), L, 'x'), y: length(el.attrs.get('y'), L, 'y'), w: length(el.attrs.get('width'), L, 'x'), h: length(el.attrs.get('height'), L, 'y') }
    const data = /^data:([^;,]*)((?:;[^;,]*)*),([\s\S]*)$/.exec(href)
    if (!data) {
      this.notes.add(NOTES.link)
      return []
    }
    const base64 = /;base64/i.test(data[2]!)
    let bytes: Uint8Array | null
    if (base64) bytes = fromBase64(data[3]!)
    else {
      try {
        bytes = utf8Encode(decodeURIComponent(data[3]!))
      } catch {
        bytes = null
      }
    }
    if (!bytes) {
      this.notes.add(NOTES.picture)
      return []
    }
    const mime = data[1]!.toLowerCase()
    if (mime === 'image/svg+xml') return this.svgPicture(bytes, port, el, state)
    let size: { w: number; h: number }
    try {
      if (isPng(bytes)) size = pixelsOf(decodePng(bytes))
      else if (isJpeg(bytes)) {
        const j = readJpeg(bytes)
        size = { w: j.width, h: j.height }
      } else if (isGif(bytes)) size = pixelsOf(decodeGif(bytes))
      else if (isBmp(bytes)) size = pixelsOf(decodeBmp(bytes))
      else throw new Error('unknown format')
    } catch {
      this.notes.add(NOTES.picture)
      return []
    }
    if (port.w <= 0) port.w = port.h > 0 ? (port.h * size.w) / size.h : size.w
    if (port.h <= 0) port.h = (port.w * size.h) / size.w
    const fit = fitViewBox({ x: 0, y: 0, w: size.w, h: size.h }, port, el.attrs.get('preserveAspectRatio'))
    const parts = split(multiply(state.ctm, fit))
    if (!parts) return []
    const id = `svg-${sha256Hex(bytes)}`
    this.images.set(id, bytes)
    const picture = this.placed([{ kind: 'image', image: id, x: 0, y: 0, w: Math.round(size.w * parts.s), h: Math.round(size.h * parts.s) }], parts)
    // a picture larger than its box (`slice`) is cut at the box
    return [group([picture], { clipPath: { ops: this.ops(rect(port.x, port.y, port.w, port.h, 0, 0), state.ctm) } })]
  }

  private svgPicture(bytes: Uint8Array, port: { x: number; y: number; w: number; h: number }, el: XmlElement, state: State): DisplayItem[] {
    if (this.nesting >= 4) {
      this.notes.add(NOTES.depth)
      return []
    }
    let inner: SvgDocument
    try {
      inner = parseSvg(utf8Decode(bytes))
    } catch {
      this.notes.add(NOTES.picture)
      return []
    }
    if (port.w <= 0 || port.h <= 0) return []
    // drawn into the image box in user units; its own drawing then goes through this element's transform
    const parts = split(state.ctm)
    if (!parts) return []
    const box: Rect = { x: Math.round(port.x * parts.s), y: Math.round(port.y * parts.s), w: Math.round(port.w * parts.s), h: Math.round(port.h * parts.s) }
    if (el.attrs.get('preserveAspectRatio') && !inner.root.attrs.has('preserveAspectRatio')) inner.root.attrs.set('preserveAspectRatio', el.attrs.get('preserveAspectRatio')!)
    const items = drawInto(inner, box, this.context, this.notes, this.images, this.nesting + 1)
    return [this.placed([group(items, { clip: box })], parts)]
  }
}

const pixelsOf = (p: { width: number; height: number }) => ({ w: p.width, h: p.height })
const clamp01 = (v: number) => (Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 1)

/** An item moved by (e, f) mpt. */
function moveBy(it: DisplayItem, e: number, f: number): DisplayItem {
  if (!e && !f) return it
  switch (it.kind) {
    case 'glyphs':
      return { ...it, x: it.x + e, y: it.y + f }
    case 'image':
      return { ...it, x: it.x + e, y: it.y + f }
    case 'path':
      return { ...it, ops: it.ops.map((op) => moveOp(op, e, f)), fill: movePaint(it.fill, e, f), stroke: movePaint(it.stroke, e, f) }
    default:
      return {
        ...it,
        clip: it.clip ? { ...it.clip, x: it.clip.x + e, y: it.clip.y + f } : null,
        origin: { x: it.origin.x + e, y: it.origin.y + f },
        ...(it.clipPath ? { clipPath: { ...it.clipPath, ops: it.clipPath.ops.map((op) => moveOp(op, e, f)) } } : {}),
        ...(it.matrix ? { matrix: [it.matrix[0], it.matrix[1], it.matrix[2], it.matrix[3], it.matrix[4] + e, it.matrix[5] + f] as Matrix } : {}),
        items: it.matrix ? it.items : it.items.map((child) => moveBy(child, e, f)),
      }
  }
}

function movePaint(p: Paint | null, e: number, f: number): Paint | null {
  if (!p || !('kind' in p)) return p
  const [a, b, c, d, x, y] = p.matrix
  return { ...p, matrix: [a, b, c, d, x + e, y + f] }
}

function moveOp(op: PathOp, e: number, f: number): PathOp {
  if (op[0] === 'Z') return op
  if (op[0] === 'C') return ['C', op[1] + e, op[2] + f, op[3] + e, op[4] + f, op[5] + e, op[6] + f]
  return [op[0], op[1] + e, op[2] + f]
}
