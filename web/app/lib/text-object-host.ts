// What composes tells the shared object interaction (`object-interaction.ts`, D1221) and what it does with the answer.
// The gesture works on boxes of the object layer, in screen pixels; the model keeps *where an object hangs*: a character
// of a paragraph plus how far it floats from it (`dx`, `dy`, D1023). This is the translation between the two, as pure
// functions: a drop becomes the paragraph nearest it and the offset that is left over (the contract note's "what each app
// does on release"), a drag of a top or left handle becomes a size and a new offset.
import type { Commit } from './object-gestures'
import type { Frame } from './geometry'

export interface Place {
  block: string
  offset: number
}
/** A point on the screen: the top-left corner of the character an object hangs from. */
export interface Spot {
  left: number
  top: number
}
/** One request to the server. A resize that moves the top left corner is two (the model has no single step for both). */
export type Step =
  | { kind: 'move'; place: Place; away: { dx: number; dy: number } }
  | { kind: 'resize'; w: number; h: number }
  | { kind: 'rotate'; rotation: number }

/** How far a box at `at` (in the layer's own coordinates) floats from the character at `spot` (on the screen), whole
 * pixels, as `floatBox` (`text-object-layer.ts`) will read it back. */
export function awayFrom(at: { x: number; y: number }, spot: Spot, layer: { left: number; top: number }): { dx: number; dy: number } {
  return { dx: Math.round(at.x - (spot.left - layer.left)), dy: Math.round(at.y - (spot.top - layer.top)) }
}

/** The paragraph a drop at screen height `y` belongs to: the one whose box holds it, else the nearest by distance; the
 * first of two that are equally near. `null` when there are no paragraphs. */
export function nearestBlock(rects: readonly { id: string; top: number; bottom: number }[], y: number): string | null {
  let best: { id: string; distance: number } | null = null
  for (const r of rects) {
    const distance = y < r.top ? r.top - y : y > r.bottom ? y - r.bottom : 0
    if (best === null || distance < best.distance) best = { id: r.id, distance }
  }
  return best?.id ?? null
}

/** The paragraph a table dragged to height `y` goes after: the one whose bottom edge is nearest (a table hangs from the
 * paragraph before it, E9.32); the first when two are equally near. `null` when there are no paragraphs. */
export function nearestGap(rects: readonly { id: string; bottom: number }[], y: number): string | null {
  let best: { id: string; distance: number } | null = null
  for (const r of rects) {
    const distance = Math.abs(y - r.bottom)
    if (best === null || distance < best.distance) best = { id: r.id, distance }
  }
  return best?.id ?? null
}

/** What the release of a gesture asks of the server. `current` is where the object hangs now with its spot on the
 * screen; `dropped` is the place the drop point is nearest to, with *its* spot (`null`: no better place was found).
 * A move that lands nearer to another character re-hangs the object from it, with the offset that is left over. */
export function stepsFor(
  change: Commit,
  at: { layer: { left: number; top: number }; start: Frame; current: { place: Place; spot: Spot }; dropped?: { place: Place; spot: Spot } | null },
): Step[] {
  switch (change.kind) {
    case 'rotate':
      return [{ kind: 'rotate', rotation: change.rotation }]
    case 'move': {
      const to = at.dropped ?? at.current
      return [{ kind: 'move', place: to.place, away: awayFrom({ x: change.x, y: change.y }, to.spot, at.layer) }]
    }
    case 'resize': {
      const { frame } = change
      const steps: Step[] = []
      if (frame.w !== at.start.w || frame.h !== at.start.h) steps.push({ kind: 'resize', w: frame.w, h: frame.h })
      // a handle on the top or the left edge moves the corner too: the object keeps its character, only the offset changes
      if (frame.x !== at.start.x || frame.y !== at.start.y) steps.push({ kind: 'move', place: at.current.place, away: awayFrom({ x: frame.x, y: frame.y }, at.current.spot, at.layer) })
      return steps
    }
  }
}
