import { describe, expect, it } from 'vitest'
import { Gesture, gridOf, type Subject } from '~/lib/object-gestures'

const subject = (extra: Partial<Subject> = {}): Subject => ({ id: 'o1', frame: { x: 200, y: 100, w: 300, h: 200 }, rotation: 0, aspect: null, grid: null, ...extra })
const begin = (grab: ConstructorParameters<typeof Gesture>[1], extra: Partial<Subject> = {}, options: Partial<ConstructorParameters<typeof Gesture>[3]> = {}) =>
  new Gesture(subject(extra), grab, { x: 300, y: 150 }, { scale: 1, ...options })

describe('a press that does not travel', () => {
  it('is a click: no preview change and nothing to commit', () => {
    const g = begin('move')
    g.update({ x: 301, y: 151 })
    expect(g.moved).toBe(false)
    expect(g.frame).toEqual(subject().frame)
    expect(g.commit()).toBeNull()
  })
  it('counts the threshold in screen pixels, so a zoomed-out slide needs a longer way in slide units', () => {
    const g = begin('move', {}, { scale: 0.5 })
    g.update({ x: 305, y: 150 }) // 5 units = 2.5 px
    expect(g.moved).toBe(false)
    g.update({ x: 308, y: 150 }) // 8 units = 4 px
    expect(g.moved).toBe(true)
  })
})

describe('moving', () => {
  it('moves the anchor by the distance travelled and commits the new top left once', () => {
    const g = begin('move')
    g.update({ x: 400, y: 190 })
    expect(g.frame).toEqual({ x: 300, y: 140, w: 300, h: 200 })
    expect(g.commit()).toEqual({ kind: 'move', id: 'o1', x: 300, y: 140 })
  })
  it('keeps the object inside its bounds, which are the area of the app and not always the slide', () => {
    const g = begin('move', {}, { bounds: { w: 800, h: 600 } })
    g.update({ x: 5000, y: 5000 })
    expect(g.frame).toMatchObject({ x: 500, y: 400 })
  })
  it('snaps to the grid for an object that holds to it, and not for one that was released', () => {
    const snapping = begin('move', { grid: gridOf(true) })
    snapping.update({ x: 330, y: 150 })
    expect(snapping.frame.x % 50).toBe(0)
    const free = begin('move', { grid: gridOf(false) })
    free.update({ x: 330, y: 150 })
    expect(free.frame.x).toBe(230)
  })
  it('comes back to nothing to commit when the drag ends where it began', () => {
    const g = begin('move')
    g.update({ x: 400, y: 190 })
    g.update({ x: 300, y: 150 })
    expect(g.commit()).toBeNull()
  })
  it('keeps a turned object’s outline inside the bounds (D1022)', () => {
    const g = begin('move', { rotation: 90 }, { bounds: { w: 1000, h: 1000 } })
    g.update({ x: -5000, y: 150 })
    // a 300 by 200 frame turned 90° is 200 wide on the area: its centre may reach 100 from the left edge
    expect(g.frame.x + g.frame.w / 2).toBe(100)
  })
})

describe('resizing', () => {
  it('pulls the dragged side and leaves the opposite one where it is', () => {
    const g = begin('se')
    g.update({ x: 350, y: 200 })
    expect(g.frame).toEqual({ x: 200, y: 100, w: 350, h: 250 })
    expect(g.commit()).toEqual({ kind: 'resize', id: 'o1', frame: { x: 200, y: 100, w: 350, h: 250 } })
  })
  it('keeps the proportions of a picture, so the server never refuses what the screen showed', () => {
    const g = begin('se', { aspect: 1.5 })
    g.update({ x: 420, y: 160 })
    expect(g.frame.w / g.frame.h).toBeCloseTo(1.5, 1)
  })
  it('ignores an edge handle for what keeps its proportions', () => {
    const g = begin('e', { aspect: 1.5 })
    g.update({ x: 420, y: 150 })
    expect(g.frame).toEqual(subject().frame)
    expect(g.commit()).toBeNull()
  })
  it('never goes past the least size nor out of the bounds', () => {
    const small = begin('se')
    small.update({ x: -900, y: -900 })
    expect(small.frame.w).toBeGreaterThanOrEqual(20)
    const big = begin('se', {}, { bounds: { w: 600, h: 400 } })
    big.update({ x: 9000, y: 9000 })
    expect(big.frame).toMatchObject({ x: 200, y: 100, w: 400, h: 300 })
  })
  it('pulls along the object’s own axes when it is turned, and keeps the last frame that fitted', () => {
    const g = begin('e', { rotation: 90, frame: { x: 400, y: 300, w: 200, h: 100 } }, { bounds: { w: 1000, h: 1000 } })
    g.update({ x: 300, y: 250 })
    const fitted = g.frame
    g.update({ x: 300, y: 99999 }) // far off the area: refused, the preview stays
    expect(g.frame).toEqual(fitted)
  })
})

describe('turning', () => {
  it('turns about the middle of the frame with no threshold, and commits the angle', () => {
    const g = begin('turn')
    g.update({ x: 350, y: 300 }) // the pointer is straight to the right of the centre (350, 200)... below it
    expect(g.moved).toBe(true)
    expect(g.commit()).toEqual({ kind: 'rotate', id: 'o1', rotation: g.rotation })
    expect(g.rotation).toBe(180)
  })
  it('steps by 15° with Shift', () => {
    const g = begin('turn')
    g.update({ x: 600, y: 120 }, { shift: true })
    expect(g.rotation % 15).toBe(0)
  })
  it('commits nothing when it comes back to the angle it had', () => {
    const g = begin('turn', { rotation: 0 })
    g.update({ x: 350, y: 300 })
    g.update({ x: 350, y: 0 })
    expect(g.rotation).toBe(0)
    expect(g.commit()).toBeNull()
  })
})

describe('gridOf', () => {
  it('is the grid unit for an object that snaps and null for one released from it', () => {
    expect(gridOf(true)).toBe(50)
    expect(gridOf(false)).toBeNull()
  })
})
