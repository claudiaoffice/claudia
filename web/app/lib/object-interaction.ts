// The one way a press on an object, a handle or the turn handle is handled in every app (D1221): this composable holds
// the `Gesture` that is under way (`object-gestures.ts`) and the Rotate By… preview, and asks its `ObjectHost` for the
// few things that differ. Creates, composes and computes each write a host (a few getters and one `commit`); the
// pointer rules — press, threshold, preview, release sends one change, Esc drops it — are then the same everywhere.
// Nothing is believed until the server says so: the preview stays on screen until the answer to the commit is in.
import { ref } from 'vue'
import type { Bounds, Frame, Point } from './geometry'
import { Gesture, type Commit, type Grab, type Subject } from './object-gestures'

/** What an app tells the interaction about its own area and objects. */
export interface ObjectHost {
  /** The area the objects may lie in, in its own units. */
  readonly bounds: Bounds
  /** Screen pixels per unit. */
  readonly scale: number
  /** A viewer may look but not change: no gesture begins. */
  readonly readonly: boolean
  /** A pointer position as a point of the area. */
  toUnits(event: { clientX: number; clientY: number }): Point
  /** The numbers of an object, or `null` when it is gone. */
  subject(id: string): Subject | null
  /** Send one change to the server; resolves when its answer is in the state. */
  commit(change: Commit): Promise<unknown>
}

/** A turn being tried from Rotate By…: not a pointer gesture, so it has no press and no release, only Done and Esc. */
export interface RotatePreview {
  id: string
  from: number
  turn: number
}

export function useObjectInteraction(host: ObjectHost) {
  const gesture = ref<Gesture | null>(null)
  const rotatePreview = ref<RotatePreview | null>(null)

  /** A press took hold of `grab` of object `id`. The caller has already selected the object and set pointer capture. */
  function begin(id: string, grab: Grab, event: { clientX: number; clientY: number }): boolean {
    const subject = host.subject(id)
    if (!subject) return false
    gesture.value = new Gesture(subject, grab, host.toUnits(event), { bounds: host.bounds, scale: host.scale })
    return true
  }

  function move(event: { clientX: number; clientY: number; shiftKey?: boolean; altKey?: boolean }): void {
    if (!gesture.value || host.readonly) return
    gesture.value.update(host.toUnits(event), { shift: event.shiftKey, alt: event.altKey })
  }

  /** The release: the one change, sent once; the preview goes when the server's answer is in (a refusal snaps it back).
   * Resolves to what was sent, or `null` for a click or a drag that changed nothing. */
  async function release(): Promise<Commit | null> {
    const g = gesture.value
    if (!g) return null
    const change = host.readonly ? null : g.commit()
    if (change) await host.commit(change)
    if (gesture.value === g) gesture.value = null
    return change
  }

  /** The frame to draw for object `id` while it is being moved or resized, else `null`. */
  function frameOf(id: string): Frame | null {
    const g = gesture.value
    return g && g.subject.id === id && g.grab !== 'turn' && g.moved ? g.frame : null
  }
  /** The angle to draw for object `id` while it is being turned, by the handle or by Rotate By…, else `null`. */
  function rotationOf(id: string): number | null {
    const g = gesture.value
    if (g && g.subject.id === id && g.grab === 'turn') return g.rotation
    return rotatePreview.value?.id === id ? rotatePreview.value.turn : null
  }
  /** Is a gesture on object `id` in its turning phase? (The angle chip shows then.) */
  const turningNow = (id: string) => gesture.value?.subject.id === id && gesture.value.grab === 'turn'

  function startRotateBy(id: string): boolean {
    const subject = host.subject(id)
    if (!subject || host.readonly) return false
    rotatePreview.value = { id, from: subject.rotation, turn: subject.rotation }
    return true
  }
  function previewRotateBy(angle: number): void {
    if (rotatePreview.value) rotatePreview.value.turn = angle
  }
  /** Done in the popover: one turn to `angle`, or nothing when it is the angle the object had. */
  async function finishRotateBy(angle: number): Promise<Commit | null> {
    const p = rotatePreview.value
    if (!p) return null
    const change: Commit | null = angle !== p.from && !host.readonly ? { kind: 'rotate', id: p.id, rotation: angle } : null
    if (change) await host.commit(change)
    if (rotatePreview.value === p) rotatePreview.value = null
    return change
  }

  /** Esc: whatever is being tried is dropped and the object is as it was. True when there was something to drop. */
  function cancel(): boolean {
    const had = gesture.value !== null || rotatePreview.value !== null
    gesture.value = null
    rotatePreview.value = null
    return had
  }

  return { gesture, rotatePreview, begin, move, release, frameOf, rotationOf, turningNow, startRotateBy, previewRotateBy, finishRotateBy, cancel }
}

export type ObjectInteraction = ReturnType<typeof useObjectInteraction>
