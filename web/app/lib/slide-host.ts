// What the slide on screen (`SlideCanvas.vue`) needs of a session (E6.31, D1473): a slide is the same page of objects in
// creates and in computes, so one canvas draws both. Creates' `SlideSession` and computes' `Session` implement it; what
// only creates has (holding an object to the grid, the agenda, the markers of lists, writing a fenced block as a
// container) is optional, and the canvas leaves it out where a session does not bring it.
import type { BaseSession, BaseState } from './base-session'
import type { ContentsEntry } from './contents'
import type { Frame } from './geometry'
import type { Shown } from './references'
import type { ShapeDef, SlideObject } from './slide-session'
import type { Anchor, StyleDef, StyleModel, StyleTarget, VisualObject } from './objects'
import type { CssEdit } from './style-css'

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

/** A colleague's selection on a slide, and whether they hold it. */
export interface Other {
  id: string
  user: string
  locked: boolean
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
    | 'notice'
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
}

/** `object` if it is on a slide; `undefined` else (a workbook's objects hang at cells too). */
export function onSlide(object: VisualObject<Anchor> | undefined): SlideObject | undefined {
  return object?.anchor.kind === 'slide' ? (object as SlideObject) : undefined
}

/** The objects of `holder` that colleagues have selected, and whether they hold them: what `selectedByOthers` says in
 * both apps. */
export function othersOn(state: Pick<BaseState, 'presence' | 'me'>, holder: string): Other[] {
  const found: Other[] = []
  for (const [user, here] of Object.entries(state.presence)) {
    if (user === state.me.user) continue
    for (const region of here.regions) {
      if (region.kind === 'objects' && region.holder === holder) for (const id of region.ids) found.push({ id, user, locked: here.locked })
    }
  }
  return found
}
