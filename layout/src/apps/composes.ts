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
import { layoutParagraph } from '../text/paragraph'
import type { Hyphenator } from '../text/hyphenate'
import type { ParagraphStyle } from '../text/style'
import { insets } from '../display/text'
import { type DisplayList, type DisplayPage, walk } from '../display/list'
import { type FlowBlock, flowItems, locate, paginate } from '../flow/paginate'
import { contentBox, type PageGeometry, pageGeometry } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import type { FontResolver } from '../fonts/resolve'
import { LAYOUT_VERSION } from '../version'
import {
  cssOf,
  drawObject,
  type ImageInfo,
  type Note,
  objectFonts,
  type PageSetupData,
  pageNumberItems,
  px,
  type ShapeOutline,
  styleFont,
  Styles,
  type TextStyle,
  type VisualObject,
} from './objects'

export type { ImageInfo, Note, PageSetupData, ShapeOutline, TextStyle } from './objects'

/** A paragraph: `{id, style, text}` (runs are authorship only and do not change how it looks). */
export interface TextBlock {
  id: string
  style: string
  text: string
}
/** A floating object as the server sends it (the shape all three apps share), anchored to a character. */
export interface TextObject extends VisualObject {
  anchor: { kind: 'block'; container: string; offset: number }
}

export interface TextDocument {
  blocks: readonly TextBlock[]
  styles: readonly TextStyle[]
  page: PageSetupData
  objects?: readonly TextObject[]
  shapes?: readonly ShapeOutline[]
  images?: readonly ImageInfo[]
  /** BCP 47 language of the text (D915), for shaping and hyphenation */
  language?: string | null
}

/** What laying out a text needs besides its fonts: the hyphenation patterns of its language, if the caller has them. */
export interface TextLayoutOptions {
  hyphenator?: Hyphenator | null
}

export interface TextPages {
  list: DisplayList
  geometry: PageGeometry
  notes: Note[]
  /** image ids the display list draws */
  images: string[]
  /** the bytes of pictures that SVG pictures carry inside them, by the image id the display list uses */
  embedded: Map<string, Uint8Array>
}

/** Styles that keep their last line on the page of the next paragraph's first: titles and headings. */
const KEEP = new Set(['title', 'heading-1', 'heading-2', 'heading-3', 'subtitle'])

function headingLike(style: string, styles: ReadonlyMap<string, TextStyle>): boolean {
  for (let s = styles.get(style), seen = 0; s && seen < 20; s = s.based_on ? styles.get(s.based_on) : undefined, seen++) {
    if (KEEP.has(s.id)) return true
  }
  return false
}

/** composes' default style: what a paragraph with a style the text does not have is drawn in. */
const BODY = 'body'

/**
 * The SHA-256 of every font file laying out `doc` needs, as `resolver` picks them, so the caller can fetch them
 * before calling {@link layoutText}.
 */
export function fontsNeeded(doc: TextDocument, resolver: FontResolver): string[] {
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const out = new Set<string>()
  for (const id of new Set(doc.blocks.map((b) => b.style))) {
    const face = styleFont(cssOf(styles, id, BODY), resolver)
    if (face) out.add(face)
  }
  for (const face of objectFonts(doc.objects ?? [], styles, doc.images ?? [], resolver, BODY)) out.add(face)
  return [...out].sort()
}

/**
 * Lay out `doc` on its pages. Every font {@link fontsNeeded} names must be in `fonts`. `options.hyphenator` holds
 * the patterns of the text's language, for the styles with `hyphens: auto` (D912).
 */
export function layoutText(doc: TextDocument, fonts: FontSet, resolver: FontResolver, options: TextLayoutOptions = {}): TextPages {
  const p = doc.page
  const geometry = pageGeometry(p.width, p.height, p.orientation, { top: p.margins[0], right: p.margins[1], bottom: p.margins[2], left: p.margins[3] })
  const box = contentBox(geometry)
  const notes: Note[] = []
  const sheet = new Styles(doc.styles, fonts, resolver, doc.language, BODY, notes)
  const styles = sheet.byId
  // ---- the flow
  const hyphenator = options.hyphenator ?? null
  const paragraphOptions = { hyphenator }
  let wantsHyphens = false
  const blocks: FlowBlock[] = doc.blocks.map((b) => {
    const r = sheet.paragraph(b.style)
    const style: ParagraphStyle = { ...r.style, keepWithNext: headingLike(b.style, styles) }
    if (style.hyphens === 'auto' && b.text) wantsHyphens = true
    const inset = insets(r.decoration)
    return { id: b.id, layout: layoutParagraph(fonts, style, b.text, box.w - inset.left - inset.right, paragraphOptions), decoration: r.decoration }
  })
  if (wantsHyphens && !hyphenator) {
    notes.push({
      kind: 'hyphenation',
      reason: doc.language ? `there are no hyphenation patterns for ${doc.language}, so words are not hyphenated` : 'the text has no language set, so words are not hyphenated',
    })
  }
  const flow = paginate(blocks, geometry)
  const pages: DisplayPage[] = flowItems(fonts, flow, blocks, geometry)

  // ---- floating objects, where they hang (D179: over the text, which does not wrap around them)
  const blockIndex = new Map(doc.blocks.map((b, i) => [b.id, i]))
  const shapes = new Map((doc.shapes ?? []).map((s) => [s.id, s]))
  const images = new Map((doc.images ?? []).map((i) => [i.id, i]))
  const usedImages: string[] = []
  const embedded = new Map<string, Uint8Array>()
  for (const o of doc.objects ?? []) {
    const index = blockIndex.get(o.anchor.container)
    const spot = index === undefined ? null : locate(flow, blocks, index, o.anchor.offset)
    if (!spot) continue
    const w = px(o.w)
    const h = px(o.h)
    // keep the object on its page: inside the margins across, and above the bottom margin
    const x = Math.max(box.x, Math.min(spot.x, box.x + box.w - w))
    const y = Math.max(box.y, Math.min(spot.top, geometry.height - geometry.margin.bottom - h))
    const group = drawObject(o, { x, y, w, h }, { fonts, resolver, styles: sheet, shapes, images, notes, embedded, paragraphOptions, diagramNote: 'charts cannot be printed from a text yet' })
    if (!group) continue
    for (const it of walk(group.items)) if (it.kind === 'image' && !usedImages.includes(it.image)) usedImages.push(it.image)
    pages[spot.page]!.items.push(group)
  }

  // ---- page numbers, centred in the bottom margin (the same in every app)
  if (p.page_numbers) pageNumberItems(fonts, pages, geometry, sheet.paragraph(BODY).style)

  return {
    list: { layoutVersion: LAYOUT_VERSION, shaper: fonts.shaperId, ...(hyphenator ? { hyphenation: hyphenator.id } : {}), pages },
    geometry,
    notes,
    images: usedImages,
    embedded,
  }
}

