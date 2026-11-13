import { describe, expect, it } from 'vitest'
import { cycleRegions, type Region } from '~/lib/regions'

/** A window part that holds focus or not, and remembers whether focus was sent to it. */
function part(name: string, opts: { holds?: unknown; enterable?: boolean } = {}) {
  const log = { entered: 0 }
  const region: Region = {
    contains: (node) => node !== null && node === opts.holds,
    enter: () => {
      if (opts.enterable === false) return false
      log.entered++
      return true
    },
  }
  return { name, region, log }
}

const focus = { menus: {}, grid: {}, panel: {} }

describe('cycleRegions', () => {
  // WCAG 2.1.2 and 2.4.1 (BITV 2.0): the grid keeps Tab for moving between cells, so something else has to carry a
  // keyboard user out of it and past the parts of the window that come before the document.
  const make = () => [
    part('menus', { holds: focus.menus }),
    part('grid', { holds: focus.grid }),
    part('panel', { holds: focus.panel }),
  ]

  it('moves on to the next part of the window', () => {
    const [menus, grid, panel] = make()
    expect(cycleRegions([menus!.region, grid!.region, panel!.region], focus.grid, false)).toBe(true)
    expect([menus!.log.entered, grid!.log.entered, panel!.log.entered]).toEqual([0, 0, 1])
  })

  it('moves back to the previous part with the reverse key', () => {
    const [menus, grid, panel] = make()
    cycleRegions([menus!.region, grid!.region, panel!.region], focus.grid, true)
    expect([menus!.log.entered, grid!.log.entered, panel!.log.entered]).toEqual([1, 0, 0])
  })

  it('wraps around at both ends', () => {
    const [menus, grid, panel] = make()
    const all = [menus!.region, grid!.region, panel!.region]
    cycleRegions(all, focus.panel, false)
    cycleRegions(all, focus.menus, true)
    expect([menus!.log.entered, grid!.log.entered, panel!.log.entered]).toEqual([1, 0, 1])
  })

  it('starts at the first part when focus is outside every part, and at the last one going back', () => {
    const [menus, grid, panel] = make()
    const all = [menus!.region, grid!.region, panel!.region]
    cycleRegions(all, null, false)
    cycleRegions(all, {}, true)
    expect([menus!.log.entered, grid!.log.entered, panel!.log.entered]).toEqual([1, 0, 1])
  })

  it('skips a part that has nothing to focus, such as a hidden panel', () => {
    const menus = part('menus', { holds: focus.menus })
    const hidden = part('panel', { enterable: false })
    const grid = part('grid', { holds: focus.grid })
    expect(cycleRegions([menus.region, hidden.region, grid.region], focus.menus, false)).toBe(true)
    expect([menus.log.entered, hidden.log.entered, grid.log.entered]).toEqual([0, 0, 1])
  })

  it('does nothing, and says so, when no part can take focus', () => {
    const a = part('a', { enterable: false })
    const b = part('b', { enterable: false })
    expect(cycleRegions([a.region, b.region], null, false)).toBe(false)
  })

  it('stays where it is when only the current part can take focus', () => {
    const grid = part('grid', { holds: focus.grid })
    const hidden = part('panel', { enterable: false })
    expect(cycleRegions([grid.region, hidden.region], focus.grid, false)).toBe(true)
    expect(grid.log.entered).toBe(1)
  })

  it('has nothing to do with no parts at all', () => {
    expect(cycleRegions([], null, false)).toBe(false)
  })
})
