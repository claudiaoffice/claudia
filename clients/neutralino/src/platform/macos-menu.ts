// The macOS menu (D44, D158): the manifest's menus behind an application menu, and Cocoa roles for the editing items.
//
// Two things this module does that the manifest itself does not know about, both D44:
//  - macOS puts About, Preferences and Quit in the *application* menu, not File/Help. This file relocates
//    `help.about` and `file.quit` into a new leading menu named after the app and drops them from their original
//    menus. There is no `file.preferences` action yet, so nothing is relocated there for now.
//  - The five standard editing roles (D158) get a fixed Neutralino `shortcut` (undo z, cut x, copy c, paste v) so
//    the key equivalent is actually claimed by the menu -- without one, `action` alone was not enough on the
//    owner's Mac (notes/e0-3-neutralino-windows-macos.md). Redo is deliberately left unbound: a documented
//    Neutralino shortcut string for Cmd+Shift+Z does not exist (gtkAccelToMacShortcut's own doc comment), and the
//    spike that first found this bug left it unbound for the same reason rather than guess.

import { buildMenus, findAction, type ManifestAction, type ManifestListing, type ShellMenuItem, type WindowMenuItem } from '../menu.js'

/** Cmd+<letter> for the four roles a key equivalent is confirmed to need on a real Mac. Not derived from the
 * manifest's own `accelerators` (those are empty for these five actions on purpose -- the page already handles
 * Ctrl+Z/Ctrl+C itself on Linux, see `manifest.py`'s `_shared_edit_block` -- so this table exists only for the
 * macOS shell, independent of what Linux binds). */
const ROLE_SHORTCUT: Readonly<Record<string, string>> = {
  'undo:': 'z',
  'cut:': 'x',
  'copy:': 'c',
  'paste:': 'v',
  // 'redo:' deliberately absent -- see this module's top comment.
}

/**
 * `<Primary>n` -> `"n"`, Neutralino's own documented example (a bare letter means Cmd+letter on macOS,
 * window/docs/api/window). Anything outside that one confirmed shape returns `null` rather than a guess: a wrong
 * shortcut string is worse than a missing one, since a missing one just falls back to a mouse click. In
 * particular, a second modifier (`<Shift>`, `<Primary><Shift>`) and a bare function key (`F1`, no modifier at all)
 * are both left out because neither is covered by that one example.
 */
export function gtkAccelToMacShortcut(accelerator: string): string | null {
  const match = /^<Primary>([A-Za-z])$/.exec(accelerator)
  return match ? (match[1] as string).toLowerCase() : null
}

function buildItem(action: ManifestAction): WindowMenuItem {
  const item: WindowMenuItem = { id: action.id, text: action.label }
  if (action.checkable) item.isChecked = false // the page corrects this once it reports real state (action_state)
  if (action.role) {
    item.action = action.role
    const roleShortcut = ROLE_SHORTCUT[action.role]
    if (roleShortcut) item.shortcut = roleShortcut
  } else {
    const translated = action.accelerators.map(gtkAccelToMacShortcut).find((s): s is string => s !== null)
    if (translated) item.shortcut = translated
  }
  return item
}

/**
 * The full native menu for one app: a leading application menu (About, Quit) ahead of the manifest's own menus,
 * each rebuilt with `file.quit` and `help.about` removed (they moved to the front) and the rest turned into
 * `WindowMenuItem`s. `appTitle` is `identity.ts`'s `AppIdentity.title`, e.g. `"Claudia Creates"`.
 */
export function buildMacMenu(listing: ManifestListing, appTitle: string): ShellMenuItem[] {
  const about = findAction(listing, 'help.about')
  const quit = findAction(listing, 'file.quit')
  const relocated = new Set<string>([about?.id, quit?.id].filter((id): id is string => id !== undefined))
  const appMenu: WindowMenuItem = {
    text: appTitle,
    menuItems: [about, quit].filter((a): a is ManifestAction => a !== undefined).map(buildItem),
  }
  // A menu that had nothing but About or Quit (Help on the front page, sheet 11) is left out, not shown empty.
  return [appMenu, ...buildMenus(listing, buildItem, relocated)]
}

/** On a Mac the clipboard items stay in the front page's short menu: their Cocoa roles are what makes ⌘X, ⌘C and ⌘V
 * work in the page's text fields at all. */
export function keptOnMacFrontPage(action: ManifestAction): boolean {
  return action.role === 'cut:' || action.role === 'copy:' || action.role === 'paste:'
}
