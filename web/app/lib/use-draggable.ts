// The part of moving a box by its header that touches the page: pointer events on a handle and an offset the box
// applies to its own insets (`--dx`, `--dy`; a CSS transform would make the box the containing block of the fixed
// popovers inside it, and they would land in the wrong place). Where it may go is `lib/dragging.ts`, which has the
// tests; this is the thin wiring both the modal dialogs and the search panel use.
import { onBeforeUnmount, ref, type Ref } from 'vue'
import { clampShift, dragged, keyShift, startsDrag, takesTyping, type Drag, type Point } from './dragging'

/** Where the offset is remembered while the page is open, by dialog: the position a person gave "All styles" is the
 * position it has the next time (not kept across a reload, and never sent anywhere). */
const remembered = new Map<string, Point>()

export function useDraggable(box: Ref<HTMLElement | null>, id?: string) {
  const offset = ref<Point>(id ? { ...(remembered.get(id) ?? { x: 0, y: 0 }) } : { x: 0, y: 0 })
  const moving = ref(false)
  let drag: Drag | null = null
  let wasMoved = false

  const viewport = () => ({ width: window.innerWidth, height: window.innerHeight })
  const set = (next: Point) => {
    offset.value = next
    if (id) remembered.set(id, { ...next })
  }

  /** The box as it is now, but without the offset: what `clampShift` measures a move from. */
  function resting() {
    const rect = box.value!.getBoundingClientRect()
    return { left: rect.left - offset.value.x, top: rect.top - offset.value.y, width: rect.width, height: rect.height }
  }

  function onMove(event: PointerEvent) {
    if (!drag) return
    wasMoved = wasMoved || Math.abs(event.clientX - drag.pointer.x) + Math.abs(event.clientY - drag.pointer.y) > 3
    set(dragged(drag, { x: event.clientX, y: event.clientY }, viewport()))
  }
  /** Was the pointer that was just let go of used to drag? The click that follows a drag is not a click on whatever it
   * ends over (the backdrop of a dialog closes it: a drag that ends there must not). Forgets itself after the click. */
  function justDragged(): boolean {
    return wasMoved
  }
  function stop() {
    if (wasMoved) setTimeout(() => (wasMoved = false), 0)
    drag = null
    moving.value = false
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', stop)
    window.removeEventListener('pointercancel', stop)
  }
  function start(event: PointerEvent) {
    if (event.button !== 0 || !box.value || !startsDrag(event.target as Element | null)) return
    event.preventDefault() // no text is selected while the header is dragged
    wasMoved = false
    const rect = resting()
    drag = { from: { ...offset.value }, pointer: { x: event.clientX, y: event.clientY }, box: rect }
    moving.value = true
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
  }
  /** Alt + arrows on the header (or anywhere in the box, for a panel that has no focusable header). */
  function key(event: KeyboardEvent) {
    const by = keyShift(event)
    if (!by || !box.value || takesTyping(event.target as Element | null)) return
    event.preventDefault()
    event.stopPropagation()
    const rest = resting()
    const wanted = { x: offset.value.x + by.x, y: offset.value.y + by.y }
    set(clampShift(rest, wanted, viewport()))
  }
  /** The window got smaller: the box may be out of it now. */
  function refit() {
    if (box.value && (offset.value.x !== 0 || offset.value.y !== 0)) set(clampShift(resting(), offset.value, viewport()))
  }
  onBeforeUnmount(stop)

  return { offset, moving, start, key, refit, justDragged }
}
