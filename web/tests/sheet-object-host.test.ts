import { describe, expect, it } from 'vitest'
import { buildSizeTable } from '~/lib/line-sizes'
import { nearestLine, stepFor } from '~/lib/sheet-object-host'

const W = 100
const plain = buildSizeTable(undefined, W)
const cellAt = (x: number, y: number) => ({ row: Math.round(y / 20), col: Math.round(x / W) })
const start = { x: 200, y: 40, w: 150, h: 60 }
const at = { start, anchor: { row: 2, col: 2 }, cellAt }

describe('nearestLine', () => {
  it('takes the line whose start is nearest, not the one the corner is in', () => {
    expect(nearestLine(plain, W, 149, 50)).toBe(1)
    expect(nearestLine(plain, W, 151, 50)).toBe(2)
    expect(nearestLine(plain, W, 0, 50)).toBe(0)
  })
  it('counts lines of their own size', () => {
    const table = buildSizeTable(new Map([[0, 300]]), W) // line 1 starts at 300, line 2 at 400
    expect(nearestLine(table, W, 340, 50)).toBe(1)
    expect(nearestLine(table, W, 360, 50)).toBe(2)
  })
  it('stays inside the sheet', () => {
    expect(nearestLine(plain, W, 99_999, 50)).toBe(49)
    expect(nearestLine(plain, W, -50, 50)).toBe(0)
  })
})

describe('stepFor', () => {
  it('moves to the cell the corner is nearest', () => {
    expect(stepFor({ kind: 'move', id: 'o', x: 410, y: 82 }, at)).toEqual({ kind: 'move', row: 4, col: 4 })
  })
  it('sends nothing for a move that stays in its cell', () => {
    expect(stepFor({ kind: 'move', id: 'o', x: 215, y: 45 }, at)).toBeNull()
  })
  it('keeps the anchor for a handle on the right or bottom edge, whatever the cell under the corner says', () => {
    expect(stepFor({ kind: 'resize', id: 'o', frame: { ...start, w: 300, h: 90 } }, at)).toEqual({ kind: 'resize', row: 2, col: 2, w: 300, h: 90 })
  })
  it('moves the anchor with a handle on the top or left edge', () => {
    expect(stepFor({ kind: 'resize', id: 'o', frame: { x: 100, y: 20, w: 250, h: 80 } }, at)).toEqual({ kind: 'resize', row: 1, col: 1, w: 250, h: 80 })
  })
  it('sends nothing for a resize that changed nothing', () => {
    expect(stepFor({ kind: 'resize', id: 'o', frame: start }, at)).toBeNull()
  })
  it('turns', () => {
    expect(stepFor({ kind: 'rotate', id: 'o', rotation: 90 }, at)).toEqual({ kind: 'rotate', rotation: 90 })
  })
})
