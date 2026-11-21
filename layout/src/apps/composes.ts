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
import { DEFAULT_STYLE } from '../styles.generated'
import { layoutParagraph, type ParagraphOptions } from '../text/paragraph'
import { DOT_EM, DOT_STEP_EM, LEADER_GAP_EM } from '../text/leader'
import { itemGeometry, type ListItemRef, type ListRef, MARKER_GAP_EM, markerCss, type SchemeGeometry } from '../text/list-geometry'
import type { Hyphenator } from '../text/hyphenate'
import type { ParagraphStyle } from '../text/style'
import { insets, lineItems } from '../display/text'
import { type DisplayList, type DisplayPage, type PathOp, rectPath, walk } from '../display/list'
import { type Exclusion, MIN_SLOT_EM, type Wrap } from '../flow/exclusions'
import { type FlowBlock, type FlowItem, type FlowPage, type FlowTable, flowItems, locate, paginate } from '../flow/paginate'
import { Rows } from '../flow/rows'
import { layoutTable, type TableData, tableStyleIds } from '../flow/table'
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
  /** Set when the paragraph is a table of contents (E9.31): its entries, each a line in its own style that leads to
   *  the paragraph `target`, and whether the target's page is drawn after it, a leader away. The pages are found here:
   *  the server never paginates (step F). */
  contents?: TextContents | null
  /** The page references in the words (step I): the page the paragraph `target` starts on goes in at `at` of `text`
   *  (offsets of `text` as given, in order). Found here, in at most three passes. */
  pageRefs?: readonly { at: number; target: string }[] | null
}
/** A table of contents as the layout draws it. */
export interface TextContents {
  entries: readonly { target: string; words: string; style: string }[]
  places: boolean
  leader: 'dots' | 'none'
}
/** A heading as the PDF's outline lists it: its words, its level (0 the title) and where it starts. */
export interface OutlineEntry {
  title: string
  level: number
  page: number
  top: number
}
/** A floating object as the server sends it (the shape all three apps share), anchored to a character. */
export interface TextObject extends VisualObject {
  /** `dx`/`dy` move the object off its anchor character, in the same units as `w`/`h` (D1023). `wrap` says how the text
   *  flows round it (D1061; none saved: over the text) and `gap` how far from it, in the same units. */
  anchor: { kind: 'block'; holder: string; offset: number; dx?: number; dy?: number; wrap?: Wrap; gap?: number }
}

export interface TextDocument {
  blocks: readonly TextBlock[]
  /** the tables of the text as `tables` gives them (with `totals`); an object of kind `table` with `ref` the id of one
   *  is where it hangs (E9.32) */
  tables?: readonly TableData[]
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
  /** the page (from 1) each paragraph starts on, by id: what a table of contents prints, and Page view shows */
  pageOf: Map<string, number>
  /** the headings, for the PDF's bookmarks (E9.31) */
  outline: OutlineEntry[]
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

/** How much room a page number takes at the end of an entry's lines: "000" in the entry's look and two leader gaps. */
function placeRoom(sheet: Styles, style: ParagraphStyle): number {
  const plain: ParagraphStyle = { ...style, align: 'left', indentLeft: 0, indentRight: 0, firstLine: 0, whiteSpace: 'nowrap', hyphens: 'manual' }
  const widest = layoutParagraph(sheet.fonts, plain, '000', 1_000_000).lines[0]?.natural ?? 0
  return widest + 2 * Math.round(LEADER_GAP_EM * style.size)
}

/** For each flow block, the paragraph of the text it is (or the entry of a table of contents it draws). */
interface Origin {
  block: number
  /** set for a table: `block` is the paragraph it follows */
  table?: true
  entry?: TextContents['entries'][number]
  contents?: TextContents
  room?: number
}

/** The page (from 1) each paragraph of the text starts on, by id. */
function pagesOf(starts: ReadonlyMap<number, { page: number }>, origins: readonly Origin[], blocks: readonly TextBlock[]): Map<string, number> {
  const out = new Map<string, number>()
  for (const [i, at] of starts) if (!origins[i]!.entry && !origins[i]!.table) out.set(blocks[origins[i]!.block]!.id, at.page + 1)
  return out
}

/** A paragraph's words with its page references filled in from `known` ("000", as wide as most pages, before then). */
function withPages(block: TextBlock, known: ReadonlyMap<string, number> | null): string {
  const refs = block.pageRefs
  if (!refs?.length) return block.text
  let out = ''
  let from = 0
  for (const ref of refs) {
    out += block.text.slice(from, ref.at) + String(known?.get(ref.target) ?? '000')
    from = ref.at
  }
  return out + block.text.slice(from)
}

/** Where each flow block starts: the page (from 0), and the top of its first line on it, in page coordinates. */
function startsOf(flow: readonly FlowPage[], blocks: readonly FlowItem[]): Map<number, { page: number; top: number }> {
  const out = new Map<number, { page: number; top: number }>()
  for (const p of flow) {
    for (const l of p.lines) if (l.line === 0 && !out.has(l.block)) out.set(l.block, { page: p.index, top: l.top })
    for (const t of p.tables) if (!out.has(t.block)) out.set(t.block, { page: p.index, top: t.top })
  }
  for (let i = 0; i < blocks.length; i++) if (!out.has(i)) out.set(i, { page: 0, top: 0 }) // an empty paragraph has a line too
  return out
}

/** The page numbers of the tables of contents, right-aligned on each entry's last line with the leader before them, and
 *  each entry a link to its heading (E9.31, step F). The column was kept free when the entries were laid out. */
function contentsItems(
  fonts: FontSet,
  sheet: Styles,
  flow: readonly FlowPage[],
  blocks: readonly FlowItem[],
  origins: readonly Origin[],
  pageOf: ReadonlyMap<string, number>,
  starts: ReadonlyMap<number, { page: number; top: number }>,
  pages: DisplayPage[],
  box: { x: number; w: number },
): void {
  const targets = new Map<string, number>()
  origins.forEach((o, i) => {
    if (!o.entry && !o.table) targets.set(blocks[i]!.id, i)
  })
  for (const p of flow) {
    for (const l of p.lines) {
      const origin = origins[l.block]!
      const { entry, contents } = origin
      if (!entry?.target || !contents) continue
      const b = blocks[l.block] as FlowBlock
      const line = b.layout.lines[l.line]!
      const target = targets.get(entry.target)
      const to = target === undefined ? undefined : starts.get(target)
      if (to) pages[p.index]!.links = [...(pages[p.index]!.links ?? []), { rect: { x: l.x + line.x, y: l.top, w: Math.max(1, line.natural), h: line.height }, page: to.page, top: to.top }]
      if (l.line !== b.layout.lines.length - 1 || !contents.places || !origin.room) continue
      const page = pageOf.get(entry.target)
      if (page === undefined) continue
      const style = b.layout.style
      const plain: ParagraphStyle = { ...style, align: 'left', indentLeft: 0, indentRight: 0, firstLine: 0, whiteSpace: 'nowrap', hyphens: 'manual' }
      const number = layoutParagraph(sheet.fonts, plain, String(page), box.w)
      const first = number.lines[0]
      if (!first) continue
      const right = box.x + box.w - (style.indentRight - origin.room)
      const left = right - first.natural
      pages[p.index]!.items.push(...lineItems(fonts, number, first, left, l.top + line.baseline - first.baseline))
      if (contents.leader !== 'dots') continue
      const em = style.size
      const from = l.x + line.x + line.natural + Math.round(LEADER_GAP_EM * em)
      const until = left - Math.round(LEADER_GAP_EM * em)
      const step = Math.max(1, Math.round(DOT_STEP_EM * em))
      const size = Math.max(1, Math.round(DOT_EM * em))
      const ops: PathOp[] = []
      for (let x = until - size; x >= from; x -= step) ops.push(...rectPath({ x, y: l.top + line.baseline - size, w: size, h: size }))
      if (ops.length) pages[p.index]!.items.push({ kind: 'path', ops, fill: style.color, stroke: null, lineWidth: 0 })
    }
  }
}

/** The distance the text keeps from an object that gives none, CSS pixels (the model's default). */
const DEFAULT_GAP = 8

/** Whether text gives way to an object: *around* and *above and below* take room, *over* and *behind* do not. */
const takesRoom = (o: TextObject): boolean => o.anchor.wrap === 'around' || o.anchor.wrap === 'above-below'

/** An object as it stands on a page: the page (from 0) and its frame in page coordinates. */
interface Standing {
  page: number
  x: number
  y: number
  w: number
  h: number
}

/** Where a paragraph's first line would stand: a page (from 0) and a top in that page's content box. */
type Start = { page: number; top: number }

/** How often text beside objects is laid out again before it is taken as it is: the first pass places the paragraphs
 *  by the rows of the text without them, and every later one by where the paragraphs then stand. */
const MAX_WRAP_PASSES = 6

/** composes' default style: what a paragraph with a style the text does not have is drawn in. */
const BODY = DEFAULT_STYLE.composes

/** The tables an object of the text shows, by the id of the object (E9.32). */
function shownTables(doc: TextDocument): Map<string, TableData> {
  const byId = new Map((doc.tables ?? []).map((t) => [t.id, t]))
  const out = new Map<string, TableData>()
  for (const o of doc.objects ?? []) {
    const table = o.kind === 'table' && o.ref ? byId.get(o.ref) : undefined
    if (table) out.set(o.id, table)
  }
  return out
}

/**
 * The SHA-256 of every font file laying out `doc` needs, as `resolver` picks them, so the caller can fetch them
 * before calling {@link layoutText}.
 */
export function fontsNeeded(doc: TextDocument, resolver: FontResolver): string[] {
  const styles = new Map(doc.styles.map((s) => [s.id, s]))
  const out = new Set<string>()
  for (const id of new Set(doc.blocks.flatMap((b) => [b.style, ...(b.contents?.entries.map((e) => e.style) ?? [])]))) {
    const face = styleFont(cssOf(styles, id, BODY), resolver)
    if (face) out.add(face)
  }
  for (const id of new Set(doc.blocks.filter((b) => b.item && b.label?.marker).map((b) => b.style))) {
    const face = styleFont(markerCss(cssOf(styles, id, BODY)), resolver)
    if (face) out.add(face)
  }
  for (const face of objectFonts(doc.objects ?? [], styles, doc.images ?? [], resolver, BODY)) out.add(face)
  for (const table of shownTables(doc).values()) {
    for (const id of tableStyleIds(table)) {
      const face = styleFont(cssOf(styles, id, BODY), resolver)
      if (face) out.add(face)
    }
  }
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
  /** The objects text gives way to, where the text without them put them (D1061). */
  let wrapping: { o: TextObject; at: Standing }[] = []
  const gapOf = (o: TextObject): number => px(o.anchor.gap ?? DEFAULT_GAP)
  /** The bands the objects of a page keep free, in the coordinates of a paragraph whose content box starts at
   *  (`left`, `top`) of the page. */
  const exclusionsOn = (page: number, left: number, top: number): Exclusion[] =>
    wrapping.filter(({ at }) => at.page === page).map(({ o, at }) => ({ box: { x: at.x - left, y: at.y - top, w: at.w, h: at.h }, wrap: o.anchor.wrap as Wrap, gap: gapOf(o) }))
  /** The flow blocks of the text, with page references as `known` has them ("000" before they are known), and for
   *  each flow block the paragraph of the text it is (or the entry of a table of contents it draws). */
  const shown = shownTables(doc)
  const tableObjects = (doc.objects ?? []).filter((o) => o.kind === 'table')
  for (const o of tableObjects) {
    const table = shown.get(o.id)
    if (!table) notes.push({ kind: 'object', object: o.id, reason: 'its table is missing' })
    else if (table.placement === 'float') notes.push({ kind: 'object', object: o.id, reason: 'a floating table is printed in the flow, below its paragraph' })
  }
  /** The tables that hang from a paragraph, in the order of their anchors, as flow items. */
  const spaceAfter = sheet.paragraph(BODY).style.spaceAfter
  const laidTables = new Map<string, FlowTable>()
  const tablesAfter = (paragraph: string): FlowTable[] =>
    tableObjects
      .filter((o) => o.anchor.holder === paragraph && shown.has(o.id))
      .sort((a, b) => a.anchor.offset - b.anchor.offset)
      .map((o) => {
        let laid = laidTables.get(o.id)
        if (!laid) {
          laid = { id: o.id, table: layoutTable(fonts, sheet, shown.get(o.id)!, box.w, paragraphOptions), spaceBefore: 0, spaceAfter }
          laidTables.set(o.id, laid)
        }
        return laid
      })
  const build = (known: ReadonlyMap<string, number> | null, around: ReadonlyMap<number, Start> | null = null) => {
    const origins: Origin[] = []
    const rows = new Map<number, Rows>()
    const withTables = (b: TextBlock, index: number, own: FlowBlock[]): FlowItem[] => {
      const after = tablesAfter(b.id)
      for (let k = 0; k < after.length; k++) origins.push({ block: index, table: true })
      return [...own, ...after]
    }
    /** the flow blocks of a paragraph (the entries of a table of contents are one each) */
    const paragraphsOf = (b: TextBlock, index: number): FlowBlock[] => {
      if (b.contents) {
        const contents = b.contents
        const entries = contents.entries.length ? contents.entries : [{ target: '', words: '', style: b.style }]
        return entries.map((entry, k) => {
          const r = sheet.paragraph(entry.style)
          // the page column has a fixed width (room for "000"), so filling it in never moves a line (mock-up D)
          const room = contents.places && entry.target ? placeRoom(sheet, r.style) : 0
          const style: ParagraphStyle = { ...r.style, indentRight: r.style.indentRight + room, keepWithNext: k < entries.length - 1 }
          const inset = insets(r.decoration)
          origins.push({ block: index, entry, contents, room })
          const id = k ? `${b.id}~${k}` : b.id
          return { id, layout: layoutParagraph(fonts, style, entry.words, box.w - inset.left - inset.right, paragraphOptions), decoration: r.decoration }
        })
      }
      origins.push({ block: index })
      const flowIndex = origins.length - 1
      const r = sheet.paragraph(b.style)
      const item = itemGeometry(doc.blocks, index, lists, schemes)
      const em = r.style.size
      const start = around?.get(flowIndex)
      const style: ParagraphStyle = {
        ...r.style,
        // beside an object a page break is where the rows say (D1062), so there is no room for widow and orphan control
        ...(start ? { orphans: 1, widows: 1 } : {}),
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
      const words = withPages(b, known)
      const options: ParagraphOptions = start
        ? {
            hyphenator,
            slots: (widest) => {
              const made = new Rows({
                start,
                lineHeight: style.lineHeight,
                pageHeight: box.h,
                column: { left: 0, right: width },
                exclusions: (page) => exclusionsOn(page, box.x + inset.left, box.y),
                minWidth: Math.max(Math.round(MIN_SLOT_EM * em), Math.min(widest, Math.floor(width / 2))),
              })
              rows.set(flowIndex, made)
              return made
            },
          }
        : paragraphOptions
      return [{ id: b.id, layout: layoutParagraph(fonts, style, words, width, options), decoration: r.decoration, ...(marker ? { marker } : {}) }]
    }
    const blocks: FlowItem[] = doc.blocks.flatMap((b, index): FlowItem[] => withTables(b, index, paragraphsOf(b, index)))
    return { blocks, origins, rows }
  }
  // ---- at most three passes: a page reference can move a line, and the line a page break (mock-up D, D901)
  const referring = doc.blocks.some((b) => b.pageRefs?.length)
  const wanted = new Set(doc.blocks.flatMap((b) => (b.pageRefs ?? []).map((ref) => ref.target)))
  let known: Map<string, number> | null = null
  let built = build(null)
  let flow = paginate(built.blocks, geometry)
  let starts = startsOf(flow, built.blocks)
  let pageOf = pagesOf(starts, built.origins, doc.blocks)
  for (let pass = 2; referring && pass <= 3; pass++) {
    if (known && [...wanted].every((target) => known!.get(target) === pageOf.get(target))) break
    known = pageOf
    built = build(known)
    flow = paginate(built.blocks, geometry)
    starts = startsOf(flow, built.blocks)
    pageOf = pagesOf(starts, built.origins, doc.blocks)
    if (pass === 3 && [...wanted].some((target) => known!.get(target) !== pageOf.get(target))) {
      notes.push({ kind: 'pages', reason: 'the page references did not settle in three passes; some may be one page off' })
    }
  }
  // ---- text round the objects that take room (D1061, D1062)
  /** An object's frame on the page its anchor character stands on in `at`, kept inside the margins across and above the
   *  bottom margin, or `null` when the character is nowhere. */
  const standing = (o: TextObject, at: { flow: readonly FlowPage[]; blocks: readonly FlowItem[] }): Standing | null => {
    const index = at.blocks.findIndex((b) => b.id === o.anchor.holder)
    const spot = index < 0 ? null : locate(at.flow, at.blocks, index, o.anchor.offset)
    if (!spot) return null
    const w = px(o.w)
    const h = px(o.h)
    const x = Math.max(box.x, Math.min(spot.x + px(o.anchor.dx ?? 0), box.x + box.w - w))
    const y = Math.max(box.y, Math.min(spot.top + px(o.anchor.dy ?? 0), geometry.height - geometry.margin.bottom - h))
    return { page: spot.page, x, y, w, h }
  }
  wrapping = (doc.objects ?? []).filter((o) => o.kind !== 'table' && takesRoom(o)).flatMap((o) => {
    const at = standing(o, { flow, blocks: built.blocks })
    return at ? [{ o, at }] : []
  })
  if (wrapping.length) {
    /** The paragraph a line stands in: a placed line belongs to a paragraph, never to a table. */
    const paragraphAt = (index: number): FlowBlock => built.blocks[index] as FlowBlock
    /** The paragraphs the objects may reach, with where each starts (before a row was pushed down), by flow block. */
    const reached = (): Map<number, Start> => {
      const first = new Map<number, Start>()
      const last = new Map<number, number>()
      for (const pg of flow) {
        for (const l of pg.lines) {
          if (l.line === 0 && !first.has(l.block)) first.set(l.block, { page: pg.index, top: l.top - (paragraphAt(l.block).layout.lines[0]!.lead ?? 0) - box.y })
          last.set(l.block, pg.index)
        }
      }
      const out = new Map<number, Start>()
      for (const [i, at] of first) {
        if (built.origins[i]!.entry) continue
        const end = last.get(i)!
        if (wrapping.some(({ o, at: s }) => s.page >= at.page && s.page <= end + 1 && (s.page > at.page || s.y - box.y + s.h + gapOf(o) > at.top))) out.set(i, at)
      }
      return out
    }
    /** Every line of a wrapped paragraph stands where its row said it would. */
    const agree = (): boolean => {
      for (const pg of flow) {
        for (const l of pg.lines) {
          const r = built.rows.get(l.block)?.place(l.line)
          if (r && (r.page !== pg.index || r.y !== l.top - box.y)) return false
        }
      }
      return true
    }
    let from = reached()
    let settled = from.size === 0
    for (let pass = 0; !settled && pass < MAX_WRAP_PASSES; pass++) {
      const using = referring ? pageOf : null
      built = build(using, from)
      flow = paginate(built.blocks, geometry)
      starts = startsOf(flow, built.blocks)
      pageOf = pagesOf(starts, built.origins, doc.blocks)
      const next = reached()
      settled = next.size === from.size && [...next].every(([i, at]) => from.get(i)?.page === at.page && from.get(i)?.top === at.top) && agree() && (!using || [...wanted].every((t) => using.get(t) === pageOf.get(t)))
      from = next
    }
    if (!settled) notes.push({ kind: 'wrap', reason: 'the text round the objects did not settle in six passes; a line may be a page off' })
  }
  const { blocks, origins } = built
  if (wantsHyphens && !hyphenator) {
    notes.push({
      kind: 'hyphenation',
      reason: doc.language ? `there are no hyphenation patterns for ${doc.language}, so words are not hyphenated` : 'the text has no language set, so words are not hyphenated',
    })
  }
  const pages: DisplayPage[] = flowItems(fonts, flow, blocks, geometry)
  contentsItems(fonts, sheet, flow, blocks, origins, pageOf, starts, pages, box)

  // ---- floating objects, where they hang: the ones text gave way to where the text without them put them, the others
  // where their character stands now (over or behind the text, which does not give way)
  const shapes = new Map((doc.shapes ?? []).map((s) => [s.id, s]))
  const images = new Map((doc.images ?? []).map((i) => [i.id, i]))
  const usedImages: string[] = []
  const embedded = new Map<string, Uint8Array>()
  const placed = new Map(wrapping.map(({ o, at }) => [o.id, at]))
  for (const o of doc.objects ?? []) {
    if (o.kind === 'table') continue // in the flow, above
    const at = placed.get(o.id) ?? standing(o, { flow, blocks })
    if (!at) continue
    const group = drawObject(o, { x: at.x, y: at.y, w: at.w, h: at.h }, { fonts, resolver, styles: sheet, shapes, images, notes, embedded, paragraphOptions, diagramNote: 'charts cannot be printed from a text yet' })
    if (!group) continue
    for (const it of walk(group.items)) if (it.kind === 'image' && !usedImages.includes(it.image)) usedImages.push(it.image)
    // behind the text it is drawn first, so the words lie over it
    if (o.anchor.wrap === 'behind') pages[at.page]!.items.unshift(group)
    else pages[at.page]!.items.push(group)
  }

  // ---- page numbers, centred in the bottom margin (the same in every app)
  if (p.page_numbers) pageNumberItems(fonts, pages, geometry, sheet.paragraph(BODY).style)

  const outline: OutlineEntry[] = []
  for (const [i, at] of starts) {
    if (origins[i]!.table) continue
    const b = doc.blocks[origins[i]!.block]!
    const level = origins[i]!.entry ? null : styles.get(b.style)?.heading
    if (level !== null && level !== undefined && b.text.trim()) outline.push({ title: b.text.trim(), level, page: at.page, top: at.top })
  }

  return {
    list: { layoutVersion: LAYOUT_VERSION, shaper: fonts.shaperId, ...(hyphenator ? { hyphenation: hyphenator.id } : {}), pages },
    pageOf,
    outline,
    geometry,
    notes,
    images: usedImages,
    embedded,
  }
}

