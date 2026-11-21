import { describe, expect, it } from 'vitest'
import { tintsOf } from '../app/lib/replay-tint'
import type { Region } from '../app/lib/protocol'

const cells = (sheet: string, r0: number, c0: number, r1 = r0, c1 = c0): Region => ({
  kind: 'cells',
  range: { first: { row: r0, col: c0, sheet }, last: { row: r1, col: c1, sheet } },
})

describe('what a replay tints', () => {
  it('names the cells of this sheet and nothing of another, with how they changed', () => {
    const t = tintsOf([cells('s1', 0, 0)], [cells('s1', 2, 2, 3, 4), cells('s2', 9, 9)])
    expect(t.cells('s1')).toEqual([
      { r0: 0, c0: 0, r1: 0, c1: 0, tint: 'now' },
      { r0: 2, c0: 2, r1: 3, c1: 4, tint: 'since' },
    ])
    expect(t.cells('s2')).toEqual([{ r0: 9, c0: 9, r1: 9, c1: 9, tint: 'since' }])
    expect(t.cells('s3')).toEqual([])
  })

  it('puts the corners of a range the right way round', () => {
    expect(tintsOf([cells('s1', 4, 5, 1, 2)], []).cells('s1')).toEqual([{ r0: 1, c0: 2, r1: 4, c1: 5, tint: 'now' }])
  })

  it('tints objects by id, and what the step did wins over what came later', () => {
    const t = tintsOf([{ kind: 'objects', holder: 'p', ids: ['a'] }], [{ kind: 'objects', holder: 'p', ids: ['a', 'b'] }])
    expect([t.object('a'), t.object('b'), t.object('c')]).toEqual(['now', 'since', null])
  })

  it('tints a paragraph as a whole, whichever stretch of it changed', () => {
    const t = tintsOf([{ kind: 'text', block: 'b1', start: 2, end: 4 }], [{ kind: 'text', block: 'b2', start: 0, end: 0 }])
    expect([t.block('b1'), t.block('b2'), t.block('b3')]).toEqual(['now', 'since', null])
  })

  it('counts the places that differ from now, for the person who cannot see the tint', () => {
    expect(tintsOf([], [cells('s1', 0, 0), { kind: 'objects', holder: 'p', ids: ['a', 'b'] }]).count).toBe(3)
    expect(tintsOf([cells('s1', 0, 0)], []).count).toBe(0)
  })
})

describe('the tints of a session', () => {
  it('are none in the present, and the differences only when asked for', async () => {
    const { replayTints } = await import('../app/lib/replay-tint')
    const focus: Region[] = [{ kind: 'text', block: 'b1', start: 0, end: 1 }]
    const changed: Region[] = [{ kind: 'text', block: 'b2', start: 0, end: 1 }]
    expect(replayTints(null).block('b1')).toBeNull()
    expect(replayTints({ focus, differences: false, changed }).block('b2')).toBeNull()
    expect(replayTints({ focus, differences: true, changed }).block('b2')).toBe('since')
  })
})
