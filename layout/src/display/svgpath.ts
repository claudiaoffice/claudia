/**
 * Shape outlines (`claudia_core.shapes`): an SVG path with absolute `M`, `L`, `C`, `A` and `Z` in a box of 100 by
 * 100 units, stretched to an object's box. Arcs become cubic curves, computed with {@link sinCos} and {@link atan2}
 * so that every engine gives the same numbers; every coordinate is rounded to a whole mpt.
 *
 * @module
 */
import { atan2, sinCos } from './detmath'
import type { PathOp, Rect } from './list'

/** A path that is not one of the outlines a shape may have. */
export class PathError extends Error {}

const BOX = 100

function tokens(d: string): (string | number)[] {
  const out: (string | number)[] = []
  const re = /([MLCAZmlcaz])|(-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?)/g
  let m: RegExpExecArray | null
  let consumed = 0
  while ((m = re.exec(d)) !== null) {
    if (d.slice(consumed, m.index).replace(/[\s,]/g, '') !== '') throw new PathError(`unexpected text in a path: ${d.slice(consumed, m.index)}`)
    consumed = m.index + m[0].length
    out.push(m[1] ? m[1] : Number(m[2]))
  }
  if (d.slice(consumed).replace(/[\s,]/g, '') !== '') throw new PathError('unexpected text at the end of a path')
  return out
}

/** An SVG elliptical arc as cubic curves, in the path's own (unrounded) units. */
function arcToCubics(x1: number, y1: number, rx: number, ry: number, phiDeg: number, large: boolean, sweep: boolean, x2: number, y2: number): number[][] {
  if ((x1 === x2 && y1 === y2) || rx === 0 || ry === 0) return [[x1, y1, x2, y2, x2, y2]]
  rx = Math.abs(rx)
  ry = Math.abs(ry)
  const [sinPhi, cosPhi] = sinCos((phiDeg * Math.PI) / 180)
  const dx = (x1 - x2) / 2
  const dy = (y1 - y2) / 2
  const x1p = cosPhi * dx + sinPhi * dy
  const y1p = -sinPhi * dx + cosPhi * dy
  const lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
  if (lambda > 1) {
    const s = Math.sqrt(lambda)
    rx *= s
    ry *= s
  }
  const num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
  const den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
  let coef = Math.sqrt(Math.max(0, num / den))
  if (large === sweep) coef = -coef
  const cxp = (coef * rx * y1p) / ry
  const cyp = (-coef * ry * x1p) / rx
  const cx = cosPhi * cxp - sinPhi * cyp + (x1 + x2) / 2
  const cy = sinPhi * cxp + cosPhi * cyp + (y1 + y2) / 2
  const theta1 = atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
  let delta = atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx) - theta1
  if (!sweep && delta > 0) delta -= 2 * Math.PI
  else if (sweep && delta < 0) delta += 2 * Math.PI
  const segments = Math.max(1, Math.ceil(Math.abs(delta) / (Math.PI / 2) - 1e-9))
  const step = delta / segments
  const k = (4 / 3) * ((1 - sinCos(step / 2)[1]) / sinCos(step / 2)[0])
  const out: number[][] = []
  let t = theta1
  for (let i = 0; i < segments; i++) {
    const [s1, c1] = sinCos(t)
    const [s2, c2] = sinCos(t + step)
    const p = (cosT: number, sinT: number): [number, number] => [cosPhi * rx * cosT - sinPhi * ry * sinT + cx, sinPhi * rx * cosT + cosPhi * ry * sinT + cy]
    const d = (cosT: number, sinT: number): [number, number] => [-cosPhi * rx * sinT - sinPhi * ry * cosT, -sinPhi * rx * sinT + cosPhi * ry * cosT]
    const [ax, ay] = p(c1, s1)
    const [bx, by] = p(c2, s2)
    const [dax, day] = d(c1, s1)
    const [dbx, dby] = d(c2, s2)
    out.push([ax + k * dax, ay + k * day, bx - k * dbx, by - k * dby, bx, by])
    t += step
  }
  // end exactly at the given point
  const last = out[out.length - 1]!
  last[4] = x2
  last[5] = y2
  return out
}

/** The outline `d` (in its 100 × 100 box) stretched to `box`, as path commands in whole mpt. */
export function outlinePath(d: string, box: Rect): PathOp[] {
  const t = tokens(d)
  const ops: PathOp[] = []
  const X = (v: number) => box.x + Math.round((v * box.w) / BOX)
  const Y = (v: number) => box.y + Math.round((v * box.h) / BOX)
  let i = 0
  let cmd = ''
  let cx = 0
  let cy = 0
  let sx = 0
  let sy = 0
  const num = (): number => {
    const v = t[i++]
    if (typeof v !== 'number') throw new PathError('a path command is missing a number')
    return v
  }
  while (i < t.length) {
    if (typeof t[i] === 'string') cmd = t[i++] as string
    else if (!cmd) throw new PathError('a path starts with M')
    if (cmd !== cmd.toUpperCase()) throw new PathError('only absolute path commands are allowed')
    switch (cmd) {
      case 'M':
        cx = sx = num()
        cy = sy = num()
        ops.push(['M', X(cx), Y(cy)])
        cmd = 'L'
        break
      case 'L':
        cx = num()
        cy = num()
        ops.push(['L', X(cx), Y(cy)])
        break
      case 'C': {
        const v = [num(), num(), num(), num(), num(), num()]
        ops.push(['C', X(v[0]!), Y(v[1]!), X(v[2]!), Y(v[3]!), X(v[4]!), Y(v[5]!)])
        cx = v[4]!
        cy = v[5]!
        break
      }
      case 'A': {
        const rx = num()
        const ry = num()
        const rot = num()
        const large = num() !== 0
        const sweep = num() !== 0
        const x = num()
        const y = num()
        // stretch the radii with the box, so the arc fits the stretched outline
        for (const c of arcToCubics(cx, cy, rx, ry, rot, large, sweep, x, y)) ops.push(['C', X(c[0]!), Y(c[1]!), X(c[2]!), Y(c[3]!), X(c[4]!), Y(c[5]!)])
        cx = x
        cy = y
        break
      }
      case 'Z':
        ops.push(['Z'])
        cx = sx
        cy = sy
        break
      default:
        throw new PathError(`unknown path command ${cmd}`)
    }
  }
  if (ops[0]?.[0] !== 'M') throw new PathError('a path starts with M')
  return ops
}
