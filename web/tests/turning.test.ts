import { describe, expect, it } from 'vitest'

import {
  SINE_MILLIONTHS,
  canTurn,
  QUICK_TURNS,
  degreesText,
  parseAngle,
  quickTurn,
  fitsOnSlide,
  moveTurned,
  nudgeInto,
  quarterTurn,
  resizeTurned,
  snapTurn,
  stepTurn,
  turnFromPointer,
  turnedExtent,
} from '~/lib/turning'

// The integer arithmetic is the server's (`claudia_core.turning`, D910): the same numbers, so that the browser and the
// server agree about what lies on the slide. The cases below are the ones `test_turning.py` checks, worked by hand.
describe('the table of sines', () => {
  it('has a value for every whole degree from 0 to 90', () => {
    expect(SINE_MILLIONTHS).toHaveLength(91)
    expect(SINE_MILLIONTHS[0]).toBe(0)
    expect(SINE_MILLIONTHS[30]).toBe(500_000)
    expect(SINE_MILLIONTHS[90]).toBe(1_000_000)
  })
  it('is the true sine to a millionth', () => {
    SINE_MILLIONTHS.forEach((value, degrees) => expect(value).toBe(Math.round(Math.sin((degrees * Math.PI) / 180) * 1e6)))
  })
})

describe('turnedExtent', () => {
  it('is the frame itself when upright', () => expect(turnedExtent(300, 100, 0)).toEqual({ w: 300, h: 100 }))
  it('swaps width and height for a quarter turn', () => {
    expect(turnedExtent(300, 100, 90)).toEqual({ w: 100, h: 300 })
    expect(turnedExtent(300, 100, 270)).toEqual({ w: 100, h: 300 })
  })
  it('keeps them for a half turn', () => expect(turnedExtent(300, 100, 180)).toEqual({ w: 300, h: 100 }))
  it('rounds the outline of a slanted frame up', () => {
    expect(turnedExtent(100, 100, 45)).toEqual({ w: 142, h: 142 })
    expect(turnedExtent(300, 100, 30)).toEqual({ w: 310, h: 237 })
  })
  it('does not care which way round the turn is counted', () => {
    expect(turnedExtent(300, 100, 330)).toEqual(turnedExtent(300, 100, 30))
    expect(turnedExtent(300, 100, 150)).toEqual(turnedExtent(300, 100, 30))
  })
})

describe('nudgeInto', () => {
  it('leaves an object that fits where it is', () => expect(nudgeInto(100, 100, 300, 100, 30)).toEqual({ x: 100, y: 100 }))
  it('moves a turned object the least that brings its outline back', () => {
    expect(nudgeInto(0, 0, 300, 100, 90)).toEqual({ x: 0, y: 100 })
    expect(nudgeInto(1300, 800, 300, 100, 90)).toEqual({ x: 1300, y: 700 })
    expect(nudgeInto(1500, 100, 300, 100, 45)).toEqual({ x: 1308, y: 100 })
  })
  it('lets the frame itself lie outside the slide while the outline is inside', () => {
    const place = nudgeInto(0, 0, 300, 100, 90)
    expect(place).not.toBeNull()
    expect(nudgeInto(-100, 100, 300, 100, 90)).toEqual({ x: -100, y: 100 }) // outline x from 0 to 100
  })
  it('says there is no place where the outline can never fit', () => expect(nudgeInto(50, 50, 1500, 800, 45)).toBeNull())
  it('agrees with fitsOnSlide', () => {
    expect(fitsOnSlide(0, 0, 300, 100, 90)).toBe(false)
    expect(fitsOnSlide(0, 100, 300, 100, 90)).toBe(true)
  })
})

describe('snapTurn', () => {
  it('lets a free turn through, in whole degrees', () => expect(snapTurn(37.4, {})).toBe(37))
  it('snaps to upright within 3 degrees of a right angle', () => {
    expect(snapTurn(2.6, {})).toBe(0)
    expect(snapTurn(357.5, {})).toBe(0)
    expect(snapTurn(92.9, {})).toBe(90)
    expect(snapTurn(183, {})).toBe(180)
    expect(snapTurn(267, {})).toBe(270)
  })
  it('does not snap just outside that', () => expect(snapTurn(94, {})).toBe(94))
  it('snaps to steps of 15 with Shift, and to nothing with Alt', () => {
    expect(snapTurn(37, { shift: true })).toBe(30)
    expect(snapTurn(38, { shift: true })).toBe(45)
    expect(snapTurn(353, { shift: true })).toBe(0)
    expect(snapTurn(2, { alt: true })).toBe(2)
    expect(snapTurn(91, { alt: true })).toBe(91)
  })
})

describe('turnFromPointer', () => {
  const centre = { x: 100, y: 100 }
  it('is upright when the pointer is straight above the centre', () => expect(turnFromPointer(centre, { x: 100, y: 20 }, {})).toBe(0))
  it('turns clockwise as the pointer goes round', () => {
    expect(turnFromPointer(centre, { x: 180, y: 100 }, {})).toBe(90)
    expect(turnFromPointer(centre, { x: 100, y: 180 }, {})).toBe(180)
    expect(turnFromPointer(centre, { x: 20, y: 100 }, {})).toBe(270)
  })
  it('reads a pointer on the centre as no change of mind: upright', () => expect(turnFromPointer(centre, centre, {})).toBe(0))
  it('snaps like snapTurn', () => expect(turnFromPointer(centre, { x: 160, y: 40 }, { shift: true })).toBe(45))
})

describe('stepTurn and quarterTurn', () => {
  it('goes round in whole degrees', () => {
    expect(stepTurn(359, 1)).toBe(0)
    expect(stepTurn(0, -1)).toBe(359)
    expect(stepTurn(10, 15)).toBe(25)
  })
  it('turns by a quarter either way', () => {
    expect(quarterTurn(0, 1)).toBe(90)
    expect(quarterTurn(0, -1)).toBe(270)
    expect(quarterTurn(350, 1)).toBe(80)
  })
})

describe('moveTurned', () => {
  const frame = { x: 600, y: 300, w: 300, h: 100 }
  it('moves the frame', () => expect(moveTurned(frame, 90, 50, 20, null)).toEqual({ ...frame, x: 650, y: 320 }))
  it('keeps the outline on the slide, not the frame', () => {
    // a quarter turn: the outline is 100 wide, so the frame may go 100 units beyond the left edge
    expect(moveTurned(frame, 90, -2000, 0, null).x).toBe(-100)
    expect(moveTurned(frame, 90, 2000, 0, null).x).toBe(1400)
    expect(moveTurned(frame, 90, 0, -2000, null).y).toBe(100)
  })
  it('snaps the frame to the grid first', () => expect(moveTurned(frame, 0, 24, 26, 50)).toEqual({ ...frame, x: 600, y: 350 }))
})

describe('resizeTurned', () => {
  const frame = { x: 600, y: 300, w: 300, h: 100 }
  it('is the ordinary resize for a pull along the object when it is upright', () => {
    expect(resizeTurned(frame, 0, 'e', 40, 0, null)).toEqual({ x: 600, y: 300, w: 340, h: 100 })
  })
  it('pulls in the object’s own axes: the east handle of a quarter-turned object is pulled down the screen', () => {
    const turned = resizeTurned(frame, 90, 'e', 0, 40, null)
    expect(turned).not.toBeNull()
    expect(turned!.w).toBe(340)
    expect(turned!.h).toBe(100)
    // the west side (the fixed one) is the top of the screen; its place does not move
    const top = (f: { x: number; y: number; w: number }) => f.y + 50 - f.w / 2 // centre y minus half the width
    expect(top(turned!) - top(frame)).toBe(0)
  })
  it('keeps the fixed corner where it is', () => {
    const turned = resizeTurned(frame, 30, 'se', 30, 20, null)!
    const corner = (f: typeof frame, r: number, ox: number, oy: number) => {
      const t = (r * Math.PI) / 180
      const cx = f.x + f.w / 2
      const cy = f.y + f.h / 2
      const dx = ox - f.w / 2
      const dy = oy - f.h / 2
      return { x: cx + dx * Math.cos(t) - dy * Math.sin(t), y: cy + dx * Math.sin(t) + dy * Math.cos(t) }
    }
    const before = corner(frame, 30, 0, 0)
    const after = corner(turned, 30, 0, 0)
    expect(Math.abs(before.x - after.x)).toBeLessThanOrEqual(1)
    expect(Math.abs(before.y - after.y)).toBeLessThanOrEqual(1)
  })
  it('keeps at least the least size', () => expect(resizeTurned(frame, 0, 'e', -1000, 0, null)!.w).toBe(20))
  it('keeps the proportions of a shape that has them, from a corner', () => {
    const turned = resizeTurned({ x: 600, y: 300, w: 200, h: 100 }, 0, 'se', 100, 0, 2)!
    expect(turned.w / turned.h).toBeCloseTo(2, 1)
  })
  it('refuses a resize that would take the outline off the slide', () => {
    expect(resizeTurned({ x: 0, y: 300, w: 300, h: 100 }, 0, 'w', -50, 0, null)).toBeNull()
  })
})

describe('what turns', () => {
  it('turns everything but a chart and a table (D1021, D1224)', () => {
    expect(['text', 'shape', 'image', 'container'].every(canTurn)).toBe(true)
    expect(canTurn('chart')).toBe(false)
    expect(canTurn('table')).toBe(false)
  })
  it('says a turn in degrees', () => {
    expect(degreesText(30)).toBe('30°')
  })
})

describe('Rotate By…', () => {
  it('reads whole degrees from what was typed', () => {
    expect(parseAngle('30')).toBe(30)
    expect(parseAngle(' 45° ')).toBe(45)
    expect(parseAngle('-20')).toBe(340)
    expect(parseAngle('360')).toBe(0)
    expect(parseAngle('30,4')).toBe(30)
    expect(parseAngle('')).toBeNull()
    expect(parseAngle('abc')).toBeNull()
  })
  it('has quick buttons that step from here or go to a fixed angle', () => {
    const at = (id: string, from: number) => quickTurn(from, QUICK_TURNS.find((q) => q.id === id)!)
    expect(at('minus15', 10)).toBe(355)
    expect(at('plus15', 350)).toBe(5)
    expect(at('quarter', 33)).toBe(90)
    expect(at('half', 33)).toBe(180)
    expect(at('threeQuarters', 33)).toBe(270)
    expect(at('upright', 33)).toBe(0)
  })
})
