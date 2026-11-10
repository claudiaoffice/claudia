// Mirrors clients/macos/tests/menu.test.ts's scope (fixture-driven, no Neutralino import needed), but tests a
// simpler module: this file's own top comment explains why there is no application-menu relocation and no `role`
// reading here, unlike macOS's buildMainMenu().
import { describe, expect, it } from 'vitest'
import { buildMainMenu, gtkAccelToWindowsShortcut, type ManifestListing } from '../src/menu.js'

function action(id: string, overrides: Partial<ManifestListing['menus'][number]['sections'][number][number]> = {}) {
  return {
    id,
    label: id,
    kind: 'page' as const,
    checkable: false,
    accelerators: [],
    role: null,
    ...overrides,
  }
}

describe('gtkAccelToWindowsShortcut', () => {
  it('translates every accelerator shape actually used in the shared manifest today', () => {
    expect(gtkAccelToWindowsShortcut('<Primary>n')).toBe('Ctrl+N')
    expect(gtkAccelToWindowsShortcut('<Primary>o')).toBe('Ctrl+O')
    expect(gtkAccelToWindowsShortcut('<Primary>q')).toBe('Ctrl+Q')
    expect(gtkAccelToWindowsShortcut('<Shift>F10')).toBe('Shift+F10')
    expect(gtkAccelToWindowsShortcut('F1')).toBe('F1')
  })

  it('translates a Ctrl+Shift+letter combination, a shape not in the manifest yet but confirmed by its own regular expression', () => {
    expect(gtkAccelToWindowsShortcut('<Primary><Shift>n')).toBe('Ctrl+Shift+N')
  })

  it('returns null for anything outside those confirmed shapes rather than guessing -- cosmetic here, so a wider confirmed set than macOS is fine, but still not unbounded', () => {
    expect(gtkAccelToWindowsShortcut('<Alt>F4')).toBeNull()
    expect(gtkAccelToWindowsShortcut('')).toBeNull()
    expect(gtkAccelToWindowsShortcut('n')).toBeNull()
  })
})

describe('buildMainMenu', () => {
  it('keeps the manifest\'s own menu order and content unchanged -- unlike macOS, nothing is relocated into a leading application menu', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [
        { label: 'File', sections: [[action('file.new'), action('file.quit')]] },
        { label: 'Help', sections: [[action('help.about')]] },
      ],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    expect(menu).toHaveLength(2)
    expect(menu[0]?.text).toBe('File')
    expect(menu[0]?.menuItems?.map((i) => i.id)).toEqual(['file.new', 'file.quit'])
    expect(menu[1]?.text).toBe('Help')
    expect(menu[1]?.menuItems?.map((i) => i.id)).toEqual(['help.about'])
  })

  it('puts a separator between sections, and only between them', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [{ label: 'Edit', sections: [[action('edit.undo')], [action('edit.copy')]] }],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    expect(menu[0]?.menuItems?.map((i) => i.text)).toEqual(['edit.undo', '-', 'edit.copy'])
  })

  it('builds a submenu as a nested menuItems array', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [
        {
          label: 'Edit',
          sections: [[{ label: 'Paste As', items: [action('edit.paste-as-plain')] }]],
        },
      ],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    const submenu = menu[0]?.menuItems?.[0]
    expect(submenu?.text).toBe('Paste As')
    expect(submenu?.menuItems?.map((i) => i.id)).toEqual(['edit.paste-as-plain'])
  })

  it('gives a checkable action isChecked: false before the page has reported real state', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [{ label: 'View', sections: [[action('view.dark-mode', { checkable: true })]] }],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    expect(menu[0]?.menuItems?.[0]?.isChecked).toBe(false)
  })

  it('never sets a native `action` field -- Windows has no Cocoa selector to route through, unlike macOS (this module\'s top comment)', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [{ label: 'Edit', sections: [[action('edit.copy', { role: 'copy:', accelerators: [] })]] }],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    expect(menu[0]?.menuItems?.[0]).not.toHaveProperty('action')
  })

  it('sets a display-only shortcut from the accelerator when one translates, role or not', () => {
    const listing: ManifestListing = {
      app: 'composes',
      header_toggles: [],
      menus: [{ label: 'File', sections: [[action('file.new', { accelerators: ['<Primary>n'] })]] }],
    }
    const menu = buildMainMenu(listing, 'Claudia Composes')
    expect(menu[0]?.menuItems?.[0]?.shortcut).toBe('Ctrl+N')
  })
})
