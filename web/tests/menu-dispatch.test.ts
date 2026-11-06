import { describe, expect, it, vi } from 'vitest'
import { applyAction, collectStates, findMenuItem } from '~/lib/menu-dispatch'
import type { Menu } from '~/components/MenuBar.vue'

function sample(onUndo = vi.fn(), onPaste = vi.fn()): Menu[] {
  return [
    {
      label: 'Edit',
      items: [
        { id: 'edit.undo', label: 'Undo', action: onUndo, disabled: false },
        { id: 'edit.redo', label: 'Redo', action: vi.fn(), disabled: true },
        { label: '', separator: true },
        {
          id: 'edit.paste-as',
          label: 'Paste as',
          items: [{ id: 'edit.paste-as-plain', label: 'Plain text', action: onPaste }],
        },
      ],
    },
    {
      label: 'View',
      items: [{ id: 'view.panel', label: 'History and chat', checked: true, action: vi.fn() }],
    },
  ]
}

describe('findMenuItem', () => {
  it('finds a top-level item by id', () => {
    expect(findMenuItem(sample(), 'edit.undo')?.label).toBe('Undo')
  })
  it('finds a submenu item by id, one level deep', () => {
    expect(findMenuItem(sample(), 'edit.paste-as-plain')?.label).toBe('Plain text')
  })
  it('returns null for an id nothing has, and skips separators safely', () => {
    expect(findMenuItem(sample(), 'file.save')).toBeNull()
  })
})

describe('applyAction', () => {
  it('runs the action and returns true for an enabled item', () => {
    const undo = vi.fn()
    expect(applyAction(sample(undo), 'edit.undo')).toBe(true)
    expect(undo).toHaveBeenCalledWith(undefined)
  })
  it('does nothing and returns false for a disabled item (a stale accelerator, say)', () => {
    expect(applyAction(sample(), 'edit.redo')).toBe(false)
  })
  it('does nothing and returns false for an unknown id', () => {
    expect(applyAction(sample(), 'file.save')).toBe(false)
  })
  it('reaches a submenu item', () => {
    const paste = vi.fn()
    expect(applyAction(sample(undefined, paste), 'edit.paste-as-plain')).toBe(true)
    expect(paste).toHaveBeenCalledOnce()
  })
  it("passes 'on'/'off' through for a checkable item, and nothing else", () => {
    const toggle = vi.fn()
    const menus: Menu[] = [{ label: 'View', items: [{ id: 'view.page', label: 'Page', checked: false, action: toggle }] }]
    applyAction(menus, 'view.page', 'on')
    expect(toggle).toHaveBeenCalledWith('on')
    applyAction(menus, 'view.page', 'bogus')
    expect(toggle).toHaveBeenLastCalledWith(undefined)
  })
})

describe('collectStates', () => {
  it('reports enabled and checked for every id-carrying item, including inside a submenu', () => {
    const states = collectStates(sample())
    expect(states['edit.undo']).toEqual({ enabled: true })
    expect(states['edit.redo']).toEqual({ enabled: false })
    expect(states['edit.paste-as-plain']).toEqual({ enabled: true })
    expect(states['view.panel']).toEqual({ enabled: true, checked: true })
  })
  it('never reports an item with no id (a style name, a shape)', () => {
    const menus: Menu[] = [{ label: 'Format', items: [{ label: 'Body text', checked: true, action: vi.fn() }] }]
    expect(collectStates(menus)).toEqual({})
  })
})
