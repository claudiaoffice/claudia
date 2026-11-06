// Connects the menu data every workspace already builds (`MenuBar.vue`'s `Menu[]`) to the shell contract: which item
// an incoming action id means, and what state to report back for it. One place, so a workspace wires its shell bridge
// in three lines instead of writing this lookup three times (D121).
import type { ActionState } from './shell-bridge'
import type { Menu, MenuItem } from '../components/MenuBar.vue'

/** Every item that can carry an `id` (top-level items and the one level of submenu the schema uses). */
function* walk(menus: Menu[]): Generator<MenuItem> {
  for (const menu of menus) {
    for (const item of menu.items) {
      if (item.separator) continue
      yield item
      if (item.items) yield* item.items
    }
  }
}

export function findMenuItem(menus: Menu[], id: string): MenuItem | null {
  for (const item of walk(menus)) if (item.id === id) return item
  return null
}

/**
 * Carries out the action the shell asked for. `target` is `'on'`/`'off'` for a checkable item (the shell always
 * sends one of the two, never a bare toggle — see `window.py`'s `_on_change_state`) and is otherwise ignored.
 * Returns whether an enabled item was found, so the caller can report a problem for anything else.
 */
export function applyAction(menus: Menu[], id: string, target?: string): boolean {
  const item = findMenuItem(menus, id)
  if (!item || item.disabled || !item.action) return false
  item.action(target === 'on' || target === 'off' ? target : undefined)
  return true
}

/** The `action_state` the shell should see for one item right now. */
function stateOf(item: MenuItem): ActionState {
  const state: ActionState = { enabled: !item.disabled }
  if (item.checked !== undefined) state.checked = item.checked
  return state
}

/** Every id-carrying item's current state, for `ShellBridge.reportStates`. */
export function collectStates(menus: Menu[]): Record<string, ActionState> {
  const states: Record<string, ActionState> = {}
  for (const item of walk(menus)) if (item.id) states[item.id] = stateOf(item)
  return states
}
