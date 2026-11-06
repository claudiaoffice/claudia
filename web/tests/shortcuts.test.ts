import { describe, expect, it, vi } from 'vitest'
import { chordLabel, dispatch, isTypingTarget, matches, sharedShortcuts } from '~/lib/shortcuts'

function key(partial: Partial<{ key: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }>) {
  return { key: '', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...partial }
}

describe('matches', () => {
  it('treats Ctrl and Cmd (metaKey) as the same primary modifier', () => {
    expect(matches({ key: 's', ctrl: true }, key({ key: 's', ctrlKey: true }))).toBe(true)
    expect(matches({ key: 's', ctrl: true }, key({ key: 's', metaKey: true }))).toBe(true)
  })
  it('is case-insensitive on the letter', () => {
    expect(matches({ key: 'z', ctrl: true }, key({ key: 'Z', ctrlKey: true }))).toBe(true)
  })
  it('requires shift and alt to match exactly, not just be present', () => {
    expect(matches({ key: 'z', ctrl: true }, key({ key: 'z', ctrlKey: true, shiftKey: true }))).toBe(false)
    expect(matches({ key: 'z', ctrl: true, shift: true }, key({ key: 'z', ctrlKey: true }))).toBe(false)
  })
})

describe('chordLabel', () => {
  it('reads Redo as Ctrl+Shift+Z, not Ctrl+Y (D122: the extra binding is dropped, not just unused)', () => {
    expect(chordLabel({ key: 'z', ctrl: true, shift: true })).toBe('Ctrl+Shift+Z')
  })
  it('upper-cases a single-letter key but leaves a named key alone', () => {
    expect(chordLabel({ key: 's', ctrl: true })).toBe('Ctrl+S')
    expect(chordLabel({ key: 'F10', shift: true })).toBe('Shift+F10')
  })
})

describe('sharedShortcuts', () => {
  it('is exactly Undo (Ctrl+Z), Redo (Ctrl+Shift+Z) and Save (Ctrl+S) — nothing bound to Ctrl+Y', () => {
    const undo = vi.fn()
    const redo = vi.fn()
    const save = vi.fn()
    const defs = sharedShortcuts({ undo, redo, save })
    expect(defs.map((d) => chordLabel(d.chord))).toEqual(['Ctrl+Z', 'Ctrl+Shift+Z', 'Ctrl+S'])
    dispatch(defs, key({ key: 'y', ctrlKey: true }))
    expect(redo).not.toHaveBeenCalled()
    dispatch(defs, key({ key: 'z', ctrlKey: true, shiftKey: true }))
    expect(redo).toHaveBeenCalledOnce()
  })
})

describe('dispatch', () => {
  it('skips a shortcut whose `enabled` says no, and returns null so the caller does not preventDefault', () => {
    const run = vi.fn()
    const defs = [{ id: 'file.save', label: 'Save', chord: { key: 's', ctrl: true }, run, enabled: () => false }]
    expect(dispatch(defs, key({ key: 's', ctrlKey: true }))).toBeNull()
    expect(run).not.toHaveBeenCalled()
  })
  it('returns the matched shortcut when one runs', () => {
    const run = vi.fn()
    const defs = [{ id: 'file.save', label: 'Save', chord: { key: 's', ctrl: true }, run }]
    expect(dispatch(defs, key({ key: 's', ctrlKey: true }))?.id).toBe('file.save')
  })
})

describe('isTypingTarget', () => {
  it('is true only for INPUT and TEXTAREA', () => {
    expect(isTypingTarget({ tagName: 'INPUT' })).toBe(true)
    expect(isTypingTarget({ tagName: 'TEXTAREA' })).toBe(true)
    expect(isTypingTarget({ tagName: 'DIV' })).toBe(false)
    expect(isTypingTarget(null)).toBe(false)
  })
})
