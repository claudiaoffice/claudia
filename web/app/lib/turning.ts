// Turning an object: how far a turned frame reaches, where it may be, and what the pointer and the keys make of a
// turn (rotation-ui, D1021, D1022, D1024). All of it is whole numbers and pure functions.
//
// The arithmetic that decides what lies on the slide is the server's, digit for digit (`claudia_core.turning`, D910):
// an integer table of sines in millionths and ceiling divisions, never a floating-point sine, so that the browser
// and the server reach the same verdict about the same slide. What only the screen needs (the angle of a pointer, the
// resize in an object's own axes) may use `Math`, because the server checks its result again with the integer rules.

import { MIN_SIZE, SLIDE_BOUNDS, type Bounds, type Frame, type Handle, type Point } from './geometry'

/** `sin(d°)` in millionths for the whole degrees 0 to 90; every other angle is a reflection of one of these. */
export const SINE_MILLIONTHS: readonly number[] = [
  0, 17452, 34899, 52336, 69756, 87156, 104528, 121869, 139173, 156434,
  173648, 190809, 207912, 224951, 241922, 258819, 275637, 292372, 309017, 325568,
  342020, 358368, 374607, 390731, 406737, 422618, 438371, 453990, 469472, 484810,
  500000, 515038, 529919, 544639, 559193, 573576, 587785, 601815, 615661, 629320,
  642788, 656059, 669131, 681998, 694658, 707107, 719340, 731354, 743145, 754710,
  766044, 777146, 788011, 798636, 809017, 819152, 829038, 838671, 848048, 857167,
  866025, 874620, 882948, 891007, 898794, 906308, 913545, 920505, 927184, 933580,
  939693, 945519, 951057, 956305, 961262, 965926, 970296, 974370, 978148, 981627,
  984808, 987688, 990268, 992546, 994522, 996195, 997564, 998630, 999391, 999848,
  1000000,
]
const MILLION = 1_000_000

const ceilDiv = (numerator: number, denominator: number) => -Math.floor(-numerator / denominator)
const wholeTurn = (degrees: number) => ((Math.round(degrees) % 360) + 360) % 360

/** `|sin|` and `|cos|` of a whole number of degrees, in millionths: what an outline's extent needs. */
function magnitudes(rotation: number): [number, number] {
  const degrees = wholeTurn(rotation) % 180
  const folded = degrees <= 90 ? degrees : 180 - degrees
  return [SINE_MILLIONTHS[folded]!, SINE_MILLIONTHS[90 - folded]!]
}

/** The width and height of the outline of a `w` by `h` frame turned `rotation` whole degrees about its centre,
 * rounded up so that the outline never reaches further than the numbers say. */
export function turnedExtent(w: number, h: number, rotation: number): { w: number; h: number } {
  const [sine, cosine] = magnitudes(rotation)
  return { w: ceilDiv(w * cosine + h * sine, MILLION), h: ceilDiv(w * sine + h * cosine, MILLION) }
}

/** The lowest and highest top-left coordinate at which an outline `extent` wide, centred on a frame `size` wide, lies
 * inside `0 … space`. */
function rangeFor(size: number, extent: number, space: number): [number, number] {
  return [ceilDiv(extent - size, 2), Math.floor((2 * space - size - extent) / 2)]
}

/** The top left nearest `(x, y)` at which a `w` by `h` frame turned `rotation` degrees has its whole outline on the
 * slide, or `null` if it can never be. The corner is that of the *unturned* frame, so it may lie outside the slide. */
export function nudgeInto(x: number, y: number, w: number, h: number, rotation: number, bounds: Bounds = SLIDE_BOUNDS): Point | null {
  const out = turnedExtent(w, h, rotation)
  const [lowX, highX] = rangeFor(w, out.w, bounds.w)
  const [lowY, highY] = rangeFor(h, out.h, bounds.h)
  if (lowX > highX || lowY > highY) return null
  return { x: Math.min(Math.max(x, lowX), highX), y: Math.min(Math.max(y, lowY), highY) }
}

/** Does the turned outline of this frame lie on the slide, wherever the frame itself is? */
export function fitsOnSlide(x: number, y: number, w: number, h: number, rotation: number, bounds: Bounds = SLIDE_BOUNDS): boolean {
  const place = nudgeInto(x, y, w, h, rotation, bounds)
  return place !== null && place.x === x && place.y === y
}

/** The modifier keys a turn by hand looks at. */
export interface TurnKeys {
  /** Steps of 15°. */
  shift?: boolean
  /** No snapping at all. */
  alt?: boolean
}
/** Within this many degrees of 0°, 90°, 180° or 270° a turn snaps upright (D1024). */
export const SNAP_DEGREES = 3
/** The steps Shift turns in. */
export const SHIFT_STEP = 15

/** A turn in degrees as the object takes it, whole and 0–359: snapped to a step of 15° with Shift, to a right angle
 * within 3° of it, and left as it is with Alt. */
export function snapTurn(degrees: number, keys: TurnKeys): number {
  if (keys.shift) return wholeTurn(Math.round(degrees / SHIFT_STEP) * SHIFT_STEP)
  if (!keys.alt) {
    const quarter = Math.round(degrees / 90) * 90
    if (Math.abs(degrees - quarter) <= SNAP_DEGREES) return wholeTurn(quarter)
  }
  return wholeTurn(degrees)
}

/** The turn an object has once its rotate handle is where `pointer` is: the handle sits straight above the centre
 * of an upright object, so the angle is counted clockwise from straight up. A pointer on the centre means nothing. */
export function turnFromPointer(centre: Point, pointer: Point, keys: TurnKeys): number {
  const dx = pointer.x - centre.x
  const dy = pointer.y - centre.y
  if (dx === 0 && dy === 0) return 0
  return snapTurn((Math.atan2(dx, -dy) * 180) / Math.PI, keys)
}

/** `rotation` turned by `by` whole degrees (an arrow key: 1, with Shift 15). */
export const stepTurn = (rotation: number, by: number) => wholeTurn(rotation + by)

/** `rotation` turned a quarter clockwise (`1`) or counter-clockwise (`-1`): Rotate Right 90° and Rotate Left 90°. */
export const quarterTurn = (rotation: number, direction: 1 | -1) => wholeTurn(rotation + 90 * direction)

const snapTo = (value: number, grid: number | null) => (grid ? Math.round(value / grid) * grid : value)

/** A frame dragged by (dx, dy) while turned `rotation` degrees. The frame goes where the pointer takes it (snapping to
 * the grid first, when the object holds to it), and then no further than keeps the *outline* on the slide. */
export function moveTurned(start: Frame, rotation: number, dx: number, dy: number, grid: number | null, bounds: Bounds = SLIDE_BOUNDS): Frame {
  const wanted = { x: snapTo(Math.round(start.x + dx), grid), y: snapTo(Math.round(start.y + dy), grid) }
  const place = nudgeInto(wanted.x, wanted.y, start.w, start.h, rotation, bounds) ?? { x: start.x, y: start.y }
  return { ...place, w: start.w, h: start.h }
}

const radians = (degrees: number) => (degrees * Math.PI) / 180

/** A point given in the frame's own axes (from its top left corner) as a point of the slide. */
function onSlide(frame: Frame, rotation: number, local: Point): Point {
  const t = radians(rotation)
  const dx = local.x - frame.w / 2
  const dy = local.y - frame.h / 2
  return {
    x: frame.x + frame.w / 2 + dx * Math.cos(t) - dy * Math.sin(t),
    y: frame.y + frame.h / 2 + dx * Math.sin(t) + dy * Math.cos(t),
  }
}

/**
 * A turned frame with `handle` dragged by (dx, dy) *on the screen*. The pull is read in the object's own axes, so a
 * handle always moves along the side it belongs to, and the opposite side or corner stays where it is on the slide.
 * With an `aspect` (width / height of an object that must keep it) only corners work. `null` when the result would
 * take the outline off the slide: the caller keeps the last frame that did fit.
 */
export function resizeTurned(start: Frame, rotation: number, handle: Handle, dx: number, dy: number, aspect: number | null, bounds: Bounds = SLIDE_BOUNDS): Frame | null {
  if (aspect !== null && handle.length !== 2) return null // an edge would break the proportions
  const t = radians(rotation)
  const along = dx * Math.cos(t) + dy * Math.sin(t) // the pull along the object's own width
  const down = -dx * Math.sin(t) + dy * Math.cos(t) // and along its own height
  const east = handle.includes('e')
  const west = handle.includes('w')
  const south = handle.includes('s')
  const north = handle.includes('n')
  let w = start.w + (east ? along : west ? -along : 0)
  let h = start.h + (south ? down : north ? -down : 0)
  if (aspect !== null) {
    const wanted = Math.abs(w - start.w) >= Math.abs(h * aspect - start.w) ? w : h * aspect
    w = Math.max(wanted, MIN_SIZE * Math.max(1, aspect))
    h = w / aspect
  }
  w = Math.round(Math.max(w, MIN_SIZE))
  h = aspect !== null ? Math.round(w / aspect) : Math.round(Math.max(h, MIN_SIZE))
  // The fixed point: the side or corner opposite the handle, before and after.
  const fixedOld = { x: east ? 0 : west ? start.w : start.w / 2, y: south ? 0 : north ? start.h : start.h / 2 }
  const fixedNew = { x: east ? 0 : west ? w : w / 2, y: south ? 0 : north ? h : h / 2 }
  const pinned = onSlide(start, rotation, fixedOld)
  // the new centre is the pinned point plus the vector from the fixed point to the centre, turned
  const toCentre = { x: w / 2 - fixedNew.x, y: h / 2 - fixedNew.y }
  const cx = pinned.x + toCentre.x * Math.cos(t) - toCentre.y * Math.sin(t)
  const cy = pinned.y + toCentre.x * Math.sin(t) + toCentre.y * Math.cos(t)
  const frame = { x: Math.round(cx - w / 2), y: Math.round(cy - h / 2), w, h }
  return fitsOnSlide(frame.x, frame.y, frame.w, frame.h, rotation, bounds) ? frame : null
}

/** Does an object of this kind turn? Charts (kind `diagram`, D1021) and tables (D1224) do not; text boxes, shapes,
 * pictures and containers do. The server decides for itself (`turn_command`) — this only keeps the handle and the
 * menu entries off what it would refuse. */
export const canTurn = (kind: string): boolean => kind !== 'diagram' && kind !== 'table'

/** The words a screen reader says for a turn: "30°". */
export const degreesText = (rotation: number): string => `${rotation}°`

/** The angle a person typed into Rotate By…: whole degrees 0–359 ("-20" is 340, "30.4" is 30), or `null` for anything
 * that is not a number (an empty field, a letter), which leaves the turn as it was. */
export function parseAngle(text: string): number | null {
  const trimmed = text.trim().replace(',', '.').replace('°', '')
  if (trimmed === '' || !Number.isFinite(Number(trimmed))) return null
  return wholeTurn(Number(trimmed))
}

/** The quick buttons of Rotate By…: two steps from where the object is, and three fixed angles and upright. */
export type QuickTurn = { id: 'minus15' | 'plus15' | 'quarter' | 'half' | 'threeQuarters' | 'upright'; by?: number; to?: number }
export const QUICK_TURNS: readonly QuickTurn[] = [
  { id: 'minus15', by: -15 },
  { id: 'plus15', by: 15 },
  { id: 'quarter', to: 90 },
  { id: 'half', to: 180 },
  { id: 'threeQuarters', to: 270 },
  { id: 'upright', to: 0 },
]
/** The turn a quick button makes from `rotation`. */
export const quickTurn = (rotation: number, quick: QuickTurn): number => (quick.to !== undefined ? wholeTurn(quick.to) : wholeTurn(rotation + (quick.by ?? 0)))
