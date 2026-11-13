// menu.ts turns one app's generated manifest JSON (tools/generate_menu.py's output) into the array
// Neutralino.window.setMainMenu() expects, applying D44's macOS placement (About/Quit move into the application
// menu) and D158's Cocoa roles. Fixture data is inlined rather than read from src/generated/menu.creates.json so
// this test does not depend on that file's current shape -- test_generate_menu.py already guards that file's own
// freshness; this one guards the *transformation*.
import { describe, expect, it } from 'vitest'
import { buildMainMenu, gtkAccelToMacShortcut } from '../src/menu.js'
import type { ManifestListing } from '../src/menu.js'

const FIXTURE: ManifestListing = {
  app: 'creates',
  header_toggles: [],
  menus: [
    {
      label: 'File',
      sections: [
        [
          { id: 'file.new', label: 'New', kind: 'page', checkable: false, accelerators: ['<Primary>n'], role: null },
        ],
        [
          { id: 'file.close', label: 'Close Document', kind: 'page', checkable: false, accelerators: [], role: null },
          { id: 'file.quit', label: 'Quit', kind: 'shell', checkable: false, accelerators: ['<Primary>q'], role: null },
        ],
      ],
    },
    {
      label: 'Edit',
      sections: [
        [
          { id: 'edit.undo', label: 'Undo', kind: 'page', checkable: false, accelerators: [], role: 'undo:' },
          { id: 'edit.redo', label: 'Redo', kind: 'page', checkable: false, accelerators: [], role: 'redo:' },
        ],
        [
          { id: 'edit.copy', label: 'Copy', kind: 'page', checkable: false, accelerators: [], role: 'copy:' },
          {
            label: 'Paste As',
            items: [
              {
                id: 'edit.paste-as-plain',
                label: 'Plain Text',
                kind: 'page',
                checkable: false,
                accelerators: [],
                role: null,
              },
            ],
          },
        ],
      ],
    },
    {
      label: 'View',
      sections: [
        [{ id: 'view.panel', label: 'History and Chat', kind: 'page', checkable: true, accelerators: [], role: null }],
      ],
    },
    {
      label: 'Config',
      sections: [
        [
          {
            id: 'config.shortcuts',
            label: 'Shortcuts',
            kind: 'page',
            checkable: false,
            accelerators: ['F1'],
            role: null,
          },
        ],
      ],
    },
    {
      label: 'Help',
      sections: [
        [
          { id: 'help.ask', label: 'Ask ai', kind: 'page', checkable: false, accelerators: [], role: null },
          {
            id: 'help.about',
            label: 'About Claudia Creates',
            kind: 'shell',
            checkable: false,
            accelerators: [],
            role: null,
          },
        ],
      ],
    },
  ],
}

describe('gtkAccelToMacShortcut', () => {
  it('turns a bare <Primary>letter accelerator into the lowercase letter Neutralino expects', () => {
    expect(gtkAccelToMacShortcut('<Primary>n')).toBe('n')
    expect(gtkAccelToMacShortcut('<Primary>Q')).toBe('q')
  })

  it('returns null for anything whose Neutralino shortcut grammar is not confirmed', () => {
    // Shift combinations, bare function keys and anything else: the Neutralino docs define only a bare
    // <Primary>-implied letter (neutralino.js.org/docs/api/window); guessing at the rest risks a wrong binding.
    expect(gtkAccelToMacShortcut('<Shift>F10')).toBeNull()
    expect(gtkAccelToMacShortcut('F1')).toBeNull()
    expect(gtkAccelToMacShortcut('<Primary><Shift>n')).toBeNull()
  })
})

describe('buildMainMenu', () => {
  const menu = buildMainMenu(FIXTURE, 'Claudia Creates')
  const byText = (label: string) => menu.find((m) => m.text === label)

  it('puts About and Quit into a leading application menu named after the app (D44)', () => {
    const app = menu[0]
    expect(app?.text).toBe('Claudia Creates')
    expect(app?.menuItems?.map((i) => i.id)).toEqual(['help.about', 'file.quit'])
    expect(app?.menuItems?.[0]?.text).toBe('About Claudia Creates')
  })

  it('drops Quit from File and About from Help, since both now live in the application menu', () => {
    const file = byText('File')
    expect(file?.menuItems?.some((i) => i.id === 'file.quit')).toBe(false)
    expect(file?.menuItems?.some((i) => i.id === 'file.new')).toBe(true)

    const help = byText('Help')
    expect(help?.menuItems?.some((i) => i.id === 'help.about')).toBe(false)
    expect(help?.menuItems?.some((i) => i.id === 'help.ask')).toBe(true)
  })

  it('keeps every other menu, in order, with a separator surviving between its sections', () => {
    expect(menu.map((m) => m.text)).toEqual(['Claudia Creates', 'File', 'Edit', 'View', 'Config', 'Help'])
    const file = byText('File')
    // File still has two sections (New | Close Document, once Quit is removed from the second) -- the separator
    // between them has to survive that removal, not just the removal of the item itself.
    expect(file?.menuItems?.map((i) => i.text)).toEqual(['New', '-', 'Close Document'])
  })

  it('sets the Cocoa action and a shortcut for the fixed set of standard editing roles', () => {
    const edit = byText('Edit')
    const copy = edit?.menuItems?.find((i) => i.id === 'edit.copy')
    expect(copy?.action).toBe('copy:')
    expect(copy?.shortcut).toBe('c')
    const undo = edit?.menuItems?.find((i) => i.id === 'edit.undo')
    expect(undo?.action).toBe('undo:')
    expect(undo?.shortcut).toBe('z')
  })

  it('leaves redo without a shortcut: Cmd+Shift+Z is not a confirmed Neutralino shortcut string (open item)', () => {
    const redo = byText('Edit')?.menuItems?.find((i) => i.id === 'edit.redo')
    expect(redo?.action).toBe('redo:')
    expect(redo?.shortcut).toBeUndefined()
  })

  it('carries a plain accelerator through when the translation is confirmed, and omits it otherwise', () => {
    const file = byText('File')
    expect(file?.menuItems?.find((i) => i.id === 'file.new')?.shortcut).toBe('n')
    const config = byText('Config')
    // F1 has no confirmed Neutralino shortcut grammar (see gtkAccelToMacShortcut) -- shown, not bound
    expect(config?.menuItems?.find((i) => i.id === 'config.shortcuts')?.shortcut).toBeUndefined()
  })

  it('renders a submenu (Paste As) as a nested menuItems array with no id of its own', () => {
    const edit = byText('Edit')
    const pasteAs = edit?.menuItems?.find((i) => i.text === 'Paste As')
    expect(pasteAs?.id).toBeUndefined()
    expect(pasteAs?.menuItems?.[0]?.id).toBe('edit.paste-as-plain')
  })

  it('marks a checkable action as checked only when told to -- initial state is unchecked, isCheckable so the page can flip it', () => {
    const view = byText('View')
    const panel = view?.menuItems?.find((i) => i.id === 'view.panel')
    expect(panel?.isChecked).toBe(false)
  })
})
