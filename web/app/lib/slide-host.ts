// What the slide on screen (`SlideCanvas.vue`) needs of a session (E6.31, D1473): a slide is the same page of objects in
// creates and in computes, so one canvas draws both. Creates' `SlideSession` and computes' `Session` implement it; what
// only creates has (holding an object to the grid, the agenda, the markers of lists, writing a fenced block as a
// container) and what only computes has (the figure of a chart) is optional, and the canvas leaves it out where a
// session does not bring it.
import type { BaseSession, BaseState } from './base-session'
import type { ChartFigures } from './charts'
import type { ContentsEntry } from './contents'
import type { Frame } from './geometry'
import type { Shown } from './references'
import type { WireData } from './protocol'
import type { Anchor, Other, SlideAnchor, StyleDef, StyleModel, StyleTarget, VisualObject } from './objects'
import type { CssEdit } from './style-css'

/** An object on a slide: the shared body and where on its slide it sits (D177). */
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

/** What the canvas reads of a session's state. */
export interface SlideHostState extends BaseState {
  /** The slide on screen (`''`: none). */
  activeSlide: string
  /** The object selected on it, or `null`. */
  selected: string | null
  /** The objects of the document by id; the canvas draws those of the slide on screen (`slideObjects`). */
  objects: Record<string, VisualObject<Anchor>>
  /** The outlines the document has taken in, by id. */
  shapes: Record<string, ShapeDef>
  styles: Record<string, StyleDef>
  styleModel: StyleModel | null
  /** What the references in the words of each object read as, by object id (step H; none in a workbook). */
  referenced: Record<string, Shown[]>
}

/** A picture from a file, as `addImage` takes it. */
export interface PictureImport {
  data: string
  alt: string
  sourceName: string
  sourcePath: string | null
  decorative?: boolean
  fit?: boolean
}

export interface SlideHost
  extends Pick<
    BaseSession<SlideHostState>,
    | 'tellLookOnly'
    | 'readOnly'
    | 'rotateObject'
    | 'removeObject'
    | 'clearBack'
    | 'writeWords'
    | 'setContainerSource'
    | 'styleViews'
    | 'bodies'
    | 'changeStyle'
    | 'renameStyle'
    | 'checkCss'
    | 'setRole'
    | 'thingDetails'
    | 'nameAndDescribe'
  > {
  readonly state: SlideHostState
  /** The objects of a slide, the one in front last. */
  slideObjects(slide: string): SlideObject[]
  /** The objects of a slide that colleagues have selected. */
  selectedByOthers(slide: string): Other[]
  /** Select an object on the slide on screen (`null`: nothing), shown to the others and held. */
  select(id: string | null): Promise<void>
  move(id: string, x: number, y: number): Promise<boolean>
  resize(id: string, frame: Frame): Promise<boolean>
  /** Put a picture on the slide on screen, in `frame`; its id, or `null` after telling why not. */
  addImage(picture: PictureImport, frame: Frame): Promise<string | null>
  applyStyle(targets: StyleTarget[], style: string, slot: string): Promise<boolean>
  deviateStyle(parent: string, targets: StyleTarget[], slot: string, edit: CssEdit): Promise<boolean>
  // creates only
  markOf?(id: string): { marker: string; indent: number } | null
  agendaOf?(id: string): ContentsEntry[] | null
  setSnap?(id: string, snap: boolean): Promise<boolean>
  fenceToContainer?(id: string, words: string): Promise<string | null>
  // computes only: what draws a chart on a slide (E6.31, D1475)
  readonly figures?: ChartFigures
}

/** Is `object` on a slide? (A workbook's objects hang at cells too.) */
export function isOnSlide(object: VisualObject<Anchor> | undefined): object is SlideObject {
  return object?.anchor.kind === 'slide'
}

/** What a session lends its slide actions: where it keeps the slide shown and the selection, and its own requests. */
export interface SlidePort {
  readonly state: { activeSlide: string; selected: string | null; objects: Record<string, VisualObject<Anchor>> }
  write(method: string, params: Record<string, unknown>): Promise<WireData | false>
  /** lock the object selected, or unlock (`null`); false when a colleague has it locked (`BaseSession.lockObject`) */
  lockObject(id: string | null, holder?: string): Promise<boolean>
  /** `write`, for a change whose answer nobody needs: did it happen? */
  changed(method: string, params: Record<string, unknown>): Promise<boolean>
}

/** What creates and computes do the same way on a slide (D1473): show one, select an object on it (shown to the others
 * and held, so that nobody changes it under my hands; a colleague who holds it first keeps it), move, resize and put
 * an object there. Each session has one and answers `SlideHost` with it. */
export class SlideActions {
  constructor(private readonly port: SlidePort) {}

  /** Show a slide (`''`: none) with nothing selected on it. */
  async show(slide: string): Promise<void> {
    if (slide === this.port.state.activeSlide) return
    await this.select(null)
    this.port.state.activeSlide = slide
  }

  async select(id: string | null): Promise<void> {
    const s = this.port.state
    if (id === s.selected) return
    s.selected = id
    const locked = await this.port.lockObject(id, id === null ? undefined : (s.objects[id]?.anchor.holder ?? s.activeSlide))
    if (!locked && s.selected === id) s.selected = null
  }

  /** The selected object went (somebody removed it): it is let go of. */
  async gone(removed: readonly string[]): Promise<void> {
    if (!removed.includes(this.port.state.selected ?? '')) return
    this.port.state.selected = null
    await this.port.lockObject(null)
  }

  async move(id: string, x: number, y: number): Promise<boolean> {
    return this.port.changed('move_object', { id, x, y })
  }

  async resize(id: string, frame: Frame): Promise<boolean> {
    return this.port.changed('resize_object', { id, ...frame })
  }

  /** Put a text box (`{kind: 'text'}`) or a shape (`{kind: 'shape', shape}`) on the slide shown, in `frame`, and select
   * it; its id, or `null` after the session told why not. */
  async insert(params: Record<string, unknown>, frame: Frame): Promise<string | null> {
    const done = await this.port.write('add_object', { slide: this.port.state.activeSlide, ...params, ...frame })
    if (done === false) return null
    await this.select(done.object)
    return done.object
  }
}
