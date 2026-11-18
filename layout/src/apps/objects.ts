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
import { type DisplayItem, type DisplayPage, type GroupItem, type PathOp, type Rect, rectPath } from '../display/list'
import { lineItems } from '../display/text'
import { outlinePath, PathError } from '../display/svgpath'
import type { PageGeometry } from '../flow/paper'
import { contentBox } from '../flow/paper'
import type { FontSet } from '../fonts/fontset'
import { type FontResolver, parseFamilies, type Resolution } from '../fonts/resolve'
import { drawSvg, parseSvg, type SvgDocument, SvgError, svgFonts } from '../svg/render'
import { boxItems, layoutBox } from '../text/box'
import { type BoxDecoration, boxDecorationFromCss, type Css, paragraphStyleFromCss, parseColor, type StyleFromCss } from '../text/css'
import { DOT_EM, DOT_STEP_EM, LEADER_GAP_EM } from '../text/leader'
import { MARKER_GAP_EM, markerCss } from '../text/list-geometry'
import { layoutParagraph, type ParagraphLayout, type ParagraphOptions } from '../text/paragraph'
import { paragraphStyle, type ParagraphStyle, type Rgba } from '../text/style'

/** A style as the server sends it: `resolved` is its CSS with parents taken in and palette roles replaced. */
export interface TextStyle {
  id: string
  based_on: string | null
  resolved: Css
  /** The heading level the style gives a paragraph, its parents taken in: 0 the title, 1 to 9 a section, null or
   *  absent none (E9.22). The server works it out; nothing here walks the parents to guess it from a name. */
  heading?: number | null
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

/** The kinds of floating object, as `claudia_core.OBJECT_KINDS` names them (`tests/test_object_kinds_agree.py` keeps the
 *  two lists the same). A `rendered` object is a text container that shows a picture once somebody drew one. */
export type ObjectKind = 'text' | 'shape' | 'image' | 'diagram' | 'rendered' | 'table'

/** A floating object, the shape all three apps share (without its app's anchor). Lengths in CSS pixels. */
export interface VisualObject {
  id: string
  kind: ObjectKind
  w: number
  h: number
  style: string
  /** Its words; `mark` is what is drawn before them (a list item's marker or a numbered title's number, counted by the
   *  server, E9.21, E9.22) and how far their level moves them in, in em. */
  paragraph: { style: string; text: string; mark?: ObjectMark | null; agenda?: Agenda | null } | null
  shape: string | null
  image: string | null
  rotation: number
}
/** The lines of an agenda (E9.31), derived by the server from the slide titles: each line's words (its number and the
 *  title) and its place (the slide number, or `null`), drawn right-aligned a leader away from the words. */
export interface Agenda {
  lines: readonly { words: string; place: string | null }[]
  leader: 'dots' | 'none'
}
/** What is drawn before the words of an object: the marker, and how far the level moves the words in (em). */
export interface ObjectMark {
  marker: string
  indent: number
}

/** The words of an object laid out in their box, with the marker before them on their first line, as the web app's
 *  `ParagraphWords` draws them: the words moved in by their level, the first line by the marker and a marker gap. */
function wordsBox(
  fonts: FontSet,
  text: string,
  style: ParagraphStyle,
  mark: ObjectMark | null | undefined,
  size: { w: number; h: number },
  decoration: BoxDecoration | undefined,
  align: 'top' | 'middle' | 'bottom',
  options: ParagraphOptions,
): { laid: ReturnType<typeof layoutBox>; marker: ParagraphLayout | null } {
  if (!mark?.marker) return { laid: layoutBox(fonts, text, style, size.w, size.h, decoration, align, options), marker: null }
  const em = style.size
  const plain: ParagraphStyle = { ...style, align: 'left', indentLeft: 0, indentRight: 0, firstLine: 0, whiteSpace: 'nowrap', hyphens: 'manual' }
  const marker = layoutParagraph(fonts, plain, mark.marker, size.w) // nowrap: one line, however wide
  const room = (marker.lines[0]?.natural ?? 0) + Math.round(MARKER_GAP_EM * em)
  const moved: ParagraphStyle = { ...style, indentLeft: style.indentLeft + Math.round(mark.indent * em), firstLine: style.firstLine + room }
  return { laid: layoutBox(fonts, text, moved, size.w, size.h, decoration, align, options), marker }
}

/** The display group of words laid out by `wordsBox`, the marker on the first line just before the words. */
function wordsItems(fonts: FontSet, laid: ReturnType<typeof layoutBox>, marker: ParagraphLayout | null, x: number, y: number, rotation = 0): GroupItem {
  const group = boxItems(fonts, laid, x, y, rotation)
  const first = laid.paragraph?.lines[0]
  const mark = marker?.lines[0]
  if (first && mark && laid.visibleLines > 0 && laid.paragraph) {
    const em = laid.paragraph.style.size
    const left = x + laid.content.x + first.x - Math.round(MARKER_GAP_EM * em) - mark.natural
    group.items.push(...lineItems(fonts, marker!, mark, left, y + laid.textTop + first.baseline - mark.baseline))
  }
  return group
}

/** An agenda in its box (E9.31): its lines' words as one text, one line each, kept clear of the places on the right;
 *  each place right-aligned on the last line its words take, with a dot leader between, as `ParagraphWords` draws it. */
function agendaItems(fonts: FontSet, agenda: Agenda, style: ParagraphStyle, r: Rect, decoration: BoxDecoration, align: 'top' | 'middle' | 'bottom', options: ParagraphOptions, rotation: number): GroupItem {
  const em = style.size
  const plain: ParagraphStyle = { ...style, align: 'left', indentLeft: 0, indentRight: 0, firstLine: 0, whiteSpace: 'nowrap', hyphens: 'manual' }
  const places = agenda.lines.map((line) => (line.place ? layoutParagraph(fonts, plain, line.place, r.w) : null))
  const widest = Math.max(0, ...places.map((p) => p?.lines[0]?.natural ?? 0))
  const room = widest ? widest + Math.round(LEADER_GAP_EM * em * 2) + Math.round(DOT_STEP_EM * em * 2) : 0
  const texts = agenda.lines.map((line) => line.words.replace(/[\n\r]/g, ' '))
  const text = texts.join('\n')
  const laid = layoutBox(fonts, text, { ...style, indentRight: style.indentRight + room }, r.w, r.h, decoration, align, options)
  const group = boxItems(fonts, laid, r.x, r.y, rotation)
  const p = laid.paragraph
  if (!p) return group
  const right = r.x + laid.content.x + laid.content.w - style.indentRight
  let start = 0
  texts.forEach((words, k) => {
    const end = start + words.length
    // the laid line its words end on: the last that starts within them (an empty line has one starting where it does)
    let at = -1
    p.lines.forEach((l, i) => {
      if (l.start >= start && (l.start < end || l.start === start)) at = i
    })
    start = end + 1
    const place = places[k]?.lines[0]
    const last = p.lines[at]
    if (!place || !last || at >= laid.visibleLines) return
    const top = r.y + laid.textTop + p.lines.slice(0, at).reduce((h, l) => h + l.height, 0)
    const placeX = right - place.natural
    group.items.push(...lineItems(fonts, places[k]!, place, placeX, top + last.baseline - place.baseline))
    if (agenda.leader !== 'dots') return
    const from = r.x + laid.content.x + last.x + last.natural + Math.round(LEADER_GAP_EM * em)
    const to = placeX - Math.round(LEADER_GAP_EM * em)
    const step = Math.max(1, Math.round(DOT_STEP_EM * em))
    const size = Math.max(1, Math.round(DOT_EM * em))
    const ops: PathOp[] = []
    for (let x = to - size; x >= from; x -= step) ops.push(...rectPath({ x, y: top + last.baseline - size, w: size, h: size }))
    if (ops.length) group.items.push({ kind: 'path', ops, fill: style.color, stroke: null, lineWidth: 0 })
  })
  return group
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
  kind: 'font' | 'object' | 'hyphenation' | 'sheet' | 'pages'
  /** for `font`: the family the style asked for and the one used */
  requested?: string
  used?: string
  /** for `object`: its id and why; for `hyphenation`, `sheet` (a scale that had to be raised, a sheet with nothing
   *  to print) and `pages` (page references that did not settle): why */
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
  const used = new Set(objects.filter((o) => (o.kind === 'image' || o.kind === 'rendered') && o.image).map((o) => o.image))
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

  private readonly markers = new Map<string, ParagraphStyle>()

  constructor(
    styles: readonly TextStyle[],
    readonly fonts: FontSet,
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

  /** The paragraph style a list marker of a paragraph in style `id` is drawn in: upright, in the regular weight. */
  marker(id: string): ParagraphStyle {
    let r = this.markers.get(id)
    if (!r) {
      const got = paragraphStyleFromCss(markerCss(this.css(id)), this.resolver, this.fonts, this.language ? { language: this.language } : {})
      if (!got) throw new Error('the server has no fonts that can be used for layout')
      r = got.style
      this.markers.set(id, r)
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
    if (o.paragraph?.agenda && words) return agendaItems(fonts, o.paragraph.agenda, words.style, r, decoration, words.verticalAlign, ctx.paragraphOptions, o.rotation)
    if (o.paragraph && words) {
      const { laid, marker } = wordsBox(fonts, o.paragraph.text, words.style, o.paragraph.mark, r, decoration, words.verticalAlign, ctx.paragraphOptions)
      return wordsItems(fonts, laid, marker, r.x, r.y, o.rotation)
    }
    const laid = layoutBox(fonts, null, null, r.w, r.h, decoration, 'top', ctx.paragraphOptions)
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
      const { laid, marker } = wordsBox(fonts, o.paragraph.text, words.style, o.paragraph.mark, inner, undefined, explicit ? words.verticalAlign : 'middle', ctx.paragraphOptions)
      items.push(wordsItems(fonts, laid, marker, inner.x, inner.y))
    }
    return group(items, false)
  }
  // a rendered text container (D390) prints as the picture it shows; one nothing has drawn a picture for yet is left
  // out, as the office exports leave it out
  if (o.kind === 'rendered' && !o.image) return null
  if (o.kind === 'image' || o.kind === 'rendered') {
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
