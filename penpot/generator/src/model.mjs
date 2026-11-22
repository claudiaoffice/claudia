// A small design model: nodes (boards, text, rectangles, circles, vector paths), a flex layout engine that places
// them the way Penpot's flex layout does, components with variants, and instances of components.
//
// Values that are tokens are written as token names ('space.8', 'color.surface'); they are resolved against the
// active themes and remembered as `appliedTokens` of the Penpot shape, so a theme switch in Penpot recolours it.
import { createHash } from 'node:crypto'
import { TYPE, fontSpecOf } from './tokens.mjs'

export const R = (n) => Math.round(n * 1000) / 1000

let CTX = null
export function configure(ctx) {
  CTX = ctx
  return CTX
}
const ctx = () => {
  if (!CTX) throw new Error('model: configure({ tokens, measurer, fileKey }) first')
  return CTX
}

// --- ids: stable across runs, so a regenerated file keeps the identity of its shapes ---------------------------

let serial = 0
export function newId(label = '') {
  const h = createHash('sha1').update(`${ctx().fileKey}/${++serial}/${label}`).digest()
  h[6] = (h[6] & 0x0f) | 0x50
  h[8] = (h[8] & 0x3f) | 0x80
  const x = h.subarray(0, 16).toString('hex')
  return `${x.slice(0, 8)}-${x.slice(8, 12)}-${x.slice(12, 16)}-${x.slice(16, 20)}-${x.slice(20, 32)}`
}

// --- values ----------------------------------------------------------------------------------------------------

const isTok = (v) => typeof v === 'string' && /^[a-z][\w-]*(\.[\w-]+)+$/.test(v)
/** A number, or a token name that resolves to one: { n, tok }. */
export function num(v) {
  if (v === undefined || v === null) return { n: 0 }
  if (typeof v === 'number') return { n: v }
  if (isTok(v)) return { n: parseFloat(ctx().tokens.value(v)), tok: v }
  throw new Error(`model: "${v}" is neither a number nor a token name`)
}
const color = (tokenName) => {
  const raw = ctx().tokens.value(tokenName)
  return parseColorText(raw)
}
/** '#RRGGBB', '#RRGGBBAA' or 'rgba(r, g, b, a)' -> { hex, opacity } */
export function parseColorText(raw) {
  let m = raw.match(/^#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?$/)
  if (m) return { hex: `#${m[1].toUpperCase()}`, opacity: m[2] ? R(parseInt(m[2], 16) / 255) : 1 }
  m = raw.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/)
  if (m) return { hex: `#${[m[1], m[2], m[3]].map((n) => (+n).toString(16).padStart(2, '0')).join('').toUpperCase()}`, opacity: m[4] === undefined ? 1 : +m[4] }
  throw new Error(`model: cannot read the colour "${raw}"`)
}

// --- nodes -----------------------------------------------------------------------------------------------------

export class Node {
  constructor(kind, name, props, children = []) {
    Object.assign(this, props)
    this.kind = kind
    this.name = name
    this.id = newId(name)
    this.children = children.flat().filter(Boolean)
  }
}

/** A board. layout: 'row' | 'column' makes it a flex layout; without one its children sit at their own x/y. */
export const board = (name, o = {}, ...children) => new Node('board', name, { w: 'auto', h: 'auto', ...o }, children)
export const rect = (name, o = {}) => new Node('rect', name, o)
export const circle = (name, o = {}) => new Node('circle', name, o)
/** A vector path; `segs` are absolute M/L/C/Z segments in the node's own coordinates (0,0 .. w,h). */
export const path = (name, segs, o = {}) => new Node('path', name, { segs, ...o })
/** Text: style names a key of TYPE; color a colour token; w 'auto' (one line) | 'fill' | a width. */
export const text = (name, content, o = {}) => new Node('text', name, { content, style: 'body', color: 'color.text', w: 'auto', h: 'auto', align: 'left', ...o })

// --- measuring text --------------------------------------------------------------------------------------------

async function measureText(n, width) {
  const spec = { ...fontSpecOf(n.style), ...(n.italic ? { style: 'italic' } : {}) }
  const m = await ctx().measurer.text(spec, n.content, width)
  const lh = spec.lh === 'normal' ? m.lineHeight : spec.lh * spec.size
  // the height of the glyph box (the font's own line height), which Penpot keeps as `height` of a position-data line
  const ch = spec.lh === 'normal' ? m.lineHeight : await ctx().measurer.lineHeight({ ...spec, lh: 'normal' })
  return { spec, lines: m.lines, lh, ch, natural: m.width }
}

// --- layout ----------------------------------------------------------------------------------------------------

const pad4 = (p) => {
  if (p === undefined) return [0, 0, 0, 0].map(num)
  const a = Array.isArray(p) ? p : [p]
  const four = a.length === 1 ? [a[0], a[0], a[0], a[0]] : a.length === 2 ? [a[0], a[1], a[0], a[1]] : a.length === 4 ? a : null
  if (!four) throw new Error('model: pad takes 1, 2 or 4 values')
  return four.map(num)
}
const isFlow = (n) => n.layout === 'row' || n.layout === 'column'
const inFlow = (c) => !c.hidden && !c.abs

/** The margins of a node as numbers [top, right, bottom, left] (and their tokens, for the shape). */
export function margins(c) {
  const m = c.m
  if (m === undefined) return [0, 0, 0, 0].map(num)
  const a = Array.isArray(m) ? m : [m]
  const four = a.length === 1 ? [a[0], a[0], a[0], a[0]] : a.length === 2 ? [a[0], a[1], a[0], a[1]] : a
  if (four.length !== 4) throw new Error('model: margin takes 1, 2 or 4 values')
  return four.map(num)
}

/** The box a node takes: { n, w, h, kids: [{ box, dx, dy }] }. aw/ah: the width/height a 'fill' node gets. */
async function size(n, aw = null, ah = null) {
  const fixedOr = (v, fill) => (typeof v === 'number' || isTok(v) ? num(v).n : v === 'fill' && fill !== null ? fill : null)
  if (n.kind === 'text') {
    const wAvail = n.w === 'auto' ? null : fixedOr(n.w, aw)
    const m = await measureText(n, wAvail)
    const lines = m.lines.length
    // Penpot lays a text out in the browser and keeps whole pixels, rounded up (a 14px line of 1.45 is 21, not 20.3)
    const w = wAvail ?? Math.ceil(m.natural)
    const h = n.h === 'auto' ? Math.ceil(lines * m.lh) : fixedOr(n.h, ah) ?? Math.ceil(lines * m.lh)
    return { n, w, h, m, kids: [] }
  }
  if (n.kind !== 'board') {
    const w = fixedOr(n.w, aw)
    const h = fixedOr(n.h, ah)
    if (w === null || h === null) throw new Error(`model: ${n.kind} "${n.name}" needs a width and a height`)
    return { n, w, h, kids: [] }
  }

  const w0 = fixedOr(n.w, aw) // null: hug
  const h0 = fixedOr(n.h, ah)
  // children that sit outside the flow (absolute, hidden): at their own x/y; 'fill' means this board
  const outside = async (w, h, kids, ox = 0, oy = 0) => {
    for (const c of n.children) {
      if (!(c.hidden || c.abs)) continue
      kids.push({ box: await size(c, w, h), dx: c.x === undefined ? ox : num(c.x).n, dy: c.y === undefined ? oy : num(c.y).n })
    }
  }
  if (!isFlow(n)) {
    // children at their own places; a 'fill' child fills this board
    const kids = []
    for (const c of n.children) if (!c.hidden) kids.push({ box: await size(c, w0, h0), dx: num(c.x).n, dy: num(c.y).n })
    const w = w0 ?? Math.max(0, ...kids.map((k) => k.dx + k.box.w))
    const h = h0 ?? Math.max(0, ...kids.map((k) => k.dy + k.box.h))
    await outside(w, h, kids)
    return { n, w, h, kids }
  }

  const row = n.layout === 'row'
  const [pt, pr, pb, pl] = pad4(n.pad).map((p) => p.n)
  const gap = num(n.gap).n
  const innerW = w0 === null ? null : w0 - pl - pr
  const innerH = h0 === null ? null : h0 - pt - pb
  const innerMain = row ? innerW : innerH
  const innerCross = row ? innerH : innerW
  const main = (b) => (row ? b.w : b.h)
  const cross = (b) => (row ? b.h : b.w)
  const mainMode = (c) => (row ? c.w : c.h)
  const crossMode = (c) => (row ? c.h : c.w)
  const mg = (c) => margins(c).map((x) => x.n)
  const mMain = (c) => (row ? mg(c)[1] + mg(c)[3] : mg(c)[0] + mg(c)[2])
  const mCross = (c) => (row ? mg(c)[0] + mg(c)[2] : mg(c)[1] + mg(c)[3])
  const mStart = (c) => (row ? mg(c)[3] : mg(c)[0])
  const mCrossStart = (c) => (row ? mg(c)[0] : mg(c)[3])
  const asBox = (c, mainAllot, crossAllot) => (row ? size(c, mainAllot, crossAllot) : size(c, crossAllot, mainAllot))

  const flow = n.children.filter(inFlow)
  const crossFor = (c) => (crossMode(c) === 'fill' && innerCross !== null ? innerCross - mCross(c) : null)

  // 1. children that do not share the free space
  const boxes = new Array(flow.length)
  let used = 0
  let fills = 0
  let fillMargins = 0
  for (const [i, c] of flow.entries()) {
    if (mainMode(c) === 'fill' && innerMain !== null) {
      fills++
      fillMargins += mMain(c)
      continue
    }
    boxes[i] = await asBox(c, null, crossFor(c))
    used += main(boxes[i]) + mMain(c)
  }
  // 2. the free space goes to the fill children, equally
  const gaps = gap * Math.max(0, flow.length - 1)
  const share = fills ? Math.max(0, innerMain - used - gaps - fillMargins) / fills : 0
  for (const [i, c] of flow.entries()) if (!boxes[i]) boxes[i] = await asBox(c, share, crossFor(c))
  const om = (i) => main(boxes[i]) + mMain(flow[i]) // what a child takes along the main axis
  const oc = (i) => cross(boxes[i]) + mCross(flow[i])

  // 3. lines (only a row may wrap, and only with a known width)
  const lines = [[]]
  let lineMain = 0
  for (const [i] of flow.entries()) {
    if (n.wrap && row && innerW !== null && lines.at(-1).length && lineMain + gap + om(i) > innerW) {
      lines.push([])
      lineMain = 0
    }
    lines.at(-1).push(i)
    lineMain += (lines.at(-1).length > 1 ? gap : 0) + om(i)
  }
  const lineMainSum = (idx) => idx.reduce((s, i) => s + om(i), 0) + gap * Math.max(0, idx.length - 1)
  const lineCross = (idx) => Math.max(0, ...idx.map(oc))

  const hugMain = Math.max(...lines.map(lineMainSum), 0)
  const hugCross = lines.reduce((s, l) => s + lineCross(l), 0) + (n.wrap ? gap : 0) * Math.max(0, lines.length - 1)
  const mainTotal = innerMain ?? hugMain
  const crossTotal = innerCross ?? hugCross
  const w = w0 ?? (row ? mainTotal : crossTotal) + pl + pr
  const h = h0 ?? (row ? crossTotal : mainTotal) + pt + pb

  // 4. places inside the padding
  const kids = []
  let crossPos = 0
  for (const idx of lines) {
    const lc = lines.length > 1 ? lineCross(idx) : crossTotal
    const slack = Math.max(0, mainTotal - lineMainSum(idx))
    let pos = 0
    let g = gap
    if (n.justify === 'center') pos = slack / 2
    else if (n.justify === 'end') pos = slack
    else if (n.justify === 'space-between' && idx.length > 1) g = gap + slack / (idx.length - 1)
    for (const i of idx) {
      const c = flow[i]
      let box = boxes[i]
      // a child that fills the cross axis of a hugging board takes what the tallest sibling made it
      if (crossMode(c) === 'fill' && lines.length === 1 && Math.abs(cross(box) - (crossTotal - mCross(c))) > 0.001) box = await asBox(c, main(box), crossTotal - mCross(c))
      const free = lc - cross(box) - mCross(c)
      const how = c.self ?? n.align
      const off = how === 'center' ? free / 2 : how === 'end' ? free : 0
      const m0 = mStart(c)
      const mc = mCrossStart(c)
      kids.push({ box, dx: pl + (row ? pos + m0 : crossPos + mc + off), dy: pt + (row ? crossPos + mc + off : pos + m0) })
      pos += om(i) + g
    }
    crossPos += lc + gap
  }
  await outside(w, h, kids, pl, pt)
  return { n, w, h, kids }
}

function place(box, x, y) {
  box.n.rect = { x: R(x), y: R(y), w: R(box.w), h: R(box.h) }
  box.n.laid = box
  for (const k of box.kids) place(k.box, x + k.dx, y + k.dy)
}

/** The box a node would take with `aw`/`ah` available to its 'fill' sides, without placing it. */
export const measureBox = (n, aw = null, ah = null) => size(n, aw, ah)

/** Lays a tree out with its top-left corner at (x, y). */
export async function layout(root, x = 0, y = 0) {
  place(await size(root), x, y)
  return root.rect
}

// --- components and instances ----------------------------------------------------------------------------------

/** Marks a board as the main instance of a component. */
export function component(node, { name, path = '', variant } = {}) {
  node.main = { componentId: newId(`component ${name}`), name, path, variant }
  return node
}

/**
 * A variant set: a container board holding one main instance per combination of the properties.
 * `props` is { Kind: ['primary', 'default'], Size: [...] }, `make(values)` builds a variant's board.
 */
export function variantSet(name, path, props, make, o = {}) {
  const names = Object.keys(props)
  const combos = names.reduce((acc, p) => acc.flatMap((a) => props[p].map((v) => [...a, [p, v]])), [[]])
  const container = board(name, { w: o.w ?? 1200, h: 'auto', layout: 'row', wrap: true, gap: 20, pad: 30, radius: 20, stroke: { raw: '#BB97D8', width: 2 }, variantContainer: true })
  const variants = {}
  const containerId = container.id
  for (const combo of combos) {
    const values = Object.fromEntries(combo)
    const node = make(values)
    node.name = name
    component(node, { name, path, variant: { id: containerId, properties: combo.map(([n, v]) => ({ name: n, value: v })), name: combo.map(([, v]) => v).join(', ') } })
    variants[combo.map(([, v]) => v).join(', ')] = node
    container.children.push(node)
  }
  container.variants = variants
  container.propNames = names
  return container
}

/** The main board of one variant of a set: pick(set, { Kind: 'primary', Size: 'small' }). */
export function pick(set, values) {
  const key = set.propNames.map((p) => values[p]).join(', ')
  const found = set.variants[key]
  if (!found) throw new Error(`model: "${set.name}" has no variant ${key}`)
  return found
}

/** A copy of a component's main board, with what an instance may change: text, sizes, visibility. */
export function instance(main, o = {}) {
  const info = main.main
  if (!info) throw new Error(`model: "${main.name}" is not a component main`)
  const copy = (orig, root) => {
    const n = Object.assign(Object.create(Object.getPrototypeOf(orig)), orig)
    n.id = newId(`copy ${orig.name}`)
    n.refId = orig.id
    n.children = orig.children.map((c) => copy(c, false))
    n.touched = new Set()
    delete n.rect
    delete n.laid
    if (root) {
      n.copy = { componentId: info.componentId, root: !o.nested }
      delete n.main
      delete n.variantContainer
    }
    return n
  }
  const n = copy(main, true)
  const mode = (v) => (v === 'fill' || v === 'auto' ? v : 'fix')
  for (const [k, sizing] of [['w', 'layout-item-h-sizing'], ['h', 'layout-item-v-sizing']]) {
    if (o[k] === undefined) continue
    if (mode(o[k]) !== mode(n[k])) n.touched.add(sizing)
    if (mode(o[k]) === 'fix') n.touched.add('geometry-group')
    n[k] = o[k]
  }
  for (const k of ['x', 'y', 'abs', 'self']) if (o[k] !== undefined) n[k] = o[k]
  if (o.abs !== undefined) n.touched.add('layout-item-absolute')
  if (o.m !== undefined) {
    n.m = o.m
    n.touched.add('layout-item-margin')
  }
  const find = (node, name) => {
    for (const c of node.children) {
      if (c.name === name) return c
      const f = find(c, name)
      if (f) return f
    }
    return null
  }
  for (const [name, edit] of Object.entries(o.edit ?? {})) {
    const t = find(n, name)
    if (!t) throw new Error(`model: "${main.name}" has no layer "${name}" to change`)
    if (edit.content !== undefined) {
      t.content = edit.content
      t.touched.add('content-group')
    }
    if (edit.hidden !== undefined) {
      t.hidden = edit.hidden
      t.touched.add('visibility-group')
    }
    if (edit.w !== undefined) t.w = edit.w
  }
  return n
}

// --- emitting --------------------------------------------------------------------------------------------------

const fill1 = (hex, opacity = 1) => ({ fillColor: hex, fillOpacity: opacity })

/** The fills of a node: a colour token, { raw: '#hex' }, or { gradient }. Returns [fills, appliedTokens key]. */
function fillsOf(f, rect) {
  if (!f) return { fills: [] }
  if (f.lazy) return { fills: [{ fillColorGradient: f.lazy(rect) }] }
  if (typeof f === 'string') {
    const c = color(f)
    return { fills: [fill1(c.hex, c.opacity)], token: f }
  }
  if (f.raw) return { fills: [fill1(f.raw, f.opacity ?? 1)] }
  if (f.gradient) return { fills: [{ fillColorGradient: f.gradient }] }
  throw new Error('model: unknown fill')
}

function strokeOf(s) {
  if (!s) return { strokes: [] }
  const c = s.raw ? { hex: s.raw, opacity: 1 } : color(s.color)
  const width = num(s.width)
  return {
    strokes: [
      {
        strokeColor: c.hex,
        strokeOpacity: c.opacity,
        strokeStyle: s.style ?? 'solid',
        strokeWidth: width.n,
        strokeAlignment: s.align ?? 'inner',
        ...(s.style === 'dashed' ? { strokeDash: s.dash ?? 4, strokeGap: s.dashGap ?? 4 } : {}),
        ...(s.cap === 'round' ? { strokeCapStart: 'round', strokeCapEnd: 'round' } : {}),
      },
    ],
    colorToken: s.color && !s.raw ? s.color : undefined,
    widthToken: width.tok,
  }
}

function geometry(n) {
  const { x, y, w, h } = n.rect
  return { x, y, width: Math.max(w, 0.01), height: Math.max(h, 0.01) }
}

function commonParams(n, parent) {
  const tokens = {}
  const p = { id: n.id, name: n.name, ...geometry(n) }
  const f = fillsOf(n.fill, n.rect)
  p.fills = f.fills
  if (f.token) tokens.fill = f.token
  const s = strokeOf(n.stroke)
  p.strokes = s.strokes
  if (s.colorToken) tokens.strokeColor = s.colorToken
  if (s.widthToken) for (const side of ['Top', 'Right', 'Bottom', 'Left']) tokens[`strokeWidth${side}`] = s.widthToken
  if (n.radius !== undefined && (n.kind === 'board' || n.kind === 'rect')) {
    const rs = Array.isArray(n.radius) ? n.radius : [n.radius, n.radius, n.radius, n.radius]
    rs.map(num).forEach((r, i) => {
      p[`r${i + 1}`] = r.n
      if (r.tok) tokens[`r${i + 1}`] = r.tok
    })
  }
  if (n.opacity !== undefined) {
    const o = num(n.opacity)
    p.opacity = o.n
    if (o.tok) tokens.opacity = o.tok
  }
  if (n.shadow) {
    const sh = ctx().tokens.value(n.shadow)
    p.shadow = sh.map((s1) => {
      const c = parseColorText(s1.color)
      return { id: newId('shadow'), style: s1.inset ? 'inner-shadow' : 'drop-shadow', offsetX: +s1.offsetX, offsetY: +s1.offsetY, blur: +s1.blur, spread: +s1.spread, hidden: false, color: { color: c.hex, opacity: c.opacity } }
    })
    tokens.shadow = n.shadow
  }
  if (n.hidden) p.hidden = true
  if (parent && isFlow(parent)) {
    const sizing = (v) => (v === 'fill' ? 'fill' : v === 'auto' ? 'auto' : 'fix')
    p.layoutItemHSizing = n.abs ? 'fix' : sizing(n.w)
    p.layoutItemVSizing = n.abs ? 'fix' : sizing(n.h)
    if (n.abs) p.layoutItemAbsolute = true
    if (n.self) p.layoutItemAlignSelf = n.self
    const mg = margins(n)
    if (mg.some((x) => x.n)) {
      p.layoutItemMargin = { m1: mg[0].n, m2: mg[1].n, m3: mg[2].n, m4: mg[3].n }
      p.layoutItemMarginType = 'multiple'
      mg.forEach((x, i) => {
        if (x.tok) tokens[`m${i + 1}`] = x.tok
      })
    }
  }
  // a component's copy: where it points, and what the person changed
  if (n.refId) p.shapeRef = n.refId
  if (n.copy) {
    p.componentId = n.copy.componentId
    p.componentFile = ctx().fileId
    if (n.copy.root) p.componentRoot = true
  }
  if (n.touched?.size) p.touched = [...n.touched]
  return { p, tokens }
}

function boardParams(n, parent) {
  const { p, tokens } = commonParams(n, parent)
  p.showContent = !n.clip
  if (isFlow(n)) {
    const [pt, pr, pb, pl] = pad4(n.pad)
    const gap = num(n.gap)
    p.layout = 'flex'
    p.layoutFlexDir = n.layout
    p.layoutGap = { rowGap: gap.n, columnGap: gap.n }
    p.layoutGapType = 'multiple'
    p.layoutPadding = { p1: pt.n, p2: pr.n, p3: pb.n, p4: pl.n }
    p.layoutPaddingType = 'multiple'
    p.layoutWrapType = n.wrap ? 'wrap' : 'nowrap'
    p.layoutAlignItems = n.align ?? 'start'
    p.layoutJustifyContent = n.justify ?? 'start'
    p.layoutAlignContent = 'start'
    if (n.gap !== undefined && num(n.gap).tok) tokens.rowGap = tokens.columnGap = num(n.gap).tok
    ;[pt, pr, pb, pl].forEach((q, i) => {
      if (q.tok) tokens[`p${i + 1}`] = q.tok
    })
    // a board's own sizing: fixed, or hugging its content
    if (!parent || !isFlow(parent)) {
      p.layoutItemHSizing = n.w === 'auto' ? 'auto' : 'fix'
      p.layoutItemVSizing = n.h === 'auto' ? 'auto' : 'fix'
    }
  }
  if (n.variantContainer) p.isVariantContainer = true
  if (n.main?.variant) {
    p.variantId = n.main.variant.id
    p.variantName = n.main.variant.name
  }
  if (typeof n.w === 'string' && isTok(n.w)) tokens.width = n.w
  if (typeof n.h === 'string' && isTok(n.h)) tokens.height = n.h
  if (Object.keys(tokens).length) p.appliedTokens = tokens
  return p
}

function textParams(n, parent) {
  const { p, tokens } = commonParams(n, parent)
  const { box } = { box: n.laid }
  const m = box.m
  const spec = m.spec
  const c = color(n.color)
  const weight = String(spec.weight)
  const italic = spec.style === 'italic'
  const variant = (weight === '400' ? '' : weight) + (italic ? 'italic' : '')
  const font = { fontId: spec.fontId, fontFamily: spec.family, fontVariantId: variant === '' ? 'regular' : variant === 'italic' ? 'italic' : variant, fontWeight: weight, fontStyle: spec.style }
  const lhFactor = Math.round((m.lh / spec.size) * 1000) / 1000
  const leaf = {
    text: n.content,
    ...font,
    fontSize: String(spec.size),
    textAlign: n.align,
    lineHeight: String(lhFactor),
    letterSpacing: String(spec.ls),
    textDecoration: n.underline ? 'underline' : 'none',
    textTransform: spec.transform,
    direction: 'ltr',
    fills: [fill1(c.hex, c.opacity)],
  }
  const { text: _t, ...para } = leaf
  p.content = { type: 'root', verticalAlign: 'top', children: [{ type: 'paragraph-set', children: [{ type: 'paragraph', ...para, children: [leaf] }] }] }
  p.fills = []
  const fixedWidth = n.w !== 'auto'
  p.growType = !fixedWidth ? 'auto-width' : n.h === 'auto' ? 'auto-height' : 'fixed'
  // Penpot draws a line as an SVG <text> at (x, y) with dominant-baseline "ideographic": y is the BOTTOM of the glyph box
  // (Safari: y - height, "hanging"), and font-size is a CSS length. So y = top of the line box + (lh - ch) / 2 + ch.
  const ch = m.ch
  p.positionData = m.lines.map((l, i) => {
    const lineW = l.w
    const dx = n.align === 'center' ? (n.rect.w - lineW) / 2 : n.align === 'right' ? n.rect.w - lineW : 0
    const y1 = (m.lh - ch) / 2
    return {
      x: R(n.rect.x + dx),
      y: R(n.rect.y + i * m.lh + y1 + ch),
      width: R(lineW),
      height: R(ch),
      x1: 0,
      y1: R(i * m.lh + y1),
      x2: R(lineW),
      y2: R(i * m.lh + y1 + ch),
      fills: leaf.fills,
      fontFamily: font.fontFamily,
      fontSize: `${leaf.fontSize}px`,
      fontStyle: font.fontStyle,
      fontWeight: font.fontWeight,
      letterSpacing: spec.ls ? `${spec.ls}px` : 'normal',
      direction: 'ltr',
      text: l.text,
      textDecoration: leaf.textDecoration,
      textTransform: leaf.textTransform,
    }
  })
  tokens.typography = `type.${n.style}`
  tokens.fill = n.color
  p.appliedTokens = tokens
  return p
}

function pathContent(n) {
  const { x, y } = n.rect
  const out = []
  for (const s of n.segs) {
    const at = (i) => R((s[i] ?? 0) + x)
    const aty = (i) => R((s[i] ?? 0) + y)
    if (s[0] === 'M') out.push({ command: 'move-to', params: { x: at(1), y: aty(2) } })
    else if (s[0] === 'L') out.push({ command: 'line-to', params: { x: at(1), y: aty(2) } })
    else if (s[0] === 'C') out.push({ command: 'curve-to', params: { x: at(5), y: aty(6), c1x: at(1), c1y: aty(2), c2x: at(3), c2y: aty(4) } })
    else out.push({ command: 'close-path', params: {} })
  }
  return out
}

/** Writes a laid out tree into a build context of @penpot/library. */
export function emit(c, n, parent = null) {
  if (n.hidden && !n.copy && !n.refId) {
    // hidden nodes are kept (they are layers), but take no room: they were laid out at zero size
  }
  if (n.kind === 'board') {
    c.addBoard(boardParams(n, parent))
    // Penpot lays a flex board out from its last child to its first (the layers panel lists them the way they read), so
    // the children go in reversed; what is outside the flow (absolute, hidden) keeps its place on top
    const order = isFlow(n) ? [...n.children.filter(inFlow).reverse(), ...n.children.filter((k) => !inFlow(k))] : n.children
    for (const k of order) emit(c, k, n)
    if (n.main) {
      c.addComponent({
        componentId: n.main.componentId,
        name: n.main.name,
        path: n.main.path,
        ...(n.main.variant ? { variantId: n.main.variant.id, variantProperties: n.main.variant.properties } : {}),
      })
    }
    c.closeBoard()
  } else if (n.kind === 'text') {
    c.addText(textParams(n, parent))
  } else if (n.kind === 'rect' || n.kind === 'circle') {
    const { p, tokens } = commonParams(n, parent)
    if (Object.keys(tokens).length) p.appliedTokens = tokens
    if (n.kind === 'rect') c.addRect(p)
    else c.addCircle(p)
  } else if (n.kind === 'path') {
    const { p, tokens } = commonParams(n, parent)
    p.content = pathContent(n)
    if (Object.keys(tokens).length) p.appliedTokens = tokens
    c.addPath(p)
  } else throw new Error(`model: cannot emit ${n.kind}`)
}

export { TYPE }
