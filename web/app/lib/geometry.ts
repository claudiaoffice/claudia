// The arithmetic of the slide: the screen scale, what a click hits, and how dragging moves or resizes a frame.
// Everything is in slide units (1600 by 900), whole numbers, as the server wants them. These are pure functions.

export const SLIDE_W = 1600
export const SLIDE_H = 900
export const MIN_SIZE = 20 // the least width or height of an object (claudia_creates.MIN_OBJECT_SIZE)

export interface Frame {
  x: number
  y: number
  w: number
  h: number
}
export type Point = { x: number; y: number }
export type Handle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

export const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
export const CORNERS: Handle[] = ['nw', 'ne', 'se', 'sw']

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), Math.max(low, high))

/** How much the slide is scaled to fit into `avail` (in screen pixels) leaving `margin` free on every side. */
export function fitScale(avail: { w: number; h: number }, margin: number): number {
  const scale = Math.min((avail.w - 2 * margin) / SLIDE_W, (avail.h - 2 * margin) / SLIDE_H)
  return Math.max(scale, 0.05)
}

/** A point on the screen as a point of the slide; `origin` is where the slide's top left corner is on the screen. */
export function toSlide(clientX: number, clientY: number, origin: { left: number; top: number }, scale: number): Point {
  return { x: (clientX - origin.left) / scale, y: (clientY - origin.top) / scale }
}

/** The frame after dragging it by (dx, dy); it stays on the slide. */
export function moveFrame(start: Frame, dx: number, dy: number): Frame {
  return {
    x: clamp(Math.round(start.x + dx), 0, SLIDE_W - start.w),
    y: clamp(Math.round(start.y + dy), 0, SLIDE_H - start.h),
    w: start.w,
    h: start.h,
  }
}

/**
 * The frame after dragging `handle` by (dx, dy). The opposite side stays where it is; the frame stays on the slide
 * and keeps the least size. With an `aspect` (width / height of a shape that must keep it) only the corners work, and
 * the frame keeps the proportions the server checks (within one unit).
 */
export function resizeFrame(start: Frame, handle: Handle, dx: number, dy: number, aspect: number | null): Frame {
  return aspect === null ? resizeFree(start, handle, dx, dy) : resizeKeeping(start, handle, dx, dy, aspect)
}

function resizeFree(start: Frame, handle: Handle, dx: number, dy: number): Frame {
  let left = start.x
  let top = start.y
  let right = start.x + start.w
  let bottom = start.y + start.h
  if (handle.includes('w')) left = clamp(Math.round(left + dx), 0, right - MIN_SIZE)
  if (handle.includes('e')) right = clamp(Math.round(right + dx), left + MIN_SIZE, SLIDE_W)
  if (handle.includes('n')) top = clamp(Math.round(top + dy), 0, bottom - MIN_SIZE)
  if (handle.includes('s')) bottom = clamp(Math.round(bottom + dy), top + MIN_SIZE, SLIDE_H)
  return { x: left, y: top, w: right - left, h: bottom - top }
}

function resizeKeeping(start: Frame, handle: Handle, dx: number, dy: number, aspect: number): Frame {
  if (handle.length !== 2) return start // an edge would break the proportions
  const east = handle.includes('e')
  const south = handle.includes('s')
  const byWidth = start.w + (east ? dx : -dx)
  const byHeight = (start.h + (south ? dy : -dy)) * aspect
  const wanted = Math.abs(byWidth - start.w) >= Math.abs(byHeight - start.w) ? byWidth : byHeight
  const roomX = east ? SLIDE_W - start.x : start.x + start.w
  const roomY = south ? SLIDE_H - start.y : start.y + start.h
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

/** Where a new object goes: the `index`-th one added gets a little further from the first so none hides another. */
export function insertFrame(kind: 'text' | 'shape', aspect: number | null, index: number): Frame {
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
