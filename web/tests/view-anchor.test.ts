// The places a view reports for the way back (D1312): a cell for computes, a paragraph id for composes.
import { describe, expect, it } from 'vitest'
import { cellAnchor, parseCellAnchor } from '~/lib/view-anchor'

describe('cell anchors', () => {
  it('say the top-left cell in sight, and read back', () => {
    expect(cellAnchor(12, 3)).toBe('12:3')
    expect(parseCellAnchor('12:3')).toEqual({ row: 12, col: 3 })
  })
  it('read nothing from what is not a cell', () => {
    for (const bad of ['', 'p4', '1:', ':2', '1:2:3', '-1:2', 'a:b']) expect(parseCellAnchor(bad)).toBeNull()
  })
})
