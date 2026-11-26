// One person's view of one presentation (creates): the slides, their objects and the shapes, kept up to date from the
// server's events. What every document has in common (connection, history, chat, people, undo) is in BaseSession.
import type { LinkLike, Region, WireData } from './protocol'
import { parseFence } from './containers'
import { holderOf, firstFocus } from './replay'
import type { Thing } from './tags'
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import { translate as t } from './i18n'
import type { Frame } from './geometry'
import type { ImageAsset } from './images'
import { othersOn, type ObjectsEvent, type Other, type PaletteEvent, type StyleDef, type StyleModel, type StyleTarget } from './objects'
import type { CssEdit } from './style-css'
import type { PrintSetupData } from '@claudia/layout'
import { pointOf, type Label } from './paragraphs'
import type { ListInfo, SchemeInfo } from './numbering'
import type { ContentsEntry } from './contents'
import type { ReferenceTarget, RefField, Show, Shown } from './references'
import { SlideActions, type PictureImport, type ShapeDef, type SlideHost, type SlideObject } from './slide-host'

// `ImageAsset`/`ImageImport` moved to `./images` (shared with computes' `session.ts`, E6.17); re-exported here
// so existing imports of them from this module keep working.
export type { ImageAsset, ImageImport } from './images'
export type { ColourRole, ObjectBody, PaletteEvent, Reading, SlideAnchor, StyleDef, VisualObject } from './objects'

// One thing on a slide is the shared `ObjectBody` plus a `SlideAnchor` (E10.16, D177): read its place with
// `slideFrame(obj)`, not `obj.x`. Computes' slides have the same objects (`slide-host.ts`, D1473).
export type { ShapeDef, SlideObject } from './slide-host'

export interface SlideInfo {
  id: string
  objects: number
  /** The slide's name in the document's one namespace (D550); `''` for one that has none yet. */
  name?: string
}
export interface SlideState extends BaseState {
  slides: SlideInfo[]
  activeSlide: string
  objects: Record<string, SlideObject>
  library: ShapeDef[] // what the server offers for insertion
  shapes: Record<string, ShapeDef> // what this document has taken in, by id
  styles: Record<string, StyleDef>
  /** The speaker notes of the slides, Markdown, by slide; a slide without any is not here (D342). */
  notes: Record<string, string>
  /** The planned time of the slides in whole seconds, by slide; a slide without one is not here (D343). */
  times: Record<string, number>
  /** What a style property means and where a style can go: the server's `style_model` (D303, D304). */
  styleModel: StyleModel | null
  selected: string | null
  /** How the presentation is printed (D917): layout and page; `null` for a server that does not know printing. */
  printSetup: PrintSetupData | null
  /** The lists the words of text boxes may be items of, and how they are drawn (E9.21, E9.22). */
  lists: ListInfo[]
  schemes: SchemeInfo[]
  /** What is drawn before the words of an object that is a list item or a numbered title, by object id: the server
   *  counts across the boxes of all slides, in reading order. */
  labels: Record<string, Label>
  /** The lines of every agenda (E9.31), by object id: derived by the server from the slide titles. */
  agendas: Record<string, ContentsEntry[]>
  /** What the references in the words of each object read as, by object id (step H). */
  referenced: Record<string, Shown[]>
}

export class SlideSession extends BaseSession<SlideState> implements SlideHost {
  /** Showing a slide, and selecting, moving and putting objects on it, as computes does (D1473). */
  private readonly slide = new SlideActions({
    state: this.state,
    write: (method, params) => this.write(method, params),
    lockObject: (id, holder) => this.lockObject(id, holder),
    changed: (method, params) => this.changed(method, params),
  })

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, {
      slides: [],
      activeSlide: '',
      library: [],
      notes: {},
      times: {},
      styleModel: null,
      selected: null,
      printSetup: null,
      lists: [],
      schemes: [],
      labels: {},
      agendas: {},
      referenced: {},
    })
  }

  // ------------------------------------------------------------------------------ loading
  protected async loadApp() {
    const link = this.need()
    const s = this.state
    const [slides, shapes, images, styles, palette, styleModel] = await Promise.all([
      link.request<SlideInfo[]>('slides'),
      link.request<{ library: ShapeDef[]; document: ShapeDef[] }>('shapes'),
      link.request<ImageAsset[]>('images'),
      link.request<StyleDef[]>('styles'),
      link.request<PaletteEvent>('palette'),
      link.request<StyleModel>('style_model'),
    ])
    const loaded = await Promise.all(
      slides.map((slide) => link.request<{ objects: SlideObject[]; notes?: string; seconds?: number | null }>('slide', { slide: slide.id })),
    )
    // an older server knows neither: the preview then starts from slide-sized pages and offers no language; nor lists
    const [printSetup, language, numbering, contents, fields] = await Promise.all([
      link.request<PrintSetupData>('print_setup').catch(() => null),
      link
        .request<{ language: string | null }>('language')
        .then((a) => a.language)
        .catch(() => undefined),
      link.request<{ lists: ListInfo[]; schemes: SchemeInfo[]; labels: Record<string, Label> }>('lists').catch(() => null),
      link.request<{ entries: Record<string, ContentsEntry[]> }>('contents').catch(() => null),
      link.request<{ fields: Record<string, Shown[]> }>('fields').catch(() => null),
    ])
    s.printSetup = printSetup
    s.language = language
    s.lists = numbering?.lists ?? []
    s.schemes = numbering?.schemes ?? []
    s.labels = numbering?.labels ?? {}
    s.agendas = contents?.entries ?? {}
    s.referenced = fields?.fields ?? {}
    s.objects = {}
    s.order = {}
    s.notes = {}
    s.times = {}
    slides.forEach((slide, i) => {
      // an older server sends neither: no notes and no times, as for a slide that has none
      if (loaded[i]!.notes) s.notes[slide.id] = loaded[i]!.notes!
      if (typeof loaded[i]!.seconds === 'number') s.times[slide.id] = loaded[i]!.seconds!
      s.order[slide.id] = loaded[i]!.objects.map((o) => o.id)
      for (const o of loaded[i]!.objects) s.objects[o.id] = o
    })
    s.slides = slides
    s.library = shapes.library
    s.shapes = Object.fromEntries(shapes.document.map((d) => [d.id, d]))
    s.images = Object.fromEntries(images.map((x) => [x.id, x]))
    s.styles = Object.fromEntries(styles.map((x) => [x.id, x]))
    s.palette = palette
    s.styleModel = styleModel
    if (!slides.some((x) => x.id === s.activeSlide)) s.activeSlide = slides[0]?.id ?? ''
    if (s.selected && !s.objects[s.selected]) s.selected = null
  }

  // -- tags (E5.20, D551)
  protected override things(): Thing[] {
    const s = this.state
    const out: Thing[] = []
    for (const slide of s.slides) if (slide.name) out.push({ id: slide.id, name: s.renamed[slide.id] ?? slide.name, kind: 'slide' })
    for (const o of Object.values(s.objects)) if (o.name) out.push({ id: o.id, name: s.renamed[o.id] ?? o.name, kind: o.kind })
    return out
  }
  protected override async inView(): Promise<Thing[]> {
    const here = this.state.activeSlide
    return this.things().filter((t) => this.holderOf(t.id) === here)
  }
  override async unnamedInView(): Promise<number> {
    const s = this.state
    const slide = s.slides.find((x) => x.id === s.activeSlide)
    return this.slideObjects(s.activeSlide).filter((o) => !o.name).length + (slide && !slide.name ? 1 : 0)
  }
  protected override tracksThings(): boolean {
    return true
  }
  protected override holderOf(id: string): string | null {
    const s = this.state
    if (s.slides.some((x) => x.id === id)) return id
    return s.objects[id]?.anchor.holder ?? null
  }
  protected override currentHolder(): string | null {
    return this.state.activeSlide || null
  }
  protected override showHolder(id: string): void {
    if (this.state.slides.some((x) => x.id === id)) this.state.activeSlide = id
  }

  /** A step of the replay is shown on the slide it touched (D551). */
  protected override followReplay(focus: Region[]): void {
    const slide = holderOf(firstFocus(focus))
    if (slide && this.state.slides.some((x) => x.id === slide)) this.state.activeSlide = slide
  }

  /** The objects of a slide, the one in front last. */
  slideObjects(slide: string): SlideObject[] {
    return (this.state.order[slide] ?? []).map((id) => this.state.objects[id]).filter((o): o is SlideObject => o !== undefined)
  }

  /** The objects of a slide that colleagues have selected, and whether they hold them. */
  selectedByOthers(slide: string): Other[] {
    return othersOn(this.state, (holder) => holder === slide)
  }

  // ------------------------------------------------------------------------------ events
  /** A slide's tab shows how many objects it has; a selected object that went is let go of. */
  protected override objectsChanged(e: ObjectsEvent): void {
    const s = this.state
    const info = s.slides.find((x) => x.id === e.holder)
    if (info) info.objects = e.order.length
    this.track(this.slide.gone(e.removed))
  }

  protected onAppEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'slides':
        this.track(this.reload())
        return true
      case 'print_setup':
        s.printSetup = data.setup as PrintSetupData
        return true
      case 'labels':
        for (const [id, label] of Object.entries(data.labels as Record<string, Label | null>)) {
          if (label) s.labels[id] = label
          else delete s.labels[id]
        }
        return true
      case 'fields':
        s.referenced[data.paragraph as string] = data.fields as Shown[]
        return true
      case 'generated': {
        const { paragraph, entries } = data as { paragraph: string; entries: ContentsEntry[] | null }
        if (entries) s.agendas[paragraph] = entries
        else delete s.agendas[paragraph]
        return true
      }
      case 'lists':
        s.lists = data.lists as ListInfo[]
        return true
      case 'schemes':
        s.schemes = data.schemes as SchemeInfo[]
        return true
      case 'slide_notes':
        if (data.notes) s.notes[data.slide as string] = data.notes as string
        else delete s.notes[data.slide as string]
        return true
      case 'slide_time':
        if (typeof data.seconds === 'number') s.times[data.slide as string] = data.seconds
        else delete s.times[data.slide as string]
        return true
    }
    return false
  }

  // ------------------------------------------------------------------------------ doing things

  /** Put a container of `type` on the slide that is shown, in `frame`; its id, or null after telling why not. */
  async addContainer(type: string, frame: Frame): Promise<string | null> {
    const id = await this.addContainerAt(type, { slide: this.state.activeSlide, x: frame.x, y: frame.y }, { w: frame.w, h: frame.h }, undefined, true)
    if (id) await this.select(id)
    return id
  }

  /** The words of a text box are one fenced block (```latex … ```) of a type the server makes: the box becomes a container
   * of that type, in the same place and size, holding the text between the fences (D560). Its id, or null if the words
   * are not such a block (nothing is changed then) or the container could not be made (the box stays). */
  async fenceToContainer(id: string, words: string): Promise<string | null> {
    const box = this.state.objects[id]
    const fenced = parseFence(words, this.state.containerTypes.map((k) => k.type))
    if (!box || !fenced) return null
    const made = await this.addContainerAt(
      fenced.type,
      { slide: box.anchor.holder, x: box.anchor.x, y: box.anchor.y },
      { w: box.w, h: box.h },
      fenced.source,
    )
    if (!made) return null
    await this.removeObject(id)
    await this.select(made)
    return made
  }

  /** Put a text box on the slide that is shown; its id, or null after telling the person why not. */
  addText(frame: Frame): Promise<string | null> {
    return this.slide.insert({ kind: 'text' }, frame)
  }

  /** Put a shape from the library (or the document) on the slide that is shown. */
  addShape(shape: string, frame: Frame): Promise<string | null> {
    return this.slide.insert({ kind: 'shape', shape }, frame)
  }

  /**
   * Import a picture from disk and put it on the slide that is shown (E10.8); its id, or null after telling the
   * person why not. `data` is the file's bytes, base64 (see `lib/images.ts`'s `fileToBase64`); `sourcePath` is the
   * file's full path if the caller could get one — a plain web browser cannot, for its own security, and passes
   * `null`. Clipboard and drag-and-drop import are not built yet; this is the "browse a file" path only.
   */
  async addImage(picture: PictureImport, frame: Frame): Promise<string | null> {
    const id = await this.putPicture(picture, { slide: this.state.activeSlide, ...frame })
    if (id) await this.select(id)
    return id
  }

  /** Print the presentation another way (D917): layout and page, one step for everybody. */
  async setPrintSetup(setup: PrintSetupData): Promise<boolean> {
    return this.changed('set_print_setup', { setup })
  }

  // -- what a talk is prepared with: speaker notes and planned times (D342, D343)
  /** The speaker notes of a slide, Markdown; `""` if it has none. */
  notesOf(slide: string): string {
    return this.state.notes[slide] ?? ''
  }

  /** The planned time of a slide in whole seconds; `null` if it has none. */
  secondsOf(slide: string): number | null {
    return this.state.times[slide] ?? null
  }

  /** How long the talk is planned to take: the planned times added up, how many slides have one and how many do not
   * (D343: a slide without a time counts nothing, and the person is told so rather than given a guess). */
  plan(): { seconds: number; planned: number; unplanned: number } {
    const ids = this.state.slides.map((slide) => slide.id)
    const times = ids.map((id) => this.state.times[id]).filter((seconds): seconds is number => seconds !== undefined)
    return { seconds: times.reduce((a, b) => a + b, 0), planned: times.length, unplanned: ids.length - times.length }
  }

  // -- lists in text boxes (E9.21, E9.22). The server counts the items across every box of every slide, in reading order
  // (slide by slide, bottom to top); what is asked for here is structure, and the markers arrive as `labels` events.
  /** The words of every object, in the order they are read, by object id: the order lists are counted in. */
  readingOrder(): string[] {
    return this.state.slides.flatMap((slide) => this.slideObjects(slide.id).filter((o) => o.paragraph).map((o) => o.id))
  }

  /** The list item the words of the selected object are, or `null`. */
  selectedItem(): { list: string; level: number } | null {
    const id = this.state.selected
    return (id && this.state.objects[id]?.paragraph?.item) || null
  }

  /** The scheme of the list the selected object's words are an item of, or `null`. */
  selectedScheme(): string | null {
    const item = this.selectedItem()
    return (item && this.state.lists.find((l) => l.id === item.list)?.scheme) ?? null
  }

  /** Can the selected object's words be made an item: an object with words, and a document I may change? */
  canList(): boolean {
    const id = this.state.selected
    return !this.readOnly && !!id && !!this.state.objects[id]?.paragraph
  }

  /** May the list of the selected box go on from an earlier one: it is the list's first box, and a box of another
   *  list of the same scheme is read before it (the server's `continue_list` rule). */
  canContinue(): boolean {
    const item = this.selectedItem()
    const scheme = this.selectedScheme()
    if (!item || !scheme) return false
    const order = this.readingOrder()
    const itemOf = (id: string) => this.state.objects[id]?.paragraph?.item
    const first = order.findIndex((id) => itemOf(id)?.list === item.list)
    if (order[first] !== this.state.selected) return false
    return order.slice(0, first).some((id) => {
      const other = itemOf(id)
      return !!other && other.list !== item.list && this.state.lists.find((l) => l.id === other.list)?.scheme === scheme
    })
  }

  private async listRequest(method: string, params: Record<string, unknown>): Promise<boolean> {
    return this.changed(method, { ...params })
  }

  /** Bullets or numbers for the selected box, or (`null`) none; asking for what it is takes it out of its list. */
  makeList(scheme: string | null): Promise<boolean> {
    const id = this.state.selected
    return id && this.canList() ? this.listRequest('make_list', { paragraphs: [id], scheme }) : Promise.resolve(false)
  }

  /** Move the selected box's item one level in (`1`) or out (`-1`). */
  indent(by: 1 | -1): Promise<boolean> {
    const id = this.state.selected
    return id && this.selectedItem() ? this.listRequest('indent_item', { paragraphs: [id], by }) : Promise.resolve(false)
  }

  /** Let the list of the selected box go on where the nearest earlier list of its kind ends. */
  continueList(): Promise<boolean> {
    const id = this.state.selected
    return id && this.selectedItem() ? this.listRequest('continue_list', { paragraph: id }) : Promise.resolve(false)
  }

  /** Number the first level of the selected box's list from `start` on. */
  startAt(start: number): Promise<boolean> {
    const item = this.selectedItem()
    return item ? this.listRequest('list_start', { list: item.list, start }) : Promise.resolve(false)
  }

  /** What is drawn before the words of an object, and how far its level moves them in (em): its list marker, or the
   *  number its style gives it (a numbered slide title), which is not moved in. `null` for none. */
  markOf(id: string): { marker: string; indent: number } | null {
    const label = this.state.labels[id]
    if (!label) return null
    const item = this.state.objects[id]?.paragraph?.item
    const scheme = item && this.state.schemes.find((x) => x.id === this.state.lists.find((l) => l.id === item.list)?.scheme)
    return { marker: label.marker, indent: item ? item.level * (scheme?.indent ?? 1.6) : 0 }
  }

  // -- agendas (E9.31): a text box whose lines are the slide titles, derived by the server; its options are a table of
  // contents' (`BaseSession.setContents`), and it is taken away as any object is.
  /** The lines of an object that is an agenda, or `null` for any other object. */
  agendaOf(id: string): ContentsEntry[] | null {
    return this.state.objects[id]?.paragraph?.generated ? (this.state.agendas[id] ?? []) : null
  }

  /** Put an agenda on a slide (the one shown, by default) and select it. */
  async insertAgenda(slide: string = this.state.activeSlide): Promise<string | null> {
    if (!slide) return null
    const done = await this.write('insert_agenda', { slide })
    if (done === false) return null
    const id = done.object as string
    await this.select(id)
    return id
  }

  // -- references in the words of objects (step H) ------------------------------------------------------------------
  /** What a reference can point at, for the picker: the slide titles, numbered items and named things. */
  async referenceTargets(query = ''): Promise<ReferenceTarget[]> {
    try {
      return await this.need().request<ReferenceTarget[]>('reference_targets', { query })
    } catch {
      return [] // an older server knows no references
    }
  }

  /** Put a reference to `target` into the words of an object at `offset` (a UTF-16 offset of its words). */
  async insertReference(id: string, offset: number, target: string, show: Show): Promise<boolean> {
    const words = this.state.objects[id]?.paragraph?.text ?? ''
    const params = { paragraph: id, offset: pointOf(words, Math.min(offset, words.length)), target, show }
    return this.changed('insert_reference', params)
  }

  /** The first reference in the words of an object, as `{field, shown}`, or `null`. */
  referenceIn(id: string): { field: RefField; shown: Shown | undefined } | null {
    const field = this.state.objects[id]?.paragraph?.fields?.[0]
    return field ? { field, shown: this.state.referenced[id]?.[0] } : null
  }

  /** Write the notes of a slide (D342): one step in the history, for everybody. `""` clears them. */
  async setNotes(slide: string, notes: string): Promise<boolean> {
    return this.changed('set_slide_notes', { slide, notes })
  }

  /** Plan a time for a slide (D343), whole seconds; `null` takes the plan away. */
  async setTime(slide: string, seconds: number | null): Promise<boolean> {
    return this.changed('set_slide_time', { slide, seconds })
  }

  /** What the tab of slide `id` (the `index`th, from 0) says: its name, or its place while it has none. */
  slideLabel(id: string, index: number): string {
    return this.nameOf(id) || t('Slide {n}', { n: index + 1 })
  }

  async addSlide(): Promise<string | null> {
    const done = await this.write('add_slide')
    if (done === false) return null
    await this.showSlide(done.slide)
    return done.slide
  }

  move(id: string, x: number, y: number): Promise<boolean> {
    return this.slide.move(id, x, y)
  }

  resize(id: string, frame: Frame): Promise<boolean> {
    return this.slide.resize(id, frame)
  }

  /** Hold an object to the grid (`snap` true) or release it (false); its own step in the history (E10.15). */
  async setSnap(id: string, snap: boolean): Promise<boolean> {
    return this.changed('set_snap', { id, snap })
  }

  // -- styles and the palette (E9.7, D200, D203). The same eight methods computes' session has, because the style
  // menu is one component talking to one `StyleHost` and neither knows which app it is in.
  /** Put a style into one slot of these targets — the one style API every app has (`apply_style`, D304). */
  async applyStyle(targets: StyleTarget[], style: string, slot: string): Promise<boolean> {
    return this.changed('apply_style', { targets, style, slot })
  }

  /** Change these targets only, in one slot: a new style from `parent`, named later (`deviate`, D75, D309). */
  async deviateStyle(parent: string, targets: StyleTarget[], slot: string, edit: CssEdit): Promise<boolean> {
    return this.changed('deviate', { parent, targets, slot, ...edit })
  }

  showSlide(slide: string): Promise<void> {
    return this.slide.show(slide)
  }

  /** Select an object (null: nothing). Selecting holds it; a colleague who holds it first keeps it. */
  select(id: string | null): Promise<void> {
    return this.slide.select(id)
  }
}
