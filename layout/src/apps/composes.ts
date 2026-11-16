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
import { itemGeometry, type ListItemRef, type ListRef, MARKER_GAP_EM, markerCss, type SchemeGeometry } from '../text/list-geometry'
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

/** A paragraph: `{id, style, text}` (runs are authorship only and do not change how it looks), and, for a list item,
 *  its place in its list and the marker the server counted for it (E9.21). A paragraph with a label and no item is a
 *  numbered heading (E9.22): its number hangs before it, in its own look. */
export interface TextBlock {
  id: string
  style: string
  text: string
  item?: ListItemRef | null
  label?: { marker: string } | null
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
  /** the lists and their schemes, for where the items sit (E9.21); a text without lists needs neither */
  lists?: readonly ListRef[]
  schemes?: readonly SchemeGeometry[]
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

/** A heading keeps its last line on the page of the next paragraph's first: the title and every heading, by the level
 *  the server says its style gives (E9.22). No list of style names: any style can be a heading. */
function keepsWithNext(style: string, styles: ReadonlyMap<string, TextStyle>): boolean {
  const level = styles.get(style)?.heading
  return level !== null && level !== undefined
}

/** A list item's marker as its own one-line paragraph, right-aligned in its box (from `left`, `step` wide less the gap
 *  to the text), upright and in the regular weight of the item's font; `x` is where the box starts in the paragraph. */
function markerOf(sheet: Styles, style: string, marker: string, indent: number, left: number, step: number, em: number): FlowBlock['marker'] {
  const own = sheet.marker(style)
  const plain: ParagraphStyle = { ...own, align: 'right', indentLeft: 0, indentRight: 0, firstLine: 0, spaceBefore: 0, spaceAfter: 0, whiteSpace: 'nowrap', underline: false, strike: false, hyphens: 'manual' }
  const width = Math.max(1, Math.round((step - MARKER_GAP_EM) * em))
  return { layout: layoutParagraph(sheet.fonts, plain, marker, width), x: indent + Math.round(left * em) }
}

/** How wide the box a heading's number is right-aligned in is, in em: room for "10.10.10" in a heading's size. */
const HEADING_NUMBER_EM = 5

/** The number of a numbered heading (E9.22): in the heading's own look, right-aligned in a box that ends a marker gap
 *  before the heading's text, so it hangs into the margin as the editor draws it. */
function headingNumberOf(sheet: Styles, own: ParagraphStyle, marker: string, em: number): FlowBlock['marker'] {
  const plain: ParagraphStyle = { ...own, align: 'right', indentLeft: 0, indentRight: 0, firstLine: 0, spaceBefore: 0, spaceAfter: 0, whiteSpace: 'nowrap', hyphens: 'manual' }
  const width = Math.round(HEADING_NUMBER_EM * em)
  return { layout: layoutParagraph(sheet.fonts, plain, marker, width), x: own.indentLeft - Math.round(MARKER_GAP_EM * em) - width }
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
  for (const id of new Set(doc.blocks.filter((b) => b.item && b.label?.marker).map((b) => b.style))) {
    const face = styleFont(markerCss(cssOf(styles, id, BODY)), resolver)
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
  const lists = doc.lists ?? []
  const schemes = doc.schemes ?? []
  const blocks: FlowBlock[] = doc.blocks.map((b, index) => {
    const r = sheet.paragraph(b.style)
    const item = itemGeometry(doc.blocks, index, lists, schemes)
    const em = r.style.size
    const style: ParagraphStyle = {
      ...r.style,
      keepWithNext: keepsWithNext(b.style, styles),
      // a list item's text starts after its marker's box; the gap to the next item of its list replaces its space after
      ...(item ? { indentLeft: r.style.indentLeft + Math.round(item.pad * em) } : {}),
      ...(item && item.gap !== null ? { spaceAfter: Math.round(item.gap * em) } : {}),
    }
    if (style.hyphens === 'auto' && b.text) wantsHyphens = true
    const inset = insets(r.decoration)
    const width = box.w - inset.left - inset.right
    const marker = !b.label?.marker
      ? undefined
      : item
        ? markerOf(sheet, b.style, b.label.marker, r.style.indentLeft, item.left, item.step, em)
        : headingNumberOf(sheet, r.style, b.label.marker, em)
    return { id: b.id, layout: layoutParagraph(fonts, style, b.text, width, paragraphOptions), decoration: r.decoration, ...(marker ? { marker } : {}) }
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

