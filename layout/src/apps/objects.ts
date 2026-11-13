/**
 * What every app's pages are made of besides its own content (D917): the styles as the server sends them, the
 * floating objects all three apps share (text boxes, shapes, pictures; E10.16), the notes a preview shows, and page
 * numbers. composes places objects where they hang in its text; creates places them on its slides; both draw them
 * here, the same way, so a text box or a picture prints alike in either app.
 *
 * Lengths of objects and of their CSS are CSS pixels (96 px = 72 pt): composes measures its objects so, and a
 * creates slide is 1600 × 900 px.
 *
 * @module
 */
import { type DisplayItem, type DisplayPage, type GroupItem, type Rect, rectPath } from '../display/list'
import { lineItems } from '../display/text'
import { outlinePath, PathError } from '../display/svgpath'
import type { PageGeometry } from '../flow/paper'
import { contentBox } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import { type FontResolver, parseFamilies, type Resolution } from '../fonts/resolve'
import { drawSvg, parseSvg, type SvgDocument, SvgError, svgFonts } from '../svg/render'
import { boxItems, layoutBox } from '../text/box'
import { type BoxDecoration, boxDecorationFromCss, type Css, paragraphStyleFromCss, parseColor, type StyleFromCss } from '../text/css'
import { layoutParagraph, type ParagraphOptions } from '../text/paragraph'
import { paragraphStyle, type ParagraphStyle, type Rgba } from '../text/style'

/** A style as the server sends it: `resolved` is its CSS with parents taken in and palette roles replaced. */
export interface TextStyle {
  id: string
  based_on: string | null
  resolved: Css
}

/** The page a document prints on, as the server sends it (D904, D917): lengths in mpt, `margins` top, right,
 *  bottom, left; `width` the short side. */
export interface PageSetupData {
  paper: string
  width: number
  height: number
  orientation: 'portrait' | 'landscape'
  margins: [number, number, number, number]
  page_numbers: boolean
}

/** A floating object, the shape all three apps share (without its app's anchor). Lengths in CSS pixels. */
export interface VisualObject {
  id: string
  kind: 'text' | 'shape' | 'image' | 'diagram'
  w: number
  h: number
  style: string
  paragraph: { style: string; text: string } | null
  shape: string | null
  image: string | null
  rotation: number
}
/** An outline: an SVG path in a box of 100 × 100, and where its words go. */
export interface ShapeOutline {
  id: string
  path: string
  text_area: { x: number; y: number; w: number; h: number }
}
/** A picture the document holds: its format, and for an SVG picture its text (D914), so it can be drawn. */
export interface ImageInfo {
  id: string
  format: string
  svg?: string
}

/**
 * Something the person should know about the pages: a font that was replaced, an object that cannot be printed (or
 * not all of it), words that are not hyphenated because the language is not known or has no patterns.
 */
export interface Note {
  kind: 'font' | 'object' | 'hyphenation'
  /** for `font`: the family the style asked for and the one used */
  requested?: string
  used?: string
  /** for `object`: its id and why; for `hyphenation`: why */
  object?: string
  reason?: string
  /** for `object`: the object is printed, only this part of it is not (an SVG picture's filters, say) */
  partial?: boolean
}

/** CSS pixels to mpt (96 px = 72 pt). */
export const px = (n: number): number => Math.round(n * 750)

/** A style's CSS, or the document's default style's when it has no such style. */
export const cssOf = (styles: ReadonlyMap<string, TextStyle>, id: string, fallback: string): Css => styles.get(id)?.resolved ?? styles.get(fallback)?.resolved ?? {}

const weight = (css: Css) => {
  const v = (css['font-weight'] ?? '').toLowerCase()
  return v === 'bold' ? 700 : v === '' || v === 'normal' ? 400 : Number(v) || 400
}

/** The font file a style's words need, as `resolver` picks it. */
export function styleFont(css: Css, resolver: FontResolver): string | null {
  return resolver.resolve(css['font-family'] ?? 'sans-serif', weight(css), /^(italic|oblique)$/i.test(css['font-style'] ?? ''), 12000)?.face.sha256 ?? null
}

/** The fonts the objects need: their words' styles, and the text inside their SVG pictures. */
export function objectFonts(objects: readonly VisualObject[], styles: ReadonlyMap<string, TextStyle>, images: readonly ImageInfo[], resolver: FontResolver, fallback: string): Set<string> {
  const out = new Set<string>()
  for (const o of objects) {
    if (!o.paragraph) continue
    const face = styleFont(cssOf(styles, o.paragraph.style, fallback), resolver)
    if (face) out.add(face)
  }
  const used = new Set(objects.filter((o) => o.kind === 'image' && o.image).map((o) => o.image))
  for (const image of images) {
    if (!image.svg || !used.has(image.id)) continue
    try {
      for (const h of svgFonts(parsedSvg(image), resolver)) out.add(h)
    } catch (e) {
      if (!(e instanceof SvgError)) throw e
    }
  }
  return out
}

/**
 * The styles of a document as paragraph styles, each resolved once, with a note for every family asked for and
 * not on the server. `fallback` is the document's default style (`body` in composes, `body-text` in creates).
 */
export class Styles {
  private readonly resolved = new Map<string, StyleFromCss>()
  private readonly noted = new Set<string>()
  readonly byId: ReadonlyMap<string, TextStyle>

  constructor(
    styles: readonly TextStyle[],
    private readonly fonts: FontSet,
    private readonly resolver: FontResolver,
    private readonly language: string | null | undefined,
    readonly fallback: string,
    readonly notes: Note[],
  ) {
    this.byId = new Map(styles.map((s) => [s.id, s]))
  }

  css(id: string): Css {
    return cssOf(this.byId, id, this.fallback)
  }

  /** The paragraph style of a style id. */
  paragraph(id: string): StyleFromCss {
    let r = this.resolved.get(id)
    if (!r) {
      const css = this.css(id)
      const got = paragraphStyleFromCss(css, this.resolver, this.fonts, this.language ? { language: this.language } : {})
      if (!got) throw new Error('the server has no fonts that can be used for layout')
      // a style that names a font first and gets it is exact; only report a family that was asked for and missed
      if (parseFamilies(css['font-family'] ?? '').length) this.note(got.font)
      r = got
      this.resolved.set(id, r)
    }
    return r
  }

  private note(r: Resolution) {
    if (r.how === 'exact' || r.how === 'substitute') return
    const key = `${r.requested}\u0000${r.family}`
    if (this.noted.has(key)) return
    this.noted.add(key)
    this.notes.push({ kind: 'font', requested: r.requested, used: r.family })
  }
}

/** What drawing objects needs. `embedded` collects the bytes of pictures inside SVG pictures. */
export interface ObjectContext {
  fonts: FontSet
  resolver: FontResolver
  styles: Styles
  shapes: ReadonlyMap<string, ShapeOutline>
  images: ReadonlyMap<string, ImageInfo>
  notes: Note[]
  embedded: Map<string, Uint8Array>
  paragraphOptions: ParagraphOptions
  /** what a diagram is called in the note when it cannot be printed */
  diagramNote: string
}

const parsed = new WeakMap<ImageInfo, SvgDocument>()
/** An SVG picture read once (finding its fonts and drawing it both need it). */
function parsedSvg(image: ImageInfo): SvgDocument {
  let doc = parsed.get(image)
  if (!doc) {
    doc = parseSvg(image.svg ?? '')
    parsed.set(image, doc)
  }
  return doc
}

/** How far a shape's words stay from its outline: 8 px, as creates draws them on screen. */
const LABEL_INSET = px(8)

/**
 * One object drawn into `r` (mpt): a text box laid out in its box, a shape's outline and its words (centred in its
 * text area unless the words' style says otherwise), a picture (an SVG one as what it is made of, D914), all
 * rotated about the centre and cut at the box. `null` (with a note) for what cannot be drawn.
 */
export function drawObject(o: VisualObject, r: Rect, ctx: ObjectContext): GroupItem | null {
  const { fonts, styles, shapes, images, notes } = ctx
  const boxCss = styles.css(o.style)
  const decoration: BoxDecoration = boxDecorationFromCss(boxCss, 12000)
  const group = (items: DisplayItem[], clip = true): GroupItem => ({
    kind: 'group',
    clip: clip ? r : null,
    rotation: Math.round(o.rotation || 0),
    origin: { x: r.x + Math.floor(r.w / 2), y: r.y + Math.floor(r.h / 2) },
    items,
  })
  if (o.kind === 'text') {
    const words = o.paragraph ? styles.paragraph(o.paragraph.style) : null
    const laid = layoutBox(fonts, o.paragraph?.text ?? null, words?.style ?? null, r.w, r.h, decoration, words?.verticalAlign ?? 'top', ctx.paragraphOptions)
    return boxItems(fonts, laid, r.x, r.y, o.rotation)
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
      const inner: Rect = {
        x: r.x + Math.round((area.x * r.w) / 100) + LABEL_INSET,
        y: r.y + Math.round((area.y * r.h) / 100) + LABEL_INSET,
        w: Math.max(0, Math.round((area.w * r.w) / 100) - 2 * LABEL_INSET),
        h: Math.max(0, Math.round((area.h * r.h) / 100) - 2 * LABEL_INSET),
      }
      const words = styles.paragraph(o.paragraph.style)
      const explicit = styles.css(o.paragraph.style)['vertical-align']
      const laid = layoutBox(fonts, o.paragraph.text, words.style, inner.w, inner.h, undefined, explicit ? words.verticalAlign : 'middle', ctx.paragraphOptions)
      items.push(boxItems(fonts, laid, inner.x, inner.y))
    }
    return group(items, false)
  }
  if (o.kind === 'image') {
    const info = o.image ? images.get(o.image) : undefined
    const placeholder = () => group([{ kind: 'path', ops: rectPath(r), fill: null, stroke: { r: 150, g: 150, b: 150, a: 255 }, lineWidth: 500, dash: [3000, 2000] }])
    if (info?.format === 'svg' && info.svg !== undefined) {
      // an SVG picture is drawn as what it is made of (D914), into the object's box
      try {
        const drawing = drawSvg(parsedSvg(info), r, { fonts, resolver: ctx.resolver })
        for (const reason of drawing.notes) notes.push({ kind: 'object', object: o.id, reason, partial: true })
        for (const [id, bytes] of drawing.images) ctx.embedded.set(id, bytes)
        return group([drawing.item])
      } catch (e) {
        if (!(e instanceof SvgError)) throw e
        notes.push({ kind: 'object', object: o.id, reason: 'its SVG picture cannot be read' })
        return placeholder()
      }
    }
    if (!info || !['png', 'jpeg', 'gif', 'bmp'].includes(info.format)) {
      notes.push({ kind: 'object', object: o.id, reason: 'its picture is missing' })
      return placeholder()
    }
    return group([{ kind: 'image', image: info.id, ...r }])
  }
  notes.push({ kind: 'object', object: o.id, reason: ctx.diagramNote })
  return null
}

/** A colour, lighter: what page numbers are drawn in. */
export const muted = (c: Rgba): Rgba => ({ ...c, a: Math.round((c.a * 65) / 100) })

/** The size of page numbers: 9 pt, in every app. */
export const PAGE_NUMBER_SIZE = 9000

/**
 * "n / N" on every page, centred in the bottom margin, 9 pt in the font and a lighter shade of the colour of the
 * document's body text — the same in every app. The bottom margin should be at least {@link PAGE_NUMBER_BAND} high.
 */
export function pageNumberItems(fonts: FontSet, pages: DisplayPage[], geometry: PageGeometry, base: ParagraphStyle): void {
  const box = contentBox(geometry)
  const size = PAGE_NUMBER_SIZE
  const style = paragraphStyle(base.face, size, { lineHeight: Math.round(size * 1.2), align: 'center', color: muted(base.color) })
  pages.forEach((page, i) => {
    const line = layoutParagraph(fonts, style, `${i + 1} / ${pages.length}`, box.w)
    const top = geometry.height - Math.floor((geometry.margin.bottom + line.height) / 2)
    page.items.push(...lineItems(fonts, line, line.lines[0]!, box.x, top))
  })
}

/** The height page numbers need below the content when a page has (almost) no bottom margin: 8 mm. */
export const PAGE_NUMBER_BAND = 22677
