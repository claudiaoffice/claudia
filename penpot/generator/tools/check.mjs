// Reads a .penpot file back (it is a zip of JSON) and (1) checks the invariants Penpot's importer relies on for
// components, copies, variants and layers, (2) renders a board to a PNG, optionally under another theme, by resolving
// the tokens the shapes carry (appliedTokens), the way Penpot would when the theme changes.
//
//   node tools/check.mjs file.penpot                       checks
//   node tools/check.mjs file.penpot render "Front page" out.png [Scheme/Dark App/composes]
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright-core'
import { buildTokensFromDoc } from './tokens-from-doc.mjs'

const ROOT = '00000000-0000-0000-0000-000000000000'
const [file, cmd, pageName, out, ...themes] = process.argv.slice(2)

const dir = mkdtempSync(join(tmpdir(), 'penpot-'))
execFileSync('unzip', ['-q', file, '-d', dir])
const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8'))
const fid = manifest.files[0].id
const fdir = join(dir, 'files', fid)
const J = (p) => JSON.parse(readFileSync(p, 'utf8'))

const pages = {}
const shapes = new Map()
for (const f of readdirSync(join(fdir, 'pages')).filter((f) => f.endsWith('.json'))) {
  const page = J(join(fdir, 'pages', f))
  pages[page.name] = { ...page, shapes: [] }
  for (const sf of readdirSync(join(fdir, 'pages', page.id))) {
    const s = J(join(fdir, 'pages', page.id, sf))
    s.page = page.name
    shapes.set(s.id, s)
    pages[page.name].shapes.push(s)
  }
}
const components = new Map(readdirSync(join(fdir, 'components')).map((f) => J(join(fdir, 'components', f))).map((c) => [c.id, c]))
const tokensDoc = J(join(fdir, 'tokens.json'))

// --- checks ----------------------------------------------------------------------------------------------------

function check() {
  const problems = []
  const bad = (m) => problems.push(m)
  for (const s of shapes.values()) {
    if (s.id === ROOT) continue
    const where = `${s.page}/${s.name}`
    if (s.parentId !== ROOT) {
      const p = shapes.get(s.parentId)
      if (!p) bad(`${where}: parent ${s.parentId} is missing`)
      else if (!p.shapes?.includes(s.id)) bad(`${where}: not listed by its parent ${p.name}`)
    }
    for (const c of s.shapes ?? []) {
      const k = shapes.get(c)
      if (!k) bad(`${where}: child ${c} is missing`)
      else if (k.parentId !== s.id) bad(`${where}: child ${k.name} points to another parent`)
    }
    if (s.type !== 'frame' && s.shapes?.length) bad(`${where}: has children but is a ${s.type}`)
    if (s.componentId && !components.has(s.componentId)) bad(`${where}: component ${s.componentId} does not exist`)
    if (s.shapeRef) {
      const ref = shapes.get(s.shapeRef)
      if (!ref) bad(`${where}: shapeRef ${s.shapeRef} does not exist`)
      else {
        if (ref.type !== s.type) bad(`${where}: is a ${s.type} but its reference is a ${ref.type}`)
        const pRef = shapes.get(s.parentId)?.shapeRef
        const refParent = ref.parentId
        const parentIsCopy = shapes.get(s.parentId)?.shapeRef
        if (!s.componentRoot && !s.componentId && parentIsCopy && refParent !== pRef) bad(`${where}: reference ${ref.name} sits under another parent than the parent's reference`)
        if ((s.shapes?.length ?? 0) !== (ref.shapes?.length ?? 0) && !s.componentId) bad(`${where}: ${s.shapes?.length ?? 0} children but its reference has ${ref.shapes?.length ?? 0}`)
      }
    }
    if (s.componentRoot && s.shapeRef) {
      const comp = components.get(s.componentId)
      if (comp && comp.mainInstanceId !== s.shapeRef) bad(`${where}: a copy root must refer to the main of its component (${comp.name})`)
    }
  }
  for (const c of components.values()) {
    const m = shapes.get(c.mainInstanceId)
    if (!m) bad(`component ${c.name}: main ${c.mainInstanceId} is missing`)
    else {
      if (m.componentId !== c.id) bad(`component ${c.name}: its main points at ${m.componentId}`)
      if (!m.componentRoot) bad(`component ${c.name}: its main is not a component root`)
      if (pages[m.page].id !== c.mainInstancePage) bad(`component ${c.name}: main is on page ${m.page}, not the page it says`)
      if (c.variantId) {
        const v = shapes.get(c.variantId)
        if (!v?.isVariantContainer) bad(`component ${c.name}: variant container ${c.variantId} is not a variant container`)
        if (m.variantId !== c.variantId) bad(`component ${c.name}: main variantId differs`)
      }
    }
  }
  // Penpot gives a hugging board nothing for a child that fills that side (the front page card was 0px high)
  for (const s of shapes.values()) {
    if (s.type !== 'frame' || !s.layout) continue
    for (const [axis, key] of [['H', 'layoutItemHSizing'], ['V', 'layoutItemVSizing']]) {
      if ((s[key] ?? 'fix') !== 'auto') continue
      for (const k of s.shapes ?? []) {
        const c = shapes.get(k)
        if (c[key] === 'fill' && !c.layoutItemAbsolute) bad(`${s.page}/${s.name}: hugs its ${axis === 'H' ? 'width' : 'height'}, but ${c.name} fills it`)
      }
    }
  }
  // Penpot lays a flex board out from its last child to its first: along the main axis the stored places must grow
  // when the children are read from the end (a row that wraps is left out)
  for (const s of shapes.values()) {
    if (s.type !== 'frame' || !s.layout || s.layoutWrapType === 'wrap') continue
    const kids = [...(s.shapes ?? [])].reverse().map((k) => shapes.get(k)).filter((k) => !k.layoutItemAbsolute && !k.hidden)
    const key = s.layoutFlexDir.startsWith('row') ? 'x' : 'y'
    for (let i = 1; i < kids.length; i++) if (kids[i][key] < kids[i - 1][key] - 0.01) bad(`${s.page}/${s.name}: ${kids[i].name} is placed before ${kids[i - 1].name}, against Penpot's layout order`)
  }
  // Re-do the flex layout from the stored sizes, the way Penpot does, and compare with the stored places
  for (const s of shapes.values()) {
    if (s.type !== 'frame' || !s.layout || s.layoutWrapType === 'wrap') continue
    const row = s.layoutFlexDir.startsWith('row')
    const kids = [...(s.shapes ?? [])].reverse().map((k) => shapes.get(k)).filter((k) => !k.layoutItemAbsolute && !k.hidden)
    if (!kids.length) continue
    const P = s.layoutPadding
    const [pt, pr, pb, pl] = [P.p1, P.p2, P.p3, P.p4]
    const gap = row ? s.layoutGap.columnGap : s.layoutGap.rowGap
    const mg = (k) => k.layoutItemMargin ?? { m1: 0, m2: 0, m3: 0, m4: 0 }
    const mainOf = (k) => (row ? k.width : k.height)
    const mainM = (k) => (row ? mg(k).m2 + mg(k).m4 : mg(k).m1 + mg(k).m3)
    const crossOf = (k) => (row ? k.height : k.width)
    const crossM = (k) => (row ? mg(k).m1 + mg(k).m3 : mg(k).m2 + mg(k).m4)
    const innerMain = (row ? s.width - pl - pr : s.height - pt - pb)
    const innerCross = (row ? s.height - pt - pb : s.width - pl - pr)
    const used = kids.reduce((a, k) => a + mainOf(k) + mainM(k), 0) + gap * (kids.length - 1)
    // hugging: the board is as big as what it holds
    const hugKey = row ? 'layoutItemHSizing' : 'layoutItemVSizing'
    if (s[hugKey] === 'auto' && Math.abs(used - innerMain) > 0.6) bad(`${s.page}/${s.name}: hugs, is ${innerMain.toFixed(1)} along its direction but holds ${used.toFixed(1)}`)
    const crossKey = row ? 'layoutItemVSizing' : 'layoutItemHSizing'
    if (s[crossKey] === 'auto') {
      const need = Math.max(...kids.map((k) => crossOf(k) + crossM(k)))
      if (Math.abs(need - innerCross) > 0.6) bad(`${s.page}/${s.name}: hugs across, is ${innerCross.toFixed(1)} but holds ${need.toFixed(1)}`)
    }
    // fill: what the others leave, shared equally; across, the whole inner side
    const mainSizing = (k) => (row ? k.layoutItemHSizing : k.layoutItemVSizing)
    const crossSizing = (k) => (row ? k.layoutItemVSizing : k.layoutItemHSizing)
    const fillers = kids.filter((k) => mainSizing(k) === 'fill')
    if (fillers.length && s[hugKey] !== 'auto') {
      const share = (innerMain - (used - fillers.reduce((a, k) => a + mainOf(k), 0))) / fillers.length
      for (const k of fillers) if (Math.abs(mainOf(k) - share) > 0.6) bad(`${s.page}/${s.name}: ${k.name} fills ${mainOf(k).toFixed(1)}, the space left gives ${share.toFixed(1)}`)
    }
    for (const k of kids) if (crossSizing(k) === 'fill' && s[crossKey] !== 'auto' && Math.abs(crossOf(k) - (innerCross - crossM(k))) > 0.6) bad(`${s.page}/${s.name}: ${k.name} fills across ${crossOf(k).toFixed(1)}, the board gives ${(innerCross - crossM(k)).toFixed(1)}`)
    let pos = (row ? s.x + pl : s.y + pt) + (s.layoutJustifyContent === 'center' ? (innerMain - used) / 2 : s.layoutJustifyContent === 'end' ? innerMain - used : 0)
    const g = s.layoutJustifyContent === 'space-between' && kids.length > 1 ? gap + (innerMain - used + gap * (kids.length - 1) - gap * (kids.length - 1)) / (kids.length - 1) : gap
    for (const k of kids) {
      const m0 = row ? mg(k).m4 : mg(k).m1
      const here = row ? k.x : k.y
      if (s.layoutJustifyContent !== 'space-between' && Math.abs(here - (pos + m0)) > 0.6) bad(`${s.page}/${s.name}: ${k.name} is at ${here.toFixed(1)} along the layout, Penpot would put it at ${(pos + m0).toFixed(1)}`)
      pos += mainOf(k) + mainM(k) + g
      const c0 = (row ? s.y + pt : s.x + pl) + (row ? mg(k).m1 : mg(k).m4)
      const free = innerCross - crossOf(k) - crossM(k)
      const how = k.layoutItemAlignSelf ?? s.layoutAlignItems
      const want = c0 + (how === 'center' ? free / 2 : how === 'end' ? free : 0)
      const have = row ? k.y : k.x
      if (Math.abs(have - want) > 0.6) bad(`${s.page}/${s.name}: ${k.name} is at ${have.toFixed(1)} across, Penpot would put it at ${want.toFixed(1)}`)
    }
  }
  // tokens that shapes use must exist
  const known = new Set()
  const walk = (node, path) => {
    if (node && typeof node === 'object' && '$value' in node) known.add(path.join('.'))
    else if (node && typeof node === 'object') for (const [k, v] of Object.entries(node)) if (!k.startsWith('$')) walk(v, [...path, k])
  }
  for (const [set, body] of Object.entries(tokensDoc)) if (!set.startsWith('$')) walk(body, [])
  const used = new Map()
  for (const s of shapes.values()) for (const [attr, t] of Object.entries(s.appliedTokens ?? {})) {
    if (!known.has(t)) bad(`${s.page}/${s.name}: ${attr} uses token ${t}, which no set defines`)
    used.set(t, (used.get(t) ?? 0) + 1)
  }
  // colours that are not tokens
  const raw = new Map()
  for (const s of shapes.values()) {
    if (s.type === 'text') continue
    for (const f of s.fills ?? []) if (f.fillColor && !s.appliedTokens?.fill) raw.set(f.fillColor, (raw.get(f.fillColor) ?? 0) + 1)
    for (const f of s.strokes ?? []) if (f.strokeColor && !s.appliedTokens?.strokeColor) raw.set(`stroke ${f.strokeColor}`, (raw.get(`stroke ${f.strokeColor}`) ?? 0) + 1)
  }
  return { problems, used, raw, unused: [...known].filter((t) => !used.has(t)) }
}

// --- rendering -------------------------------------------------------------------------------------------------

const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
function parseColorText(raw) {
  let m = raw.match(/^#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?$/)
  if (m) return { hex: `#${m[1]}`, opacity: m[2] ? parseInt(m[2], 16) / 255 : 1 }
  m = raw.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/)
  if (m) return { hex: `#${[m[1], m[2], m[3]].map((n) => (+n).toString(16).padStart(2, '0')).join('')}`, opacity: m[4] === undefined ? 1 : +m[4] }
  throw new Error(`colour ${raw}`)
}

function renderer(resolver) {
  let uid = 0
  const defs = []
  const colorOf = (s, attr) => (resolver && s.appliedTokens?.[attr] ? parseColorText(resolver.value(s.appliedTokens[attr])) : null)
  const paint = (f, s) => {
    if (f.fillColorGradient) {
      const g = f.fillColorGradient
      const id = `g${uid++}`
      defs.push(`<linearGradient id="${id}" gradientUnits="objectBoundingBox" x1="${g.startX}" y1="${g.startY}" x2="${g.endX}" y2="${g.endY}">${g.stops.map((st) => `<stop offset="${st.offset}" stop-color="${st.color}" stop-opacity="${st.opacity}"/>`).join('')}</linearGradient>`)
      return `fill="url(#${id})"`
    }
    const t = colorOf(s, 'fill')
    return `fill="${t?.hex ?? f.fillColor}" fill-opacity="${t ? t.opacity : f.fillOpacity ?? 1}"`
  }
  const strokeAttrs = (s) => {
    const st = s.strokes?.[0]
    if (!st) return ''
    const t = colorOf(s, 'strokeColor')
    return ` stroke="${t?.hex ?? st.strokeColor}" stroke-opacity="${t ? t.opacity : st.strokeOpacity ?? 1}" stroke-width="${st.strokeWidth}"${st.strokeStyle === 'dashed' ? ` stroke-dasharray="${st.strokeDash ?? 4} ${st.strokeGap ?? 4}"` : ''}${st.strokeCapStart === 'round' ? ' stroke-linecap="round" stroke-linejoin="round"' : ''}`
  }
  const inset = (s) => {
    const st = s.strokes?.[0]
    const w = st && st.strokeAlignment === 'inner' ? st.strokeWidth : 0
    return { x: s.x + w / 2, y: s.y + w / 2, w: s.width - w, h: s.height - w, w2: w / 2 }
  }
  const filterOf = (s) => {
    if (!s.shadow?.length) return ''
    const id = `f${uid++}`
    const sh = s.shadow
      .map((d) => {
        const c = resolver && s.appliedTokens?.shadow ? resolver.value(s.appliedTokens.shadow) : null
        return `<feDropShadow dx="${d.offsetX}" dy="${d.offsetY}" stdDeviation="${d.blur / 2}" flood-color="${d.color.color}" flood-opacity="${d.color.opacity}"/>`
      })
      .join('')
    defs.push(`<filter id="${id}" x="-50%" y="-50%" width="200%" height="200%">${sh}</filter>`)
    return ` filter="url(#${id})"`
  }
  const pathD = (c) =>
    typeof c === 'string' ? c : c
      .map((k) => {
        const p = k.params
        if (k.command === 'move-to') return `M${p.x} ${p.y}`
        if (k.command === 'line-to') return `L${p.x} ${p.y}`
        if (k.command === 'curve-to') return `C${p.c1x} ${p.c1y} ${p.c2x} ${p.c2y} ${p.x} ${p.y}`
        return 'Z'
      })
      .join('')
  function draw(s) {
    if (s.hidden) return ''
    const op = s.opacity !== undefined && s.opacity !== 1 ? ` opacity="${s.opacity}"` : ''
    let body = ''
    const fills = s.fills ?? []
    if (s.type === 'frame' || s.type === 'rect') {
      const i = inset(s)
      const r = Math.max(0, Math.min(s.r1 ?? 0, s.width / 2, s.height / 2) - i.w2)
      const f = fills[0] ? paint(fills[0], s) : 'fill="none"'
      body += `<rect x="${i.x}" y="${i.y}" width="${i.w}" height="${i.h}" rx="${r}" ${f}${strokeAttrs(s)}${filterOf(s)}/>`
    } else if (s.type === 'circle') {
      const f = fills[0] ? paint(fills[0], s) : 'fill="none"'
      body += `<ellipse cx="${s.x + s.width / 2}" cy="${s.y + s.height / 2}" rx="${s.width / 2}" ry="${s.height / 2}" ${f}${strokeAttrs(s)}/>`
    } else if (s.type === 'path') {
      const f = fills[0] ? paint(fills[0], s) : 'fill="none"'
      body += `<path d="${pathD(s.content)}" ${f}${strokeAttrs(s)} fill-rule="evenodd"/>`
    } else if (s.type === 'text') {
      const para = s.content.children[0].children[0]
      const leaf = para.children[0]
      const t = colorOf(s, 'fill')
      const col = t ?? parseColorText(leaf.fills[0].fillColor + '')
      const colOpacity = t ? t.opacity : leaf.fills[0].fillOpacity
      // drawn the way Penpot's svg-text does it: <text x y> at the position-data line, dominant-baseline "ideographic"
      // (y is the bottom of the glyph box), textLength = the measured width, font-size a CSS length
      for (const l of s.positionData) {
        body += `<text x="${l.x}" y="${l.y}" dominant-baseline="ideographic" textLength="${l.width}" lengthAdjust="spacingAndGlyphs" style="font-family:'${l.fontFamily}';font-size:${l.fontSize};font-weight:${l.fontWeight};font-style:${l.fontStyle};letter-spacing:${l.letterSpacing};text-transform:${l.textTransform};text-decoration:${l.textDecoration};white-space:pre" fill="${col.hex}" fill-opacity="${colOpacity}">${esc(l.text)}</text>`
      }
    }
    if (s.type === 'frame') {
      const kids = (s.shapes ?? []).map((k) => draw(shapes.get(k))).join('')
      if (s.showContent === false) {
        const id = `c${uid++}`
        defs.push(`<clipPath id="${id}"><rect x="${s.x}" y="${s.y}" width="${s.width}" height="${s.height}" rx="${s.r1 ?? 0}"/></clipPath>`)
        body += `<g clip-path="url(#${id})">${kids}</g>`
      } else body += kids
    }
    return op ? `<g${op}>${body}</g>` : body
  }
  return { draw, defs }
}

async function render(page, resolver, png) {
  const root = pages[page].shapes.find((s) => s.parentId === ROOT && s.id !== ROOT && s.type === 'frame')
  const top = pages[page].shapes.filter((s) => s.parentId === ROOT && s.id !== ROOT)
  const x1 = Math.min(...top.map((s) => s.x))
  const y1 = Math.min(...top.map((s) => s.y))
  const x2 = Math.max(...top.map((s) => s.x + s.width))
  const y2 = Math.max(...top.map((s) => s.y + s.height))
  const r = renderer(resolver)
  const body = top.map((s) => r.draw(s)).join('')
  const w = Math.ceil(x2 - x1)
  const h = Math.ceil(y2 - y1)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="${x1} ${y1} ${w} ${h}"><defs>${r.defs.join('')}</defs>${body}</svg>`
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args: ['--no-sandbox'] })
  const p = await b.newPage({ viewport: { width: w, height: h } })
  await p.goto(process.env.CLAUDIA_URL ?? 'http://127.0.0.1:8765/')
  await p.waitForTimeout(500)
  await p.evaluate(async () => { for (const f of ['400 14px Inter', '500 14px Inter', '600 14px Inter', 'italic 400 14px Inter', '400 40px Fraunces', '400 14px "JetBrains Mono"', '400 34px Sacramento']) await document.fonts.load(f, 'abc') })
  await p.evaluate((markup) => { document.body.innerHTML = `<div style="position:absolute;left:0;top:0;background:#fff">${markup}</div>`; document.body.style.overflow = 'visible' }, svg)
  await p.waitForTimeout(300)
  await p.screenshot({ path: png, clip: { x: 0, y: 0, width: w, height: h } })
  await b.close()
  writeFileSync(png.replace(/\.png$/, '.svg'), svg)
  return { w, h }
}

if (!cmd) {
  const { problems, used, raw, unused } = check()
  console.log(`${shapes.size - 1} shapes, ${components.size} components, ${used.size} tokens used on shapes, ${unused.length} defined but not used on a shape`)
  console.log('colours that are not tokens:', Object.fromEntries(raw))
  if (problems.length) {
    console.log(`${problems.length} PROBLEMS`)
    for (const p of problems.slice(0, 60)) console.log(' -', p)
    process.exitCode = 1
  } else console.log('no structural problems found')
} else if (cmd === 'render') {
  const resolver = buildTokensFromDoc(tokensDoc, themes.length ? themes : null)
  console.log(await render(pageName, resolver, out))
}
