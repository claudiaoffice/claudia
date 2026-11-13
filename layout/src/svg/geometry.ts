/**
 * SVG geometry: transforms, lengths, path data and the basic shapes, as outlines of lines and cubic curves in user
 * units. Angles go through {@link sinCos}, so a rotated or arced outline has the same numbers in every engine.
 *
 * @module
 */
import { sinCos } from '../display/detmath'
import { arcToCubics } from '../display/svgpath'

/** An affine transform in floating point: (x, y) → (a·x + c·y + e, b·x + d·y + f). */
export type Affine = [number, number, number, number, number, number]
export const UNIT: Affine = [1, 0, 0, 1, 0, 0]

/** `m` after `n`: first `n`, then `m`. */
export function multiply(m: Affine, n: Affine): Affine {
  return [
    m[0] * n[0] + m[2] * n[1],
    m[1] * n[0] + m[3] * n[1],
    m[0] * n[2] + m[2] * n[3],
    m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4],
    m[1] * n[4] + m[3] * n[5] + m[5],
  ]
}

export const apply = (m: Affine, x: number, y: number): [number, number] => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]

/** How much `m` scales lengths: the square root of its area factor. */
export const scaleOf = (m: Affine): number => Math.sqrt(Math.abs(m[0] * m[3] - m[1] * m[2]))

const NUMBER = /[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/g
const DEG = Math.PI / 180

/** Numbers in a list (`1,2 3e2 -4`). */
export function numbers(text: string): number[] {
  return (text.match(NUMBER) ?? []).map(Number)
}

/** A `transform` attribute; `null` if it cannot be read (the element is then not drawn, as browsers do). */
export function parseTransform(text: string | undefined): Affine | null {
  if (!text || !text.trim() || text.trim() === 'none') return UNIT
  let m: Affine = UNIT
  const re = /\s*(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)\s*,?/gy
  let found: RegExpExecArray | null
  let consumed = 0
  while ((found = re.exec(text)) !== null) {
    consumed = re.lastIndex
    const v = numbers(found[2]!)
    let t: Affine
    switch (found[1]) {
      case 'matrix':
        if (v.length !== 6) return null
        t = v as Affine
        break
      case 'translate':
        t = [1, 0, 0, 1, v[0] ?? 0, v[1] ?? 0]
        break
      case 'scale':
        t = [v[0] ?? 1, 0, 0, v[1] ?? v[0] ?? 1, 0, 0]
        break
      case 'rotate': {
        const [s, c] = sinCos((v[0] ?? 0) * DEG)
        const r: Affine = [c, s, -s, c, 0, 0]
        if (v.length >= 3) t = multiply(multiply([1, 0, 0, 1, v[1]!, v[2]!], r), [1, 0, 0, 1, -v[1]!, -v[2]!])
        else t = r
        break
      }
      case 'skewX': {
        const [s, c] = sinCos((v[0] ?? 0) * DEG)
        t = [1, 0, s / c, 1, 0, 0]
        break
      }
      default: {
        const [s, c] = sinCos((v[0] ?? 0) * DEG)
        t = [1, s / c, 0, 1, 0, 0]
      }
    }
    m = multiply(m, t)
  }
  if (text.slice(consumed).trim()) return null
  return m
}

/** What a length is relative to: the font size, and the width and height of the viewport (for %). */
export interface LengthContext {
  fontSize: number
  width: number
  height: number
}

/** A length in user units; `fallback` if it cannot be read. `axis` decides what a percentage is of. */
export function length(text: string | undefined, ctx: LengthContext, axis: 'x' | 'y' | 'xy', fallback = 0): number {
  if (text === undefined) return fallback
  const m = /^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(px|pt|pc|mm|cm|in|em|ex|%)?\s*$/.exec(text)
  if (!m) return fallback
  const n = Number(m[1])
  switch (m[2]) {
    case 'pt':
      return (n * 4) / 3
    case 'pc':
      return n * 16
    case 'mm':
      return (n * 96) / 25.4
    case 'cm':
      return (n * 96) / 2.54
    case 'in':
      return n * 96
    case 'em':
      return n * ctx.fontSize
    case 'ex':
      return (n * ctx.fontSize) / 2
    case '%': {
      const base = axis === 'x' ? ctx.width : axis === 'y' ? ctx.height : Math.sqrt((ctx.width * ctx.width + ctx.height * ctx.height) / 2)
      return (n * base) / 100
    }
    default:
      return n
  }
}

/** One segment of an outline in user units: move, line, cubic curve, close. */
export type Segment = ['M', number, number] | ['L', number, number] | ['C', number, number, number, number, number, number] | ['Z']

/** Path data (`d`) as segments; whatever follows an error is dropped, as SVG says. */
export function parsePath(d: string): Segment[] {
  const out: Segment[] = []
  let p = 0
  const n = d.length
  const skip = () => {
    while (p < n && /[\s,]/.test(d[p]!)) p++
  }
  const NUM = /[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/y
  const number = (): number | null => {
    skip()
    NUM.lastIndex = p
    const m = NUM.exec(d)
    if (!m) return null
    p = NUM.lastIndex
    return Number(m[0])
  }
  // an arc's flags are single digits, and may be written without anything between them ("a5 5 0 015 5")
  const flag = (): boolean | null => {
    skip()
    const c = d[p]
    if (c !== '0' && c !== '1') return null
    p++
    return c === '1'
  }
  const numbersFor = (k: number): number[] | null => {
    const v: number[] = []
    for (let j = 0; j < k; j++) {
      const x = number()
      if (x === null) return null
      v.push(x)
    }
    return v
  }
  let cmd = ''
  let x = 0
  let y = 0
  let sx = 0
  let sy = 0
  let qx = 0
  let qy = 0
  let cx2 = 0
  let cy2 = 0
  let prev = ''
  for (;;) {
    skip()
    if (p >= n) break
    if (/[MmLlHhVvCcSsQqTtAaZz]/.test(d[p]!)) cmd = d[p++]!
    else if (!cmd || cmd === 'Z' || cmd === 'z') break
    else if (cmd === 'M') cmd = 'L'
    else if (cmd === 'm') cmd = 'l'
    if (!out.length && cmd !== 'M' && cmd !== 'm') break
    const rel = cmd === cmd.toLowerCase()
    const ox = rel ? x : 0
    const oy = rel ? y : 0
    const C = cmd.toUpperCase()
    if (C === 'Z') {
      out.push(['Z'])
      x = sx
      y = sy
      prev = 'Z'
      continue
    }
    if (C === 'M' || C === 'L') {
      const v = numbersFor(2)
      if (!v) break
      x = ox + v[0]!
      y = oy + v[1]!
      if (C === 'M') {
        sx = x
        sy = y
      }
      out.push([C, x, y])
    } else if (C === 'H' || C === 'V') {
      const v = numbersFor(1)
      if (!v) break
      if (C === 'H') x = ox + v[0]!
      else y = oy + v[0]!
      out.push(['L', x, y])
    } else if (C === 'C' || C === 'S') {
      const v = numbersFor(C === 'C' ? 6 : 4)
      if (!v) break
      const smooth = prev === 'C' || prev === 'S'
      const x1 = C === 'C' ? ox + v[0]! : smooth ? 2 * x - cx2 : x
      const y1 = C === 'C' ? oy + v[1]! : smooth ? 2 * y - cy2 : y
      const k = C === 'C' ? 2 : 0
      cx2 = ox + v[k]!
      cy2 = oy + v[k + 1]!
      x = ox + v[k + 2]!
      y = oy + v[k + 3]!
      out.push(['C', x1, y1, cx2, cy2, x, y])
    } else if (C === 'Q' || C === 'T') {
      const v = numbersFor(C === 'Q' ? 4 : 2)
      if (!v) break
      const smooth = prev === 'Q' || prev === 'T'
      if (C === 'Q') {
        qx = ox + v[0]!
        qy = oy + v[1]!
      } else {
        qx = smooth ? 2 * x - qx : x
        qy = smooth ? 2 * y - qy : y
      }
      const ex = ox + v[C === 'Q' ? 2 : 0]!
      const ey = oy + v[C === 'Q' ? 3 : 1]!
      out.push(['C', x + (2 / 3) * (qx - x), y + (2 / 3) * (qy - y), ex + (2 / 3) * (qx - ex), ey + (2 / 3) * (qy - ey), ex, ey])
      x = ex
      y = ey
    } else {
      const r = numbersFor(3)
      const large = r ? flag() : null
      const sweep = large !== null ? flag() : null
      const e = sweep !== null ? numbersFor(2) : null
      if (!r || large === null || sweep === null || !e) break
      const ex = ox + e[0]!
      const ey = oy + e[1]!
      for (const c of arcToCubics(x, y, r[0]!, r[1]!, r[2]!, large, sweep, ex, ey)) out.push(['C', c[0]!, c[1]!, c[2]!, c[3]!, c[4]!, c[5]!])
      x = ex
      y = ey
    }
    prev = C
  }
  return out
}

/** The circle constant for drawing a quarter ellipse as one cubic curve. */
const KAPPA = 0.5522847498307936

/** An ellipse as four cubic curves, starting at its rightmost point. */
export function ellipse(cx: number, cy: number, rx: number, ry: number): Segment[] {
  const kx = rx * KAPPA
  const ky = ry * KAPPA
  return [
    ['M', cx + rx, cy],
    ['C', cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry],
    ['C', cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy],
    ['C', cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry],
    ['C', cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy],
    ['Z'],
  ]
}

/** A rectangle, with rounded corners when `rx`/`ry` are given. */
export function rect(x: number, y: number, w: number, h: number, rx: number, ry: number): Segment[] {
  if (rx <= 0 && ry <= 0) return [['M', x, y], ['L', x + w, y], ['L', x + w, y + h], ['L', x, y + h], ['Z']]
  rx = Math.min(rx > 0 ? rx : ry, w / 2)
  ry = Math.min(ry > 0 ? ry : rx, h / 2)
  const kx = rx * (1 - KAPPA)
  const ky = ry * (1 - KAPPA)
  return [
    ['M', x + rx, y],
    ['L', x + w - rx, y],
    ['C', x + w - kx, y, x + w, y + ky, x + w, y + ry],
    ['L', x + w, y + h - ry],
    ['C', x + w, y + h - ky, x + w - kx, y + h, x + w - rx, y + h],
    ['L', x + rx, y + h],
    ['C', x + kx, y + h, x, y + h - ky, x, y + h - ry],
    ['L', x, y + ry],
    ['C', x, y + ky, x + kx, y, x + rx, y],
    ['Z'],
  ]
}

/** The points of a polyline or polygon as segments. */
export function poly(points: string | undefined, close: boolean): Segment[] {
  const v = numbers(points ?? '')
  if (v.length < 4) return []
  const out: Segment[] = [['M', v[0]!, v[1]!]]
  for (let i = 2; i + 1 < v.length; i += 2) out.push(['L', v[i]!, v[i + 1]!])
  if (close) out.push(['Z'])
  return out
}

/** The box around an outline's points (control points included, so it may be a little larger), or `null`. */
export function bounds(segments: readonly Segment[]): { x: number; y: number; w: number; h: number } | null {
  let x0 = Infinity
  let y0 = Infinity
  let x1 = -Infinity
  let y1 = -Infinity
  for (const s of segments) {
    for (let k = 1; k + 1 < s.length; k += 2) {
      const px = s[k] as number
      const py = s[k + 1] as number
      x0 = Math.min(x0, px)
      y0 = Math.min(y0, py)
      x1 = Math.max(x1, px)
      y1 = Math.max(y1, py)
    }
  }
  return x0 === Infinity ? null : { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
}

/**
 * How a viewBox fits into a viewport (`preserveAspectRatio`): the transform from viewBox units to viewport units,
 * and whether the result is to be clipped (`slice`).
 */
export function fitViewBox(view: { x: number; y: number; w: number; h: number }, port: { x: number; y: number; w: number; h: number }, aspect: string | undefined): Affine {
  const sx = port.w / view.w
  const sy = port.h / view.h
  const words = (aspect ?? 'xMidYMid meet').trim().split(/\s+/)
  const align = words[0] === 'defer' ? (words[1] ?? 'xMidYMid') : (words[0] ?? 'xMidYMid')
  const slice = words.includes('slice')
  if (align === 'none') return [sx, 0, 0, sy, port.x - view.x * sx, port.y - view.y * sy]
  const s = slice ? Math.max(sx, sy) : Math.min(sx, sy)
  const free = (portSize: number, viewSize: number, where: string) => (where === 'Min' ? 0 : where === 'Mid' ? (portSize - viewSize * s) / 2 : portSize - viewSize * s)
  const xa = /^x(Min|Mid|Max)/.exec(align)?.[1] ?? 'Mid'
  const ya = /Y(Min|Mid|Max)$/.exec(align)?.[1] ?? 'Mid'
  return [s, 0, 0, s, port.x + free(port.w, view.w, xa) - view.x * s, port.y + free(port.h, view.h, ya) - view.y * s]
}
