// One person's view of one text: the paragraphs the screen draws, kept up to date from the server's events, and the
// ways of writing into them. Everything a person does is a request; the text changes when the server's events say so.
//
// Typing is the one thing that is not shown only after the answer: the characters of the word being typed wait in
// `pending` (drawn at the caret, marked as not yet written) and go out as one request when the word ends, after a pause,
// or before anything else the person does. So a word is one step in the history, and typing does not wait for the network.
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
  type Block,
  type ListItem,
  type Pos,
  type TextEvent,
} from './blocks'
import type { PaletteEvent, StyleModel } from './objects'
import type { PageSetupData, ShapeOutline, TextObject } from '@claudia/layout'
import type { LinkLike, Region, WireData } from './protocol'
import { styleUses, type CssCheck, type CssEdit, type StyleView } from './style-css'

import { translate as t } from './i18n'
export interface SuggestionInfo {
  id: string
  author: string | null
  block: string
  start: number
  end: number
  original: string
  /** `null` for a remark, which suggests no change. */
  replacement: string | null
  reason: string
  state: string
  outdated: boolean
}
/** A list of the document (the server's `lists`): its scheme, the number it starts at and, when it has one, its name. */
export interface ListInfo {
  id: string
  scheme: string
  start: number
  name: string | null
}
/** How a list looks (the server's `schemes`): whether it counts, how far a level moves the text in and the gap between
 * two items, both in em. */
export interface SchemeInfo {
  id: string
  name: string
  kind: 'bullet' | 'number'
  indent: number
  gap: number
}
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
  styles: StyleView[]
  /** The document's colour roles and how they read against each other (D200); a paragraph style names them, and
   * the resolved colours arrive with the styles themselves. */
  palette: PaletteEvent | null
  /** What a style property means and where a style can go: the server's `style_model` (D303, D304). */
  styleModel: StyleModel | null
  blocks: Block[]
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
  /** The language the text is written in (D915), a BCP 47 tag; `null` when it is not set. `undefined` for a server
   *  that does not know languages. */
  language: string | null | undefined
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
}

export const IDLE_FLUSH_MS = 700
export const PLACE_MS = 150
export const ZONE_WORDS = 3
const WORD_END = /[\s.,;:!?)\]}"”»]$/u

const same = (a: Pos, b: Pos) => a.block === b.block && a.offset === b.offset
const collapsed = (pos: Pos): Selection => ({ anchor: { ...pos }, focus: { ...pos } })

export class TextSession extends BaseSession<TextState> {
  private chain: Promise<unknown> = Promise.resolve()
  private jobs = 0
  private idle: ReturnType<typeof setTimeout> | null = null
  private placing: ReturnType<typeof setTimeout> | null = null
  private placed = ''
  private moved = 0
  private ready = false
  private flushQueued = false

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, { styles: [], palette: null, styleModel: null, blocks: [], lists: [], schemes: [], suggestions: [], selection: null, pending: null, sending: null, page: null, language: undefined })
  }

  get readOnly(): boolean {
    return this.state.me.role === 'viewer'
  }

  // ------------------------------------------------------------------------------ loading
  protected async loadApp() {
    const link = this.need()
    const [answer, suggestions, palette, styleModel, page] = await Promise.all([
      link.request<{ styles: StyleView[]; blocks: Block[]; lists: ListInfo[]; schemes: SchemeInfo[] }>('blocks'),
      link.request<SuggestionInfo[]>('suggestions'),
      link.request<PaletteEvent>('palette'),
      link.request<StyleModel>('style_model'),
      // an older server has no pages: the preview then starts from A4 and cannot store a change
      link.request<PageSetupData>('page').catch(() => null),
    ])
    // an older server has no language either; the preview then hyphenates nothing and offers no choice
    const language = await link
      .request<{ language: string | null }>('language')
      .then((a) => a.language)
      .catch(() => undefined)
    const s = this.state
    s.page = page
    s.language = language
    s.styles = answer.styles
    s.lists = answer.lists
    s.schemes = answer.schemes
    s.palette = palette
    s.styleModel = styleModel
    s.blocks = answer.blocks.map((b) => ({ ...b, runs: runsToUnits(b.text, b.runs) }))
    s.suggestions = suggestions.map((x) => this.suggestionInUnits(x))
    s.pending = null
    s.sending = null
    s.selection = this.clamped(s.selection)
    if (!this.ready) {
      for (const hold of Object.values(s.presence)) hold.regions = hold.regions.map((r) => this.regionInUnits(r))
      this.ready = true
    }
  }

  protected override onWelcome() {
    this.ready = false
  }

  private clamped(selection: Selection | null): Selection | null {
    const first = this.state.blocks[0]
    if (!first) return null
    const fit = (pos: Pos): Pos => {
      const block = this.state.blocks.find((b) => b.id === pos.block)
      return block ? { block: block.id, offset: Math.min(pos.offset, block.text.length) } : { block: first.id, offset: 0 }
    }
    return selection ? { anchor: fit(selection.anchor), focus: fit(selection.focus) } : collapsed({ block: first.id, offset: 0 })
  }

  // ------------------------------------------------------------------------------ positions on the wire
  private textOf(block: string): string {
    return this.state.blocks.find((b) => b.id === block)?.text ?? ''
  }

  private suggestionInUnits(item: SuggestionInfo): SuggestionInfo {
    const text = this.textOf(item.block)
    return { ...item, start: unitOf(text, item.start), end: unitOf(text, item.end) }
  }

  private regionInUnits(region: Region): Region {
    if (region.kind !== 'text') return region
    const text = this.textOf(region.block)
    return { ...region, start: unitOf(text, region.start), end: unitOf(text, region.end) }
  }

  protected override adoptRegions(regions: Region[]): Region[] {
    return this.ready ? regions.map((r) => this.regionInUnits(r)) : regions
  }

  // ------------------------------------------------------------------------------ events
  protected onAppEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'text':
      case 'split':
      case 'join':
      case 'style':
      case 'item':
      case 'labels': {
        const event = eventInUnits(s.blocks, data as TextEvent)
        if (!applyEvent(s.blocks, event)) this.track(this.reload())
        else this.follow(event)
        return true
      }
      case 'styles':
        s.styles = data.styles as StyleView[]
        return true
      case 'page':
        s.page = data.setup as PageSetupData
        return true
      case 'language':
        s.language = (data.language as string | null) ?? null
        return true
      case 'lists':
        s.lists = data.lists as ListInfo[]
        return true
      case 'palette':
        // Only the styles are drawn from, and they travel with this event; the roles are kept for the controls
        // that offer them by name (D200).
        s.palette = data as PaletteEvent
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
    if (sending && event.type === 'text' && !event.removed && event.inserted === sending.text && event.block === sending.at.block && event.offset === sending.at.offset) {
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
        const moved = followSpan({ block: r.block, start: r.start, end: r.end }, event)
        return { kind: 'text', block: moved.block, start: moved.start, end: moved.end }
      })
    }
  }

  // ------------------------------------------------------------------------------ where I am
  /** The caret or selection as the person sees it moved (clicks, arrow keys). */
  setSelection(anchor: Pos, focus: Pos = anchor) {
    const s = this.state
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
    return sel ? ordered(this.state.blocks, sel.anchor, sel.focus) : null
  }

  isCollapsed(): boolean {
    const r = this.range()
    return !r || same(r[0], r[1])
  }

  selectedText(): string {
    const r = this.range()
    return r ? textBetween(this.state.blocks, r[0], r[1]) : ''
  }

  /** Show the others where my caret is, and keep the ± n words around it to myself while I write. */
  private place() {
    if (this.placing) clearTimeout(this.placing)
    this.placing = setTimeout(() => this.track(this.placeNow()), PLACE_MS)
  }

  async placeNow(): Promise<void> {
    this.placing = null
    const sel = this.state.selection
    if (!sel || this.state.status !== 'open') return
    const text = this.textOf(sel.focus.block)
    const params = { block: sel.focus.block, offset: pointOf(text, sel.focus.offset), words: ZONE_WORDS }
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
    await this.write(unwritten.at, unwritten.at, unwritten.text)
    s.sending = null
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

  /** Run a change after whatever was typed before it has been sent. */
  private act<T>(job: () => Promise<T>): Promise<T> {
    return this.enqueue(async () => {
      await this.sendPending()
      return job()
    })
  }

  private denied(): boolean {
    if (!this.readOnly) return false
    this.notice(t('You can only look at this document.'), 'warning')
    return true
  }

  // ------------------------------------------------------------------------------ writing
  /** Replace the text between two positions; the caret ends up behind what was put in. */
  private async write(from: Pos, to: Pos, text: string): Promise<boolean> {
    const s = this.state
    const [a, b] = ordered(s.blocks, from, to)
    if (indexOf(s.blocks, a.block) < 0 || indexOf(s.blocks, b.block) < 0) return false
    const params = {
      block: a.block,
      start: pointOf(this.textOf(a.block), a.offset),
      end_block: b.block,
      end: pointOf(this.textOf(b.block), b.offset),
      text,
      base: s.revision,
    }
    const version = this.moved
    const done = await this.attempt('replace_text', params)
    if (done === false) return false
    if (version === this.moved) s.selection = collapsed({ block: done.block, offset: unitOf(this.textOf(done.block), done.offset) })
    return true
  }

  /** Type: the characters appear at once, and are sent when the word ends. */
  type(text: string) {
    if (!text || this.denied()) return
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
      await this.write(a, b, first)
      text = text.slice(first.length)
    }
    if (text) this.append(text)
  }

  private append(text: string) {
    const s = this.state
    const caret = s.selection?.focus
    if (!caret) return
    if (s.pending) s.pending.text += text
    else s.pending = { at: { ...caret }, text }
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
    if (this.denied()) return undefined
    return this.act(async () => {
      const r = this.range()
      if (!r) return false
      const block = this.state.blocks.find((b) => b.id === r[0].block)
      if (block?.item && !block.text && same(r[0], r[1])) return this.leaveList(block)
      return this.write(r[0], r[1], '\n')
    })
  }

  /** Put text in place of the selection (paste; Enter). */
  replaceSelection(text: string): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => {
      const r = this.range()
      return r ? this.write(r[0], r[1], text) : false
    })
  }

  paste(text: string) {
    void this.replaceSelection(text.replace(/\r\n?/g, '\n'))
  }

  /** The selected text, which is then taken out. */
  cut(): string {
    const text = this.selectedText()
    if (text && !this.denied()) void this.replaceSelection('')
    return text
  }

  /** Backspace (`word`: Ctrl+Backspace). Before the first character it joins the paragraph to the one before. */
  deleteBackward(word = false) {
    if (this.denied()) return
    const s = this.state
    if (this.jobs === 0 && s.pending && this.isCollapsed()) {
      const text = word ? s.pending.text.slice(0, wordStart(s.pending.text, s.pending.text.length)) : [...s.pending.text].slice(0, -1).join('')
      s.pending = text ? { at: s.pending.at, text } : null
      return
    }
    void this.act(async () => this.deleteAround(word, -1))
  }

  /** Delete (`word`: Ctrl+Delete). At the end of a paragraph it joins the next one to it. */
  deleteForward(word = false) {
    if (this.denied()) return
    void this.act(async () => this.deleteAround(word, 1))
  }

  private async deleteAround(word: boolean, direction: -1 | 1): Promise<boolean> {
    const r = this.range()
    if (!r) return false
    if (!same(r[0], r[1])) return this.write(r[0], r[1], '')
    const { blocks } = this.state
    const i = indexOf(blocks, r[0].block)
    const text = blocks[i]!.text
    if (direction < 0) {
      if (r[0].offset > 0) {
        const start = word ? wordStart(text, r[0].offset) : r[0].offset - (text.codePointAt(r[0].offset - 2)! > 0xffff ? 2 : 1)
        return this.write({ block: r[0].block, offset: Math.max(0, start) }, r[0], '')
      }
      if (blocks[i]!.item) return this.leaveList(blocks[i]!) // out of the list first, as every editor does
      const before = blocks[i - 1]
      return before ? this.write({ block: before.id, offset: before.text.length }, r[0], '') : false
    }
    if (r[0].offset < text.length) {
      const end = word ? wordEnd(text, r[0].offset) : r[0].offset + (text.codePointAt(r[0].offset)! > 0xffff ? 2 : 1)
      return this.write(r[0], { block: r[0].block, offset: end }, '')
    }
    const after = blocks[i + 1]
    return after ? this.write(r[0], { block: after.id, offset: 0 }, '') : false
  }

  /** Give the paragraphs of the selection this style. */
  setStyle(style: string): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => {
      const r = this.range()
      if (!r) return false
      const { blocks } = this.state
      const [i, j] = [indexOf(blocks, r[0].block), indexOf(blocks, r[1].block)]
      for (const block of blocks.slice(i, j + 1).filter((b) => b.style !== style)) {
        if ((await this.attempt('set_style', { block: block.id, style, base: this.state.revision })) === false) return false
      }
      return true
    })
  }

  /** Lay the text out on another page (D904): one step in the history, for everybody. */
  setPage(setup: PageSetupData): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => (await this.attempt('set_page', { setup, base: this.state.revision })) !== false)
  }

  /** Say which language the text is written in (D915), or `null` for not known: one step, for everybody. */
  setLanguage(language: string | null): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => (await this.attempt('set_language', { language, base: this.state.revision })) !== false)
  }

  /** The floating objects, their outlines and their images, for printing (D907). Read when the preview opens. */
  async printExtras(): Promise<PrintExtras> {
    const link = this.need()
    const [objects, shapes, images] = await Promise.all([
      link.request<{ objects: TextObject[] }>('objects').then((a) => a.objects).catch(() => []),
      link.request<ShapeOutline[]>('shapes').catch(() => []),
      link.request<TextImage[]>('images').catch(() => []),
    ])
    return { objects, shapes, images }
  }

  // -- lists (E9.21). The numbering is the server's: what is asked for is structure, and the markers arrive as events.
  /** The list item the caret is in, or `null`. */
  currentItem(): ListItem | null {
    const focus = this.state.selection?.focus
    return this.state.blocks.find((b) => b.id === focus?.block)?.item ?? null
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
    const { blocks, lists } = this.state
    const first = blocks.findIndex((b) => b.item?.list === item.list)
    if (blocks[first]?.id !== this.state.selection?.focus.block) return false
    return blocks.slice(0, first).some((b) => b.item && b.item.list !== item.list && lists.find((l) => l.id === b.item!.list)?.scheme === scheme)
  }

  /** The paragraphs of the selection. */
  private selectedBlocks(): Block[] {
    const r = this.range()
    if (!r) return []
    const { blocks } = this.state
    return blocks.slice(indexOf(blocks, r[0].block), indexOf(blocks, r[1].block) + 1)
  }

  /** Bullets or numbers for the selected paragraphs, or (`null`) plain paragraphs. Asking for what they are takes them
   * out of their list; the server decides (`make_list`). */
  makeList(scheme: string | null): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => {
      const blocks = this.selectedBlocks().map((b) => b.id)
      if (!blocks.length) return false
      return (await this.attempt('make_list', { blocks, scheme, base: this.state.revision })) !== false
    })
  }

  /** Move the selected items one level in (`1`) or out (`-1`). */
  indent(by: 1 | -1): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => {
      const blocks = this.selectedBlocks().filter((b) => b.item).map((b) => b.id)
      if (!blocks.length) return false
      return (await this.attempt('indent_item', { blocks, by, base: this.state.revision })) !== false
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
    const block = this.state.selection?.focus.block
    if (this.denied() || !block || !this.currentItem()) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('continue_list', { block, base: this.state.revision })) !== false)
  }

  /** Number the first level of the caret's list from `start` on. */
  startAt(start: number): Promise<boolean> {
    const item = this.currentItem()
    if (this.denied() || !item) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('list_start', { list: item.list, start, base: this.state.revision })) !== false)
  }

  /** The way out of a list from an item with nothing in it: one level out, at the first level out of the list. */
  private leaveList(block: Block): Promise<boolean> {
    const item = block.item!
    return item.level > 0 ? this.attemptOk('indent_item', { blocks: [block.id], by: -1 }) : this.attemptOk('make_list', { blocks: [block.id], scheme: null })
  }

  private async attemptOk(method: string, params: Record<string, unknown>): Promise<boolean> {
    return (await this.attempt(method, { ...params, base: this.state.revision })) !== false
  }

  /** The style of the paragraph the caret is in. */
  currentStyle(): string {
    const focus = this.state.selection?.focus
    return this.state.blocks.find((b) => b.id === focus?.block)?.style ?? 'body'
  }

  // -- styles (CSS, E9.7)
  styleView(id: string): StyleView | undefined {
    return this.state.styles.find((s) => s.id === id)
  }

  /** How many paragraphs have each style. */
  uses(): Record<string, number> {
    return styleUses(this.state.blocks)
  }

  /** Change a style for everything that has it: properties to set and remove, or the complete text of its CSS. */
  changeStyle(style: string, edit: CssEdit): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('change_style', { style, ...edit, base: this.state.revision })) !== false)
  }

  /**
   * Change only the selected paragraphs: each style among them is deviated from, which makes a new style that is named
   * later (D75). Paragraphs that had the same style get the same new style.
   */
  deviateStyle(edit: CssEdit): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => {
      const r = this.range()
      if (!r) return false
      const { blocks } = this.state
      const [i, j] = [indexOf(blocks, r[0].block), indexOf(blocks, r[1].block)]
      const parents = new Map<string, string[]>()
      for (const block of blocks.slice(i, j + 1)) parents.set(block.style, [...(parents.get(block.style) ?? []), block.id])
      for (const [parent, ids] of parents) {
        const params = { parent, blocks: ids, ...edit, base: this.state.revision }
        if ((await this.attempt('deviate_style', params)) === false) return false
      }
      return true
    })
  }

  /** Give a colour role another colour: every paragraph style that meant it follows (D200). */
  setRole(role: string, colour: string): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('set_role', { role, colour, base: this.state.revision })) !== false)
  }

  /** Put a whole palette in place of this document's — what "the colours it started with" does. */
  replacePalette(roles: unknown[]): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('replace_palette', { roles, base: this.state.revision })) !== false)
  }

  renameStyle(style: string, name: string): Promise<boolean> {
    if (this.denied()) return Promise.resolve(false)
    return this.act(async () => (await this.attempt('rename_style', { style, name, base: this.state.revision })) !== false)
  }

  /** What the server makes of this CSS text, line by line. A read: it does not wait for typing or other changes. */
  async checkCss(text: string): Promise<CssCheck | null> {
    try {
      return await this.need().request<CssCheck>('check_css', { text })
    } catch {
      return null
    }
  }

  // -- suggestions
  accept(id: string): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => (await this.attempt('accept_suggestion', { id, base: this.state.revision })) !== false)
  }

  reject(id: string): Promise<boolean> | undefined {
    if (this.denied()) return undefined
    return this.act(async () => (await this.attempt('reject_suggestion', { id, base: this.state.revision })) !== false)
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
