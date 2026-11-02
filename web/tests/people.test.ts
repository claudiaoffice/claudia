import { describe, expect, it } from 'vitest'
import { ago, colorOf, initial, inkOn } from '~/lib/people'

const state = { me: { user: 'ann', role: 'owner', color: '#d6477a' }, people: [{ id: 2, user: 'ben', color: '#13917f' }] }

describe('people', () => {
  it('colours everybody, the assistant in iris', () => {
    expect(colorOf(state, 'ann')).toBe('#d6477a')
    expect(colorOf(state, 'ben')).toBe('#13917f')
    expect(colorOf(state, 'AI')).toBe('#5b4bc4')
    expect(colorOf(state, 'nobody')).toMatch(/^#/)
  })
  it('puts ink on apricot and white on the dark colours', () => {
    expect(inkOn('#f2a057')).toBe('#1f1a33')
    for (const dark of ['#5b4bc4', '#d6477a', '#13917f', '#1f1a33']) expect(inkOn(dark)).toBe('#ffffff')
  })
  it('takes the first letter', () => {
    expect(initial(' ben')).toBe('B')
    expect(initial('')).toBe('?')
  })
  it('says how long ago', () => {
    const now = Date.parse('2026-11-02T12:00:00Z')
    expect(ago('2026-11-02T11:59:50Z', now)).toBe('just now')
    expect(ago('2026-11-02T11:55:00Z', now)).toBe('5 min ago')
    expect(ago('2026-11-02T09:00:00Z', now)).toBe('3 h ago')
    expect(ago('2026-11-01T09:00:00Z', now)).toBe('yesterday')
  })
})
