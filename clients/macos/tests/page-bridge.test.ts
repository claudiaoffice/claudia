// page-bridge.ts is the thin adapter D159 (option 2) calls for: injected into the externally-loaded page so its
// shell-bridge.ts (unchanged, D121) can speak the contract through Neutralino instead of WebKit's messageHandlers.
// The pure decision logic lives here, separate from the handful of real Neutralino/window calls installBridge()
// makes, because those can only really be checked by hand on a Mac (see this package's README "Open" section) --
// everything that does NOT need a live Neutralino is tested here instead.
import { describe, expect, it } from 'vitest'
import {
  applyActionStates,
  nextCheckedTarget,
  routeMenuClick,
  type KnownAction,
} from '../src/page-bridge.js'
import type { WindowMenuItem } from '../src/menu.js'

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
