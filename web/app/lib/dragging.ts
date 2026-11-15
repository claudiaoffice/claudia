// Moving a dialog or a panel by its header (UX-39). The browser centres a modal <dialog> and the search panel sits at a
// corner; a person moves either by pointing at the header and dragging, or from the keyboard with Alt + the arrow keys.
// What this file decides is only where it may go: the header, the part one holds, never leaves the window, so that a
// dialog can always be got back and closed. The components (`Modal.vue`, `SearchPanel.vue`) read the pointer and apply the result
// as a CSS `translate` on top of wherever the box starts, so nothing here knows about layout.

export interface Point {
  x: number
  y: number
}

/** A box on the screen, as `getBoundingClientRect` says it. */
export interface Box {
  left: number
  top: number
  width: number
  height: number
}

export interface Viewport {
  width: number
  height: number
}

/** The height of a header: all of it stays on the screen. */
export const GRAB = 48
/** What Alt + an arrow moves a box by, and with Shift as well. */
export const STEP = 20
export const BIG_STEP = 100

/** `shift` (how far the box is moved from where it was) limited so that the header stays on the screen: its whole height
 * (the box can go down until only the header shows) and, when the box is no wider than the window, its whole width, so
 * that the buttons at the end of the header (Close) can still be reached. A box wider than the window slides between
 * its two edges instead, so that either end can be brought into view. */
export function clampShift(box: Box, shift: Point, viewport: Viewport): Point {
  const [least, most] = [Math.min(0, viewport.width - box.width), Math.max(0, viewport.width - box.width)]
  const left = Math.min(Math.max(box.left + shift.x, least), most)
  const top = Math.min(Math.max(box.top + shift.y, 0), Math.max(0, viewport.height - GRAB))
  return { x: left - box.left, y: top - box.top }
}

/** How far an Alt + arrow key moves a box: `null` for any other key. */
export function keyShift(event: { key: string; altKey: boolean; shiftKey: boolean }): Point | null {
  if (!event.altKey) return null
  const by = event.shiftKey ? BIG_STEP : STEP
  switch (event.key) {
    case 'ArrowLeft':
      return { x: -by, y: 0 }
    case 'ArrowRight':
      return { x: by, y: 0 }
    case 'ArrowUp':
      return { x: 0, y: -by }
    case 'ArrowDown':
      return { x: 0, y: by }
    default:
      return null
  }
}

/** A drag in progress. `box` is the box where it rests, without any offset; `from` is the offset it had when the header
 * was taken hold of, and `pointer` where the pointer was then. */
export interface Drag {
  readonly from: Point
  readonly pointer: Point
  readonly box: Box
}

/** The offset the box should have once the pointer is at `pointer`, kept inside the window. */
export function dragged(drag: Drag, pointer: Point, viewport: Viewport): Point {
  return clampShift(drag.box, { x: drag.from.x + pointer.x - drag.pointer.x, y: drag.from.y + pointer.y - drag.pointer.y }, viewport)
}

/** Where an element a person can press that is *not* the handle sits: a button or a field in a header takes its own
 * clicks, and must not start a drag. */
export function startsDrag(target: { closest?: (selector: string) => unknown } | null): boolean {
  return target !== null && !target.closest?.('button, input, select, textarea, a, [role="menuitem"]')
}

/** A place where Alt + an arrow already means something to the person typing: on a Mac, Option + an arrow moves by a
 * word in a field. A box is moved from the keyboard only while the focus is somewhere else (a button, the header). */
export function takesTyping(target: { closest?: (selector: string) => unknown; isContentEditable?: boolean } | null): boolean {
  return !!target && (target.isContentEditable === true || !!target.closest?.('input:not([type=checkbox]):not([type=radio]):not([type=button]), textarea, select, [contenteditable=""], [contenteditable="true"]'))
}
