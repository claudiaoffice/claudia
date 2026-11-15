// Where a dialog or panel may be moved to (UX-39): the header never leaves the window, so a dialog can always be got back.
import { describe, expect, it } from 'vitest'
import { BIG_STEP, GRAB, STEP, clampShift, dragged, keyShift, startsDrag, takesTyping } from '~/lib/dragging'

const screen = { width: 1200, height: 800 }
const dialog = { left: 380, top: 200, width: 440, height: 300 }

describe('clamping a move', () => {
  it('leaves a move that stays on the screen as it is', () => {
    expect(clampShift(dialog, { x: -200, y: 120 }, screen)).toEqual({ x: -200, y: 120 })
  })

  it('keeps the whole header on the screen, at the top and at the bottom', () => {
    expect(clampShift(dialog, { x: 0, y: -900 }, screen)).toEqual({ x: 0, y: -200 })
    expect(clampShift(dialog, { x: 0, y: 900 }, screen).y).toBe(screen.height - GRAB - dialog.top)
  })

  it('keeps the whole width on the screen, so that the buttons at the end of the header can be reached', () => {
    expect(clampShift(dialog, { x: -2000, y: 0 }, screen).x).toBe(-dialog.left)
    expect(clampShift(dialog, { x: 2000, y: 0 }, screen).x).toBe(screen.width - dialog.width - dialog.left)
  })

  it('lets a box wider than the window slide between its two edges, so that either end can be brought into view', () => {
    const wide = { left: 0, top: 10, width: 900, height: 300 }
    const small = { width: 640, height: 480 }
    expect(clampShift(wide, { x: 500, y: 0 }, small).x).toBe(0)
    expect(clampShift(wide, { x: -500, y: 0 }, small).x).toBe(-260)
  })

  it('brings a box back in when the window has become smaller than where it was', () => {
    const shifted = clampShift({ left: 900, top: 700, width: 380, height: 400 }, { x: 0, y: 0 }, { width: 640, height: 480 })
    expect(shifted).toEqual({ x: 640 - 380 - 900, y: 480 - GRAB - 700 })
  })

  it('handles a window shorter than a header', () => {
    expect(clampShift(dialog, { x: 0, y: 50 }, { width: 1200, height: 20 }).y).toBe(-dialog.top)
  })
})

describe('dragging by the pointer', () => {
  const drag = { from: { x: 30, y: -10 }, pointer: { x: 500, y: 220 }, box: dialog }

  it('adds how far the pointer went to where the dialog was', () => {
    expect(dragged(drag, { x: 540, y: 260 }, screen)).toEqual({ x: 70, y: 30 })
  })

  it('does not follow the pointer off the screen', () => {
    expect(dragged(drag, { x: 5000, y: 5000 }, screen)).toEqual({ x: screen.width - dialog.width - dialog.left, y: screen.height - GRAB - dialog.top })
  })

  it('is where it started when the pointer has not moved', () => {
    expect(dragged(drag, drag.pointer, screen)).toEqual(drag.from)
  })
})

describe('moving with the keyboard', () => {
  const key = (k: string, altKey = true, shiftKey = false) => keyShift({ key: k, altKey, shiftKey })

  it('moves by a step with Alt and an arrow', () => {
    expect(key('ArrowLeft')).toEqual({ x: -STEP, y: 0 })
    expect(key('ArrowRight')).toEqual({ x: STEP, y: 0 })
    expect(key('ArrowUp')).toEqual({ x: 0, y: -STEP })
    expect(key('ArrowDown')).toEqual({ x: 0, y: STEP })
  })

  it('moves by a big step with Shift as well', () => {
    expect(key('ArrowDown', true, true)).toEqual({ x: 0, y: BIG_STEP })
  })

  it('leaves the arrow keys alone without Alt (they move in a list or a field) and every other key', () => {
    expect(key('ArrowDown', false)).toBeNull()
    expect(key('a')).toBeNull()
  })
})

describe('what starts a drag', () => {
  const target = (hit: boolean) => ({ closest: (selector: string) => (hit && selector.includes('button') ? {} : null) })

  it('starts on the empty part of a header', () => {
    expect(startsDrag(target(false))).toBe(true)
  })

  it('does not start on a button or a field in it, which take their own clicks', () => {
    expect(startsDrag(target(true))).toBe(false)
  })

  it('does not start from nothing', () => {
    expect(startsDrag(null)).toBe(false)
  })
})

describe('where Alt + an arrow belongs to somebody typing', () => {
  const inside = (matches: boolean, isContentEditable = false) => ({ isContentEditable, closest: () => (matches ? {} : null) })

  it('is a text field, a text area, a choice list or editable text', () => {
    expect(takesTyping(inside(true))).toBe(true)
    expect(takesTyping(inside(false, true))).toBe(true)
  })

  it('is not a button, a checkbox or the header', () => {
    expect(takesTyping(inside(false))).toBe(false)
  })

  it('is not anything when nothing has the focus', () => {
    expect(takesTyping(null)).toBe(false)
  })
})
