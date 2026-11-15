import { describe, expect, it } from 'vitest'
import { descriptionOf } from '~/lib/text-container-names'
import { floatBox, MIN_SIDE, neighbour, resizedBy } from '~/lib/text-containers'

describe('where a container floats', () => {
  it('is at the top of its paragraph, against its right edge', () => {
    expect(floatBox({ left: 10, top: 20, width: 900, height: 900 }, { left: 50, top: 120, width: 600, height: 40 }, 200, 100)).toEqual({ left: 440, top: 100, width: 200, height: 100 })
  })
  it('does not stick out to the left of a narrow paragraph', () => {
    expect(floatBox({ left: 0, top: 0, width: 900, height: 900 }, { left: 50, top: 0, width: 100, height: 20 }, 300, 100).left).toBe(50)
  })
})
describe('sizing and stepping', () => {
  it('follows the corner but keeps a size that can be grabbed', () => {
    expect(resizedBy(300, 200, 20.4, -30)).toEqual({ w: 320, h: 170 })
    expect(resizedBy(100, 100, -500, -500)).toEqual({ w: MIN_SIDE, h: MIN_SIDE })
  })
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
