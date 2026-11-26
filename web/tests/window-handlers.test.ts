// What the entries every document window has do (D1644): File, Undo and Redo, the clipboard, View, Preferences and Help,
// the same in the three apps. Where they stand and when they fit is the definition's; this is what they do.
import { describe, expect, it, vi } from 'vitest'
import { DEFINITIONS } from '~/lib/menus.generated'
import { handlerGaps } from '~/lib/menus/assemble'
import { windowHandlers, type WindowContext } from '~/lib/menus/window-handlers'

const t = (msgid: string, vars: Record<string, string | number> = {}) =>
  msgid.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`))

function context(over: Partial<WindowContext> = {}): WindowContext {
  return {
    t,
    open: vi.fn(),
    leave: vi.fn(),
    print: vi.fn(),
    history: { undo: vi.fn(), redo: vi.fn(), undoLabel: () => '', redoLabel: () => '' },
    paste: vi.fn(),
    search: vi.fn(),
    panel: { open: () => true, toggle: vi.fn() },
    replay: { start: vi.fn(), notNow: () => null },
    back: vi.fn(),
    theme: { on: () => false, toggle: vi.fn() },
    ask: vi.fn(),
    help: vi.fn(),
    language: { current: () => 'en', choose: vi.fn() },
    ...over,
  }
}

describe('the entries every window has', () => {
  it('opens the About dialog from Help ▸ About, in every app (the shells send help.about)', () => {
    const c = context()
    windowHandlers(c)['help.about']!.run()
    expect(c.open).toHaveBeenCalledWith('about')
  })

  // UX-95: hand over, accept and leave had no entry since the workbook made them one dialog
  it('opens the My Role dialog from File ▸ Manage ▸ My Role…', () => {
    const c = context()
    windowHandlers(c)['file.manage.my-role']!.run()
    expect(c.open).toHaveBeenCalledWith('my-role')
  })

  it('names what Undo and Redo would take back or do again', () => {
    const handlers = windowHandlers(context({ history: { undo: vi.fn(), redo: vi.fn(), undoLabel: () => 'Add Container', redoLabel: () => '' } }))
    expect(handlers['edit.undo']!.label!()).toBe('Undo Add Container')
    expect(handlers['edit.redo']!.label!()).toBe('Redo')
  })

  it('gives Copy and Share… a sentence of their own for who may not (D1640, D1650)', () => {
    const handlers = windowHandlers(context())
    expect(handlers['edit.copy']!.why).toEqual({ role: 'Only editors and owners can copy from this document.' })
    expect(handlers['file.manage.share']!.why).toEqual({ role: 'Only an owner can share this document.' })
  })

  it('names each language by its own name, ticks the one in use, and chooses it', () => {
    const c = context({ language: { current: () => 'de', choose: vi.fn() } })
    const handlers = windowHandlers(c)
    expect([handlers['config.language.de']!.label!(), handlers['config.language.de']!.checked!()]).toEqual(['Deutsch', true])
    expect(handlers['config.language.en']!.checked!()).toBe(false)
    handlers['config.language.en']!.run()
    expect(c.language.choose).toHaveBeenCalledWith('en')
  })

  it('has no handler for an action no app has', () => {
    const ids = new Set(Object.values(DEFINITIONS).flatMap((app) => [...collect(app)]))
    for (const id of Object.keys(windowHandlers(context()))) expect(ids.has(id), id).toBe(true)
    // and an app's gaps are only its own entries
    expect(handlerGaps(DEFINITIONS.composes, windowHandlers(context())).unknown).toEqual([])
  })
})

function collect(app: (typeof DEFINITIONS)['composes']): Set<string> {
  const ids = new Set<string>()
  for (const menu of [...app.menus, ...app.contexts]) {
    for (const section of menu.sections) for (const placed of section) for (const entry of 'items' in placed ? placed.items : [placed]) ids.add(entry.id)
  }
  return ids
}
