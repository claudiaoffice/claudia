import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { fromBase64, sha256Hex, utf8Decode, utf8Encode } from '../src/bytes'
import { canonicalJson } from '../src/canonical'
import { type DisplayItem, type GroupItem, isGradient, type PathItem, walk } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { decodePng } from '../src/image/png'
import { writePdf } from '../src/pdf/writer'
import { parsePath, parseTransform } from '../src/svg/geometry'
import { drawSvg, parseSvg, SvgError, svgFonts } from '../src/svg/render'
import { parseXml, XmlError } from '../src/svg/xml'
import { here, sha256 } from './helpers'
import { readPdf } from './pdf'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

const fixture = (name: string) => readFileSync(join(here, 'svg', name), 'utf8')
const draw = (svg: string, box = { x: 0, y: 0, w: 200000, h: 120000 }) => drawSvg(parseSvg(svg), box, { fonts, resolver })
const items = (g: GroupItem) => [...walk(g.items)]
const paths = (g: GroupItem) => items(g).filter((i): i is PathItem => i.kind === 'path')
const SVG = (body: string, attrs = 'viewBox="0 0 200 120"') => `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ${attrs}>${body}</svg>`

describe('bytes', () => {
  it('computes SHA-256 like everyone else', () => {
    for (const text of ['', 'abc', 'x'.repeat(55), 'y'.repeat(64), 'Grüße, ünïcode ✓'.repeat(20)]) expect(sha256Hex(utf8Encode(text))).toBe(sha256(text))
  })
  it('reads Base64 and UTF-8', () => {
    expect(utf8Decode(fromBase64('R3LDvMOfZSDinJM=')!)).toBe('Grüße ✓')
    expect(fromBase64('***')).toBeNull()
    expect(utf8Decode(Uint8Array.from([0xef, 0xbb, 0xbf, 0x61, 0xff, 0x62]))).toBe('a�b')
    expect(utf8Decode(utf8Encode('𝄞 music'))).toBe('𝄞 music')
  })
})

describe('the XML reader', () => {
  it('reads elements, attributes, text, entities and CDATA, with namespaces resolved', () => {
    const root = parseXml(
      '<?xml version="1.0"?><!-- c --><svg xmlns="http://www.w3.org/2000/svg" xmlns:x="http://www.w3.org/1999/xlink" xmlns:o="urn:other">' +
        '<use x:href="#a"/><text>a &amp; b &#x263A;<![CDATA[<raw>]]></text><o:thing/></svg>',
    )
    expect(root.name).toBe('svg')
    const [use, text, other] = root.children as { name: string; attrs: Map<string, string>; children: unknown[] }[]
    expect(use!.attrs.get('href')).toBe('#a')
    expect(text!.children.join('')).toBe('a & b ☺<raw>')
    expect(other!.name).toBe('{urn:other}thing')
  })
  it('refuses a DOCTYPE, bad nesting and undeclared prefixes', () => {
    expect(() => parseXml('<!DOCTYPE svg [<!ENTITY x "y">]><svg/>')).toThrow(XmlError)
    expect(() => parseXml('<svg><g></svg>')).toThrow(/does not close/)
    expect(() => parseXml('<svg><p:x/></svg>')).toThrow(/not declared/)
    expect(() => parseXml('<svg a=b/>')).toThrow(/quoted/)
    expect(() => parseXml('<svg>&bogus;</svg>')).toThrow(/entity/)
    expect(() => parseSvg('<html/>')).toThrow(SvgError)
  })
})

describe('SVG geometry', () => {
  it('reads every path command, relative ones and arcs with flags written together', () => {
    const d = parsePath('M10 10 h5 v5 H0 V0 l1 1 c1 0 2 1 2 2 s1 2 2 2 q1 1 2 0 t2 0 a5 5 0 015 5 z m1 1')
    expect(d[0]).toEqual(['M', 10, 10])
    expect(d[1]).toEqual(['L', 15, 10])
    expect(d[2]).toEqual(['L', 15, 15])
    expect(d.filter((s) => s[0] === 'C').length).toBeGreaterThanOrEqual(5)
    expect(d.at(-1)).toEqual(['M', 11, 11])
    expect(parsePath('M 0 0 L 10 x 20 20')).toEqual([['M', 0, 0]])
    expect(parsePath('L 1 1')).toEqual([])
  })
  it('reads transforms, and refuses what it cannot read', () => {
    expect(parseTransform('translate(10 20) scale(2)')).toEqual([2, 0, 0, 2, 10, 20])
    const r = parseTransform('rotate(90)')!
    expect(r.map((v) => Math.round(v * 1e9) / 1e9)).toEqual([0, 1, -1, 0, 0, 0])
    expect(parseTransform('matrix(1 2 3 4 5 6)')).toEqual([1, 2, 3, 4, 5, 6])
    expect(parseTransform('rotate(45) bogus(1)')).toBeNull()
  })
})

describe('drawSvg', () => {
  it('fits the viewBox into the box as preserveAspectRatio says, in whole mpt', () => {
    const out = draw(SVG('<rect x="10" y="10" width="20" height="10" fill="red"/>', 'viewBox="0 0 100 100"'), { x: 1000, y: 2000, w: 200000, h: 100000 })
    const [p] = paths(out.item)
    // meet: scale 1000 mpt per unit, centred across (50 pt free on either side)
    expect(p!.ops[0]).toEqual(['M', 1000 + 50000 + 10000, 2000 + 10000])
    expect(p!.fill).toEqual({ r: 255, g: 0, b: 0, a: 255 })
    const none = draw(SVG('<rect width="100" height="100" fill="blue"/>', 'viewBox="0 0 100 100" preserveAspectRatio="none"'), { x: 0, y: 0, w: 200000, h: 100000 })
    expect(paths(none.item)[0]!.ops[2]).toEqual(['L', 200000, 100000])
    expect(out.item.clip).toEqual({ x: 1000, y: 2000, w: 200000, h: 100000 })
  })

  it('draws strokes with their width, dashes, ends and corners scaled with the picture', () => {
    const out = draw(SVG('<path d="M0 0 L50 0" stroke="#000" stroke-width="2" stroke-dasharray="3 1 2" stroke-linecap="round" stroke-linejoin="bevel" fill="none"/>', 'viewBox="0 0 100 60"'), { x: 0, y: 0, w: 200000, h: 120000 })
    const [p] = paths(out.item)
    expect(p!.lineWidth).toBe(4000)
    expect(p!.dash).toEqual([6000, 2000, 4000, 6000, 2000, 4000])
    expect(p!.lineCap).toBe('round')
    expect(p!.lineJoin).toBe('bevel')
    expect(p!.fill).toBeNull()
  })

  it('applies style sheets, presentation attributes, style attributes and currentColor in their order', () => {
    const out = draw(SVG('<style>.a{fill:#00ff00} rect#b{fill:#0000ff} g rect{fill:red}</style><g color="#ff00ff"><rect class="a" width="1" height="1"/><rect id="b" class="a" width="1" height="1" fill="red"/><rect class="a" style="fill:currentColor" width="1" height="1"/></g>'))
    expect(paths(out.item).map((p) => p.fill)).toEqual([
      { r: 0, g: 255, b: 0, a: 255 },
      { r: 0, g: 0, b: 255, a: 255 },
      { r: 255, g: 0, b: 255, a: 255 },
    ])
    expect(out.notes).toContain('some of its style rules are not understood')
  })

  it('turns gradients into paints placed on the page, with their stops', () => {
    const out = draw(fixture('paint.svg'))
    const ps = paths(out.item)
    const lin = ps[0]!.fill!
    expect(isGradient(lin) && lin.kind).toBe('linear')
    if (!isGradient(lin)) return
    expect(lin.stops.map((s) => s.offset)).toEqual([0, 500000, 1000000])
    // objectBoundingBox: from the rectangle's top left to its bottom right, on the page
    const at = (x: number, y: number) => [Math.round((lin.matrix[0] * x + lin.matrix[2] * y) / 1e6 + lin.matrix[4]), Math.round((lin.matrix[1] * x + lin.matrix[3] * y) / 1e6 + lin.matrix[5])]
    expect(at(lin.coords[0]!, lin.coords[1]!)).toEqual([5000, 5000])
    expect(at(lin.coords[2]!, lin.coords[3]!)).toEqual([95000, 55000])
    const radial = ps.find((p) => p.fill && isGradient(p.fill) && p.fill.kind === 'radial')
    expect(radial).toBeDefined()
    const fade = ps.find((p) => p.fill && isGradient(p.fill) && p.fill.stops.at(-1)!.color.a === 0)
    expect(fade).toBeDefined()
    expect(ps.at(-1)!.fillRule).toBe('evenodd')
    expect(out.notes).toEqual([])
  })

  it('draws use, symbols, nested svg, clip paths and group opacity', () => {
    const out = draw(fixture('groups.svg'))
    const groups = items(out.item).filter((i): i is GroupItem => i.kind === 'group')
    expect(groups.some((g) => g.opacity === 128)).toBe(true)
    expect(groups.some((g) => g.clipPath && g.clipPath.ops.length > 4)).toBe(true)
    // the star of the symbol, scaled from its 10 × 10 viewBox to 40 × 40 at (80, 10)
    const star = paths(out.item).find((p) => p.fill && !isGradient(p.fill) && p.fill.r === 0xf4)
    expect(star!.ops[0]).toEqual(['M', 100000, 10000])
    // the rect with the class `soft` gets its opacity from the sheet: one path, half transparent through its group
    expect(groups.filter((g) => g.opacity !== undefined)).toHaveLength(2)
  })

  it('draws a picture made by pdftocairo (a formula): glyphs as paths used by reference', () => {
    const out = draw(fixture('formula.svg'), { x: 0, y: 0, w: 160000, h: 34000 })
    expect(paths(out.item).length).toBeGreaterThan(10)
    expect(out.notes).toEqual([])
  })

  it('sets text in the server fonts, anchored as asked, and names what it leaves out', () => {
    const svg = SVG('<text x="100" y="50" font-family="Inter" font-size="20" text-anchor="middle" fill="#123456">Mitte <tspan font-weight="bold">fett</tspan></text><text x="0" y="100"><textPath>x</textPath>y</text>')
    expect(svgFonts(parseSvg(svg), resolver).length).toBeGreaterThan(0)
    const out = draw(svg)
    const runs = items(out.item).filter((i) => i.kind === 'glyphs')
    expect(runs.map((r) => r.kind === 'glyphs' && r.text)).toEqual(['Mitte ', 'fett', 'y'])
    const [a, b] = runs as Extract<DisplayItem, { kind: 'glyphs' }>[]
    expect(a!.color).toEqual({ r: 0x12, g: 0x34, b: 0x56, a: 255 })
    expect(a!.size).toBe(20000)
    expect(a!.face.sha256).not.toBe(b!.face.sha256 + 'x')
    // centred: the two runs together are as far left of 100 pt as right of it
    const end = b!.x + b!.glyphs.at(-1)!.dx + 10000
    expect(Math.abs(100000 - a!.x - (end - 100000))).toBeLessThan(15000)
    expect(out.notes).toContain('text along a path is left out')
    const bare = drawSvg(parseSvg(svg), { x: 0, y: 0, w: 200000, h: 120000 })
    expect(bare.notes).toContain('its text is left out: no font to draw it with')
  })

  it('embeds pictures given as data URLs and names the others', () => {
    const png = readFileSync(join(here, 'images', 'rgb.png'))
    const href = `data:image/png;base64,${png.toString('base64')}`
    const out = draw(SVG(`<image x="10" y="10" width="40" height="40" href="${href}"/><image href="https://example.org/x.png" width="5" height="5"/><g filter="url(#f)" mask="url(#m)"><rect width="1" height="1" fill="url(#p)"/></g><pattern id="p"/>`))
    const imgs = items(out.item).filter((i) => i.kind === 'image')
    expect(imgs).toHaveLength(1)
    const id = imgs[0]!.kind === 'image' ? imgs[0]!.image : ''
    expect(out.images.get(id)).toEqual(new Uint8Array(png))
    expect(id).toBe(`svg-${sha256(png)}`)
    expect(out.notes).toEqual(expect.arrayContaining(['pictures linked from outside the file are left out', 'filters (blurs, shadows) are left out', 'masks are left out', 'pattern fills are left out']))
  })

  it('draws an SVG inside an SVG', () => {
    const inner = SVG('<circle cx="50" cy="50" r="50" fill="#00f"/>', 'viewBox="0 0 100 100"')
    const out = draw(SVG(`<image x="0" y="0" width="100" height="100" href="data:image/svg+xml;base64,${Buffer.from(inner).toString('base64')}"/>`))
    expect(paths(out.item)[0]!.fill).toEqual({ r: 0, g: 0, b: 255, a: 255 })
  })

  it('skips what is hidden or broken, and never loops', () => {
    const out = draw(SVG('<rect width="5" height="5" display="none"/><rect width="5" height="5" transform="bogus"/><g id="loop"><use href="#loop"/></g><rect width="0" height="5"/><switch><rect width="3" height="3"/><rect width="4" height="4"/></switch>'))
    expect(paths(out.item)).toHaveLength(1)
  })

  it('gives the same display list every time', () => {
    for (const name of ['shapes.svg', 'paint.svg', 'groups.svg', 'formula.svg']) {
      const a = canonicalJson(draw(fixture(name)).item)
      const b = canonicalJson(draw(fixture(name)).item)
      expect(a).toBe(b)
    }
  })
})

describe('SVG to PDF', () => {
  const pdfOf = (name: string, w: number, h: number) => {
    const out = draw(fixture(name), { x: 0, y: 0, w, h })
    return writePdf([{ width: w, height: h, items: [out.item] }], fonts, (id) => out.images.get(id), { title: name })
  }

  it('writes gradients, soft masks, clip paths and transparency groups that pdf.js reads', async () => {
    for (const name of ['shapes.svg', 'paint.svg', 'groups.svg', 'formula.svg']) {
      const pdf = pdfOf(name, 200000, 120000)
      const read = await readPdf(pdf)
      expect(read.pages).toHaveLength(1)
      expect(sha256(pdf)).toBe(sha256(pdfOf(name, 200000, 120000)))
    }
    const text = Buffer.from(pdfOf('paint.svg', 200000, 120000)).toString('latin1')
    expect(text).toContain('/ShadingType 2')
    expect(text).toContain('/ShadingType 3')
    expect(text).toContain('/SMask')
    const groups = Buffer.from(writePdf([{ width: 200000, height: 120000, items: [draw(fixture('groups.svg')).item] }], fonts, () => undefined, { title: 'g' }, { compress: false })).toString('latin1')
    expect(groups).toContain('/S /Transparency')
    expect(groups).toMatch(/ W n/)
  })

  // A browser-grade renderer (librsvg) draws the SVG, poppler draws our PDF of it: the two pictures must agree.
  const tools = (() => {
    try {
      execFileSync('rsvg-convert', ['--version'])
      execFileSync('pdftoppm', ['-v'], { stdio: 'ignore' })
      return true
    } catch {
      return false
    }
  })()
  it.skipIf(!tools)('looks like librsvg draws the same SVG', () => {
    const dir = mkdtempSync(join(tmpdir(), 'svgcmp-'))
    for (const name of ['shapes.svg', 'paint.svg', 'groups.svg', 'formula.svg']) {
      const svg = fixture(name)
      const [, , vw, vh] = /viewBox="([^"]+)"/.exec(svg)![1]!.split(/\s+/).map(Number) as number[]
      const scale = 3
      writeFileSync(join(dir, 'a.pdf'), pdfOf(name, vw! * 1000, vh! * 1000))
      execFileSync('pdftoppm', ['-png', '-r', String(72 * scale), '-singlefile', join(dir, 'a.pdf'), join(dir, 'ours')])
      execFileSync('rsvg-convert', ['-w', String(vw! * scale), '-h', String(vh! * scale), '-b', 'white', '-o', join(dir, 'theirs.png'), join(here, 'svg', name)])
      const ours = decodePng(readFileSync(join(dir, 'ours.png')))
      const theirs = decodePng(readFileSync(join(dir, 'theirs.png')))
      expect([ours.width, ours.height]).toEqual([theirs.width, theirs.height])
      let far = 0
      let sum = 0
      for (let i = 0; i < ours.rgb.length; i++) {
        const d = Math.abs(ours.rgb[i]! - theirs.rgb[i]!)
        sum += d
        if (d > 96) far++
      }
      const pixels = ours.width * ours.height * 3
      // edges are smoothed differently; the pictures themselves must be the same
      expect(sum / pixels, `${name}: mean difference`).toBeLessThan(4)
      expect(far / pixels, `${name}: share of very different values`).toBeLessThan(0.015)
    }
  })
})
