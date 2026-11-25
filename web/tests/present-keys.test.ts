// The keys that start the show (E10.2, D344, D1648): F5 and Shift+F5 are the definition's; the letter keys beside them.
import { describe, expect, it } from 'vitest'
import { dispatch, hintOf } from '../app/lib/shortcuts'
import { presentShortcuts } from '../app/lib/present-keys'

const key = (over: Partial<Record<string, unknown>>) => ({ key: '', code: '', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...over }) as never

describe('the keys that start the show', () => {
  it('are F5 and Shift+F5 in the menus outside a Mac', () => {
    expect(hintOf('view.present-start', false)).toBe('F5')
    expect(hintOf('view.present-here', false)).toBe('Shift+F5')
  })
  it('are the letter keys on a Mac, where F5 is a system key', () => {
    expect(hintOf('view.present-start', true)).toBe('Ctrl+Option+P')
    expect(hintOf('view.present-here', true)).toBe('Ctrl+Shift+Option+H')
  })
})

describe('the letter keys beside F5', () => {
  const calls: string[] = []
  const defs = presentShortcuts((s) => s, { start: () => calls.push('start'), here: () => calls.push('here') }, false)
  it('start the show outside a Mac too, by the physical key', () => {
    calls.length = 0
    dispatch(defs, key({ key: 'p', code: 'KeyP', ctrlKey: true, altKey: true }))
    dispatch(defs, key({ key: 'H', code: 'KeyH', ctrlKey: true, altKey: true, shiftKey: true }))
    expect(calls).toEqual(['start', 'here'])
  })
  it('keep a plain P for the text', () => {
    calls.length = 0
    expect(dispatch(defs, key({ key: 'p', code: 'KeyP' }))).toBeNull()
    expect(calls).toEqual([])
  })
  it('leave F5 to the entries: their ids are their own', () => {
    expect(defs.map((d) => d.id)).toEqual(['view.present-start.letter', 'view.present-here.letter'])
  })
  it('are the definition’s own on a Mac', () => {
    expect(presentShortcuts((s) => s, { start: () => 0, here: () => 0 }, true)).toEqual([])
  })
})
