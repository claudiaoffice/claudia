// Turns one app's generated manifest (tools/generate_menu.py's JSON, itself clients/linux's
// claudia_shell_gtk.manifest.<app>().describe()) into Neutralino's own WindowMenuItem tree
// (Neutralino.window.setMainMenu). No Neutralino import here -- same discipline as manifest.py's own "nothing here
// imports GTK" -- so this is testable with plain fixture data (tests/menu.test.ts).
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

export interface ManifestAction {
  id: string
  label: string
  kind: 'page' | 'shell' | 'editing'
  checkable: boolean
  accelerators: string[]
  role: string | null
}

export interface ManifestSubmenu {
  label: string
  items: ManifestAction[]
}

export type ManifestEntry = ManifestAction | ManifestSubmenu

export interface ManifestMenu {
  label: string
  sections: ManifestEntry[][]
}

export interface ManifestListing {
  app: string
  menus: ManifestMenu[]
  header_toggles: ManifestAction[]
}

/** What `Neutralino.window.setMainMenu()` expects. Named to match the framework's own `WindowMenuItem`
 * (neutralino.js.org/docs/api/window), so a reader comparing this file to the Neutralino docs sees the same shape. */
export interface WindowMenuItem {
  id?: string
  text: string
  isDisabled?: boolean
  isChecked?: boolean
  menuItems?: WindowMenuItem[]
  shortcut?: string
  action?: string
}

function isSubmenu(entry: ManifestEntry): entry is ManifestSubmenu {
  return 'items' in entry
}

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

function buildEntry(entry: ManifestEntry): WindowMenuItem {
  if (isSubmenu(entry)) {
    return { text: entry.label, menuItems: entry.items.map(buildItem) }
  }
  return buildItem(entry)
}

const SEPARATOR: WindowMenuItem = { text: '-' }

function buildMenu(menu: ManifestMenu, omit: ReadonlySet<string>): WindowMenuItem {
  const sections = menu.sections
    .map((section) => section.filter((entry) => isSubmenu(entry) || !omit.has(entry.id)))
    .filter((section) => section.length > 0)
  const items: WindowMenuItem[] = []
  sections.forEach((section, index) => {
    if (index > 0) items.push(SEPARATOR)
    items.push(...section.map(buildEntry))
  })
  return { text: menu.label, menuItems: items }
}

/**
 * The full native menu for one app: a leading application menu (About, Quit) ahead of the manifest's own menus,
 * each rebuilt with `file.quit` and `help.about` removed (they moved to the front) and the rest turned into
 * `WindowMenuItem`s. `appTitle` is `identity.ts`'s `AppIdentity.title`, e.g. `"Claudia Creates"`.
 */
export function buildMainMenu(listing: ManifestListing, appTitle: string): WindowMenuItem[] {
  const about = findAction(listing, 'help.about')
  const quit = findAction(listing, 'file.quit')
  const relocated = new Set<string>([about?.id, quit?.id].filter((id): id is string => id !== undefined))

  const appMenu: WindowMenuItem = {
    text: appTitle,
    menuItems: [about, quit].filter((a): a is ManifestAction => a !== undefined).map(buildItem),
  }

  return [appMenu, ...listing.menus.map((menu) => buildMenu(menu, relocated))]
}

function findAction(listing: ManifestListing, id: string): ManifestAction | undefined {
  for (const menu of listing.menus) {
    for (const section of menu.sections) {
      for (const entry of section) {
        if (!isSubmenu(entry) && entry.id === id) return entry
      }
    }
  }
  return undefined
}
