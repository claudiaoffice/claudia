import { describe, expect, it } from 'vitest'
import { cycleObject } from '~/lib/descriptions'

describe('cycleObject: the keyboard way to reach a floating object', () => {
  const ids = ['a', 'b', 'c']
  it('starts at the first object going forward and at the last going back, when none is selected', () => {
    expect(cycleObject(ids, null, 1)).toBe('a')
    expect(cycleObject(ids, null, -1)).toBe('c')
  })
  it('steps on and wraps round at both ends', () => {
    expect(cycleObject(ids, 'a', 1)).toBe('b')
    expect(cycleObject(ids, 'c', 1)).toBe('a')
    expect(cycleObject(ids, 'a', -1)).toBe('c')
  })
  it('treats a selection that is gone like none, and finds nothing where there is nothing', () => {
    expect(cycleObject(ids, 'gone', 1)).toBe('a')
    expect(cycleObject([], null, 1)).toBeNull()
  })
})
