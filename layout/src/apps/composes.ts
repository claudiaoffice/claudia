/**
 * A composes text, as the server describes it, laid out on pages: the paragraphs in their styles, the floating
 * objects where they hang, page numbers. Pure: the caller fetches the fonts the text needs (see
 * {@link fontsNeeded}) and registers them in the {@link FontSet} first.
 *
 * Its input is the wire form of the document (`blocks`, the `resolved` CSS of `styles`, `page`, `objects`,
 * `shapes`, `images`), so any client of a composes server can print exactly the same pages.
 *
 * @module
 */
import { boxItems, layoutBox } from '../text/box'
import { type BoxDecoration, boxDecorationFromCss, type Css, paragraphStyleFromCss, parseColor, type StyleFromCss } from '../text/css'
import { layoutParagraph } from '../text/paragraph'
import { paragraphStyle, type ParagraphStyle, type Rgba } from '../text/style'
import { insets, lineItems } from '../display/text'
import { type DisplayItem, type DisplayList, type DisplayPage, type GroupItem, type Rect, rectPath } from '../display/list'
import { outlinePath, PathError } from '../display/svgpath'
import { type FlowBlock, flowItems, locate, paginate } from '../flow/paginate'
import { contentBox, type PageGeometry, pageGeometry } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import { parseFamilies, type FontResolver, type Resolution } from '../fonts/resolve'
import { LAYOUT_VERSION } from '../version'

/** A paragraph: `{id, style, text}` (runs are authorship only and do not change how it looks). */
export interface TextBlock {
  id: string
  style: string
  text: string
}
/** A style as the server sends it: `resolved` is its CSS with parents taken in and palette roles replaced. */
export interface TextStyle {
  id: string
  based_on: string | null
  resolved: Css
}
/** The `page` answer of a composes server (D904): lengths in mpt, `margins` top, right, bottom, left. */
export interface PageSetupData {
  paper: string
  width: number
  height: number
  orientation: 'portrait' | 'landscape'
  margins: [number, number, number, number]
  page_numbers: boolean
}
/** A floating object as the server sends it (the shape all three apps share), anchored to a character. */
export interface TextObject {
  id: string
  kind: 'text' | 'shape' | 'image' | 'diagram'
  /** CSS pixels */
  w: number
  h: number
  style: string
  paragraph: { style: string; text: string } | null
  shape: string | null
  image: string | null
  rotation: number
  anchor: { kind: 'block'; container: string; offset: number }
}
export interface ShapeOutline {
  id: string
  path: string
  text_area: { x: number; y: number; w: number; h: number }
}
export interface ImageInfo {
  id: string
  format: string
}

export interface TextDocument {
  blocks: readonly TextBlock[]
  styles: readonly TextStyle[]
  page: PageSetupData
  objects?: readonly TextObject[]
  shapes?: readonly ShapeOutline[]
  images?: readonly ImageInfo[]
  /** BCP 47 language of the text, for shaping */
  language?: string
}

/** Something the person should know about the pages: a font that was replaced, an object that cannot be printed. */
export interface Note {
  kind: 'font' | 'object'
  /** for `font`: the family the style asked for and the one used */
  requested?: string
  used?: string
  /** for `object`: its id and why */
  object?: string
  reason?: string
}

export interface TextPages {
  list: DisplayList
  geometry: PageGeometry
  notes: Note[]
  /** image ids the display list draws */
  images: string[]
}

/** CSS pixels to mpt (96 px = 72 pt). */
const px = (n: number) => Math.round(n * 750)

/** Styles that keep their last line on the page of the next paragraph's first: titles and headings. */
const KEEP = new Set(['title', 'heading-1', 'heading-2', 'heading-3', 'subtitle'])

function headingLike(style: string, styles: ReadonlyMap<string, TextStyle>): boolean {
  for (let s = styles.get(style), seen = 0; s && seen < 20; s = s.based_on ? styles.get(s.based_on) : undefined, seen++) {
    if (KEEP.has(s.id)) return true
  }
  return false
}

const cssOf = (styles: ReadonlyMap<string, TextStyle>, id: string): Css => styles.get(id)?.resolved ?? styles.get('body')?.resolved ?? {}

/**
 * The SHA-256 of every font file laying out `doc` needs, as `resolver` picks them, so the caller can fetch them
 * before calling {@link layoutText}.
 */
export function fontsNeeded(doc: TextDocument, resolver: FontResolver): string[] {
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const ids = new Set<string>(doc.blocks.map((b) => b.style))
  ids.add('body')
  for (const o of doc.objects ?? []) if (o.paragraph) ids.add(o.paragraph.style)
  const out = new Set<string>()
  for (const id of ids) {
    const css = cssOf(styles, id)
    const r = resolver.resolve(css['font-family'] ?? 'sans-serif', weight(css), /^(italic|oblique)$/i.test(css['font-style'] ?? ''), 12000)
    if (r) out.add(r.face.sha256)
  }
  return [...out].sort()
}

const weight = (css: Css) => {
  const v = (css['font-weight'] ?? '').toLowerCase()
  return v === 'bold' ? 700 : v === '' || v === 'normal' ? 400 : Number(v) || 400
}

/** Lay out `doc` on its pages. Every font {@link fontsNeeded} names must be in `fonts`. */
export function layoutText(doc: TextDocument, fonts: FontSet, resolver: FontResolver): TextPages {
  const p = doc.page
  const geometry = pageGeometry(p.width, p.height, p.orientation, { top: p.margins[0], right: p.margins[1], bottom: p.margins[2], left: p.margins[3] })
  const box = contentBox(geometry)
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const notes: Note[] = []
  const noted = new Set<string>()
  const note = (r: Resolution) => {
    if (r.how === 'exact' || r.how === 'substitute') return
    const key = `${r.requested}\u0000${r.family}`
    if (noted.has(key)) return
    noted.add(key)
    notes.push({ kind: 'font', requested: r.requested, used: r.family })
  }
  const resolved = new Map<string, StyleFromCss>()
  const styleFor = (id: string): StyleFromCss => {
    let r = resolved.get(id)
    if (!r) {
      const css = cssOf(styles, id)
      const got = paragraphStyleFromCss(css, resolver, fonts, doc.language ? { language: doc.language } : {})
      if (!got) throw new Error('the server has no fonts that can be used for layout')
      // a style that names a font first and gets it is exact; only report a family that was asked for and missed
      if (parseFamilies(css['font-family'] ?? '').length) note(got.font)
      r = got
      resolved.set(id, r)
    }
    return r
  }

  // ---- the flow
  const blocks: FlowBlock[] = doc.blocks.map((b) => {
    const r = styleFor(b.style)
    const style: ParagraphStyle = { ...r.style, keepWithNext: headingLike(b.style, styles) }
    const inset = insets(r.decoration)
    return { id: b.id, layout: layoutParagraph(fonts, style, b.text, box.w - inset.left - inset.right), decoration: r.decoration }
  })
  const flow = paginate(blocks, geometry)
  const pages: DisplayPage[] = flowItems(fonts, flow, blocks, geometry)

  // ---- floating objects, where they hang (D179: over the text, which does not wrap around them)
  const blockIndex = new Map(doc.blocks.map((b, i) => [b.id, i]))
  const shapes = new Map((doc.shapes ?? []).map((s) => [s.id, s]))
  const images = new Map((doc.images ?? []).map((i) => [i.id, i]))
  const usedImages: string[] = []
  for (const o of doc.objects ?? []) {
    const index = blockIndex.get(o.anchor.container)
    const spot = index === undefined ? null : locate(flow, blocks, index, o.anchor.offset)
    if (!spot) continue
    const w = px(o.w)
    const h = px(o.h)
    // keep the object on its page: inside the margins across, and above the bottom margin
    const x = Math.max(box.x, Math.min(spot.x, box.x + box.w - w))
    const y = Math.max(box.y, Math.min(spot.top, geometry.height - geometry.margin.bottom - h))
    const group = objectItems(o, { x, y, w, h }, fonts, styles, styleFor, shapes, images, notes)
    if (!group) continue
    for (const it of group.items) if (it.kind === 'image' && !usedImages.includes(it.image)) usedImages.push(it.image)
    pages[spot.page]!.items.push(group)
  }

  // ---- page numbers, centred in the bottom margin
  if (p.page_numbers) {
    const body = styleFor('body').style
    const size = Math.max(6000, Math.round((body.size * 3) / 4))
    const style = paragraphStyle(body.face, size, { lineHeight: Math.round(size * 1.2), align: 'center', color: muted(body.color) })
    pages.forEach((page, i) => {
      const line = layoutParagraph(fonts, style, `${i + 1} / ${pages.length}`, box.w)
      const top = geometry.height - Math.floor((geometry.margin.bottom + line.height) / 2)
      page.items.push(...lineItems(fonts, line, line.lines[0]!, box.x, top))
    })
  }

  return {
    list: { layoutVersion: LAYOUT_VERSION, shaper: fonts.shaperId, pages },
    geometry,
    notes,
    images: usedImages,
  }
}

const muted = (c: Rgba): Rgba => ({ ...c, a: Math.round((c.a * 65) / 100) })

function objectItems(
  o: TextObject,
  r: Rect,
  fonts: FontSet,
  styles: ReadonlyMap<string, TextStyle>,
  styleFor: (id: string) => StyleFromCss,
  shapes: ReadonlyMap<string, ShapeOutline>,
  images: ReadonlyMap<string, ImageInfo>,
  notes: Note[],
): GroupItem | null {
  const boxCss = cssOf(styles, o.style)
  const decoration: BoxDecoration = boxDecorationFromCss(boxCss, 12000)
  const group = (items: DisplayItem[], clip = true): GroupItem => ({
    kind: 'group',
    clip: clip ? r : null,
    rotation: Math.round(o.rotation || 0),
    origin: { x: r.x + Math.floor(r.w / 2), y: r.y + Math.floor(r.h / 2) },
    items,
  })
  if (o.kind === 'text') {
    const words = o.paragraph ? styleFor(o.paragraph.style) : null
    const laid = layoutBox(fonts, o.paragraph?.text ?? null, words?.style ?? null, r.w, r.h, decoration, words?.verticalAlign ?? 'top')
    const g = boxItems(fonts, laid, r.x, r.y, o.rotation)
    return g
  }
  if (o.kind === 'shape') {
    const outline = o.shape ? shapes.get(o.shape) : undefined
    if (!outline) {
      notes.push({ kind: 'object', object: o.id, reason: 'its outline is missing' })
      return null
    }
    const items: DisplayItem[] = []
    try {
      const fill = parseColor(boxCss.fill)
      const stroke = parseColor(boxCss.stroke)
      const width = Math.max(0, Math.round(Number.parseFloat(boxCss['stroke-width'] ?? '1') * 750) || 0)
      items.push({ kind: 'path', ops: outlinePath(outline.path, r), fill: fill && fill.a > 0 ? fill : null, stroke: stroke && stroke.a > 0 && width > 0 ? stroke : null, lineWidth: width })
    } catch (e) {
      if (!(e instanceof PathError)) throw e
      notes.push({ kind: 'object', object: o.id, reason: 'its outline cannot be read' })
      return null
    }
    if (o.paragraph?.text) {
      const area = outline.text_area
      const inner: Rect = { x: r.x + Math.round((area.x * r.w) / 100), y: r.y + Math.round((area.y * r.h) / 100), w: Math.round((area.w * r.w) / 100), h: Math.round((area.h * r.h) / 100) }
      const words = styleFor(o.paragraph.style)
      const laid = layoutBox(fonts, o.paragraph.text, words.style, inner.w, inner.h, undefined, words.verticalAlign)
      items.push(boxItems(fonts, laid, inner.x, inner.y))
    }
    return group(items, false)
  }
  if (o.kind === 'image') {
    const info = o.image ? images.get(o.image) : undefined
    if (!info || !['png', 'jpeg', 'gif', 'bmp'].includes(info.format)) {
      notes.push({ kind: 'object', object: o.id, reason: info?.format === 'svg' ? 'SVG pictures cannot be printed yet' : 'its picture is missing' })
      return group([{ kind: 'path', ops: rectPath(r), fill: null, stroke: { r: 150, g: 150, b: 150, a: 255 }, lineWidth: 500, dash: [3000, 2000] }])
    }
    return group([{ kind: 'image', image: info.id, ...r }])
  }
  notes.push({ kind: 'object', object: o.id, reason: 'charts cannot be printed from a text yet' })
  return null
}
