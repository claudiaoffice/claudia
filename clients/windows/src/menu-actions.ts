// What a click in the native menu means, and how an `action_state` from the page changes the menu. Pure decision
// logic with no Neutralino or DOM import, so it is checked with plain data (tests/menu-actions.test.ts); the handful
// of real `Neutralino` calls that use it are in shell-page.ts.

import type { WindowMenuItem } from './menu.js'

export interface KnownAction {
  id: string
  checkable: boolean
}

export type MenuClickRoute =
  | { kind: 'quit' }
  | { kind: 'forward'; action: string; target: 'on' | 'off' | undefined }

/** Quit is the one click that is the shell's own: Neutralino itself ends the application rather than the page being
 * asked (the shell ends the process either way). On Windows it stays in the File menu where the manifest has it --
 * there is no application menu to move it to (D44), which is the one place this file differs from clients/macos.
 * Everything else -- including `help.about`, which is `Kind.SHELL` in the shared manifest because GTK shows its own
 * native dialog for it, and the Edit items, which Windows has no native role for -- is forwarded to the page:
 * Neutralino has no native About (`nativeAbout: false`, D158 point 4), so `AboutDialog.vue` has to handle it there
 * instead, the one place this shell's routing deliberately disagrees with the manifest's own `kind` field. */
export function routeMenuClick(
  id: string,
  known: readonly KnownAction[],
  checkedState: Readonly<Record<string, boolean>> = {},
): MenuClickRoute {
  if (id === 'file.quit') return { kind: 'quit' }
  const action = known.find((a) => a.id === id)
  const target = action?.checkable ? nextCheckedTarget(checkedState[id]) : undefined
  return { kind: 'forward', action: id, target }
}

/** Flips a tracked checked state. An id the shell has not seen a state for yet starts `false`, so the first click
 * always reads as turning the thing on -- there is no menu item that defaults to already-on before the page has
 * said otherwise. */
export function nextCheckedTarget(current: boolean | undefined): 'on' | 'off' {
  return current ? 'off' : 'on'
}

export interface ActionState {
  enabled?: boolean
  checked?: boolean
  label?: string
}

/** A new menu tree with `states` applied to the items named (by id) in it, everything else unchanged. Used to
 * rebuild the argument to `Neutralino.window.setMainMenu()` after an `action_state` message, since Neutralino has
 * no per-item update call -- only setting the whole menu again (confirmed by the only real example in its own
 * docs and by the spike's own `menu.set`, which always rebuilds and resends the full array). */
export function applyActionStates(
  menu: readonly WindowMenuItem[],
  states: Readonly<Record<string, ActionState>>,
): WindowMenuItem[] {
  const patchOne = (item: WindowMenuItem): WindowMenuItem => {
    const patched: WindowMenuItem = item.menuItems ? { ...item, menuItems: item.menuItems.map(patchOne) } : { ...item }
    const state = item.id ? states[item.id] : undefined
    if (state) {
      if (state.checked !== undefined) patched.isChecked = state.checked
      if (state.enabled !== undefined) patched.isDisabled = !state.enabled
      if (state.label !== undefined) patched.text = state.label
    }
    return patched
  }
  return menu.map(patchOne)
}
