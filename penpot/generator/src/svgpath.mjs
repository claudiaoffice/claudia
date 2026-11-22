// SVG path data -> absolute M/L/C/Z segments (what Penpot's path content has: move-to, line-to, curve-to, close-path).
// Handles every command, the compact arc flags of minified icon paths ("a2 2 0 013 3"), and turns arcs into cubics.

const ARGS = { M: 2, L: 2, H: 1, V: 1, C: 6, S: 4, Q: 4, T: 2, A: 7, Z: 0 }

function tokenize(d) {
  const out = []
  const re = /([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)/g
  let m
  while ((m = re.exec(d))) out.push(m[1] ?? +m[2])
  return out
}

/** Arc flags are single characters 0/1 that may be glued to the next number; this reads them from the raw text. */
function tokenizeWithArcs(d) {
  const out = []
  let i = 0
  let cmd = null
  let argIndex = 0
  const num = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/
  while (i < d.length) {
    const ch = d[i]
    if (/[\s,]/.test(ch)) {
      i++
      continue
    }
    if (/[MmLlHhVvCcSsQqTtAaZz]/.test(ch)) {
      cmd = ch
      argIndex = 0
      out.push(ch)
      i++
      continue
    }
    const isFlag = (cmd === 'A' || cmd === 'a') && (argIndex % 7 === 3 || argIndex % 7 === 4)
    if (isFlag) {
      out.push(+ch)
      i++
    } else {
      const m = d.slice(i).match(num)
      if (!m) throw new Error(`svg path: unexpected "${d.slice(i, i + 8)}"`)
      out.push(+m[0])
      i += m[0].length
    }
    argIndex++
  }
  return out
}

function arcToCubics(x1, y1, rx, ry, phiDeg, fa, fs, x2, y2) {
  if (rx === 0 || ry === 0) return [['L', x2, y2]]
  const phi = (phiDeg * Math.PI) / 180
  const cos = Math.cos(phi)
  const sin = Math.sin(phi)
  const dx = (x1 - x2) / 2
  const dy = (y1 - y2) / 2
  const x1p = cos * dx + sin * dy
  const y1p = -sin * dx + cos * dy
  rx = Math.abs(rx)
  ry = Math.abs(ry)
  const lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
  if (lambda > 1) {
    rx *= Math.sqrt(lambda)
    ry *= Math.sqrt(lambda)
  }
  const num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
  const den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
  const co = (fa === fs ? -1 : 1) * Math.sqrt(Math.max(0, num / den))
  const cxp = (co * rx * y1p) / ry
  const cyp = (-co * ry * x1p) / rx
  const cx = cos * cxp - sin * cyp + (x1 + x2) / 2
  const cy = sin * cxp + cos * cyp + (y1 + y2) / 2
  const ang = (ux, uy, vx, vy) => {
    const a = Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    return a
  }
  const th1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
  let dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
  if (!fs && dth > 0) dth -= 2 * Math.PI
  if (fs && dth < 0) dth += 2 * Math.PI
  const n = Math.max(1, Math.ceil(Math.abs(dth) / (Math.PI / 2) - 1e-9))
  const step = dth / n
  const t = (4 / 3) * Math.tan(step / 4)
  const out = []
  let a = th1
  for (let i = 0; i < n; i++) {
    const b = a + step
    const p = (ang2, k) => {
      const ca = Math.cos(ang2)
      const sa = Math.sin(ang2)
      return [ca - k * sa, sa + k * ca]
    }
    const [e1x, e1y] = p(a, t)
    const [e2x, e2y] = p(b, -t)
    const to = (ux, uy) => [cos * rx * ux - sin * ry * uy + cx, sin * rx * ux + cos * ry * uy + cy]
    const c1 = to(e1x, e1y)
    const c2 = to(e2x, e2y)
    const end = to(Math.cos(b), Math.sin(b))
    out.push(['C', c1[0], c1[1], c2[0], c2[1], i === n - 1 ? x2 : end[0], i === n - 1 ? y2 : end[1]])
    a = b
  }
  return out
}

/** @returns {Array<['M',number,number]|['L',number,number]|['C',number,number,number,number,number,number]|['Z']>} */
export function parsePath(d) {
  const tok = tokenizeWithArcs(d)
  const segs = []
  let i = 0
  let cmd = null
  let x = 0
  let y = 0
  let sx = 0
  let sy = 0
  let lastC = null // last cubic control point, for S
  let lastQ = null
  while (i < tok.length) {
    if (typeof tok[i] === 'string') cmd = tok[i++]
    else if (cmd === 'M') cmd = 'L'
    else if (cmd === 'm') cmd = 'l'
    const up = cmd.toUpperCase()
    const rel = cmd !== up
    const n = ARGS[up]
    const a = tok.slice(i, i + n)
    i += n
    if (a.length < n) throw new Error(`svg path: "${cmd}" needs ${n} numbers`)
    const ox = rel ? x : 0
    const oy = rel ? y : 0
    let nextC = null
    let nextQ = null
    switch (up) {
      case 'M':
        x = a[0] + ox
        y = a[1] + oy
        sx = x
        sy = y
        segs.push(['M', x, y])
        break
      case 'L':
        x = a[0] + ox
        y = a[1] + oy
        segs.push(['L', x, y])
        break
      case 'H':
        x = a[0] + ox
        segs.push(['L', x, y])
        break
      case 'V':
        y = a[0] + oy
        segs.push(['L', x, y])
        break
      case 'C':
        segs.push(['C', a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy, a[4] + ox, a[5] + oy])
        nextC = [a[2] + ox, a[3] + oy]
        x = a[4] + ox
        y = a[5] + oy
        break
      case 'S': {
        const c1 = lastC ? [2 * x - lastC[0], 2 * y - lastC[1]] : [x, y]
        segs.push(['C', c1[0], c1[1], a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy])
        nextC = [a[0] + ox, a[1] + oy]
        x = a[2] + ox
        y = a[3] + oy
        break
      }
      case 'Q':
      case 'T': {
        const q = up === 'Q' ? [a[0] + ox, a[1] + oy] : lastQ ? [2 * x - lastQ[0], 2 * y - lastQ[1]] : [x, y]
        const e = up === 'Q' ? [a[2] + ox, a[3] + oy] : [a[0] + ox, a[1] + oy]
        segs.push(['C', x + (2 / 3) * (q[0] - x), y + (2 / 3) * (q[1] - y), e[0] + (2 / 3) * (q[0] - e[0]), e[1] + (2 / 3) * (q[1] - e[1]), e[0], e[1]])
        nextQ = q
        x = e[0]
        y = e[1]
        break
      }
      case 'A': {
        const ex = a[5] + ox
        const ey = a[6] + oy
        segs.push(...arcToCubics(x, y, a[0], a[1], a[2], a[3], a[4], ex, ey))
        x = ex
        y = ey
        break
      }
      case 'Z':
        segs.push(['Z'])
        x = sx
        y = sy
        break
    }
    lastC = nextC
    lastQ = nextQ
  }
  return segs
}

export const circlePath = (cx, cy, r) => parsePath(`M${cx - r} ${cy}A${r} ${r} 0 1 0 ${cx + r} ${cy}A${r} ${r} 0 1 0 ${cx - r} ${cy}Z`)

export function mapPath(segs, f) {
  return segs.map((s) => {
    if (s[0] === 'Z') return s
    const out = [s[0]]
    for (let i = 1; i < s.length; i += 2) {
      const [px, py] = f(s[i], s[i + 1])
      out.push(px, py)
    }
    return out
  })
}

/** The bounding box of the path's points (control points included: a tight enough box for an icon). */
export function boundsOf(segs) {
  let x1 = Infinity
  let y1 = Infinity
  let x2 = -Infinity
  let y2 = -Infinity
  for (const s of segs) {
    for (let i = 1; i < s.length; i += 2) {
      x1 = Math.min(x1, s[i])
      x2 = Math.max(x2, s[i])
      y1 = Math.min(y1, s[i + 1])
      y2 = Math.max(y2, s[i + 1])
    }
  }
  return { x1, y1, x2, y2 }
}
