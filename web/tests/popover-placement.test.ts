import { describe, expect, it } from 'vitest'
import { placePopover } from '~/lib/popover-placement'

const window = { w: 1360, h: 860 }

describe('a panel at a point of the window', () => {
  it('stays where it was asked for when it fits', () => {
    expect(placePopover({ x: 100, y: 120, width: 300, height: 200, window })).toEqual({ left: 100, top: 120, maxHeight: 844 })
  })

  it('is pushed back into the window at the right and at the bottom', () => {
    const placed = placePopover({ x: 1300, y: 700, width: 300, height: 400, window })
    expect(placed.left).toBe(1360 - 300 - 8)
    expect(placed.top).toBe(860 - 400 - 8)
  })

  it('never grows beyond the window', () => {
    const placed = placePopover({ x: 20, y: 20, width: 300, height: 5000, window })
    expect(placed.top).toBe(8)
    expect(placed.maxHeight).toBe(860 - 16)
  })
})

describe('a panel that hangs from a button', () => {
  it('stays below the button and scrolls when the room is short, so the button can still be pressed', () => {
    const placed = placePopover({ x: 40, y: 104, width: 300, height: 900, window, anchored: true })
    expect(placed.top).toBe(104)
    expect(placed.maxHeight).toBe(860 - 104 - 8)
  })

  it('does not need to scroll when it fits below the button', () => {
    const placed = placePopover({ x: 40, y: 104, width: 300, height: 300, window, anchored: true })
    expect(placed).toEqual({ left: 40, top: 104, maxHeight: 860 - 104 - 8 })
  })

  it('moves up like any panel when the button is so low that there is hardly any room below it', () => {
    const placed = placePopover({ x: 40, y: 800, width: 300, height: 400, window, anchored: true })
    expect(placed.top).toBe(860 - 400 - 8)
  })
})
