import { describe, expect, it } from 'vitest'
import {
  SLIDE_H,
  SLIDE_W,
  fitScale,
  insertFrame,
  moveFrame,
  resizeFrame,
  toSlide,
  type Frame,
} from '~/lib/geometry'

describe('fitScale', () => {
  it('fits the 16:9 slide into the space left, with a margin', () => {
    expect(fitScale({ w: 1632, h: 932 }, 16)).toBe(1)
    expect(fitScale({ w: 816, h: 2000 }, 8)).toBeCloseTo(0.5)
    expect(fitScale({ w: 5000, h: 466 }, 8)).toBeCloseTo(0.5)
  })
  it('never gives zero or a negative scale, however small the window is', () => {
    expect(fitScale({ w: 0, h: 0 }, 16)).toBeGreaterThan(0)
    expect(fitScale({ w: 10, h: 10 }, 16)).toBeGreaterThan(0)
  })
})

describe('toSlide', () => {
  it('turns a point on the screen into slide units', () => {
    const where = { left: 100, top: 50 }
    expect(toSlide(300, 150, where, 0.5)).toEqual({ x: 400, y: 200 })
  })
})

describe('moveFrame', () => {
  const start: Frame = { x: 100, y: 100, w: 400, h: 200 }
  it('moves by the distance, in whole units', () => {
    expect(moveFrame(start, 10.4, -20.6)).toEqual({ x: 110, y: 79, w: 400, h: 200 })
  })
  it('keeps the object on the slide', () => {
    expect(moveFrame(start, -500, -500)).toEqual({ x: 0, y: 0, w: 400, h: 200 })
    expect(moveFrame(start, 5000, 5000)).toEqual({ x: SLIDE_W - 400, y: SLIDE_H - 200, w: 400, h: 200 })
  })
})

describe('resizeFrame without a fixed shape', () => {
  const start: Frame = { x: 100, y: 100, w: 400, h: 200 }
  it('drags the south-east corner and leaves the north-west one where it is', () => {
    expect(resizeFrame(start, 'se', 50, 30, null)).toEqual({ x: 100, y: 100, w: 450, h: 230 })
  })
  it('drags the north-west corner and leaves the south-east one where it is', () => {
    expect(resizeFrame(start, 'nw', 40, 20, null)).toEqual({ x: 140, y: 120, w: 360, h: 180 })
  })
  it('an edge changes one dimension only', () => {
    expect(resizeFrame(start, 'e', 60, 99, null)).toEqual({ x: 100, y: 100, w: 460, h: 200 })
    expect(resizeFrame(start, 'n', 99, -40, null)).toEqual({ x: 100, y: 60, w: 400, h: 240 })
    expect(resizeFrame(start, 'w', -30, 0, null)).toEqual({ x: 70, y: 100, w: 430, h: 200 })
    expect(resizeFrame(start, 's', 0, 25, null)).toEqual({ x: 100, y: 100, w: 400, h: 225 })
  })
  it('does not shrink below the least size, and the opposite edge stays put', () => {
    expect(resizeFrame(start, 'se', -1000, -1000, null)).toEqual({ x: 100, y: 100, w: 20, h: 20 })
    expect(resizeFrame(start, 'nw', 1000, 1000, null)).toEqual({ x: 480, y: 280, w: 20, h: 20 })
  })
  it('does not leave the slide', () => {
    expect(resizeFrame(start, 'se', 5000, 5000, null)).toEqual({ x: 100, y: 100, w: SLIDE_W - 100, h: SLIDE_H - 100 })
    expect(resizeFrame(start, 'nw', -5000, -5000, null)).toEqual({ x: 0, y: 0, w: 500, h: 300 })
  })
})

describe('resizeFrame with a fixed shape (a circle: width / height = 1)', () => {
  const circle: Frame = { x: 200, y: 200, w: 200, h: 200 }
  it('keeps the proportions, following the bigger change', () => {
    expect(resizeFrame(circle, 'se', 50, 10, 1)).toEqual({ x: 200, y: 200, w: 250, h: 250 })
    expect(resizeFrame(circle, 'se', 10, 60, 1)).toEqual({ x: 200, y: 200, w: 260, h: 260 })
  })
  it('keeps the opposite corner fixed from every corner', () => {
    expect(resizeFrame(circle, 'nw', -40, -40, 1)).toEqual({ x: 160, y: 160, w: 240, h: 240 })
    expect(resizeFrame(circle, 'ne', 40, -40, 1)).toEqual({ x: 200, y: 160, w: 240, h: 240 })
    expect(resizeFrame(circle, 'sw', -40, 40, 1)).toEqual({ x: 160, y: 200, w: 240, h: 240 })
  })
  it('stays within the least size and the slide, still in proportion', () => {
    expect(resizeFrame(circle, 'se', -1000, -1000, 1)).toEqual({ x: 200, y: 200, w: 20, h: 20 })
    const big = resizeFrame(circle, 'se', 5000, 5000, 1)
    expect(big.w).toBe(big.h)
    expect(big.x + big.w).toBeLessThanOrEqual(SLIDE_W)
    expect(big.y + big.h).toBeLessThanOrEqual(SLIDE_H)
  })
  it('gives sizes the server accepts for any proportion (within one unit)', () => {
    for (const aspect of [0.5, 0.75, 1, 1.5, 2]) {
      const frame = resizeFrame({ x: 100, y: 100, w: 300, h: Math.round(300 / aspect) }, 'se', 37, 11, aspect)
      expect(Math.abs(frame.w - frame.h * aspect)).toBeLessThanOrEqual(1)
    }
  })
})

describe('insertFrame', () => {
  it('puts a text box near the top left and a shape near the middle', () => {
    expect(insertFrame('text', null, 0)).toEqual({ x: 160, y: 120, w: 640, h: 140 })
    const shape = insertFrame('shape', null, 0)
    expect(shape.x + shape.w / 2).toBeCloseTo(SLIDE_W / 2, -1)
  })
  it('gives a shape with fixed proportions a size that has them', () => {
    const circle = insertFrame('shape', 1, 0)
    expect(circle.w).toBe(circle.h)
  })
  it('shifts the next ones a little so that they do not hide each other, and stays on the slide', () => {
    const [a, b] = [insertFrame('text', null, 0), insertFrame('text', null, 1)]
    expect(b.x).toBeGreaterThan(a.x)
    for (let i = 0; i < 200; i++) {
      const f = insertFrame('shape', null, i)
      expect(f.x).toBeGreaterThanOrEqual(0)
      expect(f.y).toBeGreaterThanOrEqual(0)
      expect(f.x + f.w).toBeLessThanOrEqual(SLIDE_W)
      expect(f.y + f.h).toBeLessThanOrEqual(SLIDE_H)
    }
  })
})
