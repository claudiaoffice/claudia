// One person's view of one presentation (creates): the slides, their objects and the shapes, kept up to date from the
// server's events. What every document has in common (connection, history, chat, people, undo) is in BaseSession.
import { type LinkLike, type Region } from './protocol'
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import type { Frame } from './geometry'
import type { ImageAsset, ImageImport } from './images'

// `ImageAsset`/`ImageImport` moved to `./images` (shared with computes' `session.ts`, E10.11); re-exported here
// so existing imports of them from this module keep working.
export type { ImageAsset, ImageImport } from './images'

export interface SlideObject {
  id: string
  slide: string
  kind: 'text' | 'shape' | 'image'
  x: number
  y: number
  w: number
  h: number
  style: string
  text: string
  shape: string | null
  image: string | null
  imported: ImageImport | null
}
/** An outline: `path` is an SVG path in a box of 100 by 100; `aspect` is width / height when it must be kept. */
export interface ShapeDef {
  format: number
  id: string
  name: string
  path: string
  aspect: number | null
  text_area: { x: number; y: number; w: number; h: number }
}
export interface StyleDef {
  id: string
  name: string
  purpose: string
  css: Record<string, string>
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
  selected: string | null
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
      selected: null,
    })
  }

  // ------------------------------------------------------------------------------ loading
  protected async loadApp() {
    const link = this.need()
    const s = this.state
    const [slides, shapes, images, styles] = await Promise.all([
      link.request<SlideInfo[]>('slides'),
      link.request<{ library: ShapeDef[]; document: ShapeDef[] }>('shapes'),
      link.request<ImageAsset[]>('images'),
      link.request<StyleDef[]>('styles'),
    ])
    const loaded = await Promise.all(slides.map((slide) => link.request<{ objects: SlideObject[] }>('slide', { slide: slide.id })))
    s.objects = {}
    s.order = {}
    slides.forEach((slide, i) => {
      s.order[slide.id] = loaded[i]!.objects.map((o) => o.id)
      for (const o of loaded[i]!.objects) s.objects[o.id] = o
    })
    s.slides = slides
    s.library = shapes.library
    s.shapes = Object.fromEntries(shapes.document.map((d) => [d.id, d]))
    s.images = Object.fromEntries(images.map((x) => [x.id, x]))
    s.styles = Object.fromEntries(styles.map((x) => [x.id, x]))
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
        if (region.kind === 'objects' && region.slide === slide) for (const id of region.ids) found.push({ id, user, locked: here.locked })
      }
    }
    return found
  }

  // ------------------------------------------------------------------------------ events
  protected onAppEvent(name: string, data: any): boolean {
    const s = this.state
    switch (name) {
      case 'objects': {
        for (const o of data.changed as SlideObject[]) s.objects[o.id] = o
        for (const id of data.removed as string[]) delete s.objects[id]
        s.order[data.slide] = data.order
        const info = s.slides.find((x) => x.id === data.slide)
        if (info) info.objects = data.order.length
        if (s.selected && (data.removed as string[]).includes(s.selected)) {
          s.selected = null
          this.track(this.letGo())
        }
        return true
      }
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
    picture: { data: string; alt: string; sourceName: string; sourcePath: string | null },
    frame: Frame,
  ): Promise<string | null> {
    const done = await this.attempt('add_image', {
      slide: this.state.activeSlide,
      data: picture.data,
      alt: picture.alt,
      source_name: picture.sourceName,
      source_path: picture.sourcePath,
      ...frame,
      base: this.state.revision,
    })
    if (done === false) return null
    await this.select(done.object)
    return done.object
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

  async remove(id: string): Promise<boolean> {
    return (await this.attempt('remove_object', { id, base: this.state.revision })) !== false
  }

  async showSlide(slide: string): Promise<void> {
    if (slide === this.state.activeSlide) return
    await this.select(null)
    this.state.activeSlide = slide
  }

  // -- the selection: shown to the others, and held so that nobody changes the object under my hands
  private regionOf(id: string): Region[] {
    return [{ kind: 'objects', slide: this.state.objects[id]?.slide ?? this.state.activeSlide, ids: [id] }]
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
