/**
 * A presentation, as a creates server describes it, laid out on pages (D917): one slide to a page, or handouts of
 * 2, 3 (beside lines for notes), 4, 6 or 9 slides to a page. Pure, like the composes adapter: the caller fetches the
 * fonts {@link slideFontsNeeded} names first.
 *
 * A slide is 1600 × 900 CSS pixels (its objects and their CSS are measured so), drawn once at 1200 × 675 pt and
 * placed on each page through a group's transform, scaled to fit its place and centred there. On the `slide` paper
 * with no margins the page is the slide itself, edge to edge; anywhere else a thin frame shows where the slide ends.
 * The objects are drawn exactly as composes draws its floating objects ({@link drawObject}).
 *
 * @module
 */
import { type DisplayItem, type DisplayList, type DisplayPage, type GroupItem, type Rect, rectPath, walk } from '../display/list'
import { contentBox, type PageGeometry, pageGeometry } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import type { FontResolver } from '../fonts/resolve'
import type { Hyphenator } from '../text/hyphenate'
import { LAYOUT_VERSION } from '../version'
import {
  cssOf,
  drawObject,
  type ImageInfo,
  type Note,
  objectFonts,
  PAGE_NUMBER_BAND,
  type PageSetupData,
  pageNumberItems,
  px,
  type ShapeOutline,
  styleFont,
  Styles,
  type TextStyle,
  type VisualObject,
} from './objects'

/** A slide's size in CSS pixels, and in mpt. */
export const SLIDE = { w: 1600, h: 900 } as const
const SLIDE_W = px(SLIDE.w)
const SLIDE_H = px(SLIDE.h)

/** The print layouts, in the order a preview offers them. */
export const SLIDE_LAYOUTS = ['slides', 'handouts-2', 'handouts-3', 'handouts-4', 'handouts-6', 'handouts-9'] as const
export type SlideLayout = (typeof SLIDE_LAYOUTS)[number]

/** An object on a slide as the server sends it: the shared body and where on its slide it sits (CSS pixels). */
export interface SlideObject extends VisualObject {
  anchor: { kind: 'slide'; container: string; x: number; y: number }
}
/** The `print_setup` answer of a creates server (D917). */
export interface PrintSetupData {
  layout: SlideLayout
  page: PageSetupData
}
export interface SlideDocument {
  /** the slides in order, each with its objects, the one in front last */
  slides: readonly { id: string; objects: readonly SlideObject[] }[]
  styles: readonly TextStyle[]
  shapes?: readonly ShapeOutline[]
  images?: readonly ImageInfo[]
  print: PrintSetupData
  /** BCP 47 language of the presentation (D915, D917), for shaping and hyphenation */
  language?: string | null
}
export interface SlideLayoutOptions {
  hyphenator?: Hyphenator | null
}
export interface SlidePages {
  list: DisplayList
  geometry: PageGeometry
  notes: Note[]
  /** image ids the display list draws */
  images: string[]
  /** the bytes of pictures that SVG pictures carry inside them, by the image id the display list uses */
  embedded: Map<string, Uint8Array>
  /** how many slides there are, and how many go on a page */
  slides: number
  perPage: number
}

/** creates' default style. */
const BODY = 'body-text'
/** The space between the slides of a handout, and between the lines for notes. */
const GAP = 22677 // 8 mm
const LINE_GAP = 22677
const FRAME = { r: 160, g: 160, b: 160, a: 255 }
const RULE = { r: 190, g: 190, b: 190, a: 255 }

/** The SHA-256 of every font file laying out `doc` needs, as `resolver` picks them. */
export function slideFontsNeeded(doc: SlideDocument, resolver: FontResolver): string[] {
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const out = objectFonts(
    doc.slides.flatMap((s) => s.objects),
    styles,
    doc.images ?? [],
    resolver,
    BODY,
  )
  if (doc.print.page.page_numbers) {
    const face = styleFont(cssOf(styles, BODY, BODY), resolver)
    if (face) out.add(face)
  }
  return [...out].sort()
}

/** How many slides a layout puts on a page. */
export const slidesPerPage = (layout: SlideLayout): number => (layout === 'slides' ? 1 : Number(layout.split('-')[1]))

/**
 * The grid of a layout on a page lying as `landscape` says: columns and rows. Three to a page are one column of
 * slides with lines beside them (portrait) or one row with lines below (landscape).
 */
export function gridOf(layout: SlideLayout, landscape: boolean): { columns: number; rows: number } {
  const n = slidesPerPage(layout)
  const portrait: Record<number, [number, number]> = { 1: [1, 1], 2: [1, 2], 3: [1, 3], 4: [2, 2], 6: [2, 3], 9: [3, 3] }
  const [c, r] = portrait[n]!
  return landscape ? { columns: r, rows: c } : { columns: c, rows: r }
}

/** Lay out `doc` as its print setup says. Every font {@link slideFontsNeeded} names must be in `fonts`. */
export function layoutSlides(doc: SlideDocument, fonts: FontSet, resolver: FontResolver, options: SlideLayoutOptions = {}): SlidePages {
  const p = doc.print.page
  const geometry = pageGeometry(p.width, p.height, p.orientation, { top: p.margins[0], right: p.margins[1], bottom: p.margins[2], left: p.margins[3] })
  const notes: Note[] = []
  const sheet = new Styles(doc.styles, fonts, resolver, doc.language, BODY, notes)
  const hyphenator = options.hyphenator ?? null
  const shapes = new Map((doc.shapes ?? []).map((s) => [s.id, s]))
  const images = new Map((doc.images ?? []).map((i) => [i.id, i]))
  const embedded = new Map<string, Uint8Array>()
  const context = { fonts, resolver, styles: sheet, shapes, images, notes, embedded, paragraphOptions: { hyphenator }, diagramNote: 'charts cannot be printed from a presentation yet' }

  // the content box, with room kept for page numbers when the bottom margin has none
  const area: Rect = contentBox(geometry)
  const numbers = p.page_numbers ? { ...geometry, margin: { ...geometry.margin, bottom: Math.max(geometry.margin.bottom, PAGE_NUMBER_BAND) } } : null
  if (numbers) area.h -= numbers.margin.bottom - geometry.margin.bottom

  // every slide drawn once, in its own coordinates (0, 0 to 1200 × 675 pt), cut at its edge
  let wantsHyphens = false
  const drawn = doc.slides.map((slide) => {
    const items: DisplayItem[] = []
    for (const o of slide.objects) {
      if (o.paragraph?.text && sheet.paragraph(o.paragraph.style).style.hyphens === 'auto') wantsHyphens = true
      const g = drawObject(o, { x: px(o.anchor.x), y: px(o.anchor.y), w: px(o.w), h: px(o.h) }, context)
      if (g) items.push(g)
    }
    return items
  })
  if (wantsHyphens && !hyphenator) {
    notes.push({
      kind: 'hyphenation',
      reason: doc.language ? `there are no hyphenation patterns for ${doc.language}, so words are not hyphenated` : 'the presentation has no language set, so words are not hyphenated',
    })
  }

  // ---- the places on a page
  const layout = doc.print.layout
  const perPage = slidesPerPage(layout)
  const { columns, rows } = gridOf(layout, geometry.width > geometry.height)
  const lined = perPage === 3
  const gap = perPage === 1 ? 0 : GAP
  const cellW = Math.floor((area.w - gap * (columns - 1)) / columns)
  const cellH = Math.floor((area.h - gap * (rows - 1)) / rows)
  /** where slide `k` of a page goes, and where its lines for notes go (three to a page) */
  const place = (k: number): { slide: Rect; lines: Rect | null } => {
    const cell: Rect = { x: area.x + (k % columns) * (cellW + gap), y: area.y + Math.floor(k / columns) * (cellH + gap), w: cellW, h: cellH }
    if (!lined) return { slide: cell, lines: null }
    if (columns === 1) {
      const w = Math.floor((cell.w - gap) * 0.55)
      return { slide: { ...cell, w }, lines: { x: cell.x + w + gap, y: cell.y, w: cell.w - w - gap, h: cell.h } }
    }
    const h = Math.floor((cell.h - gap) * 0.5)
    return { slide: { ...cell, h }, lines: { x: cell.x, y: cell.y + h + gap, w: cell.w, h: cell.h - h - gap } }
  }
  /** a slide fitted into `r`, centred, keeping its 16:9 */
  const fitted = (r: Rect): { scale: number; rect: Rect } => {
    // scale in millionths, so the transform is exact; the slide's size on the page follows from it
    const scale = Math.max(1, Math.min(Math.floor((r.w * 1_000_000) / SLIDE_W), Math.floor((r.h * 1_000_000) / SLIDE_H)))
    const w = Math.round((SLIDE_W * scale) / 1_000_000)
    const h = Math.round((SLIDE_H * scale) / 1_000_000)
    return { scale, rect: { x: r.x + Math.floor((r.w - w) / 2), y: r.y + Math.floor((r.h - h) / 2), w, h } }
  }
  // the page is the slide itself when it is slide-sized with no margins: no frame then
  const whole = fitted(area).rect
  const edgeToEdge = perPage === 1 && area.x === 0 && area.y === 0 && whole.w >= geometry.width - 1 && whole.h >= geometry.height - 1

  const pages: DisplayPage[] = []
  const count = Math.max(1, Math.ceil(doc.slides.length / perPage))
  for (let n = 0; n < count; n++) {
    const items: DisplayItem[] = []
    for (let k = 0; k < perPage; k++) {
      const index = n * perPage + k
      if (index >= drawn.length) break
      const { slide, lines } = place(k)
      const { scale, rect } = fitted(slide)
      const group: GroupItem = {
        kind: 'group',
        clip: null,
        rotation: 0,
        origin: { x: 0, y: 0 },
        matrix: [scale, 0, 0, scale, rect.x, rect.y],
        clipPath: { ops: rectPath({ x: 0, y: 0, w: SLIDE_W, h: SLIDE_H }) },
        items: drawn[index]!,
      }
      items.push(group)
      if (!edgeToEdge) items.push({ kind: 'path', ops: rectPath(rect), fill: null, stroke: FRAME, lineWidth: 500 })
      if (lines) {
        for (let y = lines.y + LINE_GAP; y <= lines.y + lines.h; y += LINE_GAP) {
          items.push({ kind: 'path', ops: [['M', lines.x, y], ['L', lines.x + lines.w, y]], fill: null, stroke: RULE, lineWidth: 400 })
        }
      }
    }
    pages.push({ width: geometry.width, height: geometry.height, items })
  }
  if (numbers) pageNumberItems(fonts, pages, numbers, sheet.paragraph(BODY).style)

  const used: string[] = []
  for (const page of pages) for (const it of walk(page.items)) if (it.kind === 'image' && !used.includes(it.image)) used.push(it.image)
  return {
    list: { layoutVersion: LAYOUT_VERSION, shaper: fonts.shaperId, ...(hyphenator ? { hyphenation: hyphenator.id } : {}), pages },
    geometry,
    notes,
    images: used,
    embedded,
    slides: doc.slides.length,
    perPage,
  }
}
