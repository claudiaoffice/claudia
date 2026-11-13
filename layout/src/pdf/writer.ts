/**
 * The PDF writer: a display list in, the bytes of a PDF out. It makes no layout decision; every glyph is drawn at the
 * position the display list gives, so the PDF is the layout, and the same display list gives the same bytes in every
 * engine (no clock, no randomness, fflate's own deflate).
 *
 * Fonts are subset by HarfBuzz with their glyph ids kept and every variation axis pinned, and embedded as TrueType
 * CID fonts (CIDFontType2, Identity-H). Each glyph carries the text it stands for into a ToUnicode map, so text can
 * be searched and copied. Raster images are embedded as they are (JPEG) or decoded and deflated (PNG, GIF's first
 * frame, BMP), with an alpha mask when they have transparency. Decoding is the library's own, so the bytes are the
 * same in every engine.
 *
 * @module
 */
import { zlibSync } from 'fflate'
import { cosMillionths, sinMillionths } from '../display/angles'
import { type DisplayItem, type DisplayPage, type GlyphRun, type Gradient, type GradientStop, type GroupItem, type ImageItem, isGradient, type Paint, type PathItem, type PathOp } from '../display/list'
import { faceId, type FaceRef, type FontSet } from '../fonts/fontset'
import { readSfnt } from '../fonts/sfnt'
import { isJpeg, readJpeg } from '../image/jpeg'
import { decodeBmp, isBmp } from '../image/bmp'
import { decodeGif, isGif } from '../image/gif'
import { decodePng, ImageError, isPng, type Pixels } from '../image/png'
import type { Rgba } from '../text/style'
import { fmt3, mulDivRound } from '../units'

/** Document information. `created` is given by the caller (no clock is read): `2026-11-12T09:30:00Z`. */
export interface PdfInfo {
  title: string
  lang?: string
  created?: string
  author?: string
  producer?: string
}

export interface PdfOptions {
  /** deflate the streams (default true); `false` gives a file that can be read in a text editor */
  compress?: boolean
}

/** The bytes of the images the display list names, by id. PNG, JPEG, GIF and BMP are understood. */
export type ImageSource = (id: string) => Uint8Array | undefined

const enc = (s: string): Uint8Array => {
  const out = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i)
    if (c > 0x7f) throw new RangeError('pdf: non-ASCII character in structural text')
    out[i] = c
  }
  return out
}
const concat = (parts: readonly Uint8Array[]): Uint8Array => {
  let n = 0
  for (const p of parts) n += p.length
  const out = new Uint8Array(n)
  let o = 0
  for (const p of parts) {
    out.set(p, o)
    o += p.length
  }
  return out
}
const hex4 = (n: number) => n.toString(16).toUpperCase().padStart(4, '0')
const utf16Hex = (s: string): string => {
  let out = ''
  for (let i = 0; i < s.length; i++) out += hex4(s.charCodeAt(i))
  return out
}
const textString = (s: string) => '<FEFF' + utf16Hex(s) + '>'
const lit = (s: string) => '(' + s.replace(/[\\()]/g, (c) => '\\' + c).replace(/[^\x20-\x7e]/g, '?') + ')'
const fmt6 = (millionths: number): string => {
  const neg = millionths < 0
  const a = Math.abs(millionths)
  let frac = String(a % 1_000_000).padStart(6, '0').replace(/0+$/, '')
  if (frac) frac = '.' + frac
  const s = `${Math.floor(a / 1_000_000)}${frac}`
  return neg && s !== '0' ? '-' + s : s
}
const unit = (c: number) => fmt3(mulDivRound(c, 1000, 255))
const rgb = (c: Rgba) => `${unit(c.r)} ${unit(c.g)} ${unit(c.b)}`

function pdfDate(iso: string | undefined): string | null {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/.exec(iso)
  if (!m) throw new RangeError('pdf: created must look like 2026-11-12T09:30:00Z')
  return `D:${m[1]}${m[2]}${m[3]}${m[4]}${m[5]}${m[6]}Z`
}

function* allItems(items: readonly DisplayItem[]): Generator<DisplayItem> {
  for (const it of items) {
    yield it
    if (it.kind === 'group') yield* allItems(it.items)
  }
}

interface EmbeddedFont {
  name: string
  ref: number
  /** gid → advance in millionths of an em, from the subset (instanced) font */
  widths: Map<number, number>
}

/**
 * Write the PDF for `pages`. `fonts` must hold every face the glyph runs name; `images` gives the bytes of every
 * image id. `Error` if a glyph run's face or an image is missing or cannot be embedded.
 */
export function writePdf(pages: readonly DisplayPage[], fonts: FontSet, images: ImageSource, info: PdfInfo, options: PdfOptions = {}): Uint8Array {
  const compress = options.compress ?? true
  const objs: Uint8Array[] = []
  const reserve = (): number => {
    objs.push(new Uint8Array(0))
    return objs.length
  }
  const setObj = (n: number, body: string | Uint8Array) => {
    const b = typeof body === 'string' ? enc(body) : body
    objs[n - 1] = concat([enc(`${n} 0 obj\n`), b, enc('\nendobj\n')])
  }
  const setStream = (n: number, dict: string, data: Uint8Array, alreadyFiltered?: string) => {
    const deflate = compress && !alreadyFiltered
    const body = deflate ? zlibSync(data, { level: 6 }) : data
    const filter = alreadyFiltered ? ` /Filter /${alreadyFiltered}` : deflate ? ' /Filter /FlateDecode' : ''
    setObj(n, concat([enc(`<< ${dict}${dict ? ' ' : ''}/Length ${body.length}${filter} >>\nstream\n`), body, enc('\nendstream')]))
  }

  const catalog = reserve()
  const pagesRoot = reserve()
  const infoObj = reserve()

  // ---- what every face needs: its glyphs, and the text each glyph stands for (first seen wins)
  const faces = new Map<string, { ref: FaceRef; gids: Set<number>; chars: Map<number, string> }>()
  const imageIds: string[] = []
  for (const page of pages) {
    for (const it of allItems(page.items)) {
      if (it.kind === 'glyphs') {
        const id = faceId(it.face)
        let f = faces.get(id)
        if (!f) faces.set(id, (f = { ref: it.face, gids: new Set(), chars: new Map() }))
        for (const g of it.glyphs) {
          f.gids.add(g.gid)
          if (g.chars && !f.chars.has(g.gid)) f.chars.set(g.gid, g.chars)
        }
      } else if (it.kind === 'image') {
        if (!imageIds.includes(it.image)) imageIds.push(it.image)
      }
    }
  }

  // ---- fonts
  const embedded = new Map<string, EmbeddedFont>()
  ;[...faces.keys()].sort().forEach((id, index) => {
    const f = faces.get(id)!
    const program = fonts.harfbuzz.subset(fonts.bytes(f.ref.sha256), f.gids, f.ref.variations)
    const sub = readSfnt(program)
    const metrics = fonts.metrics(f.ref)
    const upem = sub.unitsPerEm
    const k = (v: number) => mulDivRound(v, 1000, upem)
    const tag = [...f.ref.sha256.slice(0, 6)].map((c) => String.fromCharCode(65 + parseInt(c, 16))).join('')
    const variant = Object.entries(f.ref.variations).sort(([a], [b]) => (a < b ? -1 : 1)).map(([t, v]) => `${t}${v}`).join('')
    // the original file's PostScript name (an instanced subset may carry its default instance's), plus the axis values
    const base = `${tag}+${(metrics.postscriptName || sub.postscriptName || 'Font').replace(/[^A-Za-z0-9-]/g, '-')}${variant ? '-' + variant : ''}`
    const fileN = reserve()
    setStream(fileN, `/Length1 ${program.length}`, program)
    const descN = reserve()
    const flags = 32 | (sub.fixedPitch ? 1 : 0) | (sub.italicAngle !== 0 ? 64 : 0)
    setObj(
      descN,
      `<< /Type /FontDescriptor /FontName /${base} /Flags ${flags} /FontBBox [${sub.bbox.map(k).join(' ')}] ` +
        `/ItalicAngle ${sub.italicAngle} /Ascent ${k(metrics.ascender)} /Descent ${k(metrics.descender)} ` +
        `/CapHeight ${k(sub.capHeight)} /StemV 80 /FontFile2 ${fileN} 0 R >>`,
    )
    const gids = [...f.gids].sort((a, b) => a - b)
    const widths = new Map<number, number>()
    const w: string[] = []
    for (const gid of gids) {
      const adv = mulDivRound(sub.advances[gid] ?? 0, 1_000_000, upem)
      widths.set(gid, adv)
      w.push(`${gid} [${fmt3(adv)}]`)
    }
    const pairs: string[] = []
    for (const gid of gids) {
      const chars = f.chars.get(gid)
      if (gid !== 0 && chars) pairs.push(`<${hex4(gid)}> <${utf16Hex(chars)}>`)
    }
    const cmap: string[] = [
      '/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n',
      '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n',
      '1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n',
    ]
    for (let i = 0; i < pairs.length; i += 100) {
      const chunk = pairs.slice(i, i + 100)
      cmap.push(`${chunk.length} beginbfchar\n${chunk.join('\n')}\nendbfchar\n`)
    }
    cmap.push('endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend')
    const uniN = reserve()
    setStream(uniN, '', enc(cmap.join('')))
    const cidN = reserve()
    setObj(
      cidN,
      `<< /Type /Font /Subtype /CIDFontType2 /BaseFont /${base} /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> ` +
        `/FontDescriptor ${descN} 0 R /DW 1000 /W [${w.join(' ')}] /CIDToGIDMap /Identity >>`,
    )
    const type0 = reserve()
    setObj(type0, `<< /Type /Font /Subtype /Type0 /BaseFont /${base} /Encoding /Identity-H /DescendantFonts [${cidN} 0 R] /ToUnicode ${uniN} 0 R >>`)
    embedded.set(id, { name: `F${index}`, ref: type0, widths })
  })

  // ---- images
  const imageRefs = new Map<string, { name: string; ref: number }>()
  imageIds.forEach((id, index) => {
    const bytes = images(id)
    if (!bytes) throw new ImageError(`image ${id} is not available`)
    const n = reserve()
    if (isJpeg(bytes)) {
      const j = readJpeg(bytes)
      const space = j.components === 1 ? 'DeviceGray' : j.components === 3 ? 'DeviceRGB' : 'DeviceCMYK'
      const decode = j.components === 4 && j.adobe ? ' /Decode [1 0 1 0 1 0 1 0]' : ''
      setStream(n, `/Type /XObject /Subtype /Image /Width ${j.width} /Height ${j.height} /ColorSpace /${space} /BitsPerComponent 8${decode}`, bytes, 'DCTDecode')
    } else if (isPng(bytes) || isGif(bytes) || isBmp(bytes)) {
      const px: Pixels = isPng(bytes) ? decodePng(bytes) : isGif(bytes) ? decodeGif(bytes) : decodeBmp(bytes)
      let smask = ''
      if (px.alpha) {
        const m = reserve()
        setStream(m, `/Type /XObject /Subtype /Image /Width ${px.width} /Height ${px.height} /ColorSpace /DeviceGray /BitsPerComponent 8`, px.alpha)
        smask = ` /SMask ${m} 0 R`
      }
      setStream(n, `/Type /XObject /Subtype /Image /Width ${px.width} /Height ${px.height} /ColorSpace /DeviceRGB /BitsPerComponent 8${smask}`, px.rgb)
    } else throw new ImageError(`image ${id} is not a PNG, JPEG, GIF or BMP`)
    imageRefs.set(id, { name: `Im${index}`, ref: n })
  })

  // ---- what pages draw with, made as they need it: graphics states, gradient patterns, transparency groups. One
  // resource dictionary serves every page and every group.
  const resources = reserve()
  const gstates = new Map<string, string>()
  const gstateRefs: string[] = []
  const patternRefs: string[] = []
  const formRefs: string[] = []
  /** the operator that sets fill and stroke opacity (0–255), or `''` for opaque */
  const opacity = (fill: number, stroke: number): string => {
    if (fill >= 255 && stroke >= 255) return ''
    const key = `${fill}:${stroke}`
    let name = gstates.get(key)
    if (!name) {
      name = `GS${gstates.size}`
      const n = reserve()
      setObj(n, `<< /Type /ExtGState /ca ${unit(fill)} /CA ${unit(stroke)} >>`)
      gstates.set(key, name)
      gstateRefs.push(`/${name} ${n} 0 R`)
    }
    return `/${name} gs`
  }
  /** a soft mask from a gradient's opacities, as a graphics state; `G` maps the gradient's space to user space */
  const alphaMask = (g: Gradient, G: Affine): string => {
    const form = reserve()
    const data = enc('/Sh0 sh')
    setStream(
      form,
      `/Type /XObject /Subtype /Form /BBox [-1000000 -1000000 1000000 1000000] /Matrix ${affine(G)} ` +
        `/Group << /S /Transparency /CS /DeviceGray >> /Resources << /Shading << /Sh0 ${shading(g, true)} >> >>`,
      data,
    )
    const n = reserve()
    const name = `GS${gstates.size}`
    gstates.set(`mask${n}`, name)
    setObj(n, `<< /Type /ExtGState /SMask << /Type /Mask /S /Luminosity /G ${form} 0 R >> >>`)
    gstateRefs.push(`/${name} ${n} 0 R`)
    return `/${name} gs`
  }
  /** a pattern for a gradient, placed by `P` (from the gradient's space to the content stream's own space) */
  const pattern = (g: Gradient, P: Affine): string => {
    const n = reserve()
    const name = `P${patternRefs.length}`
    setObj(n, `<< /Type /Pattern /PatternType 2 /Shading ${shading(g, false)} /Matrix ${affine(P)} >>`)
    patternRefs.push(`/${name} ${n} 0 R`)
    return name
  }

  /**
   * The content of `items` drawn on a page `H` high, where `ctm` is the transform from the coordinates being drawn
   * in to those of the content stream (a page, or a transparency group).
   */
  const content = (items: readonly DisplayItem[], H: number): string => {
    const ops: string[] = []
    let ctm: Affine = [1, 0, 0, 1, 0, 0]
    const draw = (it: DisplayItem) => {
      if (it.kind === 'glyphs') ops.push(glyphOps(it, embedded.get(faceId(it.face))!, H, opacity(it.color.a, 255)))
      else if (it.kind === 'path') ops.push(pathPaint(it))
      else if (it.kind === 'image') ops.push(imageOps(it, imageRefs.get(it.image)!.name, H))
      else drawGroup(it)
    }
    const pathPaint = (p: PathItem): string => {
      const out: string[] = []
      const geometry = pathGeometry(p, H)
      const paint = (paint: Paint, stroke: boolean) => {
        const parts: string[] = ['q']
        if (isGradient(paint)) {
          const G = gradientSpace(paint, H)
          const alphas = new Set(paint.stops.map((s) => s.color.a))
          if (alphas.size > 1) parts.push(alphaMask(paint, G))
          else parts.push(stroke ? opacity(255, [...alphas][0] ?? 255) : opacity([...alphas][0] ?? 255, 255))
          parts.push(`/Pattern ${stroke ? 'CS' : 'cs'} /${pattern(paint, compose(ctm, G))} ${stroke ? 'SCN' : 'scn'}`)
        } else {
          parts.push(stroke ? opacity(255, paint.a) : opacity(paint.a, 255))
          parts.push(`${rgb(paint)} ${stroke ? 'RG' : 'rg'}`)
        }
        if (stroke) parts.push(strokeStyle(p))
        parts.push(geometry, stroke ? 'S' : p.fillRule === 'evenodd' ? 'f*' : 'f', 'Q')
        out.push(parts.filter(Boolean).join(' '))
      }
      if (p.fill) paint(p.fill, false)
      if (p.stroke && p.lineWidth > 0) paint(p.stroke, true)
      return out.join('\n')
    }
    const drawGroup = (g: GroupItem) => {
      ops.push('q')
      const saved = ctm
      if (g.rotation % 360 !== 0) {
        const c = cosMillionths(g.rotation)
        const s = sinMillionths(g.rotation)
        const ox = g.origin.x
        const oy = H - g.origin.y
        // clockwise on the page (y down) is clockwise in PDF space too: x' = x·c + y·s, y' = −x·s + y·c, about (ox, oy)
        const e = ox - mulDivRound(ox, c, 1_000_000) - mulDivRound(oy, s, 1_000_000)
        const f = oy + mulDivRound(ox, s, 1_000_000) - mulDivRound(oy, c, 1_000_000)
        ops.push(`${fmt6(c)} ${fmt6(-s)} ${fmt6(s)} ${fmt6(c)} ${fmt3(e)} ${fmt3(f)} cm`)
        ctm = compose(ctm, [c / 1e6, -s / 1e6, s / 1e6, c / 1e6, e / 1000, f / 1000])
      }
      if (g.matrix) {
        const [a, b, c, d, e, f] = g.matrix
        // the matrix is in page coordinates (y down); in PDF's (y up) it is F·M·F⁻¹ with F(x, y) = (x, H − y)
        const E = mulDivRound(c, H, 1_000_000) + e
        const Fy = H - mulDivRound(d, H, 1_000_000) - f
        ops.push(`${fmt6(a)} ${fmt6(-b)} ${fmt6(-c)} ${fmt6(d)} ${fmt3(E)} ${fmt3(Fy)} cm`)
        ctm = compose(ctm, [a / 1e6, -b / 1e6, -c / 1e6, d / 1e6, E / 1000, Fy / 1000])
      }
      if (g.clip) ops.push(`${fmt3(g.clip.x)} ${fmt3(H - g.clip.y - g.clip.h)} ${fmt3(g.clip.w)} ${fmt3(g.clip.h)} re W n`)
      if (g.clipPath) ops.push(`${pathGeometry({ ops: g.clipPath.ops }, H)} ${g.clipPath.evenOdd ? 'W*' : 'W'} n`)
      if (g.opacity !== undefined && g.opacity < 255) {
        // one layer, drawn as a whole and then made transparent (SVG's group opacity)
        const form = reserve()
        const name = `Fm${formRefs.length}`
        formRefs.push(`/${name} ${form} 0 R`)
        const body = content(g.items, H)
        setStream(form, `/Type /XObject /Subtype /Form /BBox [-100000 -100000 100000 100000] /Group << /S /Transparency >> /Resources ${resources} 0 R`, enc(body))
        ops.push(`${opacity(g.opacity, g.opacity)} /${name} Do`)
      } else for (const child of g.items) draw(child)
      ctm = saved
      ops.push('Q')
    }
    for (const it of items) draw(it)
    return ops.filter(Boolean).join('\n')
  }

  // ---- pages
  const pageRefs: number[] = []
  for (const page of pages) {
    const contentN = reserve()
    setStream(contentN, '', enc(content(page.items, page.height)))
    const pageN = reserve()
    setObj(
      pageN,
      `<< /Type /Page /Parent ${pagesRoot} 0 R /MediaBox [0 0 ${fmt3(page.width)} ${fmt3(page.height)}] /Resources ${resources} 0 R /Contents ${contentN} 0 R >>`,
    )
    pageRefs.push(pageN)
  }
  const res: string[] = []
  if (embedded.size) res.push(`/Font << ${[...embedded.values()].map((f) => `/${f.name} ${f.ref} 0 R`).join(' ')} >>`)
  const xobjects = [...[...imageRefs.values()].map((i) => `/${i.name} ${i.ref} 0 R`), ...formRefs]
  if (xobjects.length) res.push(`/XObject << ${xobjects.join(' ')} >>`)
  if (gstateRefs.length) res.push(`/ExtGState << ${gstateRefs.join(' ')} >>`)
  if (patternRefs.length) res.push(`/Pattern << ${patternRefs.join(' ')} >>`)
  setObj(resources, `<< ${res.join(' ')} >>`)

  setObj(pagesRoot, `<< /Type /Pages /Count ${pageRefs.length} /Kids [${pageRefs.map((r) => r + ' 0 R').join(' ')}] >>`)
  setObj(catalog, `<< /Type /Catalog /Pages ${pagesRoot} 0 R${info.lang ? ` /Lang ${lit(info.lang)}` : ''} /ViewerPreferences << /DisplayDocTitle true >> >>`)
  const date = pdfDate(info.created)
  setObj(
    infoObj,
    `<< /Title ${textString(info.title)}${info.author ? ` /Author ${textString(info.author)}` : ''} /Producer ${textString(info.producer ?? 'claudia layout')}` +
      `${date ? ` /CreationDate ${lit(date)}` : ''} >>`,
  )

  const header = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37, 0x0a, 0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a])
  const parts: Uint8Array[] = [header]
  const offsets: number[] = []
  let pos = header.length
  for (const o of objs) {
    offsets.push(pos)
    parts.push(o)
    pos += o.length
  }
  const xref = [`xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`]
  for (const off of offsets) xref.push(`${String(off).padStart(10, '0')} 00000 n \n`)
  xref.push(`trailer\n<< /Size ${objs.length + 1} /Root ${catalog} 0 R /Info ${infoObj} 0 R >>\nstartxref\n${pos}\n%%EOF\n`)
  parts.push(enc(xref.join('')))
  return concat(parts)
}

function glyphOps(run: GlyphRun, font: EmbeddedFont, H: number, gs: string): string {
  const parts: string[] = []
  let cur = 0 // pen position as the viewer will have it, millionths of an em
  for (const g of run.glyphs) {
    const target = mulDivRound(g.dx, 1_000_000, run.size)
    if (cur !== target) parts.push(fmt3(cur - target)) // a TJ number moves left by thousandths of an em
    cur = target
    parts.push(`<${hex4(g.gid)}>`)
    cur += font.widths.get(g.gid) ?? 0
  }
  return `${gs ? 'q ' + gs + ' ' : ''}BT /${font.name} ${fmt3(run.size)} Tf ${rgb(run.color)} rg 1 0 0 1 ${fmt3(run.x)} ${fmt3(H - run.y)} Tm [${parts.join(' ')}] TJ ET${gs ? ' Q' : ''}`
}

/** An affine transform in PDF space (y up), in points: `[a, b, c, d, e, f]`. */
type Affine = [number, number, number, number, number, number]

/** `m` after `n`: first `n`, then `m`. */
function compose(m: Affine, n: Affine): Affine {
  return [
    m[0] * n[0] + m[2] * n[1],
    m[1] * n[0] + m[3] * n[1],
    m[0] * n[2] + m[2] * n[3],
    m[1] * n[2] + m[3] * n[3],
    m[0] * n[4] + m[2] * n[5] + m[4],
    m[1] * n[4] + m[3] * n[5] + m[5],
  ]
}

/** A transform as PDF writes it: six numbers, rounded (to millionths, and to thousandths of a point). */
const affine = (m: Affine): string =>
  `[${m.slice(0, 4).map((v) => fmt6(Math.round(v * 1_000_000))).join(' ')} ${fmt3(Math.round(m[4] * 1000))} ${fmt3(Math.round(m[5] * 1000))}]`

/** From a gradient's own space (in points) to PDF page space, on a page `H` mpt high. */
function gradientSpace(g: Gradient, H: number): Affine {
  const [a, b, c, d, e, f] = g.matrix
  return [a / 1e6, -b / 1e6, c / 1e6, -d / 1e6, e / 1000, (H - f) / 1000]
}

/** A gradient's shading: its colours (or, `gray`, its opacities as grey levels) along its axis. */
function shading(g: Gradient, gray: boolean): string {
  const stops = [...g.stops]
  if (!stops.length) stops.push({ offset: 0, color: { r: 0, g: 0, b: 0, a: 0 } })
  if (stops[0]!.offset > 0) stops.unshift({ ...stops[0]!, offset: 0 })
  if (stops.at(-1)!.offset < 1_000_000) stops.push({ ...stops.at(-1)!, offset: 1_000_000 })
  const colour = (c: Rgba) => `[${gray ? unit(c.a) : `${unit(c.r)} ${unit(c.g)} ${unit(c.b)}`}]`
  const piece = (p: GradientStop, q: GradientStop) => `<< /FunctionType 2 /Domain [0 1] /C0 ${colour(p.color)} /C1 ${colour(q.color)} /N 1 >>`
  let fn: string
  if (stops.length === 2) fn = piece(stops[0]!, stops[1]!)
  else {
    const pieces: string[] = []
    for (let i = 0; i + 1 < stops.length; i++) pieces.push(piece(stops[i]!, stops[i + 1]!))
    const bounds = stops.slice(1, -1).map((s) => fmt6(s.offset))
    fn = `<< /FunctionType 3 /Domain [0 1] /Functions [${pieces.join(' ')}] /Bounds [${bounds.join(' ')}] /Encode [${pieces.map(() => '0 1').join(' ')}] >>`
  }
  const c = g.coords.map(fmt3)
  const coords = g.kind === 'linear' ? c.slice(0, 4) : [c[3], c[4], c[5], c[0], c[1], c[2]]
  return `<< /ShadingType ${g.kind === 'linear' ? 2 : 3} /ColorSpace /${gray ? 'DeviceGray' : 'DeviceRGB'} /Coords [${coords.join(' ')}] /Function ${fn} /Extend [true true] >>`
}

/** A path's outline as PDF operators, on a page `H` high. */
function pathGeometry(p: { ops: readonly PathOp[] }, H: number): string {
  const out: string[] = []
  for (const op of p.ops) {
    if (op[0] === 'M') out.push(`${fmt3(op[1])} ${fmt3(H - op[2])} m`)
    else if (op[0] === 'L') out.push(`${fmt3(op[1])} ${fmt3(H - op[2])} l`)
    else if (op[0] === 'C') out.push(`${fmt3(op[1])} ${fmt3(H - op[2])} ${fmt3(op[3])} ${fmt3(H - op[4])} ${fmt3(op[5])} ${fmt3(H - op[6])} c`)
    else out.push('h')
  }
  return out.join(' ')
}

/** How a path's outline is stroked: width, ends, corners and dashes. */
function strokeStyle(p: PathItem): string {
  const out = [`${fmt3(p.lineWidth)} w`]
  if (p.lineCap) out.push(`${p.lineCap === 'round' ? 1 : 2} J`)
  if (p.lineJoin) out.push(`${p.lineJoin === 'round' ? 1 : 2} j`)
  if (p.miterLimit !== undefined && p.miterLimit !== 10000) out.push(`${fmt3(Math.max(1000, p.miterLimit))} M`)
  if (p.dash?.length) out.push(`[${p.dash.map(fmt3).join(' ')}] ${fmt3(p.dashOffset ?? 0)} d`)
  return out.join(' ')
}

function imageOps(it: ImageItem, name: string, H: number): string {
  return `q ${fmt3(it.w)} 0 0 ${fmt3(it.h)} ${fmt3(it.x)} ${fmt3(H - it.y - it.h)} cm /${name} Do Q`
}
