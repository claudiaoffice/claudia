/**
 * A slide, as creates and computes both print it (E6.31, D1473): 1600 × 900 CSS pixels, its objects drawn once in its
 * own coordinates (1200 × 675 pt) and placed on a page through a group's transform, scaled to fit its place, centred
 * there and cut at its edge. Creates lays out presentations with it ({@link layoutSlides}), computes a slide among the
 * sheets of a workbook ({@link layoutSheet}).
 *
 * @module
 */
import { type DisplayItem, type GroupItem, type PathItem, type Rect, rectPath } from '../display/list'
import { drawObject, type ObjectContext, px, type VisualObject } from './objects'

/** A slide's size in CSS pixels. */
export const SLIDE = { w: 1600, h: 900 } as const
const SLIDE_W = px(SLIDE.w)
const SLIDE_H = px(SLIDE.h)
const FRAME = { r: 160, g: 160, b: 160, a: 255 }

/** An object on a slide as the server sends it: the shared body and where on its slide it sits (CSS pixels). */
export interface SlideObject extends VisualObject {
  anchor: { kind: 'slide'; holder: string; x: number; y: number }
}

/** The objects of a slide drawn in the slide's own coordinates, the one in front last. */
export function drawSlide(objects: readonly SlideObject[], context: ObjectContext): DisplayItem[] {
  return objects.flatMap((o) => drawObject(o, { x: px(o.anchor.x), y: px(o.anchor.y), w: px(o.w), h: px(o.h) }, context) ?? [])
}

/** A slide fitted into `r`, centred, keeping its 16:9: the scale in millionths (so the transform is exact) and where it
 * lies. */
export function fittedSlide(r: Rect): { scale: number; rect: Rect } {
  const scale = Math.max(1, Math.min(Math.floor((r.w * 1_000_000) / SLIDE_W), Math.floor((r.h * 1_000_000) / SLIDE_H)))
  const w = Math.round((SLIDE_W * scale) / 1_000_000)
  const h = Math.round((SLIDE_H * scale) / 1_000_000)
  return { scale, rect: { x: r.x + Math.floor((r.w - w) / 2), y: r.y + Math.floor((r.h - h) / 2), w, h } }
}

/** A drawn slide as large as `place` takes it, centred, cut at its edge; `rect` is where it lies. */
export function placedSlide(drawn: DisplayItem[], place: Rect): { group: GroupItem; rect: Rect } {
  const { scale, rect } = fittedSlide(place)
  const group: GroupItem = {
    kind: 'group',
    clip: null,
    rotation: 0,
    origin: { x: 0, y: 0 },
    matrix: [scale, 0, 0, scale, rect.x, rect.y],
    clipPath: { ops: rectPath({ x: 0, y: 0, w: SLIDE_W, h: SLIDE_H }) },
    items: drawn,
  }
  return { group, rect }
}

/** The thin frame that shows where a slide ends on a page that is not the slide itself. */
export function slideFrame(rect: Rect): PathItem {
  return { kind: 'path', ops: rectPath(rect), fill: null, stroke: FRAME, lineWidth: 500 }
}
