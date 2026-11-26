// menu-actions.ts holds the pure decisions of the shell page: what a menu click means and how an `action_state` from
// the web app changes the menu. The few real Neutralino calls that use it are in shell-page.ts (tested with fakes).
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  applyActionStates,
  drawMenu,
  nextCheckedTarget,
  routeMenuClick,
  type KnownAction,
} from '../src/menu-actions.js'
import { buildMenus, type ManifestEntry, type WindowMenuItem } from '../src/menu.js'

const KNOWN: KnownAction[] = [
  { id: 'file.new', checkable: false },
  { id: 'file.quit', checkable: false },
  { id: 'help.about', checkable: false },
  { id: 'view.panel', checkable: true },
]

describe('routeMenuClick', () => {
  it('routes file.quit to the shell itself, not the page (D44: Quit lives in the application menu)', () => {
    expect(routeMenuClick('file.quit', KNOWN)).toEqual({ kind: 'quit' })
  })

  it('routes help.about to the page despite being Kind.SHELL in the manifest (D158 point 4: no native About on macOS)', () => {
    expect(routeMenuClick('help.about', KNOWN)).toEqual({ kind: 'forward', action: 'help.about', target: undefined })
  })

  it('forwards an ordinary action as-is, with no target (not checkable)', () => {
    expect(routeMenuClick('file.new', KNOWN)).toEqual({ kind: 'forward', action: 'file.new', target: undefined })
  })

  it('forwards a checkable action with the toggled target the page should move to', () => {
    expect(routeMenuClick('view.panel', KNOWN, { 'view.panel': false })).toEqual({
      kind: 'forward',
      action: 'view.panel',
      target: 'on',
    })
    expect(routeMenuClick('view.panel', KNOWN, { 'view.panel': true })).toEqual({
      kind: 'forward',
      action: 'view.panel',
      target: 'off',
    })
  })

  it('forwards an id the shell has never heard of rather than dropping it silently (the page itself can refuse it)', () => {
    expect(routeMenuClick('tools.ask', KNOWN)).toEqual({ kind: 'forward', action: 'tools.ask', target: undefined })
  })
})

describe('nextCheckedTarget', () => {
  it('toggles, defaulting an unknown current state to unchecked (so the first click always turns something on)', () => {
    expect(nextCheckedTarget(undefined)).toBe('on')
    expect(nextCheckedTarget(false)).toBe('on')
    expect(nextCheckedTarget(true)).toBe('off')
  })
})

describe('applyActionStates', () => {
  const menu: WindowMenuItem[] = [
    {
      text: 'View',
      menuItems: [
        { id: 'view.panel', text: 'History and Chat', isChecked: false },
        { id: 'view.dark', text: 'Dark Mode', isChecked: false },
      ],
    },
    { text: 'Help', menuItems: [{ id: 'help.ask', text: 'Ask ai' }] },
  ]

  it('patches isChecked/isDisabled/text for the ids named, in place, leaving the rest untouched', () => {
    const next = applyActionStates(menu, { 'view.panel': { checked: true }, 'help.ask': { enabled: false } })
    const panel = next[0]?.menuItems?.find((i) => i.id === 'view.panel')
    const dark = next[0]?.menuItems?.find((i) => i.id === 'view.dark')
    const ask = next[1]?.menuItems?.find((i) => i.id === 'help.ask')
    expect(panel?.isChecked).toBe(true)
    expect(dark?.isChecked).toBe(false) // untouched
    expect(ask?.isDisabled).toBe(true)
  })

  it('relabels an item when the page sends a new label (D125: permanently-disabled stub items use this)', () => {
    const next = applyActionStates(menu, { 'help.ask': { label: 'Not available yet' } })
    expect(next[1]?.menuItems?.find((i) => i.id === 'help.ask')?.text).toBe('Not available yet')
  })

  it('returns a new tree rather than mutating the one passed in (the caller may be re-rendering from it elsewhere)', () => {
    applyActionStates(menu, { 'view.panel': { checked: true } })
    expect(menu[0]?.menuItems?.find((i) => i.id === 'view.panel')?.isChecked).toBe(false)
  })
})

// slice 6 of the menu work (D1645): an entry the page leaves out is not drawn, by the rule the page and the Linux shell
// draw by too (clients/contract/fixtures/menu-collapse.json), and a menu with nothing left says why (D1603)
describe('drawMenu', () => {
  type Spec = string | { submenu: string; items: string[] }
  const fixture = JSON.parse(readFileSync(resolve(__dirname, '../../contract/fixtures/menu-collapse.json'), 'utf8')) as {
    cases: { name: string; sections: Spec[][]; drawn: Spec[] }[]
  }
  const action = (label: string): ManifestEntry => ({ id: `test.${label.replace('~', '')}`, label, kind: 'page', checkable: false, accelerators: [], role: null })
  const item = (entry: ManifestEntry) => ({ id: 'id' in entry ? entry.id : undefined, text: entry.label })
  const asSpec = (items: readonly WindowMenuItem[]): Spec[] =>
    items.map((i) => (i.text === '-' ? '-' : i.menuItems ? { submenu: i.text, items: i.menuItems.map((sub) => sub.text) } : i.text))

  it.each(fixture.cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const sections = c.sections.map((section) => section.map((e) => (typeof e === 'string' ? action(e) : { label: e.submenu, items: e.items.map(action) as never })))
    const whole = buildMenus({ app: 'test', menus: [{ word: 'test', label: 'Test', sections }], header_toggles: [] }, item)
    const hidden = c.sections.flat().flatMap((e) => (typeof e === 'string' ? [e] : e.items)).filter((l) => l.startsWith('~'))
    const states = Object.fromEntries(hidden.map((l) => [`test.${l.slice(1)}`, { visible: false }]))
    const drawn = drawMenu(applyActionStates(whole, states), {})
    expect(asSpec(drawn[0]?.menuItems ?? [])).toEqual(c.drawn)
  })

  it('puts the greyed line that says why into a menu with nothing left, and keeps its title (D1603)', () => {
    const whole = buildMenus({ app: 'test', menus: [{ word: 'insert', label: 'Insert', sections: [[action('Image…')]] }], header_toggles: [] }, item)
    const drawn = drawMenu(applyActionStates(whole, { 'test.Image…': { visible: false } }), { insert: 'Nothing to insert: you can only look at this document.' })
    expect(drawn).toEqual([{ text: 'Insert', menuItems: [{ text: 'Nothing to insert: you can only look at this document.', isDisabled: true }] }])
  })

  it('shows an entry again that the page puts back', () => {
    const whole = buildMenus({ app: 'test', menus: [{ word: 'insert', label: 'Insert', sections: [[action('Image…')]] }], header_toggles: [] }, item)
    const back = applyActionStates(applyActionStates(whole, { 'test.Image…': { visible: false } }), { 'test.Image…': { visible: true } })
    expect(drawMenu(back, {})).toEqual([{ text: 'Insert', menuItems: [{ id: 'test.Image…', text: 'Image…' }] }])
  })
})
