// Turns one app's generated manifest (tools/generate_menu.py's JSON, itself clients/linux's
// claudia_menus.manifest.<app>().describe()) into Neutralino's own WindowMenuItem tree
// (Neutralino.window.setMainMenu). No Neutralino import here -- same discipline as manifest.py's own "nothing here
// imports GTK" -- so this is testable with plain fixture data (tests/menu.test.ts).
//
// What a menu item looks like on one operating system (its shortcut, a Cocoa role, an application menu on macOS) is
// that platform's: src/platform/macos-menu.ts and src/platform/windows-menu.ts. Everything else is here.

export interface ManifestAction {
  id: string
  label: string
  kind: 'page' | 'shell' | 'editing'
  checkable: boolean
  accelerators: string[]
  role: string | null
  /** Does it belong in the short menu of the front page (sheet 11, `manifest.on_start`)? Absent in an older listing. */
  start?: boolean
}

export interface ManifestSubmenu {
  label: string
  items: ManifestAction[]
}

export type ManifestEntry = ManifestAction | ManifestSubmenu

export interface ManifestMenu {
  /** The menu's word in lower case (`insert`), by which the page names a menu with nothing left (D1645). */
  word: string
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

/** An item as the shell keeps it, between the page's reports: a `WindowMenuItem` that may be left out for now
 * (`isHidden`, D1645), and for a menu of the bar its word in the definition (`word`: "insert"), by which the page
 * names a menu with nothing left. `drawMenu` (menu-actions.ts) turns it into what Neutralino is given. */
export interface ShellMenuItem extends WindowMenuItem {
  isHidden?: boolean
  word?: string
  menuItems?: ShellMenuItem[]
}

export function isSubmenu(entry: ManifestEntry): entry is ManifestSubmenu {
  return 'items' in entry
}

export const SEPARATOR: WindowMenuItem = { text: '-' }

/** A menu item from one manifest action, the way a platform draws it. */
export type ItemBuilder = (action: ManifestAction) => WindowMenuItem

/** The manifest's own menus, in their order, as `WindowMenuItem`s: one separator between two sections, the actions
 * in `omit` left out (moved elsewhere by the platform), and a section or a menu that has nothing left left out, not
 * shown empty. */
export function buildMenus(listing: ManifestListing, buildItem: ItemBuilder, omit: ReadonlySet<string> = new Set()): ShellMenuItem[] {
  const entry = (item: ManifestEntry): WindowMenuItem =>
    isSubmenu(item) ? { text: item.label, menuItems: item.items.map(buildItem) } : buildItem(item)
  return listing.menus
    .map((menu) => {
      const items: WindowMenuItem[] = []
      menu.sections
        .map((section) => section.filter((item) => isSubmenu(item) || !omit.has(item.id)))
        .filter((section) => section.length > 0)
        .forEach((section, index) => {
          if (index > 0) items.push(SEPARATOR)
          items.push(...section.map(entry))
        })
      return { text: menu.label, word: menu.word, menuItems: items }
    })
    .filter((menu) => menu.menuItems.length > 0)
}

/** The action with this id anywhere in the listing's menus (flyouts not included), or `undefined`. */
export function findAction(listing: ManifestListing, id: string): ManifestAction | undefined {
  for (const menu of listing.menus) {
    for (const section of menu.sections) {
      for (const entry of section) {
        if (!isSubmenu(entry) && entry.id === id) return entry
      }
    }
  }
  return undefined
}

/**
 * The short menu of the front page (sheet 11): only what works without a document — the actions the manifest marks
 * `start` — with empty sections, flyouts and menus left out rather than greyed — and what `alsoKeep` keeps besides
 * (the platform's own, `keepAtStart` in src/platform/page.ts).
 */
export function startListing(listing: ManifestListing, alsoKeep: (action: ManifestAction) => boolean): ManifestListing {
  const kept = (action: ManifestAction) => action.start === true || alsoKeep(action)
  const menus = listing.menus
    .map((menu) => ({
      ...menu,
      sections: menu.sections
        .map((section) =>
          section
            .map((entry): ManifestEntry | null => {
              if (!isSubmenu(entry)) return kept(entry) ? entry : null
              const items = entry.items.filter(kept)
              return items.length ? { ...entry, items } : null
            })
            .filter((entry): entry is ManifestEntry => entry !== null),
        )
        .filter((section) => section.length > 0),
    }))
    .filter((menu) => menu.sections.length > 0)
  return { ...listing, menus }
}
