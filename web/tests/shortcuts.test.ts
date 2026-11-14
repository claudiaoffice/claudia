import { describe, expect, it, vi } from 'vitest'
import type { Menu } from '~/components/MenuBar.vue'
import { chordLabel, chordOf, dispatch, hintOf, isTypingTarget, matches, menuShortcuts, regionShortcuts, searchShortcuts, sharedShortcuts } from '~/lib/shortcuts'

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
  it('goes by the character first, and by the place only when the key typed no letter or digit (UX-35)', () => {
    // a German keyboard has Z where a US one has Y: Ctrl+Alt+Y is the key that types y, wherever it is
    const sql = { key: 'y', code: 'KeyY', ctrl: true, alt: true }
    expect(matches(sql, key({ key: 'y', code: 'KeyZ', ctrlKey: true, altKey: true }))).toBe(true)
    expect(matches(sql, key({ key: 'z', code: 'KeyY', ctrlKey: true, altKey: true }))).toBe(false)
    // Option+Y types ¥ on a Mac: then the place decides
    expect(matches(sql, key({ key: '¥', code: 'KeyY', metaKey: true, altKey: true }))).toBe(true)
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

describe('one key table for every client (UX-35)', () => {
  it('gives a menu action its key from the table, and refuses one the table does not have', () => {
    expect(chordOf('file.print')).toEqual({ key: 'p', code: 'KeyP', ctrl: true })
    expect(() => chordOf('file.nothing')).toThrow('no key for file.nothing')
  })

  it('shows a key the way people read it', () => {
    expect(hintOf('edit.row-insert-above')).toBe('Shift+Alt+↑')
    expect(hintOf('config.shortcuts')).toBe('Ctrl+?') // the symbol, without the Shift that types it
    expect(hintOf('edit.clear')).toBe('Del')
    expect(hintOf('format.look')).toBe('Shift+F10')
    expect(hintOf(undefined)).toBeUndefined()
    expect(hintOf('config.language.de')).toBeUndefined()
  })

  it('makes every keyed menu entry a shortcut, enabled as the entry is, except the keys of the view and those taken', () => {
    const ran: string[] = []
    const menus: Menu[] = [
      {
        label: 'File',
        items: [
          { id: 'file.print', label: 'Print…', action: () => ran.push('print') },
          { label: '', separator: true },
          { id: 'file.manage', label: 'Manage', items: [{ id: 'file.manage.share', label: 'Share…', action: () => ran.push('share'), disabled: true }] },
          { id: 'file.save', label: 'Save', action: () => ran.push('save') },
        ],
      },
      { label: 'Edit', items: [{ id: 'edit.copy', label: 'Copy', action: () => ran.push('copy') }, { label: 'No id', action: () => ran.push('none') }] },
    ]
    const defs = menuShortcuts(menus, new Set(['file.save']))
    expect(defs.map((d) => d.id)).toEqual(['file.print', 'file.manage.share'])
    expect(dispatch(defs, key({ key: 'p', ctrlKey: true }))?.id).toBe('file.print')
    expect(dispatch(defs, key({ key: 'S', code: 'KeyS', ctrlKey: true, altKey: true, shiftKey: true }))).toBeNull() // disabled
    expect(ran).toEqual(['print'])
  })
})

describe('a symbol', () => {
  it('is the character, with or without the Shift that typed it', () => {
    const shortcuts = { key: '?', ctrl: true, shift: true }
    expect(matches(shortcuts, key({ key: '?', ctrlKey: true, shiftKey: true }))).toBe(true)
    expect(matches(shortcuts, key({ key: '?', ctrlKey: true }))).toBe(true)
    expect(matches(shortcuts, key({ key: '/', ctrlKey: true }))).toBe(false)
  })
})
