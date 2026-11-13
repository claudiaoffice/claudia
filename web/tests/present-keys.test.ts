import { describe, expect, it } from 'vitest'
import { dispatch } from '../app/lib/shortcuts'
import { onMac, presentChord, presentHint, presentShortcuts } from '../app/lib/present-keys'

const key = (over: Partial<Record<string, unknown>>) => ({ key: '', code: '', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...over }) as never

describe('the keys that start the show', () => {
  it('names F5 and Shift+F5 outside a Mac', () => {
    expect(presentHint('start', false)).toBe('F5')
    expect(presentHint('here', false)).toBe('Shift+F5')
  })
  it('names the letter chords on a Mac, where F5 is a system key', () => {
    expect(presentHint('start', true)).toBe('Ctrl+Option+P')
    expect(presentHint('here', true)).toBe('Ctrl+Option+Shift+P')
  })
  it('has no function key for the notes and the time, on any system', () => {
    expect(presentChord('notes', false)).toEqual(presentChord('notes', true))
    expect(presentHint('time', false)).toBe('Ctrl+Alt+D')
  })
  it('knows a Mac by its platform', () => {
    expect(onMac({ platform: 'MacIntel' })).toBe(true)
    expect(onMac({ platform: 'Linux x86_64' })).toBe(false)
    expect(onMac(undefined)).toBe(false)
  })
})

describe('what the window listens for', () => {
  const calls: string[] = []
  const defs = presentShortcuts((s) => s, {
    start: () => calls.push('start'),
    here: () => calls.push('here'),
    notes: () => calls.push('notes'),
    time: () => calls.push('time'),
  })
  it('starts from the first slide on F5 and on the letter chord, by the physical key', () => {
    calls.length = 0
    dispatch(defs, key({ key: 'F5' }))
    // Option+P types π on a Mac: only the code identifies the key
    dispatch(defs, key({ key: 'π', code: 'KeyP', metaKey: true, altKey: true }))
    expect(calls).toEqual(['start', 'start'])
  })
  it('starts from this slide with Shift', () => {
    calls.length = 0
    dispatch(defs, key({ key: 'F5', shiftKey: true }))
    dispatch(defs, key({ key: 'P', code: 'KeyP', ctrlKey: true, altKey: true, shiftKey: true }))
    expect(calls).toEqual(['here', 'here'])
  })
  it('keeps a plain P for the text', () => {
    calls.length = 0
    expect(dispatch(defs, key({ key: 'p', code: 'KeyP' }))).toBeNull()
    expect(calls).toEqual([])
  })
  it('can be switched off, as when the document may not be read', () => {
    calls.length = 0
    const off = presentShortcuts((s) => s, { start: () => calls.push('x'), here: () => 0, notes: () => 0, time: () => 0 }, { start: () => false })
    expect(dispatch(off, key({ key: 'F5' }))).toBeNull()
    expect(calls).toEqual([])
  })
})
