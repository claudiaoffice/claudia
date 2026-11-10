// The page-side adapter D159 (option 2) needed: injected into the externally-loaded page (the real document
// server's own loopback page, D115) so web/app/lib/shell-bridge.ts -- unchanged, D121 -- can speak the shell
// contract through Neutralino instead of through WebKit's messageHandlers, which only WebKitGTK (Linux) actually
// provides. shell-bridge.ts's own detectHandler() looks for exactly one thing: `window.webkit.messageHandlers
// .claudia.postMessage`. This file shims that shape, so **shell-bridge.ts itself needs no change at all** -- the
// shim is the whole adapter, consistent with D121's "the page speaks the contract directly" now covering a third
// shell the same way it already covers Linux and macOS. Nearly identical to clients/macos/src/page-bridge.ts --
// the wiring below is OS-agnostic Neutralino API calls, not Windows- or macOS-specific ones; the two files differ
// only in what they say about why (menu.ts's own top comment has the one real behavioural difference: no `role`
// field to read), not in what they do.
//
// Pure decision logic (what a menu click means, how to patch a menu tree for action_state) is separated from the
// handful of real `Neutralino`/`window` calls in installBridge(), because only the pure half can be checked here:
// whether Neutralino's injection actually reaches a page loaded from an *external* URL at all is confirmed for
// macOS (D159's note, "Confirmed, 2026-11-07 (owner's own Mac)") but **not yet re-confirmed on a real Windows
// machine** -- this package's README says so. installBridge() is written to make that check easy, not to replace it.

import { buildMainMenu, type ManifestListing, type WindowMenuItem } from './menu.js'

export interface KnownAction {
  id: string
  checkable: boolean
}

export type MenuClickRoute =
  | { kind: 'quit' }
  | { kind: 'forward'; action: string; target: 'on' | 'off' | undefined }

/** `file.quit` is handled by the shell itself (`Neutralino.app.exit()`) rather than forwarded to the page -- the
 * same split Linux's GTK shell makes for its own Kind.SHELL actions, and the same one macOS's routeMenuClick makes
 * (there, because D44 moved Quit into the application menu; here, File still holds Quit in its ordinary place, but
 * the shell is still the thing that should actually end the process either way). Everything else -- including
 * `help.about`, which is `Kind.SHELL` in the shared manifest because GTK shows its own native dialog for it -- is
 * forwarded to the page: Neutralino reports `nativeAbout: false` on Windows just as it does on macOS (D158 point
 * 3), so `AboutDialog.vue` has to handle it there instead, the one place this shell's routing deliberately
 * disagrees with the manifest's own `kind` field. */
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
 * docs, and by the spike's own `menu.set`, which always rebuilds and resends the full array). */
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

// ------------------------------------------------------------------------------------------- the live wiring

/** The slice of the real `Neutralino` global this file calls. Typed by hand (Neutralino ships no first-party
 * TypeScript types for the injected client library), like clients/macos/src/page-bridge.ts's own `NeutralinoLike`,
 * so a fake can stand in during a test -- though none of installBridge() itself has a test today, see this
 * module's top comment for why. */
export interface NeutralinoLike {
  window: { setMainMenu(menu: WindowMenuItem[]): Promise<void>; print(): Promise<void> }
  events: { on(name: string, handler: (event: { detail: unknown }) => void): Promise<void> }
  app: { exit(): Promise<void> }
}

export interface WindowLike {
  webkit?: { messageHandlers?: { claudia?: { postMessage(raw: string): void } } }
  __claudiaShell?: { receive(raw: string): void }
}

function collectKnownActions(menu: readonly WindowMenuItem[]): KnownAction[] {
  const out: KnownAction[] = []
  for (const item of menu) {
    if (item.menuItems) out.push(...collectKnownActions(item.menuItems))
    else if (item.id) out.push({ id: item.id, checkable: item.isChecked !== undefined })
  }
  return out
}

/**
 * Wires a live `Neutralino` object and the page's `window` together: builds the native menu from `listing`
 * (`menu.ts`'s `buildMainMenu`), shims `window.webkit.messageHandlers.claudia` so `shell-bridge.ts`'s existing
 * `detectHandler()` finds it, answers the page's `hello` with `welcome` directly (there is no separate native
 * shell process to round-trip to -- this script *is* the shell, running inside the page, D159 option 2), and turns
 * `mainMenuItemClicked` into contract `action` messages via `routeMenuClick`.
 */
export function installBridge(neutralino: NeutralinoLike, win: WindowLike, listing: ManifestListing, appTitle: string): void {
  let menu = buildMainMenu(listing, appTitle)
  const known = collectKnownActions(menu)
  const checkedState: Record<string, boolean> = {}
  for (const item of known) if (item.checkable) checkedState[item.id] = false

  void neutralino.window.setMainMenu(menu)

  win.webkit = win.webkit ?? {}
  win.webkit.messageHandlers = win.webkit.messageHandlers ?? {}
  win.webkit.messageHandlers.claudia = {
    postMessage(raw: string) {
      let message: unknown
      try {
        message = JSON.parse(raw)
      } catch {
        return // malformed JSON from our own page's shell-bridge.ts would be our bug, not the shell's to fix here
      }
      if (!message || typeof message !== 'object') return
      const { type } = message as { type?: unknown }
      if (type === 'hello') {
        win.__claudiaShell?.receive(
          JSON.stringify({ type: 'welcome', contract: 1, shell: 'claudia-windows', capabilities: ['native-menu', 'actions'] }),
        )
      } else if (type === 'action_state') {
        const { states } = message as { states?: Record<string, ActionState> }
        if (states) {
          menu = applyActionStates(menu, states)
          void neutralino.window.setMainMenu(menu)
        }
      }
    },
  }

  void neutralino.events.on('mainMenuItemClicked', (event) => {
    const { id } = (event.detail ?? {}) as { id?: string }
    if (!id) return
    const route = routeMenuClick(id, known, checkedState)
    if (route.kind === 'quit') {
      void neutralino.app.exit()
      return
    }
    if (route.target !== undefined) checkedState[id] = route.target === 'on'
    win.__claudiaShell?.receive(JSON.stringify({ type: 'action', action: route.action, target: route.target }))
  })
}
