// One person's view of one text: the paragraphs the screen draws, kept up to date from the server's events, and the
// ways of writing into them. Everything a person does is a request; the text changes when the server's events say so.
//
// Typing is the one thing that is not shown only after the answer: the characters of the word being typed wait in
// `pending` (drawn at the caret, marked as not yet written) and go out as one request when the word ends, after a pause,
// or before anything else the person does. So a word is one step in the history, and typing does not wait for the network.
import { parseFence } from './containers'
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import {
  applyEvent,
  eventInUnits,
  followPos,
  followSpan,
  indexOf,
  ordered,
  pointOf,
  runsToUnits,
  unitOf,
  wordEnd,
  wordStart,
  textBetween,
  type Paragraph,
  type ListItem,
  type Pos,
  type TextEvent,
} from './paragraphs'
import { NEW_OBJECT_CAP, type ImageAsset } from './images'
import { othersOn, type Other, type ParagraphAnchor, type PaletteEvent, type StyleModel, type StyleTarget, type VisualObject } from './objects'
import { NEW_OBJECT_WRAP, nextWrap, wrapOf, wrapParams, type Wrap } from './wrap'
import { DEFAULT_STYLE, type PageSetupData, type ShapeOutline, type TextObject } from '@claudia/layout'
import type { LinkLike, Region, WireData } from './protocol'
import type { ListInfo, SchemeInfo } from './numbering'
import { FIELD_CHAR, fieldIndex, plain, type ReferenceTarget, type RefField, type Show, type Shown } from './references'
import { MAX_NAME, type Thing, type ThingKind } from './tags'
import type { Deleted, DeleteHow } from './style-deletion'
import { headingLevel, styleUses, type CssEdit, type StyleView } from './style-css'
import { isBoxId, oneLine, type TableEntry, type TableEvent, type TableInfo, withEvent } from './tables'
import { translate as t } from './i18n'


export interface SuggestionInfo {
  id: string
  author: string | null
  paragraph: string
  start: number
  end: number
  original: string
  /** `null` for a remark, which suggests no change. */
  replacement: string | null
  reason: string
  state: string
  outdated: boolean
}
export type { ListInfo, SchemeInfo } from './numbering'
export interface Selection {
  anchor: Pos
  focus: Pos
}
/** Characters that are written but not (yet) in the document, and where they go. */
export interface Unwritten {
  at: Pos
  text: string
}
export interface TextState extends BaseState {
  /** The document's styles, by id, in the order the server lists them (D1432). */
  styles: Record<string, StyleView>
  /** What a style property means and where a style can go: the server's `style_model` (D303, D304). */
  styleModel: StyleModel | null
  paragraphs: Paragraph[]
  lists: ListInfo[]
  schemes: SchemeInfo[]
  suggestions: SuggestionInfo[]
  selection: Selection | null
  /** Typed and kept back until the word ends. */
  pending: Unwritten | null
  /** On its way to the server. */
  sending: Unwritten | null
  /** The page the text is printed on (D904); `null` until loaded or for a server that does not know pages. */
  page: PageSetupData | null
  /** The floating objects, by id (a container is one): each hangs from a character of a paragraph (D179). */
  objects: Record<string, VisualObject<ParagraphAnchor>>
  /** The outlines the shapes among the objects are drawn with, by id (the server's `shapes`). */
  shapes: Record<string, TextShape>
  /** The outlines the server offers for insertion (Edit ▸ the shapes), as creates has them. */
  library: TextShape[]
  /** The object a person has selected here; this is not shared with colleagues. */
  selectedObject: string | null
  /** The container whose text is being written in its own editor, or `null`; not shared. The object menu's
   * Edit text and Enter set it, and `TextObjectLayer.vue` shows the editor. */
  editingObject: string | null
  /** The tables of the text by id (E9.32): what the objects of kind `table` point at with `ref`. */
  tables: Record<string, TableInfo>
  /** The box of a table the caret is in, or `null`; not shared with colleagues. Edit ▸ Row, Column, Sort and the
   *  other table entries are only there while it is set. */
  box: { table: string; row: string; col: string } | null
}

/** An outline as the server sends it (`shapes`): `path` is an SVG path in a box of 100 by 100, `aspect` is width / height
 * when it must be kept. The same as creates' `ShapeDef`. */
export interface TextShape {
  format: number
  id: string
  name: string
  path: string
  aspect: number | null
  text_area: { x: number; y: number; w: number; h: number }
}

/** What `shapes` answers: the outlines the server offers and the ones this document has taken in, as in creates. */
interface ShapeAnswer {
  library: TextShape[]
  document: TextShape[]
}

/** A server from before the texts had a library answered `shapes` with the list of the document's outlines alone. */
function shapesOf(answer: ShapeAnswer | TextShape[]): ShapeAnswer {
  return Array.isArray(answer) ? { library: [], document: answer } : answer
}

/** An image of the text as the server sends it (`images`): base64 data. */
export interface TextImage {
  id: string
  format: string
  data: string
}
/** What the print preview needs beyond the paragraphs: the floating objects and what they are drawn with (D907). */
export interface PrintExtras {
  objects: TextObject[]
  shapes: ShapeOutline[]
  images: TextImage[]
  /** the tables, with their total rows (E9.32); none from a server that has no tables */
  tables?: TableInfo[]
}

export const IDLE_FLUSH_MS = 700
export const PLACE_MS = 150
export const ZONE_WORDS = 3
const WORD_END = /[\s.,;:!?)\]}"”»]$/u

const same = (a: Pos, b: Pos) => a.paragraph === b.paragraph && a.offset === b.offset
const collapsed = (pos: Pos): Selection => ({ anchor: { ...pos }, focus: { ...pos } })

export class TextSession extends BaseSession<TextState> {
  private chain: Promise<unknown> = Promise.resolve()
  private jobs = 0
  private idle: ReturnType<typeof setTimeout> | null = null
  private placing: ReturnType<typeof setTimeout> | null = null
  private placed = ''
  private moved = 0
  /** How often the caret had been moved by the person when the pending words were begun (see `sendPending`). */
  private typedAt = 0
  /** What the page selected in the words not sent yet (Home or Shift+Home right after typing, D1350, UX-100): selected
   *  once they are sent. */
  private unsentSelection: { at: Pos; anchor: Pos; focus: Pos } | null = null
  private ready = false
  private flushQueued = false

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, { styleModel: null, paragraphs: [], lists: [], schemes: [], suggestions: [], selection: null, pending: null, sending: null, page: null, library: [], selectedObject: null, editingObject: null, tables: {}, box: null })
  }

  // ------------------------------------------------------------------------------ floating objects (D560)
  /** The objects that hang from the paragraph `paragraph`, in the order the server sent them. */
  objectsIn(paragraph: string): VisualObject<ParagraphAnchor>[] {
    return Object.values(this.state.objects).filter((o) => o.anchor.holder === paragraph)
  }

  /** The server counts a place in a paragraph in characters, the screen in UTF-16 units. */
  private placeOnWire(place: { paragraph: string; offset: number }): { paragraph: string; offset: number } {
    const paragraph = this.state.paragraphs.find((b) => b.id === place.paragraph)
    return { paragraph: place.paragraph, offset: paragraph ? pointOf(paragraph.text, place.offset) : place.offset }
  }

  /** Where an object hangs, in the units of the screen (the server counts characters, the page UTF-16 units), or `null`
   * while its paragraph is not known here. */
  placeOf(o: VisualObject<ParagraphAnchor>): { paragraph: string; offset: number } | null {
    const paragraph = this.state.paragraphs.find((b) => b.id === o.anchor.holder)
    return paragraph ? { paragraph: paragraph.id, offset: Math.min(unitOf(paragraph.text, o.anchor.offset), paragraph.text.length) } : null
  }

  /** Select an object (`null`: none), which locks it as in the other apps (D1223); a colleague who has it locked keeps
   * it, and the person is told. The lock replaces the words held round the caret, which are held again once no object
   * is selected.
   * `paragraph` is the one a new object hangs from, before the server has told of it. */
  async selectObject(id: string | null, paragraph?: string): Promise<void> {
    const s = this.state
    if (id === s.selectedObject) return
    s.selectedObject = id
    this.placed = ''
    if (!(await this.lockObject(id, paragraph)) && s.selectedObject === id) s.selectedObject = null
    if (s.selectedObject === null) this.place()
  }

  /** The objects of this text that colleagues have selected, and whether they have them locked. */
  selectedByOthers(): Other[] {
    const paragraphs = this.state.paragraphs
    return othersOn(this.state, (holder) => paragraphs.some((b) => b.id === holder))
  }

  /** Hang a container of `type` from `place` (a paragraph and a place in it, in screen units); its id, or `null` after
   * telling the person why not. It is selected, ready to be written in. The words go above and below it, as they do
   * for a new picture (D1334). */
  async addContainer(type: string, place: { paragraph: string; offset: number }, size: { w: number; h: number }): Promise<string | null> {
    await this.flush()
    const id = await this.addContainerAt(type, this.newObjectAt(place), size, undefined, true)
    if (id) await this.selectObject(id, place.paragraph)
    return id
  }

  /** Where a new container goes on the wire: the place, and the wrap every new object gets (D1061, D1334). */
  private newObjectAt(place: { paragraph: string; offset: number }): Record<string, unknown> {
    return { ...this.placeOnWire(place), ...wrapParams(NEW_OBJECT_WRAP) }
  }

  /** Pasted text that is one fenced block (```latex … ```) of a type the server makes becomes a container at `place`
   * (D560); its id, or `null` if it is not such a block (the caller pastes it as text then). */
  async pasteFence(text: string, place: { paragraph: string; offset: number }): Promise<string | null> {
    const fenced = parseFence(text.trim(), this.state.containerTypes.map((k) => k.type))
    if (!fenced) return null
    await this.flush()
    const id = await this.addContainerAt(fenced.type, this.newObjectAt(place), NEW_OBJECT_CAP, fenced.source, true)
    if (id) await this.selectObject(id, place.paragraph)
    return id
  }

  /**
   * Import a picture from disk and hang it from `place` (a paragraph and a place in it, in screen units); its id, or
   * `null` after telling the person why not. It is selected. `data` is the file's bytes, base64 (`lib/images.ts`'s
   * `fileToBase64`); `sourcePath` is the file's full path if the caller could get one — a plain web browser cannot,
   * for its own security — and `null` if not. The same request as creates' (`add_image`), with a place in the text.
   */
  async addImage(
    picture: { data: string; alt: string; sourceName: string; sourcePath: string | null; decorative?: boolean; fit?: boolean },
    place: { paragraph: string; offset: number },
    size: { w: number; h: number },
    wrap?: Wrap,
  ): Promise<string | null> {
    const id = await this.putPicture(picture, { ...this.placeOnWire(place), ...(wrap ? wrapParams(wrap) : {}), ...size })
    if (id) await this.selectObject(id, place.paragraph)
    return id
  }

  /** Hang a text box (`kind` `text`) or a shape (with the id of its outline, from the library or the document) from
   * `place`; its id, or `null` after telling the person why not. It is selected. `wrap` says how the text flows round it. */
  private async addBox(
    kind: { kind: 'text' } | { kind: 'shape'; shape: string },
    place: { paragraph: string; offset: number },
    size: { w: number; h: number },
    wrap?: Wrap,
  ): Promise<string | null> {
    const done = await this.write('add_object', { ...this.placeOnWire(place), ...(wrap ? wrapParams(wrap) : {}), ...kind, ...size })
    if (done === false) return null
    await this.selectObject(done.object as string, place.paragraph)
    return done.object as string
  }

  /** Edit ▸ Text Box: an empty text box, written in as a container is not (its words are a paragraph). */
  addTextBox(place: { paragraph: string; offset: number }, size: { w: number; h: number }, wrap?: Wrap): Promise<string | null> {
    return this.addBox({ kind: 'text' }, place, size, wrap)
  }

  /** Edit ▸ a shape of the library. */
  addShape(shape: string, place: { paragraph: string; offset: number }, size: { w: number; h: number }, wrap?: Wrap): Promise<string | null> {
    return this.addBox({ kind: 'shape', shape }, place, size, wrap)
  }

  /** How the text flows round an object (D1061); `gap` is how far it keeps from it (left out: the object's own). */
  async setWrap(id: string, wrap: Wrap, gap?: number): Promise<boolean> {
    return (await this.write('set_wrap', { id, ...wrapParams(wrap, gap) })) !== false
  }

  /** What the key of Format ▸ Wrap Text does (D1064): the object `id` goes on to the next mode; the mode it has now, or
   * `null` when there is no such object or the server would not. */
  async cycleWrap(id: string): Promise<Wrap | null> {
    const o = this.state.objects[id]
    if (!o) return null
    const next = nextWrap(wrapOf(o.anchor).wrap)
    return (await this.setWrap(id, next)) ? next : null
  }

  /** Hang an object from another place of the text. `away` is how far it floats from that character (D1023): left out,
   * the object keeps the offset it has. */
  async moveObject(id: string, place: { paragraph: string; offset: number }, away?: { dx: number; dy: number }): Promise<boolean> {
    const from = this.state.objects[id]?.anchor.holder
    if ((await this.write('move_object', { id, ...this.placeOnWire(place), ...(away ?? {}) })) === false) return false
    // the lock names the paragraph the object hangs from: a selected object moved to another one is locked there (D1223)
    if (this.state.selectedObject === id && place.paragraph !== from) await this.lockObject(id, place.paragraph)
    return true
  }

  async resizeObject(id: string, w: number, h: number): Promise<boolean> {
    return (await this.write('resize_object', { id, w, h })) !== false
  }

  // -- the style of an object: the one style API every app has (`apply_style`, `deviate`, D304); a paragraph's own
  // styling is above. These two are what `object-style-host.ts` needs besides `changeStyle`, `renameStyle`, `setRole`
  // and `checkCss`.
  /** Put a style into one slot of these targets (`apply_style`). */
  async applyObjectStyle(targets: StyleTarget[], style: string, slot: string): Promise<boolean> {
    return (await this.write('apply_style', { targets, style, slot })) !== false
  }

  /** Change these targets only, in one slot: a new style from `parent`, named later (`deviate`, D75, D309). */
  async deviateObjectStyle(parent: string, targets: StyleTarget[], slot: string, edit: CssEdit): Promise<boolean> {
    return (await this.write('deviate', { parent, targets, slot, ...edit })) !== false
  }

  // ------------------------------------------------------------------------------ tables (E9.32)
  /** Ask for the tables again: the words of a box changed, or a total did. */
  private async reloadTables(): Promise<void> {
    const found = await this.need().request<TableInfo[]>('tables').catch(() => null)
    if (!found) return
    this.state.tables = Object.fromEntries(found.map((x) => [x.id, x]))
    const { box } = this.state
    const own = box ? this.state.tables[box.table] : undefined
    // the box went with its table, its row or its column
    if (box && !(own?.rows.includes(box.row) && own.columns.some((c) => c.id === box.col))) this.state.box = null
  }

  /** The box the caret is in; `null` when it is not in a table. */
  focusBox(box: TextState['box']): void {
    this.state.box = box
  }
  /** The table the caret is in, or `null`. */
  boxTable(): TableInfo | null {
    const box = this.state.box
    return (box && this.state.tables[box.table]) || null
  }

  /** Put a table after the paragraph `place` is in: `rows` by `cols` boxes, the first `headerRows` the header. Its
   *  object's and its own id, or `null` when the server refused (the person is told why). */
  async addTable(place: { paragraph: string; offset: number }, size: { rows: number; cols: number; headerRows: number }): Promise<{ object: string; table: string } | null> {
    const done = await this.write('add_table', { ...this.placeOnWire(place), rows: size.rows, cols: size.cols, header_rows: size.headerRows })
    if (done === false) return null
    return { object: done.object as string, table: done.table as string }
  }

  /** An empty paragraph after `paragraph` and after what hangs from its end, such as a table at the end of the text
   *  (D1331); the caret goes to it. Its id, or `null` when the server refused (the person is told why). */
  async addParagraphAfter(paragraph: string): Promise<string | null> {
    const done = await this.write('add_paragraph_after', { paragraph })
    if (done === false) return null
    const made = done.paragraph as string
    if (!this.state.paragraphs.some((b) => b.id === made)) await this.reload() // the event did not come before the answer
    this.setSelection({ paragraph: made, offset: 0 })
    return made
  }

  /** Type `text` into a box, in place of the words it has. One line: a line break becomes a space (D1212). */
  async setBox(table: string, row: string, col: string, text: string): Promise<boolean> {
    if (this.refused()) return false
    const words = oneLine(text)
    // What the box has is looked at when this job runs, after the ones before it: a commit by Enter and the one by
    // leaving the box come close together, and the second must see what the first did (B1: the words were doubled).
    return this.run(async () => {
      const old = this.boxText(table, row, col)
      if (words === old) return true
      const paragraph = `${table}/${row}/${col}`
      const params = { paragraph, start: 0, end_paragraph: paragraph, end: [...old].length, text: words, base: this.state.revision }
      if ((await this.attempt('replace_text', params)) === false) return false
      this.rememberBox(table, row, col, words) // the server's events bring the box's words only after a round trip
      return true
    })
  }

  private boxText(table: string, row: string, col: string): string {
    return this.state.tables[table]?.entries.find(([r, c]) => r === row && c === col)?.[2].text ?? ''
  }

  /** Show `words` in the box at once; `reloadTables` confirms it a moment later. */
  private rememberBox(table: string, row: string, col: string, words: string): void {
    const shown = this.state.tables[table]
    if (!shown) return
    const entry = shown.entries.find(([r, c]) => r === row && c === col)
    if (entry) entry[2].text = words
    else if (words) shown.entries.push([row, col, { text: words, style: '' }] as TableEntry)
  }

  /** One of the server's table methods for table `table`: false when it was refused or the person may not. */
  private async changeTable(method: string, table: string, params: Record<string, unknown> = {}): Promise<boolean> {
    return this.write(method, { table, ...params }).then((done) => done !== false)
  }
  /** `place` is `{ after: id }` or `{ before: id }`. */
  insertRows(table: string, place: { after: string } | { before: string }, count = 1): Promise<boolean> {
    return this.changeTable('insert_rows', table, { count, ...place })
  }
  deleteRows(table: string, ids: string[]): Promise<boolean> {
    return this.changeTable('delete_rows', table, { ids })
  }
  insertColumns(table: string, place: { after: string } | { before: string }, count = 1): Promise<boolean> {
    return this.changeTable('insert_columns', table, { count, ...place })
  }
  deleteColumns(table: string, ids: string[]): Promise<boolean> {
    return this.changeTable('delete_columns', table, { ids })
  }
  sortRows(table: string, column: string, descending = false): Promise<boolean> {
    return this.changeTable('sort_rows', table, { column, descending })
  }
  /** `options` has any of `header_rows`, `banded`, `look`, `placement`, `width` (the server's `set_table_options`). */
  setTableOptions(table: string, options: Record<string, unknown>): Promise<boolean> {
    return this.changeTable('set_table_options', table, { options })
  }
  /** `changes` has any of `kind`, `total`, `width` (the server's `set_column`). */
  setColumn(table: string, column: string, changes: Record<string, unknown>): Promise<boolean> {
    return this.changeTable('set_column', table, { column, changes })
  }
  mergeCells(table: string, row: string, col: string, rows: number, cols: number): Promise<boolean> {
    return this.changeTable('merge_cells', table, { row, col, rows, cols })
  }
  splitCell(table: string, row: string, col: string): Promise<boolean> {
    return this.changeTable('split_cell', table, { row, col })
  }
  /** Take a table away with the object that shows it; undo brings it back. */
  async removeTable(table: string): Promise<boolean> {
    return this.write('remove_table', { id: table }).then((done) => done !== false)
  }

  // ------------------------------------------------------------------------------ loading
  protected async loadApp() {
    const link = this.need()
    const [answer, suggestions, palette, styleModel, page, objects, images, shapes, tables] = await Promise.all([
      link.request<{ styles: StyleView[]; paragraphs: Paragraph[]; lists: ListInfo[]; schemes: SchemeInfo[] }>('paragraphs'),
      link.request<SuggestionInfo[]>('suggestions'),
      link.request<PaletteEvent>('palette'),
      link.request<StyleModel>('style_model'),
      // an older server has no pages: the preview then starts from A4 and cannot store a change
      link.request<PageSetupData>('page').catch(() => null),
      // an older server shows no floating objects
      link.request<{ objects: VisualObject<ParagraphAnchor>[] }>('objects').then((a) => a.objects).catch(() => []),
      link.request<ImageAsset[]>('images').catch(() => []),
      link.request<ShapeAnswer | TextShape[]>('shapes').then(shapesOf).catch(() => shapesOf([])),
      // an older server has no tables
      link.request<TableInfo[]>('tables').catch(() => []),
    ])
    // an older server has no language either; the preview then hyphenates nothing and offers no choice
    const language = await link
      .request<{ language: string | null }>('language')
      .then((a) => a.language)
      .catch(() => undefined)
    const s = this.state
    s.page = page
    s.language = language
    s.objects = Object.fromEntries(objects.map((o) => [o.id, o]))
    s.images = Object.fromEntries(images.map((x) => [x.id, x]))
    s.shapes = Object.fromEntries(shapes.document.map((x) => [x.id, x]))
    s.library = shapes.library
    s.tables = Object.fromEntries(tables.map((x) => [x.id, x]))
    if (s.box && !s.tables[s.box.table]) s.box = null
    if (s.selectedObject && !s.objects[s.selectedObject]) this.track(this.selectObject(null))
    s.styles = Object.fromEntries(answer.styles.map((x) => [x.id, x]))
    s.lists = answer.lists
    s.schemes = answer.schemes
    s.palette = palette
    s.styleModel = styleModel
    s.paragraphs = answer.paragraphs.map((b) => ({ ...b, runs: runsToUnits(b.text, b.runs) }))
    s.suggestions = suggestions.map((x) => this.suggestionInUnits(x))
    s.pending = null
    s.sending = null
    s.selection = this.clamped(s.selection)
    void this.floating() // the names a tag in the chat shows
    if (!this.ready) {
      for (const hold of Object.values(s.presence)) hold.regions = hold.regions.map((r) => this.regionInUnits(r))
      this.ready = true
    }
  }

  protected override onWelcome() {
    this.ready = false
  }

  private clamped(selection: Selection | null): Selection | null {
    const first = this.state.paragraphs[0]
    if (!first) return null
    const fit = (pos: Pos): Pos => {
      const paragraph = this.state.paragraphs.find((b) => b.id === pos.paragraph)
      return paragraph ? { paragraph: paragraph.id, offset: Math.min(pos.offset, paragraph.text.length) } : { paragraph: first.id, offset: 0 }
    }
    return selection ? { anchor: fit(selection.anchor), focus: fit(selection.focus) } : collapsed({ paragraph: first.id, offset: 0 })
  }

  // ------------------------------------------------------------------------------ positions on the wire
  private textOf(paragraph: string): string {
    return this.state.paragraphs.find((b) => b.id === paragraph)?.text ?? ''
  }

  private suggestionInUnits(item: SuggestionInfo): SuggestionInfo {
    const text = this.textOf(item.paragraph)
    return { ...item, start: unitOf(text, item.start), end: unitOf(text, item.end) }
  }

  private regionInUnits(region: Region): Region {
    if (region.kind !== 'text') return region
    const text = this.textOf(region.paragraph)
    return { ...region, start: unitOf(text, region.start), end: unitOf(text, region.end) }
  }

  protected override adoptRegions(regions: Region[]): Region[] {
    return this.ready ? regions.map((r) => this.regionInUnits(r)) : regions
  }

  // ------------------------------------------------------------------------------ events
  /** A selected object that went is no longer selected, and no longer locked. */
  protected override objectsChanged(): void {
    const s = this.state
    if (s.selectedObject && !s.objects[s.selectedObject]) this.track(this.selectObject(null))
  }

  protected onAppEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'text':
      case 'split':
      case 'join':
      case 'style':
      case 'item':
      case 'labels':
      case 'paragraph_generated':
      case 'generated':
      case 'paragraph_fields':
      case 'fields': {
        // the words of a box of a table: not a paragraph of the text, so the tables are asked for again (E9.32)
        const at = (data.paragraph ?? data.paragraph) as string | undefined
        if (at && isBoxId(at)) {
          this.track(this.reloadTables())
          return true
        }
        const event = eventInUnits(s.paragraphs, data as TextEvent)
        if (!applyEvent(s.paragraphs, event)) this.track(this.reload())
        else this.follow(event)
        return true
      }
      case 'page':
        s.page = data.setup as PageSetupData
        return true
      case 'table': {
        withEvent(s.tables, data as unknown as TableEvent)
        const table = s.tables[data.id as string]
        if (s.box && !s.tables[s.box.table]) s.box = null
        else if (table?.columns.some((c) => c.total !== null)) this.track(this.reloadTables()) // the totals are derived
        return true
      }
      case 'lists':
        s.lists = data.lists as ListInfo[]
        return true
      case 'schemes':
        s.schemes = data.schemes as SchemeInfo[]
        return true
      case 'suggestions': {
        for (const item of data.items as SuggestionInfo[]) {
          const known = s.suggestions.findIndex((x) => x.id === item.id)
          const mine = this.suggestionInUnits(item)
          if (mine.state !== 'open') {
            if (known >= 0) s.suggestions.splice(known, 1)
          } else if (known >= 0) s.suggestions[known] = mine
          else s.suggestions.push(mine)
        }
        return true
      }
    }
    return false
  }

  /** Everything that sits at a place in the text moves with the change. */
  private follow(event: TextEvent) {
    const s = this.state
    const sending = s.sending
    if (sending && event.type === 'text' && !event.removed && event.inserted === sending.text && event.paragraph === sending.at.paragraph && event.offset === sending.at.offset) {
      s.sending = null // our own words arrived: the document shows them now
    }
    if (s.selection) {
      s.selection.anchor = followPos(s.selection.anchor, event)
      s.selection.focus = followPos(s.selection.focus, event)
    }
    for (const unwritten of [s.pending, s.sending]) if (unwritten) unwritten.at = followPos(unwritten.at, event)
    for (const hold of Object.values(s.presence)) {
      hold.regions = hold.regions.map((r): Region => {
        if (r.kind !== 'text') return r
        const moved = followSpan({ paragraph: r.paragraph, start: r.start, end: r.end }, event)
        return { kind: 'text', paragraph: moved.paragraph, start: moved.start, end: moved.end }
      })
    }
  }

  // ------------------------------------------------------------------------------ where I am
  /** The caret or selection as the person sees it moved (clicks, arrow keys). */
  setSelection(anchor: Pos, focus: Pos = anchor) {
    const s = this.state
    s.box = null // the caret is in the words now, not in a box of a table
    const now = s.selection
    if (now && same(now.anchor, anchor) && same(now.focus, focus)) return
    this.flushNow()
    s.selection = { anchor: { ...anchor }, focus: { ...focus } }
    this.moved++
    this.place()
  }

  /** The selection, first position first; `null` if there is no text yet. */
  range(): [Pos, Pos] | null {
    const sel = this.state.selection
    return sel ? ordered(this.state.paragraphs, sel.anchor, sel.focus) : null
  }

  isCollapsed(): boolean {
    const r = this.range()
    return !r || same(r[0], r[1])
  }

  selectedText(): string {
    const r = this.range()
    return r ? textBetween(this.state.paragraphs, r[0], r[1]) : ''
  }

  /** Show the others where my caret is, and keep the ± n words around it to myself while I write. */
  private place() {
    if (this.placing) clearTimeout(this.placing)
    this.placing = setTimeout(() => this.track(this.placeNow()), PLACE_MS)
  }

  async placeNow(): Promise<void> {
    this.placing = null
    const sel = this.state.selection
    // a selected object is locked, and holding the words would let go of it (D1223)
    if (!sel || this.state.status !== 'open' || this.state.selectedObject) return
    const text = this.textOf(sel.focus.paragraph)
    const params = { paragraph: sel.focus.paragraph, offset: pointOf(text, sel.focus.offset), words: ZONE_WORDS }
    const where = JSON.stringify(params)
    if (where === this.placed) return
    this.placed = where
    const link = this.need()
    try {
      if (this.readOnly) await link.request('look', params)
      else await link.request('hold', params).catch(() => link.request('look', params)) // a colleague holds it: just look
    } catch {
      this.placed = '' // not worth bothering the person; the next move tries again
    }
  }

  /** Let go of my zone (the person left the text). */
  async release(): Promise<void> {
    await this.flush()
    this.placed = ''
    try {
      await this.need().request('unlock')
    } catch {
      /* the lock runs out by itself */
    }
  }

  // ------------------------------------------------------------------------------ the queue
  /** Things that change the text run one after the other, each seeing the effects of the one before. */
  private enqueue<T>(job: () => Promise<T>): Promise<T> {
    this.jobs++
    const run = this.chain.then(job, job).finally(() => this.jobs--)
    this.chain = run.catch(() => undefined)
    return this.track(run)
  }

  /** Send what was typed so far. Runs as a job, so everything that was queued before it has been done. */
  private async sendPending(): Promise<void> {
    const s = this.state
    const unwritten = s.pending
    if (!unwritten) return
    s.pending = null
    s.sending = unwritten
    // The caret goes behind the words only if it has not been moved since they were typed: a click that came before
    // the words went out (they wait for the word end, or for an earlier request) is where the person wants to be.
    await this.replaceText(unwritten.at, unwritten.at, unwritten.text, this.typedAt)
    s.sending = null
    const put = this.unsentSelection
    this.unsentSelection = null
    if (put && same(put.at, unwritten.at)) s.selection = { anchor: put.anchor, focus: put.focus }
  }

  /** The page's caret or selection reaches into the words typed but not sent yet (Home or Shift+Home right after
   *  typing): they go out now, and then `anchor` and `focus` are selected, places in the paragraph as it will be with
   *  them (UTF-16 units, as the page counts), instead of the caret going behind them (D1350, UX-100). While they are not
   *  sent the paragraph does not have them, so before and after them are one place in it, and only the page knows. */
  selectOnceSent(anchor: Pos, focus: Pos): void {
    const unwritten = this.state.pending
    if (!unwritten) return
    this.moved++ // the caret was moved since they were typed: the answer does not put it behind them
    this.unsentSelection = { at: { ...unwritten.at }, anchor: { ...anchor }, focus: { ...focus } }
    void this.flushNow()
  }

  /** Have what was typed sent as soon as the jobs before are done. */
  private flushNow(): Promise<void> | undefined {
    if (this.idle) clearTimeout(this.idle)
    this.idle = null
    if (!this.state.pending || this.flushQueued) return undefined
    this.flushQueued = true
    return this.enqueue(async () => {
      this.flushQueued = false
      await this.sendPending()
    })
  }

  /** Send what was typed; resolves when everything before it is done. */
  override async flush(): Promise<void> {
    do {
      await this.flushNow()
      await this.chain
    } while (this.state.pending || this.jobs > 0) // characters typed while a job ran are appended when it is done
  }

  /** A change waits for the words typed before it, and for every change queued before it (D1432). */
  protected override run<T>(job: () => Promise<T>): Promise<T> {
    return this.enqueue(async () => {
      await this.sendPending()
      return job()
    })
  }

  // ------------------------------------------------------------------------------ writing
  /** Replace the text between two positions; the caret ends up behind what was put in. Runs as a job (`run`). */
  private async replaceText(from: Pos, to: Pos, text: string, version = this.moved): Promise<boolean> {
    const s = this.state
    const [a, b] = ordered(s.paragraphs, from, to)
    if (indexOf(s.paragraphs, a.paragraph) < 0 || indexOf(s.paragraphs, b.paragraph) < 0) return false
    const params = {
      paragraph: a.paragraph,
      start: pointOf(this.textOf(a.paragraph), a.offset),
      end_paragraph: b.paragraph,
      end: pointOf(this.textOf(b.paragraph), b.offset),
      text,
      base: s.revision,
    }
    const done = await this.attempt('replace_text', params)
    if (done === false) return false
    if (version === this.moved) s.selection = collapsed({ paragraph: done.paragraph, offset: unitOf(this.textOf(done.paragraph), done.offset) })
    return true
  }

  /** Is the caret (or the start of the selection) on a table of contents? Then typing is refused: its entries come
   * from the headings (E9.31). */
  private onContents(): boolean {
    const at = this.range()?.[0]
    const paragraph = at && this.state.paragraphs.find((b) => b.id === at.paragraph)
    if (!paragraph?.generated) return false
    this.notice(t('A table of contents takes no typing: its entries come from the headings.'), 'warning')
    return true
  }

  /** Type: the characters appear at once, and are sent when the word ends. */
  type(text: string) {
    if (!text || this.refused() || this.onContents()) return
    const caret = this.state.selection?.focus
    const pending = this.state.pending
    if (this.jobs > 0 || !this.isCollapsed() || (pending && caret && !same(pending.at, caret))) {
      void this.enqueue(() => this.typeNow(text))
      return
    }
    this.append(text)
  }

  /** Typing that had to wait for a job: the caret is where the jobs before it left it. */
  private async typeNow(text: string) {
    const caret = this.state.selection?.focus
    if (this.state.pending && caret && !same(this.state.pending.at, caret)) await this.sendPending()
    if (!this.isCollapsed()) {
      const [a, b] = this.range()!
      const [first = ''] = text
      await this.replaceText(a, b, first)
      text = text.slice(first.length)
    }
    if (text) this.append(text)
  }

  private append(text: string) {
    const s = this.state
    const caret = s.selection?.focus
    if (!caret) return
    if (s.pending) s.pending.text += text
    else {
      s.pending = { at: { ...caret }, text }
      this.typedAt = this.moved
    }
    if (WORD_END.test(text)) void this.flushNow()
    else {
      if (this.idle) clearTimeout(this.idle)
      this.idle = setTimeout(() => void this.flushNow(), IDLE_FLUSH_MS)
    }
    this.place()
  }

  /**
   * Enter: ends the paragraph at the caret (a selection is replaced). In an item the server gives the new paragraph the
   * same item; an *empty* item is the way out instead: one level out, and at the first level out of the list (E9.21).
   */
  newline(): Promise<boolean> | undefined {
    if (this.refused()) return undefined
    return this.run(async () => {
      const r = this.range()
      if (!r) return false
      const paragraph = this.state.paragraphs.find((b) => b.id === r[0].paragraph)
      if (paragraph?.item && !paragraph.text && same(r[0], r[1])) return this.leaveList(paragraph)
      return this.replaceText(r[0], r[1], '\n')
    })
  }

  /** Put text in place of the selection (paste; Enter). */
  replaceSelection(text: string): Promise<boolean> | undefined {
    if (this.refused() || (text && this.onContents())) return undefined
    return this.run(async () => {
      const r = this.range()
      return r ? this.replaceText(r[0], r[1], text) : false
    })
  }

  paste(text: string) {
    void this.replaceSelection(plain(text.replace(/\r\n?/g, '\n'))) // pasted words make no reference (step H)
  }

  /** The selected text, which is then taken out. */
  cut(): string {
    const text = this.selectedText()
    if (text && !this.refused()) void this.replaceSelection('')
    return text
  }

  /** Backspace (`word`: Ctrl+Backspace). Before the first character it joins the paragraph to the one before. */
  deleteBackward(word = false) {
    if (this.refused()) return
    const s = this.state
    if (this.jobs === 0 && s.pending && this.isCollapsed()) {
      const text = word ? s.pending.text.slice(0, wordStart(s.pending.text, s.pending.text.length)) : [...s.pending.text].slice(0, -1).join('')
      s.pending = text ? { at: s.pending.at, text } : null
      return
    }
    void this.run(async () => this.deleteAround(word, -1))
  }

  /** Delete (`word`: Ctrl+Delete). At the end of a paragraph it joins the next one to it. */
  deleteForward(word = false) {
    if (this.refused()) return
    void this.run(async () => this.deleteAround(word, 1))
  }

  private async deleteAround(word: boolean, direction: -1 | 1): Promise<boolean> {
    const r = this.range()
    if (!r) return false
    if (!same(r[0], r[1])) return this.replaceText(r[0], r[1], '')
    const { paragraphs } = this.state
    const i = indexOf(paragraphs, r[0].paragraph)
    if (paragraphs[i]!.generated) return this.removeContentsNow(r[0].paragraph) // the second key on a table takes it away
    const text = paragraphs[i]!.text
    const neighbour = direction < 0 ? (r[0].offset === 0 ? paragraphs[i - 1] : undefined) : r[0].offset === text.length ? paragraphs[i + 1] : undefined
    if (neighbour?.generated) {
      // the first key next to a table selects it, as the mock-up has it (E9.31): a table is never half deleted
      this.state.selection = collapsed({ paragraph: neighbour.id, offset: 0 })
      return true
    }
    const atom = direction < 0 ? r[0].offset - 1 : r[0].offset
    if (!word && text[atom] === FIELD_CHAR) {
      // the first key next to a reference selects it, the second takes it away (mock-up D): never lost by a slip
      this.state.selection = { anchor: { paragraph: r[0].paragraph, offset: atom }, focus: { paragraph: r[0].paragraph, offset: atom + 1 } }
      return true
    }
    if (direction < 0) {
      if (r[0].offset > 0) {
        const start = word ? wordStart(text, r[0].offset) : r[0].offset - (text.codePointAt(r[0].offset - 2)! > 0xffff ? 2 : 1)
        return this.replaceText({ paragraph: r[0].paragraph, offset: Math.max(0, start) }, r[0], '')
      }
      if (paragraphs[i]!.item) return this.leaveList(paragraphs[i]!) // out of the list first, as every editor does
      const before = paragraphs[i - 1]
      return before ? this.replaceText({ paragraph: before.id, offset: before.text.length }, r[0], '') : false
    }
    if (r[0].offset < text.length) {
      const end = word ? wordEnd(text, r[0].offset) : r[0].offset + (text.codePointAt(r[0].offset)! > 0xffff ? 2 : 1)
      return this.replaceText(r[0], { paragraph: r[0].paragraph, offset: end }, '')
    }
    const after = paragraphs[i + 1]
    return after ? this.replaceText(r[0], { paragraph: after.id, offset: 0 }, '') : false
  }

  /** Give the paragraphs of the selection this style. */
  setStyle(style: string): Promise<boolean> | undefined {
    if (this.refused()) return undefined
    return this.run(async () => {
      const r = this.range()
      if (!r) return false
      const { paragraphs } = this.state
      const [i, j] = [indexOf(paragraphs, r[0].paragraph), indexOf(paragraphs, r[1].paragraph)]
      for (const paragraph of paragraphs.slice(i, j + 1).filter((b) => b.style !== style)) {
        if ((await this.attempt('set_style', { paragraph: paragraph.id, style, base: this.state.revision })) === false) return false
      }
      return true
    })
  }

  /** Lay the text out on another page (D904): one step in the history, for everybody. */
  setPage(setup: PageSetupData): Promise<boolean> | undefined {
    return this.write('set_page', { setup }).then((done) => done !== false)
  }

  // -- tags (E5.20, D551). This replica keeps no objects: they are asked for when a tag needs them, and the names they
  // had when last asked are remembered, so that a tag in the chat shows what the thing is called now.
  private readonly objectNames = new Map<string, string>()
  private async floating(): Promise<(TextObject & { name?: string })[]> {
    const found = await this.need()
      .request<{ objects: (TextObject & { name?: string })[] }>('objects')
      .then((a) => a.objects)
      .catch(() => [])
    this.objectNames.clear()
    for (const o of found) if (o.name) this.objectNames.set(o.id, o.name)
    return found
  }
  override nameOf(id: string): string | undefined {
    return this.state.renamed[id] ?? this.state.paragraphs.find((b) => b.id === id)?.name ?? this.objectNames.get(id)
  }
  /** What a paragraph is, as a thing (D554): a heading (its style gives a heading level, E9.22), an item of a list, or
   * a paragraph. The level comes worked out from the server with the styles, so this is no second rule. */
  paragraphKind(paragraph: Paragraph): ThingKind {
    if (headingLevel(this.styleViews(), paragraph.style) !== null) return 'heading'
    return paragraph.item ? 'item' : 'paragraph'
  }
  /** The named paragraphs: from the replica, which `paragraphs` and `thing_renamed` keep current. */
  protected override things(): Thing[] {
    const s = this.state
    return s.paragraphs.flatMap((b) => {
      const name = s.renamed[b.id] ?? b.name
      return name ? [{ id: b.id, name, kind: this.paragraphKind(b) }] : []
    })
  }
  /** What `#` offers in a text: the named objects, every named paragraph, and, still to be named when picked, the
   * headings (the outline of the text) and the paragraph the caret is in. */
  protected override async inView(): Promise<Thing[]> {
    const s = this.state
    const objects = (await this.floating()).filter((o) => o.name).map((o) => ({ id: o.id, name: s.renamed[o.id] ?? o.name!, kind: o.kind }))
    const named = this.things()
    const known = new Set(named.map((t) => t.id))
    const caret = s.selection?.focus.paragraph
    const offered = s.paragraphs.flatMap((b): Thing[] => {
      if (known.has(b.id)) return []
      const kind = this.paragraphKind(b)
      if (kind !== 'heading' && b.id !== caret) return []
      const words = b.text.replace(/\s+/g, ' ').trim().slice(0, MAX_NAME)
      return [{ id: b.id, name: words || t('This paragraph'), kind, unnamed: true }]
    })
    return [...objects, ...named, ...offered]
  }
  /** A paragraph without a name is named when it is first pointed at (D554): a heading by its words, any other by what
   * it is. Objects as before. */
  override async thingToReference(id: string): Promise<Thing | null> {
    const paragraph = this.state.paragraphs.find((b) => b.id === id)
    if (!paragraph) return super.thingToReference(id)
    const named = this.things().find((thing) => thing.id === id)
    if (named) return named
    const done = await this.attempt('name_thing', { id, base: this.state.revision })
    if (done === false) return null
    this.state.renamed[id] = done.name
    return { id, name: done.name, kind: this.paragraphKind(paragraph) }
  }
  override async unnamedInView(): Promise<number> {
    return (await this.floating()).filter((o) => !o.name).length
  }
  protected override async locate(id: string): Promise<{ holder: string | null } | null> {
    if (this.state.paragraphs.some((b) => b.id === id)) return { holder: id }
    const found = (await this.floating()).find((o) => o.id === id)
    return found ? { holder: found.anchor.holder } : null
  }

  /** The floating objects, their outlines and their images, for printing (D907). Read when the preview opens. */
  async printExtras(): Promise<PrintExtras> {
    const link = this.need()
    const [objects, shapes, images, tables] = await Promise.all([
      link.request<{ objects: TextObject[] }>('objects').then((a) => a.objects).catch(() => []),
      link.request<ShapeAnswer | TextShape[]>('shapes').then((a) => shapesOf(a).document as ShapeOutline[]).catch(() => []),
      link.request<TextImage[]>('images').catch(() => []),
      link.request<TableInfo[]>('tables').catch(() => []),
    ])
    return { objects, shapes, images, tables }
  }

  // -- lists (E9.21). The numbering is the server's: what is asked for is structure, and the markers arrive as events.
  /** The list item the caret is in, or `null`. */
  currentItem(): ListItem | null {
    const focus = this.state.selection?.focus
    return this.state.paragraphs.find((b) => b.id === focus?.paragraph)?.item ?? null
  }

  // ------------------------------------------------------------------------------ references (step H)
  /** What a reference can point at, for the picker: headings, numbered items, named things (`query` filters). */
  async referenceTargets(query = ''): Promise<ReferenceTarget[]> {
    try {
      return await this.need().request<ReferenceTarget[]>('reference_targets', { query })
    } catch {
      return [] // an older server knows no references
    }
  }

  /** Put a reference to `target` at the caret (in place of the selection), showing `show`; the caret goes after it. */
  insertReference(target: string, show: Show): Promise<boolean> {
    if (this.refused() || this.onContents()) return Promise.resolve(false)
    return this.run(async () => {
      const r = this.range()
      if (!r) return false
      if (!same(r[0], r[1]) && !(await this.replaceText(r[0], r[1], ''))) return false
      const at = this.state.selection?.focus ?? r[0]
      const params = { paragraph: at.paragraph, offset: pointOf(this.textOf(at.paragraph), at.offset), target, show, base: this.state.revision }
      if ((await this.attempt('insert_reference', params)) === false) return false
      this.state.selection = collapsed({ paragraph: at.paragraph, offset: at.offset + 1 })
      return true
    })
  }

  /** Make the `index`-th reference of a paragraph show `show` (Show As). */
  setFieldShow(paragraph: string, index: number, show: Show): Promise<boolean> {
    return this.write('set_field', { paragraph: paragraph, index, show }).then((done) => done !== false)
  }

  /** The reference at a place of the text (the character after `at`), as `{paragraph, index, field, shown}`, or `null`. */
  referenceAt(at: Pos): { paragraph: string; index: number; field: RefField; shown: Shown | undefined } | null {
    const paragraph = this.state.paragraphs.find((b) => b.id === at.paragraph)
    if (!paragraph || paragraph.text[at.offset] !== FIELD_CHAR) return null
    const index = fieldIndex(paragraph.text, at.offset)
    const field = paragraph.fields?.[index]
    return field ? { paragraph: paragraph.id, index, field, shown: paragraph.shown?.[index] } : null
  }

  // ------------------------------------------------------------------------------ tables of contents (E9.31)
  /** The table of contents the caret is on, or `null`. */
  currentContents(): Paragraph | null {
    const at = this.state.selection?.focus
    const paragraph = at && this.state.paragraphs.find((b) => b.id === at.paragraph)
    return paragraph?.generated ? paragraph : null
  }

  /** Put a "Contents" paragraph and a table of contents at the caret, as one step; the caret goes onto the table. */
  insertContents(): Promise<boolean> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(async () => {
      const at = this.state.selection?.focus
      if (!at) return false
      const done = await this.attempt('insert_contents', { paragraph: at.paragraph, base: this.state.revision })
      if (done === false) return false
      if (typeof done.paragraph === 'string') this.state.selection = collapsed({ paragraph: done.paragraph, offset: 0 })
      return true
    })
  }

  /** Take a table of contents away (its "Contents" paragraph stays, as the author's words). */
  removeContents(paragraph: string): Promise<boolean> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(async () => this.removeContentsNow(paragraph))
  }

  private async removeContentsNow(paragraph: string): Promise<boolean> {
    return (await this.attempt('remove_contents', { paragraph, base: this.state.revision })) !== false
  }

  /** The scheme (`bullets`, `numbers`) of the list the caret's item belongs to, or `null`. */
  currentScheme(): string | null {
    const item = this.currentItem()
    return (item && this.state.lists.find((l) => l.id === item.list)?.scheme) ?? null
  }

  /** May the list of the caret's item go on from an earlier one? Only from its first item, and only when an item of
   * another list of the same scheme lies before it (the same rule as the server's `continue_list`). */
  canContinue(): boolean {
    const item = this.currentItem()
    const scheme = this.currentScheme()
    if (!item || !scheme) return false
    const { paragraphs, lists } = this.state
    const first = paragraphs.findIndex((b) => b.item?.list === item.list)
    if (paragraphs[first]?.id !== this.state.selection?.focus.paragraph) return false
    return paragraphs.slice(0, first).some((b) => b.item && b.item.list !== item.list && lists.find((l) => l.id === b.item!.list)?.scheme === scheme)
  }

  /** The paragraphs of the selection. */
  private selectedParagraphs(): Paragraph[] {
    const r = this.range()
    if (!r) return []
    const { paragraphs } = this.state
    return paragraphs.slice(indexOf(paragraphs, r[0].paragraph), indexOf(paragraphs, r[1].paragraph) + 1)
  }

  /** Bullets or numbers for the selected paragraphs, or (`null`) plain paragraphs. Asking for what they are takes them
   * out of their list; the server decides (`make_list`). */
  makeList(scheme: string | null): Promise<boolean> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(async () => {
      const paragraphs = this.selectedParagraphs().map((b) => b.id)
      if (!paragraphs.length) return false
      return (await this.attempt('make_list', { paragraphs, scheme, base: this.state.revision })) !== false
    })
  }

  /** Move the selected items one level in (`1`) or out (`-1`). */
  indent(by: 1 | -1): Promise<boolean> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(async () => {
      const paragraphs = this.selectedParagraphs().filter((b) => b.item).map((b) => b.id)
      if (!paragraphs.length) return false
      return (await this.attempt('indent_item', { paragraphs, by, base: this.state.revision })) !== false
    })
  }

  /** Tab and Shift+Tab: in a list item they move it in or out. `false` where the key is not ours (a plain paragraph). */
  tab(back: boolean): boolean {
    if (this.readOnly || !this.currentItem()) return false
    void this.indent(back ? -1 : 1)
    return true
  }

  /** Let the list of the caret's item go on where the nearest earlier list of its kind ends. */
  continueList(): Promise<boolean> {
    const paragraph = this.state.selection?.focus.paragraph
    if (!paragraph || !this.currentItem()) return Promise.resolve(false)
    return this.write('continue_list', { paragraph }).then((done) => done !== false)
  }

  /** Number the first level of the caret's list from `start` on. */
  startAt(start: number): Promise<boolean> {
    const item = this.currentItem()
    if (!item) return Promise.resolve(false)
    return this.write('list_start', { list: item.list, start }).then((done) => done !== false)
  }

  /** The way out of a list from an item with nothing in it: one level out, at the first level out of the list. */
  private leaveList(paragraph: Paragraph): Promise<boolean> {
    const item = paragraph.item!
    return item.level > 0 ? this.attemptOk('indent_item', { paragraphs: [paragraph.id], by: -1 }) : this.attemptOk('make_list', { paragraphs: [paragraph.id], scheme: null })
  }

  private async attemptOk(method: string, params: Record<string, unknown>): Promise<boolean> {
    return (await this.attempt(method, { ...params, base: this.state.revision })) !== false
  }

  /** The style of the paragraph the caret is in. */
  currentStyle(): string {
    const focus = this.state.selection?.focus
    return this.state.paragraphs.find((b) => b.id === focus?.paragraph)?.style ?? DEFAULT_STYLE.composes
  }

  // -- styles (CSS, E9.7)
  styleView(id: string): StyleView | undefined {
    return this.state.styles[id]
  }

  /** How many paragraphs have each style. */
  uses(): Record<string, number> {
    return styleUses(this.state.paragraphs)
  }

  /**
   * Change only the selected paragraphs: each style among them is deviated from, which makes a new style that is named
   * later (D75). Paragraphs that had the same style get the same new style.
   */
  deviateStyle(edit: CssEdit): Promise<boolean> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(async () => {
      const r = this.range()
      if (!r) return false
      const { paragraphs } = this.state
      const [i, j] = [indexOf(paragraphs, r[0].paragraph), indexOf(paragraphs, r[1].paragraph)]
      const parents = new Map<string, string[]>()
      for (const paragraph of paragraphs.slice(i, j + 1)) parents.set(paragraph.style, [...(parents.get(paragraph.style) ?? []), paragraph.id])
      for (const [parent, ids] of parents) {
        const params = { parent, paragraphs: ids, ...edit, base: this.state.revision }
        if ((await this.attempt('deviate_style', params)) === false) return false
      }
      return true
    })
  }

  /** A deletion or a hiding goes after whatever was typed before it, like every change that is not typing. */
  override deleteStyle(style: string, how: DeleteHow, target: string | null): Promise<Deleted | false> {
    if (this.refused()) return Promise.resolve(false)
    return this.run(() => super.deleteStyle(style, how, target))
  }

  /** Make a style give its paragraphs a heading level (E9.22): a level, `'body'` for none, `null` as its parent. */
  setHeadingLevel(style: string, level: number | 'body' | null): Promise<boolean> {
    return this.write('set_heading_level', { style, level }).then((done) => done !== false)
  }

  // -- suggestions
  accept(id: string): Promise<boolean> | undefined {
    return this.write('accept_suggestion', { id }).then((done) => done !== false)
  }

  reject(id: string): Promise<boolean> | undefined {
    return this.write('reject_suggestion', { id }).then((done) => done !== false)
  }

  // -- undo and redo wait for what was typed
  override async undo(): Promise<boolean> {
    await this.flush()
    return super.undo()
  }

  override async redo(): Promise<boolean> {
    await this.flush()
    return super.redo()
  }
}
