import { describe, expect, it } from 'vitest'
import { awayFrom, nearestParagraph, nearestGap, stepsFor } from '~/lib/text-object-host'
import { floatBox } from '~/lib/text-object-layer'

const layer = { left: 100, top: 50 }
const start = { x: 40, y: 30, w: 200, h: 100 }
const here = { place: { paragraph: 'b1', offset: 3 }, spot: { left: 140, top: 80 } } // the character is at (40, 30) of the layer

describe('awayFrom', () => {
  it('is how far a box floats from its character, in whole pixels', () => {
    expect(awayFrom({ x: 60, y: 20 }, { left: 140, top: 80 }, layer)).toEqual({ dx: 20, dy: -10 })
  })
  it('is read back by floatBox as the same place', () => {
    const away = awayFrom({ x: 75, y: 90 }, { left: 140, top: 80 }, layer)
    const box = floatBox({ left: layer.left, top: layer.top, width: 800, height: 600 }, { left: 140, top: 80 }, away, 200, 100)
    expect([box.left, box.top]).toEqual([75, 90])
  })
})

describe('nearestParagraph', () => {
  const rects = [
    { id: 'a', top: 0, bottom: 40 },
    { id: 'b', top: 50, bottom: 90 },
    { id: 'c', top: 100, bottom: 140 },
  ]
  it('is the paragraph that holds the height', () => expect(nearestParagraph(rects, 70)).toBe('b'))
  it('is the nearest one in the gap between two, the first when it is a tie', () => {
    expect(nearestParagraph(rects, 43)).toBe('a')
    expect(nearestParagraph(rects, 45)).toBe('a')
    expect(nearestParagraph(rects, 48)).toBe('b')
  })
  it('is the first above the text and the last below it', () => {
    expect(nearestParagraph(rects, -500)).toBe('a')
    expect(nearestParagraph(rects, 900)).toBe('c')
  })
  it('is null without paragraphs', () => expect(nearestParagraph([], 10)).toBeNull())
})

describe('nearestGap', () => {
  const rects = [
    { id: 'a', bottom: 40 },
    { id: 'b', bottom: 90 },
    { id: 'c', bottom: 140 },
  ]
  it('is the paragraph whose bottom edge is nearest, so a table goes after it', () => {
    expect(nearestGap(rects, 85)).toBe('b')
    expect(nearestGap(rects, 118)).toBe('c')
  })
  it('is the first of two that are equally near, the first above the text and the last below it', () => {
    expect(nearestGap(rects, 65)).toBe('a')
    expect(nearestGap(rects, -10)).toBe('a')
    expect(nearestGap(rects, 1000)).toBe('c')
  })
  it('is null without paragraphs', () => expect(nearestGap([], 5)).toBeNull())
})

describe('stepsFor', () => {
  it('a move keeps the character and changes the offset when nothing is nearer', () => {
    const steps = stepsFor({ kind: 'move', id: 'o', x: 90, y: 60 }, { layer, start, current: here })
    expect(steps).toEqual([{ kind: 'move', place: here.place, away: { dx: 50, dy: 30 } }])
  })
  it('a move that is dropped nearer another character hangs from that one, with what is left over', () => {
    const dropped = { place: { paragraph: 'b2', offset: 0 }, spot: { left: 140, top: 380 } }
    const steps = stepsFor({ kind: 'move', id: 'o', x: 60, y: 340 }, { layer, start, current: here, dropped })
    expect(steps).toEqual([{ kind: 'move', place: { paragraph: 'b2', offset: 0 }, away: { dx: 20, dy: 10 } }])
  })
  it('a turn is one rotate step', () => {
    expect(stepsFor({ kind: 'rotate', id: 'o', rotation: 45 }, { layer, start, current: here })).toEqual([{ kind: 'rotate', rotation: 45 }])
  })
  it('a corner on the bottom right is a resize alone', () => {
    const steps = stepsFor({ kind: 'resize', id: 'o', frame: { ...start, w: 300, h: 150 } }, { layer, start, current: here })
    expect(steps).toEqual([{ kind: 'resize', w: 300, h: 150 }])
  })
  it('a corner on the top left is a resize and a new offset, from the same character', () => {
    const steps = stepsFor({ kind: 'resize', id: 'o', frame: { x: 20, y: 10, w: 220, h: 120 } }, { layer, start, current: here })
    expect(steps).toEqual([
      { kind: 'resize', w: 220, h: 120 },
      { kind: 'move', place: here.place, away: { dx: -20, dy: -20 } },
    ])
  })
  it('a handle that changes only the position of the far side asks for no move', () => {
    const steps = stepsFor({ kind: 'resize', id: 'o', frame: { ...start, h: 160 } }, { layer, start, current: here })
    expect(steps.map((s) => s.kind)).toEqual(['resize'])
  })
})
