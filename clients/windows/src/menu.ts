// Turns one app's generated manifest (tools/generate_menu.py's JSON, itself clients/linux's
// claudia_shell_gtk.manifest.<app>().describe()) into Neutralino's own WindowMenuItem tree
// (Neutralino.window.setMainMenu). No Neutralino import here -- same discipline as manifest.py's own "nothing here
// imports GTK" and clients/macos/src/menu.ts -- so this is testable with plain fixture data (tests/menu.test.ts).
//
// Simpler than its macOS sibling, for two reasons the spike and the macOS build each found (D44, D158,
// notes/e0-3-neutralino-windows-macos.md §2):
//  - Windows keeps File, Edit, Format, View, Tools, Config, Help as one ordinary window menu. There is no
//    application-menu convention to move About and Quit into, so unlike macOS's buildMainMenu() this file does not
//    rebuild or relocate anything -- the manifest's own menu order is the window menu, unchanged.
//  - "On Windows no Cocoa actions exist; the Edit items worked through `document.execCommand` in the page" -- the
//    manifest's `role` field (D158) exists only to give macOS's `NSMenuItem` a Cocoa selector so Cmd+C is claimed
//    by the menu at all. Windows has no such requirement: every item, Edit's standard ones included, is forwarded
//    to the page as a plain `action` message (menu-actions.ts's routeMenuClick does not special-case them either),
//    and the page's own shortcut handling (`web/app/lib/shortcuts.ts`, D122) is what actually runs the command --
//    the same path Linux already uses for Undo/Redo (`_shared_edit_block`'s own comment: "page-handled, not
//    shell-handled"). So this file reads `role` from nothing; the field stays in the shared manifest for macOS
//    alone and is simply absent from every WindowMenuItem this module builds.
//  - `shortcut` is display-only here (confirmed on a real Windows 11 machine, the spike's own finding): the OS
//    does not claim the key combination the way macOS's Cocoa layer does, so a wrong or missing guess only costs a
//    blank column next to the label, never a silently broken shortcut. `gtkAccelToWindowsShortcut` is still kept
//    to the shapes actually seen in the shared manifest (`grep accelerators= manifest.py`) rather than written as
//    a general GTK-accelerator parser, so a shape nobody has used yet does not quietly mistranslate -- but, unlike
//    macOS's `gtkAccelToMacShortcut`, it is allowed to cover more than one shape precisely because getting one
//    wrong here is cosmetic, not functional.

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
 * (neutralino.js.org/docs/api/window), the same naming choice clients/macos/src/menu.ts makes, so a reader
 * comparing either file to the Neutralino docs sees the same shape. */
export interface WindowMenuItem {
  id?: string
  text: string
  isDisabled?: boolean
  isChecked?: boolean
  menuItems?: WindowMenuItem[]
  shortcut?: string
}

function isSubmenu(entry: ManifestEntry): entry is ManifestSubmenu {
  return 'items' in entry
}

const LETTER = /^<Primary>([A-Za-z])$/
const SHIFT_LETTER = /^<Primary><Shift>([A-Za-z])$/
const SHIFT_FUNCTION = /^<Shift>(F[1-9][0-2]?)$/
const BARE_FUNCTION = /^(F[1-9][0-2]?)$/

/**
 * The shared manifest's GTK accelerator syntax, turned into the "Ctrl+Shift+N" style Windows menus display --
 * limited to the exact shapes `grep accelerators= clients/linux/src/claudia_shell_gtk/manifest.py` turns up today
 * (`<Primary>n`, `<Primary>o`, `<Primary>q`, `<Shift>F10`, `F1`), each confirmed by its own regular expression
 * rather than a general parser. `null` for anything else -- a blank shortcut column is the safe default for a
 * shape this function has not been told about yet, the same "do not guess" discipline
 * `gtkAccelToMacShortcut` uses, just with a wider confirmed set because a wrong guess here only costs that one
 * cosmetic column (this module's own top comment).
 */
export function gtkAccelToWindowsShortcut(accelerator: string): string | null {
  const letter = LETTER.exec(accelerator)
  if (letter) return `Ctrl+${(letter[1] as string).toUpperCase()}`
  const shiftLetter = SHIFT_LETTER.exec(accelerator)
  if (shiftLetter) return `Ctrl+Shift+${(shiftLetter[1] as string).toUpperCase()}`
  const shiftFunction = SHIFT_FUNCTION.exec(accelerator)
  if (shiftFunction) return `Shift+${shiftFunction[1]}`
  const bareFunction = BARE_FUNCTION.exec(accelerator)
  if (bareFunction) return bareFunction[1] as string
  return null
}

function buildItem(action: ManifestAction): WindowMenuItem {
  const item: WindowMenuItem = { id: action.id, text: action.label }
  if (action.checkable) item.isChecked = false // the page corrects this once it reports real state (action_state)
  const translated = action.accelerators.map(gtkAccelToWindowsShortcut).find((s): s is string => s !== null)
  if (translated) item.shortcut = translated
  return item
}

function buildEntry(entry: ManifestEntry): WindowMenuItem {
  if (isSubmenu(entry)) {
    return { text: entry.label, menuItems: entry.items.map(buildItem) }
  }
  return buildItem(entry)
}

const SEPARATOR: WindowMenuItem = { text: '-' }

function buildMenu(menu: ManifestMenu): WindowMenuItem {
  const items: WindowMenuItem[] = []
  menu.sections.forEach((section, index) => {
    if (index > 0 && section.length > 0) items.push(SEPARATOR)
    items.push(...section.map(buildEntry))
  })
  return { text: menu.label, menuItems: items }
}

/**
 * The full native window menu for one app: the manifest's own menus, unchanged in order and content (unlike
 * macOS's buildMainMenu(), nothing is relocated into a leading application menu -- see this module's top comment).
 * `appTitle` is accepted for interface parity with the macOS build (both are called the same way from
 * shell-page-entry.ts) even though this function does not use it.
 */
export function buildMainMenu(listing: ManifestListing, _appTitle: string): WindowMenuItem[] {
  return listing.menus.map(buildMenu)
}
