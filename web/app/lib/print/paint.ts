// Drawing a page of a display list in the browser, as SVG in points (the display list's mpt, written with three
// decimals: browsers cap font sizes at a few thousand pixels, so mpt cannot be the SVG's own unit). Words stand where
// the PDF puts them, in the very font files the PDF embeds (registered with the FontFace API under names of their
// own); the letters inside a word are shaped by the browser, which agrees with the layout to a few hundredths of a
// point (the layout spike measured 0.06 pt in Chrome, 0.04 in Firefox, 0.01 in Safari).
import { faceId, fmt3, isGradient, type DisplayItem, type DisplayPage, type FaceRef, type FontSet, type Matrix, type Paint, type PathOp, type Rgba } from '@claudia/layout'

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const n = (mpt: number) => fmt3(mpt)
const colour = (c: Rgba) => `rgba(${c.r},${c.g},${c.b},${fmt3(Math.round((c.a * 1000) / 255))})`

/** The CSS family name a font file is registered under in this page. */
export const familyOf = (sha256: string) => `claudia-print-${sha256.slice(0, 16)}`

const registered = new Map<string, Promise<void>>()
/** Make the font files of `faces` usable in this page (once per file). */
export async function registerFaces(fonts: FontSet, faces: Iterable<FaceRef>): Promise<void> {
  const jobs: Promise<void>[] = []
  for (const face of faces) {
    let job = registered.get(face.sha256)
    if (!job) {
      const font = new FontFace(familyOf(face.sha256), fonts.bytes(face.sha256).slice().buffer as ArrayBuffer)
      job = font.load().then((f) => void document.fonts.add(f))
      registered.set(face.sha256, job)
    }
    jobs.push(job)
  }
  await Promise.all(jobs)
}

/** The faces a page list uses. */
export function facesOf(pages: readonly DisplayPage[]): FaceRef[] {
  const seen = new Map<string, FaceRef>()
  const visit = (items: readonly DisplayItem[]) => {
    for (const it of items) {
      if (it.kind === 'glyphs') seen.set(faceId(it.face), it.face)
      else if (it.kind === 'group') visit(it.items)
    }
  }
  for (const p of pages) visit(p.items)
  return [...seen.values()]
}

/** A millionths value as a plain decimal. */
const m6 = (v: number) => String(v / 1_000_000)
const matrixAttr = (m: Matrix) => `matrix(${m6(m[0])} ${m6(m[1])} ${m6(m[2])} ${m6(m[3])} ${n(m[4])} ${n(m[5])})`
const pathData = (ops: readonly PathOp[]) => ops.map((o) => (o[0] === 'Z' ? 'Z' : `${o[0]}${(o.slice(1) as number[]).map(n).join(' ')}`)).join('')

/** The SVG markup of one page. `imageUrl` gives an image id's object URL. */
export function pageSvg(page: DisplayPage, imageUrl: (id: string) => string | undefined, prefix = 'p'): string {
  let ids = 0
  const defs: string[] = []
  const out: string[] = []
  const id = () => `${prefix}-${++ids}`
  const paint = (p: Paint | null): string => {
    if (!p) return 'none'
    if (!isGradient(p)) return colour(p)
    const gid = id()
    const stops = p.stops.map((s) => `<stop offset="${m6(s.offset)}" stop-color="rgb(${s.color.r},${s.color.g},${s.color.b})" stop-opacity="${fmt3(Math.round((s.color.a * 1000) / 255))}"/>`).join('')
    const c = p.coords.map(n)
    const geometry = p.kind === 'linear' ? `x1="${c[0]}" y1="${c[1]}" x2="${c[2]}" y2="${c[3]}"` : `cx="${c[0]}" cy="${c[1]}" r="${c[2]}" fx="${c[3]}" fy="${c[4]}" fr="${c[5]}"`
    defs.push(`<${p.kind}Gradient id="${gid}" gradientUnits="userSpaceOnUse" gradientTransform="${matrixAttr(p.matrix)}" ${geometry}>${stops}</${p.kind}Gradient>`)
    return `url(#${gid})`
  }
  const draw = (it: DisplayItem) => {
    if (it.kind === 'glyphs') {
      const vars = Object.entries(it.face.variations).map(([t, v]) => `'${t}' ${v}`).join(', ')
      const style = `font-family:'${familyOf(it.face.sha256)}';font-size:${n(it.size)}px;white-space:pre;font-kerning:normal;font-optical-sizing:none${vars ? `;font-variation-settings:${vars}` : ''}`
      out.push(`<text x="${n(it.x)}" y="${n(it.y)}" fill="${colour(it.color)}" style="${esc(style)}">${esc(it.text)}</text>`)
    } else if (it.kind === 'path') {
      const attrs = [`d="${pathData(it.ops)}"`, `fill="${paint(it.fill)}"`]
      if (it.fillRule) attrs.push('fill-rule="evenodd"')
      if (it.stroke && it.lineWidth > 0) {
        attrs.push(`stroke="${paint(it.stroke)}"`, `stroke-width="${n(it.lineWidth)}"`)
        if (it.dash) attrs.push(`stroke-dasharray="${it.dash.map(n).join(' ')}"`)
        if (it.dashOffset) attrs.push(`stroke-dashoffset="${n(it.dashOffset)}"`)
        if (it.lineCap) attrs.push(`stroke-linecap="${it.lineCap}"`)
        if (it.lineJoin) attrs.push(`stroke-linejoin="${it.lineJoin}"`)
        attrs.push(`stroke-miterlimit="${fmt3(it.miterLimit ?? 10000)}"`)
      }
      out.push(`<path ${attrs.join(' ')}/>`)
    } else if (it.kind === 'image') {
      const url = imageUrl(it.image)
      if (url) out.push(`<image href="${esc(url)}" x="${n(it.x)}" y="${n(it.y)}" width="${n(it.w)}" height="${n(it.h)}" preserveAspectRatio="none"/>`)
    } else {
      // the PDF's order: rotate, transform, clip to the rectangle, clip to the path, then the layer's opacity
      const transforms: string[] = []
      if (it.rotation % 360) transforms.push(`rotate(${it.rotation} ${n(it.origin.x)} ${n(it.origin.y)})`)
      if (it.matrix) transforms.push(matrixAttr(it.matrix))
      let open = 0
      const g = (attrs: string) => {
        out.push(`<g ${attrs}>`)
        open++
      }
      if (transforms.length) g(`transform="${transforms.join(' ')}"`)
      if (it.clip) {
        const cid = id()
        defs.push(`<clipPath id="${cid}"><rect x="${n(it.clip.x)}" y="${n(it.clip.y)}" width="${n(it.clip.w)}" height="${n(it.clip.h)}"/></clipPath>`)
        g(`clip-path="url(#${cid})"`)
      }
      if (it.clipPath) {
        const cid = id()
        defs.push(`<clipPath id="${cid}"><path d="${pathData(it.clipPath.ops)}"${it.clipPath.evenOdd ? ' clip-rule="evenodd"' : ''}/></clipPath>`)
        g(`clip-path="url(#${cid})"`)
      }
      if (it.opacity !== undefined && it.opacity < 255) g(`opacity="${fmt3(Math.round((it.opacity * 1000) / 255))}"`)
      if (!open) g('')
      it.items.forEach(draw)
      for (; open > 0; open--) out.push('</g>')
    }
  }
  page.items.forEach(draw)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n(page.width)} ${n(page.height)}" width="100%" height="100%"><defs>${defs.join('')}</defs>${out.join('')}</svg>`
}
