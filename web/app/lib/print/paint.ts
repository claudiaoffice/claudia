// Drawing a page of a display list in the browser, as SVG in points (the display list's mpt, written with three
// decimals: browsers cap font sizes at a few thousand pixels, so mpt cannot be the SVG's own unit). Words stand where
// the PDF puts them, in the very font files the PDF embeds (registered with the FontFace API under names of their
// own); the letters inside a word are shaped by the browser, which agrees with the layout to a few hundredths of a
// point (the layout spike measured 0.06 pt in Chrome, 0.04 in Firefox, 0.01 in Safari).
import { faceId, fmt3, type DisplayItem, type DisplayPage, type FaceRef, type FontSet, type Rgba } from '@claudia/layout'

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

/** The SVG markup of one page. `imageUrl` gives an image id's object URL. */
export function pageSvg(page: DisplayPage, imageUrl: (id: string) => string | undefined, prefix = "p"): string {
  let clips = 0
  const out: string[] = []
  const draw = (it: DisplayItem) => {
    if (it.kind === 'glyphs') {
      const vars = Object.entries(it.face.variations).map(([t, v]) => `'${t}' ${v}`).join(', ')
      const style = `font-family:'${familyOf(it.face.sha256)}';font-size:${n(it.size)}px;white-space:pre;font-kerning:normal;font-optical-sizing:none${vars ? `;font-variation-settings:${vars}` : ''}`
      out.push(`<text x="${n(it.x)}" y="${n(it.y)}" fill="${colour(it.color)}" style="${esc(style)}">${esc(it.text)}</text>`)
    } else if (it.kind === 'path') {
      const d = it.ops.map((o) => (o[0] === 'Z' ? 'Z' : `${o[0]}${(o.slice(1) as number[]).map(n).join(' ')}`)).join('')
      const fill = it.fill ? colour(it.fill) : 'none'
      const stroke = it.stroke ? ` stroke="${colour(it.stroke)}" stroke-width="${n(it.lineWidth)}"${it.dash ? ` stroke-dasharray="${it.dash.map(n).join(' ')}"` : ''}` : ''
      out.push(`<path d="${d}" fill="${fill}"${stroke}/>`)
    } else if (it.kind === 'image') {
      const url = imageUrl(it.image)
      if (url) out.push(`<image href="${esc(url)}" x="${n(it.x)}" y="${n(it.y)}" width="${n(it.w)}" height="${n(it.h)}" preserveAspectRatio="none"/>`)
    } else {
      const attrs: string[] = []
      if (it.rotation % 360) attrs.push(`transform="rotate(${it.rotation} ${n(it.origin.x)} ${n(it.origin.y)})"`)
      if (it.clip) {
        const id = `${prefix}-clip${++clips}`
        out.push(`<clipPath id="${id}"><rect x="${n(it.clip.x)}" y="${n(it.clip.y)}" width="${n(it.clip.w)}" height="${n(it.clip.h)}"/></clipPath>`)
        out.push(`<g ${attrs.join(' ')}><g clip-path="url(#${id})">`)
        it.items.forEach(draw)
        out.push('</g></g>')
      } else {
        out.push(`<g ${attrs.join(' ')}>`)
        it.items.forEach(draw)
        out.push('</g>')
      }
    }
  }
  page.items.forEach(draw)
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${n(page.width)} ${n(page.height)}" width="100%" height="100%">${out.join('')}</svg>`
}
