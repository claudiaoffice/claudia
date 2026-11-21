import { describe, expect, it } from 'vitest'
import { descriptionOf } from '~/lib/text-container-names'
import { columnOf, floatBox, letsGoOfObject, neighbour } from '~/lib/text-object-layer'

describe('where an object floats', () => {
  const layer = { left: 10, top: 20, width: 900, height: 900 }
  it('hangs at its anchor character, not at the edge of the paragraph (D907)', () => {
    expect(floatBox(layer, { left: 130, top: 160 }, {}, 200, 100)).toEqual({ left: 120, top: 140, width: 200, height: 100 })
  })
  it('is moved off the anchor by the offset the model keeps (D1023)', () => {
    expect(floatBox(layer, { left: 130, top: 160 }, { dx: 25, dy: -10 }, 200, 100)).toEqual({ left: 145, top: 130, width: 200, height: 100 })
  })
  it('stays inside the column across, the left edge winning for an object wider than it', () => {
    const column = { left: 50, top: 0, width: 600, height: 900 }
    expect(floatBox(layer, { left: 600, top: 100 }, {}, 200, 100, column).left).toBe(450 - 10)
    expect(floatBox(layer, { left: 60, top: 100 }, { dx: -40 }, 200, 100, column).left).toBe(50 - 10)
    expect(floatBox(layer, { left: 60, top: 100 }, {}, 700, 100, column).left).toBe(50 - 10)
  })
  it('is never above the top of the layer', () => {
    expect(floatBox(layer, { left: 60, top: 30 }, { dy: -50 }, 20, 20).top).toBe(0)
  })
})
describe('the column objects may hang in', () => {
  it('is the box of the text without its padding', () => {
    expect(columnOf({ left: 100, top: 10, width: 700, height: 900 }, 40, 60)).toEqual({ left: 140, top: 10, width: 600, height: 900 })
    expect(columnOf({ left: 0, top: 0, width: 50, height: 5 }, 40, 60).width).toBe(0)
  })
})
describe('what lets go of a selected object', () => {
  it('is a press anywhere but on an object', () => {
    const on = { closest: (s: string) => (s === '[data-object]' ? {} : null) }
    const off = { closest: () => null }
    expect(letsGoOfObject(off)).toBe(true)
    expect(letsGoOfObject(on)).toBe(false)
    expect(letsGoOfObject(null)).toBe(true)
    expect(letsGoOfObject({})).toBe(true)
  })
})
describe('stepping', () => {
  it('steps to the next or previous paragraph and stays at the ends', () => {
    expect(neighbour(['a', 'b', 'c'], 'b', 1)).toBe('c')
    expect(neighbour(['a', 'b', 'c'], 'c', 1)).toBe('c')
    expect(neighbour(['a', 'b', 'c'], 'a', -1)).toBe('a')
    expect(neighbour(['a'], 'zz', 1)).toBe('zz')
  })
})

describe('what a screen reader says', () => {
  const t = (id: string, vars?: Record<string, string | number>) => (vars ? id.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k])) : id)
  it('names the type and the description, or says there is none', () => {
    expect(descriptionOf({ description: 'Flow of orders' }, 'Mermaid', t)).toBe('Mermaid container: Flow of orders')
    expect(descriptionOf({ description: '' }, 'LaTeX', t)).toBe('LaTeX container (no description)')
  })
})
