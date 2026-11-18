// The arithmetic of the slide: the screen scale, what a click hits, and how dragging moves or resizes a frame.
// Everything is in slide units (1600 by 900), whole numbers, as the server wants them. These are pure functions.

export const SLIDE_W = 1600
export const SLIDE_H = 900
export const MIN_SIZE = 20 // the least width or height of an object (claudia_creates.MIN_OBJECT_SIZE)
export const GRID_SIZE = 50 // units between grid lines (E10.15); SLIDE_W and SLIDE_H both divide evenly by it

export interface Frame {
  x: number
  y: number
  w: number
  h: number
}
export type Point = { x: number; y: number }
/** The area an object may lie in, from the origin: the slide in creates, the page's width and height in composes, the
 * sheet's drawn extent in computes. Every function below that keeps a frame "on the slide" takes one, defaulting to
 * the slide, so creates behaves as it always did and the other two apps pass their own (D1221). */
export type Bounds = { w: number; h: number }
export const SLIDE_BOUNDS: Bounds = { w: SLIDE_W, h: SLIDE_H }
export type Handle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

export const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
export const CORNERS: Handle[] = ['nw', 'ne', 'se', 'sw']

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), Math.max(low, high))

/** `value` rounded to the nearest multiple of `grid`; unchanged without one (an object that does not snap). */
const snapTo = (value: number, grid: number | null) => (grid ? Math.round(value / grid) * grid : value)

/** How much the slide is scaled to fit into `avail` (in screen pixels) leaving `margin` free on every side. */
export function fitScale(avail: { w: number; h: number }, margin: number): number {
  const scale = Math.min((avail.w - 2 * margin) / SLIDE_W, (avail.h - 2 * margin) / SLIDE_H)
  return Math.max(scale, 0.05)
}

/** A point on the screen as a point of the slide; `origin` is where the slide's top left corner is on the screen. */
export function toSlide(clientX: number, clientY: number, origin: { left: number; top: number }, scale: number): Point {
  return { x: (clientX - origin.left) / scale, y: (clientY - origin.top) / scale }
}

/** The frame after dragging it by (dx, dy); it stays on the slide. With `grid`, the moved position snaps to the
 * nearest grid line (E10.15) before it is kept on the slide. */
export function moveFrame(start: Frame, dx: number, dy: number, grid: number | null = null, bounds: Bounds = SLIDE_BOUNDS): Frame {
  return {
    x: clamp(snapTo(Math.round(start.x + dx), grid), 0, bounds.w - start.w),
    y: clamp(snapTo(Math.round(start.y + dy), grid), 0, bounds.h - start.h),
    w: start.w,
    h: start.h,
  }
}

/**
 * The frame after dragging `handle` by (dx, dy). The opposite side stays where it is; the frame stays on the slide
 * and keeps the least size. With an `aspect` (width / height of a shape that must keep it) only the corners work, and
 * the frame keeps the proportions the server checks (within one unit). With `grid` (E10.15), the dragged edge snaps
 * to the nearest grid line; with an `aspect`, only the dominant dimension is snapped and the other follows it
 * exactly, so the proportions are never thrown off by rounding to two different grid lines.
 */
export function resizeFrame(
  start: Frame,
  handle: Handle,
  dx: number,
  dy: number,
  aspect: number | null,
  grid: number | null = null,
  bounds: Bounds = SLIDE_BOUNDS,
): Frame {
  return aspect === null ? resizeFree(start, handle, dx, dy, grid, bounds) : resizeKeeping(start, handle, dx, dy, aspect, grid, bounds)
}

function resizeFree(start: Frame, handle: Handle, dx: number, dy: number, grid: number | null, bounds: Bounds): Frame {
  let left = start.x
  let top = start.y
  let right = start.x + start.w
  let bottom = start.y + start.h
  if (handle.includes('w')) left = clamp(snapTo(Math.round(left + dx), grid), 0, right - MIN_SIZE)
  if (handle.includes('e')) right = clamp(snapTo(Math.round(right + dx), grid), left + MIN_SIZE, bounds.w)
  if (handle.includes('n')) top = clamp(snapTo(Math.round(top + dy), grid), 0, bottom - MIN_SIZE)
  if (handle.includes('s')) bottom = clamp(snapTo(Math.round(bottom + dy), grid), top + MIN_SIZE, bounds.h)
  return { x: left, y: top, w: right - left, h: bottom - top }
}

function resizeKeeping(start: Frame, handle: Handle, dx: number, dy: number, aspect: number, grid: number | null, bounds: Bounds): Frame {
  if (handle.length !== 2) return start // an edge would break the proportions
  const east = handle.includes('e')
  const south = handle.includes('s')
  const byWidth = start.w + (east ? dx : -dx)
  const byHeight = (start.h + (south ? dy : -dy)) * aspect
  const wanted = snapTo(Math.abs(byWidth - start.w) >= Math.abs(byHeight - start.w) ? byWidth : byHeight, grid)
  const roomX = east ? bounds.w - start.x : start.x + start.w
  const roomY = south ? bounds.h - start.y : start.y + start.h
  const least = MIN_SIZE * Math.max(1, aspect)
  let w = clamp(wanted, least, Math.min(roomX, roomY * aspect))
  let h = Math.round(w / aspect)
  w = Math.round(h * aspect)
  while (w > roomX || h > roomY) {
    h -= 1
    w = Math.round(h * aspect)
  }
  return { x: east ? start.x : start.x + start.w - w, y: south ? start.y : start.y + start.h - h, w, h }
}

const TEXT_BOX = { w: 640, h: 140 }
const SHAPE_HEIGHT = 240
const SHAPE_WIDTH = 360
const STEP = 32 // how far each new object is shifted from the one before
const STEPS = 8

/** Where a new object goes: the `index`-th one added gets a little further from the first so none hides another.
 * An image is sized the same way a shape is (it always has an aspect, since every decoded picture has a width and
 * height); it is not its own branch below. */
export function insertFrame(kind: 'text' | 'shape' | 'image', aspect: number | null, index: number): Frame {
  const shift = (index % STEPS) * STEP
  if (kind === 'text') return { x: 160 + shift, y: 120 + shift, ...TEXT_BOX }
  const h = SHAPE_HEIGHT
  const w = aspect === null ? SHAPE_WIDTH : Math.round(h * aspect)
  return {
    x: Math.min(Math.round((SLIDE_W - w) / 2) + shift, SLIDE_W - w),
    y: Math.min(Math.round((SLIDE_H - h) / 2) + shift, SLIDE_H - h),
    w,
    h,
  }
}

/** Where a popover `width` pixels wide goes beside a selected object's on-screen `rect`: to its right, top-aligned,
 *  or to its left when the right would leave the window — so that the object it styles stays in view. */
export function besideRect(rect: { left: number; top: number; right: number }, width: number, viewport: number, gap = 12): Point {
  const right = rect.right + gap
  return { x: right + width <= viewport ? right : Math.max(gap, rect.left - gap - width), y: rect.top }
}

/** Where to scroll one axis of a grid so that a line (a row or column) that is out of sight ends up in the middle of
 * what is drawn, or `null` when it is in sight already and the view stays where it is (D553: a change a replay
 * follows is not left at the edge, where it is easy to miss). `start` and `size` are the line's, `scroll` and `view`
 * the viewport's, `header` the frozen strip at its start that covers part of it; the result is never negative. */
export function centredScroll(start: number, size: number, scroll: number, view: number, header: number): number | null {
  const shown = view - header
  if (start >= scroll && start + size <= scroll + shown) return null
  return Math.max(0, Math.round(start + size / 2 - shown / 2))
}
