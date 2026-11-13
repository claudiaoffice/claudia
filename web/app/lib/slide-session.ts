// One person's view of one presentation (creates): the slides, their objects and the shapes, kept up to date from the
// server's events. What every document has in common (connection, history, chat, people, undo) is in BaseSession.
import type { LinkLike, Region, WireData } from './protocol'
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import { describeParams } from './descriptions'
import type { Frame } from './geometry'
import type { ImageAsset } from './images'
import type { ColourRole, ObjectBody, ObjectsEvent, PaletteEvent, SlideAnchor, StyleDef, StyleModel, StyleTarget, VisualObject } from './objects'
import type { CssCheck, CssEdit } from './style-css'
import type { PrintSetupData } from '@claudia/layout'

// `ImageAsset`/`ImageImport` moved to `./images` (shared with computes' `session.ts`, E6.17); re-exported here
// so existing imports of them from this module keep working.
export type { ImageAsset, ImageImport } from './images'
export type { ColourRole, ObjectBody, PaletteEvent, Reading, SlideAnchor, StyleDef, VisualObject } from './objects'

/** One thing on a slide: the shared `ObjectBody` plus a `SlideAnchor` — the only part of it that is this app's
 * own (E10.16, D177). Read its place with `slideFrame(obj)`, not `obj.x`. */
export type SlideObject = VisualObject<SlideAnchor>
/** An outline: `path` is an SVG path in a box of 100 by 100; `aspect` is width / height when it must be kept. */
export interface ShapeDef {
  format: number
  id: string
  name: string
  path: string
  aspect: number | null
  text_area: { x: number; y: number; w: number; h: number }
}

export interface SlideInfo {
  id: string
  objects: number
}
export interface SlideState extends BaseState {
  slides: SlideInfo[]
  activeSlide: string
  objects: Record<string, SlideObject>
  order: Record<string, string[]> // slide -> object ids, the one in front last
  library: ShapeDef[] // what the server offers for insertion
  shapes: Record<string, ShapeDef> // what this document has taken in, by id
  images: Record<string, ImageAsset> // the decoded pictures this document has taken in, by id (E10.8)
  styles: Record<string, StyleDef>
  /** The speaker notes of the slides, Markdown, by slide; a slide without any is not here (D342). */
  notes: Record<string, string>
  /** The planned time of the slides in whole seconds, by slide; a slide without one is not here (D343). */
  times: Record<string, number>
  /** The document's colour roles and how they read against each other (D200); the styles are what is drawn from. */
  palette: PaletteEvent | null
  /** What a style property means and where a style can go: the server's `style_model` (D303, D304). */
  styleModel: StyleModel | null
  selected: string | null
  /** How the presentation is printed (D917): layout and page; `null` for a server that does not know printing. */
  printSetup: PrintSetupData | null
  /** The language of the presentation (D915, D917), a BCP 47 tag; `null` when not set, `undefined` for a server
   *  that does not know languages. */
  language: string | null | undefined
}

export class SlideSession extends BaseSession<SlideState> {
  private holding = false
  private shown = ''

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, {
      slides: [],
      activeSlide: '',
      objects: {},
      order: {},
      library: [],
      shapes: {},
      images: {},
      styles: {},
      notes: {},
      times: {},
      palette: null,
      styleModel: null,
      selected: null,
      printSetup: null,
      language: undefined,
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
    // an older server knows neither: the preview then starts from slide-sized pages and offers no language
    const [printSetup, language] = await Promise.all([
      link.request<PrintSetupData>('print_setup').catch(() => null),
      link
        .request<{ language: string | null }>('language')
        .then((a) => a.language)
        .catch(() => undefined),
    ])
    s.printSetup = printSetup
    s.language = language
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

  /** The objects of a slide, the one in front last. */
  objectsOn(slide: string): SlideObject[] {
    return (this.state.order[slide] ?? []).map((id) => this.state.objects[id]).filter((o): o is SlideObject => o !== undefined)
  }

  /** The objects of a slide that colleagues have selected, and whether they hold them. */
  selectedByOthers(slide: string): { id: string; user: string; locked: boolean }[] {
    const found: { id: string; user: string; locked: boolean }[] = []
    for (const [user, here] of Object.entries(this.state.presence)) {
      if (user === this.state.me.user) continue
      for (const region of here.regions) {
        if (region.kind === 'objects' && region.container === slide) for (const id of region.ids) found.push({ id, user, locked: here.locked })
      }
    }
    return found
  }

  // ------------------------------------------------------------------------------ events
  protected onAppEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'objects': {
        const e = data as ObjectsEvent // typed, so a renamed field is a compile error and not a silent undefined
        for (const o of e.changed as SlideObject[]) s.objects[o.id] = o
        for (const id of e.removed) delete s.objects[id]
        s.order[e.container] = e.order
        const info = s.slides.find((x) => x.id === e.container)
        if (info) info.objects = e.order.length
        if (e.removed.includes(s.selected ?? '')) {
          s.selected = null
          this.track(this.letGo())
        }
        return true
      }
      case 'styles':
        // Found by driving a real browser: the styles were requested once at open and never again, so a style a
        // colleague changed — or a palette role anybody changed (D200) — did not reach this slide until the
        // document was reopened. The whole book travels, as it does in composes.
        s.styles = Object.fromEntries((data.styles as StyleDef[]).map((x) => [x.id, x]))
        return true
      case 'palette':
        // Only the styles are drawn from, and they arrive with the event above. Kept so that a palette change is
        // not reported as an unknown event, and so the roles are here for the menu that will offer them.
        s.palette = data as PaletteEvent
        return true
      case 'shape':
        if (data.definition) s.shapes[data.id] = data.definition
        else delete s.shapes[data.id]
        return true
      case 'image':
        if (data.asset) s.images[data.id] = data.asset
        else delete s.images[data.id]
        return true
      case 'slides':
        this.track(this.reload())
        return true
      case 'print_setup':
        s.printSetup = data.setup as PrintSetupData
        return true
      case 'language':
        s.language = (data.language as string | null) ?? null
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
  private async insert(params: Record<string, unknown>, frame: Frame): Promise<string | null> {
    const done = await this.attempt('add_object', { slide: this.state.activeSlide, ...params, ...frame, base: this.state.revision })
    if (done === false) return null
    await this.select(done.object)
    return done.object
  }

  /** Put a text box on the slide that is shown; its id, or null after telling the person why not. */
  addText(frame: Frame): Promise<string | null> {
    return this.insert({ kind: 'text' }, frame)
  }

  /** Put a shape from the library (or the document) on the slide that is shown. */
  addShape(shape: string, frame: Frame): Promise<string | null> {
    return this.insert({ kind: 'shape', shape }, frame)
  }

  /**
   * Import a picture from disk and put it on the slide that is shown (E10.8); its id, or null after telling the
   * person why not. `data` is the file's bytes, base64 (see `lib/images.ts`'s `fileToBase64`); `sourcePath` is the
   * file's full path if the caller could get one — a plain web browser cannot, for its own security, and passes
   * `null`. Clipboard and drag-and-drop import are not built yet; this is the "browse a file" path only.
   */
  async addImage(
    picture: { data: string; alt: string; sourceName: string; sourcePath: string | null; decorative?: boolean },
    frame: Frame,
  ): Promise<string | null> {
    const done = await this.attempt('add_image', {
      slide: this.state.activeSlide,
      data: picture.data,
      alt: picture.alt,
      source_name: picture.sourceName,
      source_path: picture.sourcePath,
      ...(picture.decorative ? { decorative: true } : {}),
      ...frame,
      base: this.state.revision,
    })
    if (done === false) return null
    await this.select(done.object)
    return done.object
  }

  /** Print the presentation another way (D917): layout and page, one step for everybody. */
  async setPrintSetup(setup: PrintSetupData): Promise<boolean> {
    if (this.readOnly) return false
    return (await this.attempt('set_print_setup', { setup, base: this.state.revision })) !== false
  }

  /** Say which language the presentation is written in (D917), or `null` for not known: one step, for everybody. */
  async setLanguage(language: string | null): Promise<boolean> {
    if (this.readOnly) return false
    return (await this.attempt('set_language', { language, base: this.state.revision })) !== false
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

  /** Write the notes of a slide (D342): one step in the history, for everybody. `""` clears them. */
  async setNotes(slide: string, notes: string): Promise<boolean> {
    if (this.readOnly) return false
    return (await this.attempt('set_slide_notes', { slide, notes, base: this.state.revision })) !== false
  }

  /** Plan a time for a slide (D343), whole seconds; `null` takes the plan away. */
  async setTime(slide: string, seconds: number | null): Promise<boolean> {
    if (this.readOnly) return false
    return (await this.attempt('set_slide_time', { slide, seconds, base: this.state.revision })) !== false
  }

  async addSlide(): Promise<string | null> {
    const done = await this.attempt('add_slide', { base: this.state.revision })
    if (done === false) return null
    await this.showSlide(done.slide)
    return done.slide
  }

  async move(id: string, x: number, y: number): Promise<boolean> {
    return (await this.attempt('move_object', { id, x, y, base: this.state.revision })) !== false
  }

  async resize(id: string, frame: Frame): Promise<boolean> {
    return (await this.attempt('resize_object', { id, ...frame, base: this.state.revision })) !== false
  }

  async setText(id: string, text: string): Promise<boolean> {
    return (await this.attempt('set_text', { id, text, base: this.state.revision })) !== false
  }

  /** Hold an object to the grid (`snap` true) or release it (false); its own step in the history (E10.15). */
  async setSnap(id: string, snap: boolean): Promise<boolean> {
    return (await this.attempt('set_snap', { id, snap, base: this.state.revision })) !== false
  }

  /** Say what an object is to someone who cannot see it, or that it is only decoration (BITV 1.1.1); its own step in the
   * history. A picture needs one or the other, which the server insists on. */
  async describe(id: string, description: string, decorative: boolean): Promise<boolean> {
    return (await this.attempt('describe_object', { id, ...describeParams(description, decorative), base: this.state.revision })) !== false
  }

  async remove(id: string): Promise<boolean> {
    return (await this.attempt('remove_object', { id, base: this.state.revision })) !== false
  }

  // -- styles and the palette (E9.7, D200, D203). The same eight methods computes' session has, because the style
  // menu is one component talking to one `StyleHost` and neither knows which app it is in.
  get readOnly(): boolean {
    return this.state.me.role === 'viewer'
  }

  /** The styles as the menu wants them, in the order the server lists them. */
  styleViews(): StyleDef[] {
    return Object.values(this.state.styles)
  }

  /** Every object of the document, for the use counts beside the style names. */
  bodies(): ObjectBody[] {
    // The client's `VisualObject` is flat — `ObjectBody & { anchor }` — so an object is already a body.
    return Object.values(this.state.objects)
  }


  /** Put a style into one slot of these targets — the one style API every app has (`apply_style`, D304). */
  async applyStyle(targets: StyleTarget[], style: string, slot: string): Promise<boolean> {
    return (await this.attempt('apply_style', { targets, style, slot, base: this.state.revision })) !== false
  }

  /** Change these targets only, in one slot: a new style from `parent`, named later (`deviate`, D75, D309). */
  async deviateStyle(parent: string, targets: StyleTarget[], slot: string, edit: CssEdit): Promise<boolean> {
    const params = { parent, targets, slot, ...edit, base: this.state.revision }
    return (await this.attempt('deviate', params)) !== false
  }

  /** Change a style for everything that has it — and for the styles based on it, where they say nothing (D73). */
  async changeStyle(style: string, edit: CssEdit): Promise<boolean> {
    return (await this.attempt('change_style', { style, ...edit, base: this.state.revision })) !== false
  }


  async renameStyle(style: string, name: string): Promise<boolean> {
    return (await this.attempt('rename_style', { style, name, base: this.state.revision })) !== false
  }

  /** Give a colour role another colour: every style that meant it follows, and so does every object (D200). */
  async setRole(role: string, colour: string): Promise<boolean> {
    return (await this.attempt('set_role', { role, colour, base: this.state.revision })) !== false
  }

  /** Put a whole palette in place of this document's — what "the colours it started with" does (D200). */
  async replacePalette(roles: ColourRole[]): Promise<boolean> {
    return (await this.attempt('replace_palette', { roles, base: this.state.revision })) !== false
  }

  /** What the server makes of this CSS text, line by line. A read: viewers may ask it too. */
  async checkCss(text: string): Promise<CssCheck | null> {
    try {
      return await this.need().request<CssCheck>('check_css', { text })
    } catch {
      return null
    }
  }

  async showSlide(slide: string): Promise<void> {
    if (slide === this.state.activeSlide) return
    await this.select(null)
    this.state.activeSlide = slide
  }

  // -- the selection: shown to the others, and held so that nobody changes the object under my hands
  private regionOf(id: string): Region[] {
    return [{ kind: 'objects', container: this.state.objects[id]?.anchor.container ?? this.state.activeSlide, ids: [id] }]
  }

  /** Select an object (null: nothing). Selecting holds it; a colleague who holds it first keeps it. */
  async select(id: string | null): Promise<void> {
    const s = this.state
    if (id === s.selected) return
    s.selected = id
    if (id === null) return this.letGo()
    const regions = this.regionOf(id)
    if (s.me.role === 'viewer') return this.showRegions(`select ${id}`, regions)
    if (!(await this.hold(regions)) && s.selected === id) s.selected = null
  }

  private async letGo(): Promise<void> {
    await this.release()
    await this.showRegions('nothing', [])
  }

  // ------------------------------------------------------------------------------ where I am, and holding what I work on
  /** Show the others where I am; `where` says it in few characters so that the same place is not sent twice. */
  private async showRegions(where: string, regions: Region[]): Promise<void> {
    if (where === this.shown || this.state.status !== 'open') return
    this.shown = where
    try {
      await this.need().request('presence', { regions })
    } catch {
      this.shown = '' // not important enough to bother the person; the next move tries again
    }
  }

  /** Hold these regions so that nobody else changes them; false after telling the person why not. */
  private async hold(regions: Region[]): Promise<boolean> {
    if ((await this.attempt('lock', { regions })) === false) return false
    this.holding = true
    this.shown = ''
    return true
  }

  private async release(): Promise<void> {
    if (!this.holding) return
    this.holding = false
    this.shown = ''
    try {
      await this.need().request('unlock')
    } catch {
      /* the lock runs out by itself */
    }
  }
}
