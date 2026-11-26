// What a click in the native menu means, and how an `action_state` from the page changes the menu. Pure decision
// logic with no Neutralino or DOM import, so it is checked with plain data (tests/menu-actions.test.ts); the handful
// of real `Neutralino` calls that use it are in shell-page.ts.

import { SEPARATOR, type ShellMenuItem, type WindowMenuItem } from './menu.js'

export interface KnownAction {
  id: string
  checkable: boolean
}

export type MenuClickRoute =
  | { kind: 'quit' }
  | { kind: 'forward'; action: string; target: 'on' | 'off' | undefined }

/** Quit is the one click that is the shell's own: the app ends rather than the page being asked to (on macOS it sits in
 * the application menu, D44; on Windows in File). Everything else -- including `help.about`, which is `Kind.SHELL` in
 * the shared manifest because GTK shows its own native dialog for it -- is forwarded to the page: Neutralino has no
 * native About (`nativeAbout: false`, D158 point 4), so `AboutDialog.vue` has to handle it there instead, the one place
 * this shell's routing deliberately disagrees with the manifest's own `kind` field. */
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
  /** False: the page leaves the entry out for now (D1645); `drawMenu` does not draw it. */
  visible?: boolean
}

/** A new menu tree with `states` applied to the items named (by id) in it, everything else unchanged. Used to
 * rebuild the argument to `Neutralino.window.setMainMenu()` after an `action_state` message, since Neutralino has
 * no per-item update call -- only setting the whole menu again (confirmed by the only real example in its own
 * docs and by the spike's own `menu.set`, which always rebuilds and resends the full array). */
export function applyActionStates(
  menu: readonly ShellMenuItem[],
  states: Readonly<Record<string, ActionState>>,
): ShellMenuItem[] {
  const patchOne = (item: ShellMenuItem): ShellMenuItem => {
    const patched: ShellMenuItem = item.menuItems ? { ...item, menuItems: item.menuItems.map(patchOne) } : { ...item }
    const state = item.id ? states[item.id] : undefined
    if (state) {
      if (state.checked !== undefined) patched.isChecked = state.checked
      if (state.enabled !== undefined) patched.isDisabled = !state.enabled
      if (state.label !== undefined) patched.text = state.label
      if (state.visible !== undefined) patched.isHidden = !state.visible
    }
    return patched
  }
  return menu.map(patchOne)
}

/** What Neutralino is given: the menus without the entries the page leaves out, by the rule the page and the Linux
 * shell draw by (clients/contract/fixtures/menu-collapse.json): no submenu with nothing in it, and no separator first,
 * last or twice. A menu of the bar with nothing left keeps its title (D1603) and holds the greyed line of `empty`
 * that says why. */
export function drawMenu(menu: readonly ShellMenuItem[], empty: Readonly<Record<string, string>>): WindowMenuItem[] {
  const drawOne = (item: ShellMenuItem): WindowMenuItem | null => {
    if (item.isHidden) return null
    if (!item.menuItems) return plainOf(item)
    const items = collapse(item.menuItems.map(drawOne).filter((i): i is WindowMenuItem => i !== null))
    return items.length ? { ...plainOf(item), menuItems: items } : null
  }
  return menu.map((top) => {
    const why = top.word ? empty[top.word] : undefined
    return drawOne(top) ?? { ...plainOf(top), menuItems: why ? [{ text: why, isDisabled: true }] : [] }
  })
}

/** The item as Neutralino takes it: without the shell's notes on it and without its items. */
function plainOf(item: ShellMenuItem): WindowMenuItem {
  const { isHidden: _hidden, word: _word, menuItems: _items, ...plain } = item
  return plain
}

/** No separator first, last or right after another. */
function collapse(items: readonly WindowMenuItem[]): WindowMenuItem[] {
  const isLine = (i: WindowMenuItem | undefined) => i?.text === SEPARATOR.text && !i.id && !i.menuItems
  const out: WindowMenuItem[] = []
  for (const i of items) if (!isLine(i) || (out.length && !isLine(out.at(-1)))) out.push(i)
  while (isLine(out.at(-1))) out.pop()
  return out
}
