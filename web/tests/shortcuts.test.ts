import { describe, expect, it, vi } from 'vitest'
import { chordLabel, dispatch, isTypingTarget, matches, regionShortcuts, searchShortcuts, sharedShortcuts } from '~/lib/shortcuts'

function key(partial: Partial<{ key: string; code: string; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean }>) {
  return { key: '', code: '', ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...partial }
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

describe('a chord on a physical key (`code`)', () => {
  // Shift+8 types `*` on a US keyboard and `(` on a German one: the key is the same, what it types is not (E9.21).
  const bullets = { key: '8', code: 'Digit8', ctrl: true, shift: true }
  it('matches whatever the layout types for that key', () => {
    expect(matches(bullets, key({ key: '*', code: 'Digit8', ctrlKey: true, shiftKey: true }))).toBe(true)
    expect(matches(bullets, key({ key: '(', code: 'Digit8', ctrlKey: true, shiftKey: true }))).toBe(true)
  })
  it('does not match another key that happens to type the same character', () => {
    expect(matches(bullets, key({ key: '8', code: 'Numpad9', ctrlKey: true, shiftKey: true }))).toBe(false)
  })
  it('still wants the modifiers exactly', () => {
    expect(matches(bullets, key({ key: '*', code: 'Digit8', ctrlKey: true }))).toBe(false)
  })
  it('is labelled by its key', () => {
    expect(chordLabel(bullets)).toBe('Ctrl+Shift+8')
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

describe('dispatch while someone is typing in a field', () => {
  const run = vi.fn()
  const save = { id: 'file.save', label: 'Save', chord: { key: 's', ctrl: true }, run }

  it('leaves an ordinary shortcut to the field', () => {
    run.mockClear()
    expect(dispatch([save], key({ key: 's', ctrlKey: true }), true)).toBeNull()
    expect(run).not.toHaveBeenCalled()
  })

  it('still runs one that says it works in a field', () => {
    run.mockClear()
    expect(dispatch([{ ...save, whileTyping: true }], key({ key: 's', ctrlKey: true }), true)?.id).toBe('file.save')
    expect(run).toHaveBeenCalledOnce()
  })

  it('runs everything when nobody is typing', () => {
    run.mockClear()
    expect(dispatch([save], key({ key: 's', ctrlKey: true }), false)?.id).toBe('file.save')
  })
})

describe('regionShortcuts', () => {
  // WCAG 2.1.2 / 2.4.1: F6 and Shift+F6 are how a keyboard user gets out of the grid and between the parts of the window.
  it('binds F6 to the next part and Shift+F6 to the previous one', () => {
    const next = vi.fn()
    const previous = vi.fn()
    const defs = regionShortcuts({ next, previous })
    expect(dispatch(defs, key({ key: 'F6' }))?.id).toBe('view.nextRegion')
    expect(dispatch(defs, key({ key: 'F6', shiftKey: true }))?.id).toBe('view.previousRegion')
    expect(next).toHaveBeenCalledOnce()
    expect(previous).toHaveBeenCalledOnce()
  })

  it('works from inside a text field too, which is where the formula bar keeps focus', () => {
    const defs = regionShortcuts({ next: vi.fn(), previous: vi.fn() })
    expect(dispatch(defs, key({ key: 'F6' }), true)?.id).toBe('view.nextRegion')
  })

  it('shows as F6 and Shift+F6 in Config ▸ Shortcuts', () => {
    const labels = regionShortcuts({ next: vi.fn(), previous: vi.fn() }).map((d) => [d.label, chordLabel(d.chord)])
    expect(labels).toEqual([
      ['Next Part of the Window', 'F6'],
      ['Previous Part of the Window', 'Shift+F6'],
    ])
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

describe('searchShortcuts', () => {
  it('is Find (Ctrl+F) and Replace (Ctrl+H), with the ids of the shell contract where there is one', () => {
    const find = vi.fn()
    const replace = vi.fn()
    const defs = searchShortcuts({ find, replace, canReplace: () => true })
    expect(defs.map((d) => [d.id, chordLabel(d.chord)])).toEqual([
      ['edit.search-replace', 'Ctrl+F'],
      ['edit.replace', 'Ctrl+H'],
    ])
    dispatch(defs, key({ key: 'f', ctrlKey: true }))
    dispatch(defs, key({ key: 'h', ctrlKey: true }))
    expect(find).toHaveBeenCalledOnce()
    expect(replace).toHaveBeenCalledOnce()
  })

  it('does not replace for somebody who can only look, and leaves Ctrl+H to the browser then', () => {
    const replace = vi.fn()
    const defs = searchShortcuts({ find: () => {}, replace, canReplace: () => false })
    expect(dispatch(defs, key({ key: 'h', ctrlKey: true }))).toBeNull()
    expect(replace).not.toHaveBeenCalled()
  })
})
