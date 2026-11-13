// The presentation as it was when the show started (D341): a copy of the slides, their objects, notes and planned
// times, and of the styles, shapes and pictures they are drawn from. The show runs on it and on nothing else, so a
// colleague's edit changes nothing on the screen in front of the audience; the presenter view says how many steps the
// document has taken since, and offers to take them in between slides.
import type { ShowSlide } from './show'
import type { ShapeDef, SlideInfo, SlideObject, SlideSession, SlideState } from './slide-session'
import type { ImageAsset } from './images'
import type { StyleDef, StyleModel } from './objects'

export interface FrozenDeck {
  /** The revision the copy was taken at, `null` for a document that has none yet. */
  revision: string | null
  slides: SlideInfo[]
  objects: Record<string, SlideObject[]>
  notes: Record<string, string>
  times: Record<string, number>
  styles: Record<string, StyleDef>
  shapes: Record<string, ShapeDef>
  images: Record<string, ImageAsset>
  styleModel: StyleModel | null
}

/** Copy what the show draws from out of the session. A JSON round trip, because the session's state is reactive and a
 * reactive object is a view of the live one, not a copy. */
export function freeze(session: Pick<SlideSession, 'state' | 'objectsOn' | 'notesOf' | 'secondsOf'>): FrozenDeck {
  const s: SlideState = session.state
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value ?? null)) as T
  const objects: Record<string, SlideObject[]> = {}
  const notes: Record<string, string> = {}
  const times: Record<string, number> = {}
  for (const slide of s.slides) {
    objects[slide.id] = copy(session.objectsOn(slide.id))
    const note = session.notesOf(slide.id)
    if (note) notes[slide.id] = note
    const seconds = session.secondsOf(slide.id)
    if (seconds !== null) times[slide.id] = seconds
  }
  return {
    revision: s.revision ?? null,
    slides: copy(s.slides),
    objects,
    notes,
    times,
    styles: copy(s.styles),
    shapes: copy(s.shapes),
    images: copy(s.images),
    styleModel: copy(s.styleModel),
  }
}

/** The slides of a frozen deck as the show counts them. */
export function showSlides(deck: FrozenDeck): ShowSlide[] {
  return deck.slides.map((slide) => ({ id: slide.id, seconds: deck.times[slide.id] ?? null, notes: deck.notes[slide.id] ?? '' }))
}
