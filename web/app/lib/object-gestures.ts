// What a press-and-drag on an object does, as one pure state machine for all three apps (D1221, contract note
// `object-interaction-contract.md`). A press on the object, a handle or the turn handle begins a `Gesture`; the
// pointer's moves update its preview (a frame and a turn, in the area's own units); the release asks it for the one
// `Commit` to send, or `null` when nothing changed. Nothing in here knows Vue, the DOM or the server: creates, composes
// and computes each translate their pointer into area units, hand over the object's own numbers, and send the commit
// with their own session. That is the whole of the difference between the three apps, so the behaviour cannot drift.
import { GRID_SIZE, SLIDE_BOUNDS, moveFrame, resizeFrame, type Bounds, type Frame, type Handle, type Point } from './geometry'
import { moveTurned, resizeTurned, turnFromPointer, type TurnKeys } from './turning'

/** What a press can take hold of: the object itself (to move it), one of its eight handles, or the turn handle. */
export type Grab = 'move' | 'turn' | Handle

/** The numbers of the object a gesture works on. `aspect` is width / height for what must keep its proportions (a
 * picture, a shape with a fixed aspect), else `null`; `grid` is the grid's unit for an object that snaps, else `null`. */
export interface Subject {
  id: string
  frame: Frame
  rotation: number
  aspect: number | null
  grid: number | null
}

/** The one change a finished gesture asks for: where the anchor goes, the new frame, or the new angle. */
export type Commit =
  | { kind: 'move'; id: string; x: number; y: number }
  | { kind: 'resize'; id: string; frame: Frame }
  | { kind: 'rotate'; id: string; rotation: number }

export interface GestureOptions {
  /** The area the object may lie in; the slide when left out. */
  bounds?: Bounds
  /** Screen pixels per unit, so the threshold below is in pixels whatever the zoom. */
  scale: number
  /** Screen pixels the pointer must travel before a press becomes a drag (a click that wobbles stays a click). */
  threshold?: number
}

export const DRAG_THRESHOLD = 3

export class Gesture {
  /** The frame to draw while the pointer is down: what the object would be if released now. */
  frame: Frame
  /** The angle to draw while the pointer is down. */
  rotation: number
  /** Has the pointer travelled past the threshold (always true once turning: a turn needs no threshold)? */
  moved = false

  private readonly bounds: Bounds
  private readonly threshold: number

  constructor(
    readonly subject: Subject,
    readonly grab: Grab,
    private readonly from: Point,
    private readonly options: GestureOptions,
  ) {
    this.bounds = options.bounds ?? SLIDE_BOUNDS
    this.threshold = options.threshold ?? DRAG_THRESHOLD
    this.frame = subject.frame
    this.rotation = subject.rotation
  }

  /** The pointer is at `to` (area units). `keys` are the modifiers a turn by hand looks at (Shift: 15° steps, Alt: free). */
  update(to: Point, keys: TurnKeys = {}): void {
    const { subject } = this
    if (this.grab === 'turn') {
      const f = subject.frame
      this.moved = true
      this.rotation = turnFromPointer({ x: f.x + f.w / 2, y: f.y + f.h / 2 }, to, keys)
      return
    }
    const dx = to.x - this.from.x
    const dy = to.y - this.from.y
    if (!this.moved && Math.hypot(dx, dy) * this.options.scale < this.threshold) return
    this.moved = true
    const { frame: start, rotation, aspect, grid } = subject
    if (rotation) {
      // A turned frame is kept where its *outline* stays on the area, and a handle pulls along the object's own axes (D1022).
      this.frame =
        this.grab === 'move'
          ? moveTurned(start, rotation, dx, dy, grid, this.bounds)
          : (resizeTurned(start, rotation, this.grab, dx, dy, aspect, this.bounds) ?? this.frame) // out of bounds: the last frame that fitted
      return
    }
    this.frame = this.grab === 'move' ? moveFrame(start, dx, dy, grid, this.bounds) : resizeFrame(start, this.grab, dx, dy, aspect, grid, this.bounds)
  }

  /** What the release sends, or `null` for a click, a drag that came back to where it began, or a turn to the same angle. */
  commit(): Commit | null {
    const { subject, frame } = this
    if (this.grab === 'turn') return this.rotation === subject.rotation ? null : { kind: 'rotate', id: subject.id, rotation: this.rotation }
    if (!this.moved) return null
    const start = subject.frame
    if (frame.x === start.x && frame.y === start.y && frame.w === start.w && frame.h === start.h) return null
    return this.grab === 'move' ? { kind: 'move', id: subject.id, x: frame.x, y: frame.y } : { kind: 'resize', id: subject.id, frame }
  }
}

/** The grid unit an object that snaps uses (E10.15); `null` for one that was released from it. */
export const gridOf = (snap: boolean): number | null => (snap ? GRID_SIZE : null)
